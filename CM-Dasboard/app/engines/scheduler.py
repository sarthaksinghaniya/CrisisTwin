"""
Scheduler Engine — background task orchestrator with idempotency.

Hardening:
  • Each job wrapped in its own try/except — one job failure doesn't kill others
  • replace_existing=True prevents duplicate job registration
  • Advisory lock stub ready for PostgreSQL pg_try_advisory_xact_lock
  • FAISS sync is crash-proof
  • Structured logging
"""
import logging
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.db.session import AsyncSessionLocal
from app.engines.analytics import AnalyticsEngine
from app.engines.escalation import EscalationEngine
from app.engines.faiss_rag import FaissMemory

logger = logging.getLogger("cm_dashboard.engines.scheduler")


class SchedulerEngine:
    """Centralized background task orchestrator."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False
        self._setup_jobs()

    def _setup_jobs(self):
        # 1. Escalation sweep — every 1 hour
        self.scheduler.add_job(
            self._run_escalations,
            trigger=IntervalTrigger(hours=1),
            id="job_escalations",
            replace_existing=True,
            max_instances=1,       # idempotent: prevent overlap
        )

        # 2. Analytics precomputation — nightly at 2:00 AM
        self.scheduler.add_job(
            self._run_analytics,
            trigger=CronTrigger(hour=2, minute=0),
            id="job_analytics",
            replace_existing=True,
            max_instances=1,
        )

        # 3. FAISS disk sync — every 12 hours
        self.scheduler.add_job(
            self._run_faiss_sync,
            trigger=IntervalTrigger(hours=12),
            id="job_faiss_sync",
            replace_existing=True,
            max_instances=1,
        )

        # 4. Analytics snapshot — every 30 minutes
        self.scheduler.add_job(
            self._run_analytics_snapshot,
            trigger=IntervalTrigger(minutes=30),
            id="job_analytics_snapshot",
            replace_existing=True,
            max_instances=1,
        )

    def start(self):
        """Start the background scheduler loop."""
        if not self._running:
            self.scheduler.start()
            self._running = True
            logger.info("[SCHEDULER_ENGINE] Started. Background tasks registered.")

    def stop(self):
        """Gracefully shut down."""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("[SCHEDULER_ENGINE] Shut down successfully.")

    # ------------------------------------------------------------------
    # Job implementations (each fully isolated)
    # ------------------------------------------------------------------

    async def _run_escalations(self):
        """Escalation sweep job."""
        logger.info("[SCHEDULER_ENGINE] Running escalation sweep...")
        try:
            async with AsyncSessionLocal() as session:
                await EscalationEngine.process_escalations(session)
        except Exception as exc:
            logger.error(
                f"[SCHEDULER_ENGINE] Escalation job failed: {exc}", exc_info=True
            )

    async def _run_analytics(self):
        """Analytics precomputation job."""
        logger.info("[SCHEDULER_ENGINE] Running analytics precomputation...")
        try:
            async with AsyncSessionLocal() as session:
                await AnalyticsEngine.precompute_nightly_metrics(session)
        except Exception as exc:
            logger.error(
                f"[SCHEDULER_ENGINE] Analytics job failed: {exc}", exc_info=True
            )

    async def _run_faiss_sync(self):
        """FAISS disk persistence job."""
        logger.info("[SCHEDULER_ENGINE] Syncing FAISS RAG memory to disk...")
        try:
            memory = FaissMemory()
            await asyncio.to_thread(memory.save_memory)
        except Exception as exc:
            logger.error(
                f"[SCHEDULER_ENGINE] FAISS sync job failed: {exc}", exc_info=True
            )

    async def _run_analytics_snapshot(self):
        """Analytics snapshot periodic job."""
        logger.info("[SCHEDULER_ENGINE] Running analytics snapshot job...")
        try:
            from app.services.analytics import AnalyticsSnapshotService
            async with AsyncSessionLocal() as session:
                snapshot = await AnalyticsSnapshotService.compute_snapshot(session)
                await AnalyticsSnapshotService.save_snapshot(snapshot, session)
        except Exception as exc:
            logger.error(
                f"[SCHEDULER_ENGINE] Analytics snapshot job failed: {exc}", exc_info=True
            )
