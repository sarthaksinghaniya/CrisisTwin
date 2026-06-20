import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.api.routes.escalation import run_escalation_check
from app.models.complaint import Complaint, ComplaintStatus

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def scheduled_escalation_job():
    logger.info("Starting scheduled escalation job...")
    async with AsyncSessionLocal() as session:
        try:
            count = await run_escalation_check(session)
            logger.info(f"Scheduled escalation job completed. {count} complaints escalated.")
        except Exception as e:
            logger.error(f"Error during scheduled escalation job: {e}", exc_info=True)
            await session.rollback()

async def scheduled_retry_pipeline_job():
    logger.info("Starting scheduled retry pipeline job...")
    
    # Import inside function to avoid circular import with main.py
    from app.main import execute_pipeline_task
    
    async with AsyncSessionLocal() as session:
        try:
            # Find complaints that have been SUBMITTED for more than 2 minutes
            two_mins_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=2)
            query = select(Complaint).filter(
                Complaint.status == ComplaintStatus.SUBMITTED,
                Complaint.created_at < two_mins_ago
            )
            result = await session.execute(query)
            stuck_complaints = result.scalars().all()
            
            if stuck_complaints:
                logger.info(f"Found {len(stuck_complaints)} stuck complaints to retry.")
                for c in stuck_complaints:
                    logger.info(f"Retrying pipeline for ticket: {c.ticket_id}")
                    try:
                        await execute_pipeline_task(c.ticket_id)
                    except Exception as e:
                        logger.error(f"Failed to retry pipeline for {c.ticket_id}: {e}", exc_info=True)
            else:
                logger.info("No stuck complaints found.")
        except Exception as e:
            logger.error(f"Error during scheduled retry pipeline job: {e}", exc_info=True)
            await session.rollback()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            scheduled_escalation_job,
            trigger=IntervalTrigger(minutes=5),
            id="escalation_job",
            replace_existing=True,
        )
        scheduler.add_job(
            scheduled_retry_pipeline_job,
            trigger=IntervalTrigger(minutes=2),
            id="retry_pipeline_job",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler started successfully.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler shut down successfully.")
