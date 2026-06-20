import os
import logging
from celery import Celery
from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "cm_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.pipeline", "app.tasks.escalation", "app.tasks.analytics"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_time_limit=3600,
)

# Setup Celery Beat Schedule
celery_app.conf.beat_schedule = {
    "escalation_job": {
        "task": "app.tasks.escalation.run_escalation_job",
        "schedule": 300.0, # every 5 minutes
    },
    "retry_pipeline_job": {
        "task": "app.tasks.escalation.run_retry_pipeline_job",
        "schedule": 120.0, # every 2 minutes
    },
    "analytics_snapshot_job": {
        "task": "app.tasks.analytics.run_analytics_snapshot_job",
        "schedule": 1800.0, # every 30 minutes
    },
}
