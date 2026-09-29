"""Celery entry points for tabular file ingest (ADR-012 durable ingest, ADR-018).

Follows `src/document_service/blob_sync/tasks.py`: identity-only JSON payloads
(file id, version), the worker re-reads all state at execution time, and both
tasks are routed explicitly to `tabular_ingest` — the queue the
`celery_worker_tabular` compose service consumes (`-Q tabular_ingest`). Without
the route, a task lands on Celery's default `celery` queue, no worker consumes
it, and an upload sits in `profiling` forever.
"""

import logging

from celery import Celery

from src.shared.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "tabular_ingest_service",
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

TABULAR_QUEUE = settings.tabular_celery_queue
PROFILE_TASK_NAME = "tabular_profile_version"
PUBLISH_TASK_NAME = "tabular_publish_version"

celery_app.conf.task_routes = {
    PROFILE_TASK_NAME: {"queue": TABULAR_QUEUE},
    PUBLISH_TASK_NAME: {"queue": TABULAR_QUEUE},
}


def _run(runner, file_id: str, version: int) -> dict:
    """One `asyncio.run` per task with a throwaway NullPool engine, so no pooled
    connection outlives the loop that opened it."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from src.shared.tabular_files.storage import TabularObjectStore

    async def _go():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            return await runner(async_sessionmaker(engine, expire_on_commit=False),
                                TabularObjectStore(), file_id, version)
        finally:
            await engine.dispose()

    return asyncio.run(_go())


@celery_app.task(name=PROFILE_TASK_NAME)
def profile_tabular_version(file_id: str, version: int) -> dict:
    from src.shared.tabular_files.worker import run_profile

    return _run(run_profile, file_id, version)


@celery_app.task(name=PUBLISH_TASK_NAME)
def publish_tabular_version(file_id: str, version: int) -> dict:
    from src.shared.tabular_files.worker import run_publish

    return _run(run_publish, file_id, version)


def enqueue_profile(file_id: str, version: int) -> None:
    profile_tabular_version.apply_async(args=[str(file_id), int(version)], queue=TABULAR_QUEUE)


def enqueue_publish(file_id: str, version: int) -> None:
    publish_tabular_version.apply_async(args=[str(file_id), int(version)], queue=TABULAR_QUEUE)
