import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.api.routes.escalation import run_escalation_check
from app.models.complaint import Complaint, ComplaintStatus

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.core.config import settings

logger = logging.getLogger(__name__)

sync_db_url = settings.SQLALCHEMY_DATABASE_URI
if "sqlite+aiosqlite" in sync_db_url:
    sync_db_url = sync_db_url.replace("sqlite+aiosqlite", "sqlite")
else:
    sync_db_url = sync_db_url.replace("+asyncpg", "")

jobstores = {
    'default': SQLAlchemyJobStore(url=sync_db_url)
}

scheduler = AsyncIOScheduler(jobstores=jobstores)

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
            # Find complaints that have been SUBMITTED or FAILED for more than 2 minutes and have retry_count < 3
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
                # Update retry trackers first
                for c in stuck_complaints:
                    c.retry_count += 1
                    c.last_retry_at = datetime.now(timezone.utc).replace(tzinfo=None)
                await session.commit()

                # Execute pipeline sequentially for the stuck complaints
                for c in stuck_complaints:
                    logger.info(f"[Ticket {c.ticket_id}] Retrying pipeline (Attempt {c.retry_count}/3)")
                    try:
                        await execute_pipeline_task(c.ticket_id)
                    except Exception as e:
                        logger.error(f"[Ticket {c.ticket_id}] Failed to retry pipeline: {e}", exc_info=True)
            else:
                logger.info("No stuck complaints found requiring retry.")
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
            max_instances=1
        )
        scheduler.add_job(
            scheduled_retry_pipeline_job,
            trigger=IntervalTrigger(minutes=2),
            id="retry_pipeline_job",
            replace_existing=True,
            max_instances=1
        )
        scheduler.start()
        logger.info("APScheduler started successfully.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler shut down successfully.")
