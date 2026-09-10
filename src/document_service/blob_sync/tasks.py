"""Celery entry points for durable Blob sync (CAP-3, ADR-006).

Follows the extraction-service precedent: the task payload is identity only
(tenant, connection, trigger class) as JSON, and the worker re-reads all state
at execution time. The scheduler and the manual trigger enqueue through
`enqueue_sync`; the task itself calls `run_sync` and returns its finite
outcome — never bytes, references, or provider diagnostics.
"""

from celery import Celery

from src.shared.config import settings

celery_app = Celery(
    "blob_sync_service",
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
)

BLOB_SYNC_QUEUE = getattr(settings, "blob_sync_celery_queue", "blob_sync")
TASK_NAME = "blob_sync_run"


def enqueue_sync(tenant_id: str, connection_id: str, trigger: str) -> None:
    celery_app.send_task(
        TASK_NAME,
        args=[tenant_id, connection_id, trigger],
        queue=BLOB_SYNC_QUEUE,
    )


@celery_app.task(name=TASK_NAME)
def run_blob_sync_task(tenant_id: str, connection_id: str, trigger: str) -> dict:
    """Worker entry point. Returns the finite run outcome for the result backend."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.document_service.blob_sync.sync import run_sync
    from src.shared.database import get_engine

    # Reopenable source-only documents processed from this worker re-acquire
    # their bytes through the registered provider seam.
    from src.document_service.blob_sync import reopen as _reopen  # noqa: F401

    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    result = asyncio.run(
        run_sync(session_factory, tenant_id, connection_id, trigger)
    )
    return {
        "run_id": result.run_id,
        "outcome": result.outcome,
        "reason": result.reason,
    }
