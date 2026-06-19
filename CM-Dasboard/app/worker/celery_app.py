import os
from celery import Celery

# Use Redis as both the message broker and result backend
# Note: In production, these should be loaded from secure environment variables.
redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
redis_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "cm_worker",
    broker=redis_url,
    backend=redis_backend,
    include=["app.tasks.pipeline_task"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
