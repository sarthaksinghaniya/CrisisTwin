import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.future import select

from app.worker.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.api.routes.escalation import run_escalation_check
from app.models.complaint import Complaint, ComplaintStatus

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.escalation.run_escalation_job")
def run_escalation_job():
    """Celery Beat task to run escalation check."""
    logger.info("Celery Beat: Starting scheduled escalation job...")
    
    async def _escalate():
        async with AsyncSessionLocal() as session:
            try:
                count = await run_escalation_check(session)
                logger.info(f"Celery Beat: Scheduled escalation job completed. {count} complaints escalated.")
            except Exception as e:
                logger.error(f"Error during scheduled escalation job: {e}", exc_info=True)
                await session.rollback()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(_escalate())


@celery_app.task(name="app.tasks.escalation.run_retry_pipeline_job")
def run_retry_pipeline_job():
    """Celery Beat task to retry stuck pipelines."""
    logger.info("Celery Beat: Starting scheduled retry pipeline job...")
    
    from app.tasks.pipeline import process_pipeline_task
    
    async def _retry():
        async with AsyncSessionLocal() as session:
            try:
                two_mins_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=2)
                query = select(Complaint).filter(
                    Complaint.status.in_([ComplaintStatus.SUBMITTED, ComplaintStatus.FAILED]),
                    Complaint.created_at < two_mins_ago,
                    Complaint.retry_count < 3
                )
                result = await session.execute(query)
                stuck_complaints = result.scalars().all()
                
                if stuck_complaints:
                    logger.info(f"Found {len(stuck_complaints)} stuck complaints to retry.")
                    for c in stuck_complaints:
                        c.retry_count += 1
                        c.last_retry_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()

                    for c in stuck_complaints:
                        logger.info(f"[Ticket {c.ticket_id}] Offloading retry to Celery Worker (Attempt {c.retry_count}/3)")
                        # Queue it in celery
                        process_pipeline_task.delay(c.ticket_id)
                else:
                    logger.info("No stuck complaints found requiring retry.")
            except Exception as e:
                logger.error(f"Error during scheduled retry pipeline job: {e}", exc_info=True)
                await session.rollback()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(_retry())
