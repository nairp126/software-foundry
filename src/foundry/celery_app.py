"""Celery application configuration."""

from celery import Celery
from foundry.config import settings

celery_app = Celery(
    "foundry",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["foundry.agents", "foundry.tasks"])
