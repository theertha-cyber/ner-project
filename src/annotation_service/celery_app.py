"""Celery app for `annotation_service`'s background work.

Separate from `training_service`'s app and, more importantly, on a separate queue. ADR-006
established Celery/RabbitMQ as this system's answer to "must not block the API", and its GPU
node pool as the place fine-tuning runs. LLM pre-labeling follows the first and must not touch
the second: it is network I/O, not GPU work, so routing it onto `training.jobs` would autoscale
GPU pods to wait on an HTTP call and would leave frequent, cheap pre-label jobs queued behind
infrequent, expensive training runs (design.md Decision 6).
"""

from celery import Celery

from src.shared.config import settings

celery_app = Celery(
    "annotation_service",
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
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue=settings.annotation_llm_celery_queue,
    imports=["src.annotation_service.worker"],
)
