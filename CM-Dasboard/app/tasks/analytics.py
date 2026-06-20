import asyncio
import logging
from app.worker.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.analytics import AnalyticsSnapshotService

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.analytics.run_analytics_snapshot_job")
def run_analytics_snapshot_job():
    """Celery Beat task to compute and save analytics snapshot."""
    logger.info("Celery Beat: Starting scheduled analytics snapshot job...")
    
    async def _run():
        async with AsyncSessionLocal() as session:
            try:
                snapshot = await AnalyticsSnapshotService.compute_snapshot(session)
                await AnalyticsSnapshotService.save_snapshot(snapshot, session)
                logger.info("Celery Beat: Scheduled analytics snapshot job completed successfully.")
            except Exception as e:
                logger.error(f"Error during scheduled analytics snapshot job: {e}", exc_info=True)
                await session.rollback()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(_run())
