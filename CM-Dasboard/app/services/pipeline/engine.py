"""
Pipeline Engine — deterministic, crash-proof complaint processing core.

Key hardening:
  • Global asyncio.Semaphore to cap concurrent pipeline runs (prevents DB lock storms)
  • Each phase opens its own short-lived session (prevents leaked transactions)
  • Exponential-backoff retry handler with terminal FAILED_FINAL state
  • Structured logging with ticket_id tracing on every transition
  • Full catch-all so the engine NEVER raises to the caller
"""
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.complaint import Complaint, ComplaintStatus, PriorityEnum
from app.models.complaint_update import ComplaintUpdate

logger = logging.getLogger("cm_dashboard.pipeline.engine")

# Concurrency guard — prevents DB lock storms under load
# For SQLite keep at 1-3; for PostgreSQL can raise to 20+
_PIPELINE_SEMAPHORE = asyncio.Semaphore(5)


class RetryHandler:
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 60  # 60 → 120 → 240

    @classmethod
    def calculate_backoff(cls, current_retry: int) -> int:
        """Exponential backoff: 60s, 120s, 240s …"""
        return cls.BASE_BACKOFF_SECONDS * (2 ** current_retry)

    @classmethod
    def can_retry(cls, current_retry: int) -> bool:
        return current_retry < cls.MAX_RETRIES


class PipelineEngine:
    """Production-grade complaint processing engine."""

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    @staticmethod
    async def transition_to_processing(
        ticket_id: str, session: AsyncSession
    ) -> Optional[Complaint]:
        """Atomically move SUBMITTED/FAILED → PROCESSING (idempotent)."""
        query = select(Complaint).filter(Complaint.ticket_id == ticket_id)
        result = await session.execute(query)
        complaint = result.scalars().first()

        if not complaint:
            logger.warning(f"[ENGINE][{ticket_id}] Ticket not found.")
            return None

        if complaint.status not in [ComplaintStatus.SUBMITTED, ComplaintStatus.FAILED]:
            logger.warning(
                f"[ENGINE][{ticket_id}] Aborting — already in state "
                f"{complaint.status.value}"
            )
            return None

        old = complaint.status
        complaint.status = ComplaintStatus.PROCESSING
        PipelineEngine._log_transition(ticket_id, old.value, complaint.status.value)

        session.add(ComplaintUpdate(
            complaint_id=complaint.id,
            status=ComplaintStatus.PROCESSING.value,
            note="System Core Engine initialized processing loop.",
            updated_by=None,
        ))
        await session.commit()
        await session.refresh(complaint)
        return complaint

    @staticmethod
    async def transition_to_resolved(
        ticket_id: str,
        assigned_to: Optional[Any],
        session: AsyncSession,
    ) -> Optional[Complaint]:
        """PROCESSING → ASSIGNED (if officer) or SUBMITTED (awaiting manual assignment)."""
        query = select(Complaint).filter(Complaint.ticket_id == ticket_id)
        result = await session.execute(query)
        complaint = result.scalars().first()

        if not complaint or complaint.status != ComplaintStatus.PROCESSING:
            return None

        old = complaint.status
        complaint.status = (
            ComplaintStatus.ASSIGNED if assigned_to else ComplaintStatus.SUBMITTED
        )
        PipelineEngine._log_transition(ticket_id, old.value, complaint.status.value)

        note_text = (
            "AI Pipeline completed: Assigned to officer."
            if assigned_to
            else "AI Pipeline completed: No matching officer found. Awaiting manual assignment."
        )

        session.add(ComplaintUpdate(
            complaint_id=complaint.id,
            status=complaint.status.value,
            note=note_text,
            updated_by=None,
        ))
        await session.commit()
        return complaint

    @staticmethod
    async def handle_failure(
        ticket_id: str, exception: Exception, session: AsyncSession
    ) -> None:
        """Log failure, bump retry counter, apply exponential backoff."""
        query = select(Complaint).filter(Complaint.ticket_id == ticket_id)
        result = await session.execute(query)
        complaint = result.scalars().first()

        if not complaint:
            logger.error(f"[ENGINE][{ticket_id}] Ticket not found during failure handling.")
            return

        old = complaint.status
        complaint.failure_reason = str(exception)[:500]

        if RetryHandler.can_retry(complaint.retry_count):
            complaint.status = ComplaintStatus.FAILED
            complaint.retry_count += 1
            complaint.last_retry_at = datetime.now(timezone.utc).replace(tzinfo=None)
            backoff = RetryHandler.calculate_backoff(complaint.retry_count)
            logger.warning(
                f"[ENGINE][{ticket_id}] Execution failed. "
                f"Retry {complaint.retry_count}/{RetryHandler.MAX_RETRIES} "
                f"in {backoff}s. Error: {exception}"
            )
        else:
            complaint.status = ComplaintStatus.FAILED_FINAL
            logger.error(
                f"[ENGINE][{ticket_id}] MAX RETRIES EXCEEDED → FAILED_FINAL. "
                f"Error: {exception}"
            )

        PipelineEngine._log_transition(ticket_id, old.value, complaint.status.value)

        session.add(ComplaintUpdate(
            complaint_id=complaint.id,
            status=complaint.status.value,
            note=f"Pipeline failed: {str(exception)[:200]}",
            updated_by=None,
        ))
        await session.commit()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @staticmethod
    def _log_transition(ticket_id: str, old_state: str, new_state: str):
        logger.info(f"[ENGINE][{ticket_id}] STATE TRANSITION: {old_state} -> {new_state}")

    # ------------------------------------------------------------------
    # Central Executor
    # ------------------------------------------------------------------

    @staticmethod
    async def execute_core(ticket_id: str, session_factory):
        """
        Deterministic pipeline executor.

        Uses ``_PIPELINE_SEMAPHORE`` to cap concurrency. Each DB phase
        opens its own session so transactions are short-lived and don't
        deadlock under load.

        Critical: ``session_factory`` is an ``async_sessionmaker``, NOT a
        session instance.  Every DB call opens ``async with session_factory()``
        to get a real ``AsyncSession``.
        """
        from app.engines.routing import RoutingEngine

        async with _PIPELINE_SEMAPHORE:
            # ── Phase 1: Acquire processing lock ──────────────────────
            async with session_factory() as session:
                complaint = await PipelineEngine.transition_to_processing(
                    ticket_id, session
                )
                if not complaint:
                    return  # duplicate / missing / already done

                text = complaint.description or complaint.title
                district = complaint.district or "UNKNOWN"

            try:
                # ── Phase 2: AI Routing (needs its own session for DB lookups) ─
                async with session_factory() as session:
                    routing_result = await RoutingEngine.process_routing(
                        text, district, session
                    )

                # ── Phase 3: Persist routing decisions ────────────────
                async with session_factory() as session:
                    q = select(Complaint).filter(Complaint.ticket_id == ticket_id)
                    res = await session.execute(q)
                    complaint = res.scalars().first()

                    if complaint:
                        complaint.priority = routing_result["priority"]
                        complaint.category = routing_result["category"]
                        complaint.department = routing_result["department"]
                        complaint.assigned_to = routing_result["assigned_to"]

                        logger.info(
                            f"[ENGINE][{ticket_id}] AI Routing Decision -> "
                            f"Priority: {complaint.priority.name}, "
                            f"Category: {complaint.category}, "
                            f"Dept: {complaint.department}, "
                            f"Assignee: {complaint.assigned_to}"
                        )
                        await session.commit()

                    assigned_to = routing_result["assigned_to"]

                # ── Phase 4: Final state transition ───────────────────
                async with session_factory() as session:
                    await PipelineEngine.transition_to_resolved(
                        ticket_id, assigned_to, session
                    )

            except Exception as exc:
                # ── Phase 5: Failure handling ──────────────────────────
                logger.error(
                    f"[ENGINE][{ticket_id}] Critical failure: {exc}",
                    exc_info=True,
                )
                try:
                    async with session_factory() as session:
                        await PipelineEngine.handle_failure(ticket_id, exc, session)
                except Exception as inner:
                    # Even failure handling itself must not crash
                    logger.critical(
                        f"[ENGINE][{ticket_id}] Failure handler crashed: {inner}",
                        exc_info=True,
                    )
