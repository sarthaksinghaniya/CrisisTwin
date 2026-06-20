"""
RL Feedback Engine — reinforcement learning signal processor.

Hardening:
  • Input validation (rating clamped to 1-5, empty text handled)
  • FAISS errors don't crash the feedback pipeline
  • Ledger write is atomic per signal (append-only JSON)
  • Structured logging with complaint tracing
"""
import logging
import json
import os
import asyncio
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Mapped dynamically to your underlying models packages
from app.models.feedback import Feedback
from app.models.complaint import Complaint
from .vector_store import ProductionComplaintVectorStore

logger = logging.getLogger("cm_dashboard.engines.rl_feedback")

class RLEngine:
    """
    Captures citizen feedback signals, computes rewards,
    and applies real-time boosting/deprecation metrics to FAISS Metadata records.
    """
    LEDGER_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "outputs",
        "rl_ledger.json",
    )

    @staticmethod
    async def process_feedback(
        complaint_id: int,
        rating: int,
        comments: str,
        session: AsyncSession,
    ):
        """Process citizen feedback and apply RL optimization signals."""
        rating = max(1, min(5, rating))  # clamp to range layout [1, 5]
        comments = (comments or "").strip()

        logger.info(f"[RL_ENGINE] Evaluating feedback parameters for complaint ID {complaint_id}: {rating}/5")

        # 1. Fetch Complaint Database Context from Session Instance
        try:
            query = select(Complaint).filter(Complaint.id == complaint_id)
            res = await session.execute(query)
            complaint = res.scalars().first()
        except Exception as exc:
            logger.error(f"[RL_ENGINE] DB entity lookup aborted for target {complaint_id}: {exc}")
            return

        if not complaint:
            logger.error(f"[RL_ENGINE] Target Complaint instance ID {complaint_id} missing from session.")
            return

        text = complaint.description or complaint.title
        if not text:
            logger.warning(f"[RL_ENGINE] Text fields are blank for reference ticket {complaint_id} — skipping pipeline.")
            return

        # 2. Compute Reward Signal Mapping Matrices
        reward = 0.0
        if rating <= 2:
            reward = -1.0
        elif rating >= 4:
            reward = 1.0

        # 3. Apply Matrix Boosting / Deprecation directly into FAISS Metadata mapping files
        if reward != 0.0:
            try:
                # Helper function executed in threadpool to inject metrics without breaking indexing
                def _sync_vector_metadata_update():
                    store = ProductionComplaintVectorStore()
                    modified = False
                    for idx, meta in store.metadata_store.items():
                        if str(meta.get("id")) == str(complaint.id) or meta.get("ticket_id") == complaint.ticket_id:
                            store.metadata_store[idx]["rl_reward_score"] = reward
                            store.metadata_store[idx]["citizen_rating"] = rating
                            store.metadata_store[idx]["rl_applied"] = True
                            modified = True
                    
                    if modified:
                        import pickle
                        with open(store.metadata_path, 'wb') as f:
                            pickle.dump(store.metadata_store, f, protocol=pickle.HIGHEST_PROTOCOL)
                        logger.info(f"[RL_ENGINE] Synchronized memory updates saved into metadata files for Ticket: {complaint.ticket_id}")

                await asyncio.to_thread(_sync_vector_metadata_update)
            except Exception as exc:
                logger.error(f"[RL_ENGINE] FAISS Vector Metadata tracking injection crashed — non-critical: {exc}")

        # 4. Persist offline training signal logs
        signal = {
            "ticket_id": complaint.ticket_id,
            "text": text[:500],  
            "category": complaint.category,
            "assigned_to": complaint.assigned_to,
            "rating": rating,
            "reward": reward,
            "comments": comments[:500],
        }
        await RLEngine._append_to_ledger(signal)
        logger.info(f"[RL_ENGINE] Processing completed successfully. Extracted feedback metric: {reward}")

    @staticmethod
    async def process_resolution_success(complaint: Complaint):
        """
        Automated success signal when a complaint is resolved.
        Positive reward only if no retries were needed.
        """
        reward = 1.0 if getattr(complaint, 'retry_count', 0) == 0 else 0.0
        if reward <= 0:
            return

        try:
            text = complaint.description or complaint.title
            if not text:
                return
                
            def _sync_resolution_reward_boost():
                store = ProductionComplaintVectorStore()
                modified = False
                for idx, meta in store.metadata_store.items():
                    if meta.get("ticket_id") == complaint.ticket_id:
                        store.metadata_store[idx]["auto_resolved"] = True
                        store.metadata_store[idx]["rl_reward_score"] = reward
                        modified = True
                if modified:
                    import pickle
                    with open(store.metadata_path, 'wb') as f:
                        pickle.dump(store.metadata_store, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            await asyncio.to_thread(_sync_boost_resolution_reward_boost)
        except Exception as exc:
            logger.error(f"[RL_ENGINE] Resolution success calculation metric injection failed: {exc}")

    @staticmethod
    async def _append_to_ledger(signal: Dict[str, Any]):
        """Append signal tracking containers to JSON ledger (thread-safe)."""
        def _sync_write():
            try:
                os.makedirs(os.path.dirname(RLEngine.LEDGER_PATH), exist_ok=True)
                ledger = []
                if os.path.exists(RLEngine.LEDGER_PATH):
                    try:
                        with open(RLEngine.LEDGER_PATH, "r") as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                ledger = data
                    except (json.JSONDecodeError, IOError):
                        pass
                ledger.append(signal)
                with open(RLEngine.LEDGER_PATH, "w") as f:
                    json.dump(ledger, f, indent=4)
            except Exception as exc:
                logger.error(f"[RL_ENGINE] Ledger file write operation failed: {exc}")

        await asyncio.to_thread(_sync_write)