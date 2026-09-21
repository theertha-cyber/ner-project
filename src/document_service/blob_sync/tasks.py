"""Celery entry points for durable Blob sync (CAP-3, ADR-006).

Follows the extraction-service precedent: the task payload is identity only
(tenant, connection, trigger class) as JSON, and the worker re-reads all state
at execution time. The scheduler and the manual trigger enqueue through
`enqueue_sync`; the task itself calls `run_sync` and returns its finite
outcome — never bytes, references, or provider diagnostics.
"""

import logging

from celery import Celery

from src.shared.config import settings

logger = logging.getLogger(__name__)

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
TICK_TASK_NAME = "blob_sync_tick"
TICK_INTERVAL_SECONDS = 60.0

# Both tasks must land on the queue the blob_sync worker consumes (`-Q blob_sync`).
# Without a route, beat publishes the tick to Celery's default `celery` queue,
# where the general-purpose worker discards it as an unregistered task and no
# scheduled sync ever runs.
celery_app.conf.task_routes = {
    TASK_NAME: {"queue": BLOB_SYNC_QUEUE},
    TICK_TASK_NAME: {"queue": BLOB_SYNC_QUEUE},
}

celery_app.conf.beat_schedule = {
    "blob-sync-tick": {
        "task": TICK_TASK_NAME,
        "schedule": TICK_INTERVAL_SECONDS,
    },
}


def enqueue_sync(tenant_id: str, connection_id: str, trigger: str) -> None:
    celery_app.send_task(
        TASK_NAME,
        args=[tenant_id, connection_id, trigger],
        queue=BLOB_SYNC_QUEUE,
    )


@celery_app.task(name=TICK_TASK_NAME)
def blob_sync_tick() -> dict:
    """Runs every `TICK_INTERVAL_SECONDS` on the beat schedule.

    Cheap by design: the tick itself is frequent, but each connection's own
    15-minute cadence (and one-catchup-after-a-miss rule) is decided by
    `evaluate_connection`, not by this interval. A tick that finds nothing due
    enqueues nothing.
    """
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.document_service.blob_sync.scheduler import (
        DECISION_CATCHUP,
        DECISION_DUE,
        evaluate_connection,
    )
    from src.shared.data_sources.providers import PROVIDER_AZURE_BLOB
    from src.shared.data_sources.store import CONNECTIONS_TABLE
    from src.shared.database import get_engine
    from src.shared.tenant_schema import schema_for_tenant
    from src.document_service.blob_sync import ledger

    from src.shared.database import get_resolver
    from src.shared.data_plane import DataPlaneNotReady, DataPlaneUnavailable

    async def _tick() -> list[str]:
        # Enumerating every active Blob connection is a control-plane read (`public.*`)
        # — the platform engine is correct here. Each connection's own ledger tables
        # below live in that TENANT's schema, so they are routed per-tenant (ADR-017).
        platform_engine = get_engine()
        platform_sessions = async_sessionmaker(platform_engine, expire_on_commit=False)
        enqueued: list[str] = []
        async with platform_sessions() as session:
            rows = (
                await session.execute(
                    text(
                        f"SELECT id, tenant_id, activated_at FROM {CONNECTIONS_TABLE} "
                        "WHERE provider = :provider AND status = 'active'"
                    ),
                    {"provider": PROVIDER_AZURE_BLOB},
                )
            ).fetchall()
        used_tenants: set[str] = set()
        try:
            for connection_id, tenant_id, activated_at in rows:
                schema = schema_for_tenant(tenant_id)
                try:
                    tenant_engine = await get_resolver().resolve(str(tenant_id))
                except (DataPlaneNotReady, DataPlaneUnavailable):
                    # Skip this connection's tick — a per-tenant outage must not abort the
                    # tick for every other tenant's connections.
                    continue
                used_tenants.add(str(tenant_id))
                tenant_sessions = async_sessionmaker(tenant_engine, expire_on_commit=False)
                async with tenant_sessions() as session:
                    await ledger.ensure_sync_tables(session, schema)
                    await session.commit()
                    last_success = await ledger.last_successful_run_at(
                        session, schema, str(connection_id)
                    )
                decision = evaluate_connection(
                    active=True, last_success_at=last_success, connected_at=activated_at
                )
                if decision.decision in (DECISION_DUE, DECISION_CATCHUP):
                    enqueue_sync(str(tenant_id), str(connection_id), decision.trigger)
                    enqueued.append(str(connection_id))
        finally:
            await _dispose_tenant_engines(used_tenants)
        return enqueued

    enqueued = asyncio.run(_tick())
    return {"enqueued": enqueued}


async def _dispose_tenant_engines(tenant_ids) -> None:
    """Dispose each tenant's cached engine before the calling `asyncio.run` loop ends.

    A pooled async engine's connections are bound to the loop that opened them. Every
    Celery task here runs in its own `asyncio.run`, so an engine left in the resolver's
    cache is reused from a *different* loop by the next task and fails with "attached to
    a different loop" / "another operation is in progress"."""
    from src.shared.database import get_resolver

    for tenant_id in tenant_ids:
        await get_resolver().invalidate_tenant(tenant_id)


def _data_plane_retry_countdown(retries: int) -> int:
    """Bounded exponential backoff for a `DataPlaneUnavailable`/`DataPlaneNotReady`
    retry (tenant-data-plane-failure-isolation spec's "Background tasks retry with
    bounded backoff and then park"): 5s, 10s, 20s, ... capped at 300s."""
    return min(5 * (2**retries), 300)


@celery_app.task(bind=True, name=TASK_NAME)
def run_blob_sync_task(self, tenant_id: str, connection_id: str, trigger: str) -> dict:
    """Worker entry point. Returns the finite run outcome for the result backend.

    A `tenant_owned` tenant's store being unreachable retries with bounded
    backoff (`NER_DATA_PLANE_TASK_MAX_RETRIES`) rather than failing the run
    outright — a transient outage should not need a fresh manual sync trigger to
    recover from. Once the budget is exhausted the task parks in a finite
    `failed_retryable` outcome; the payload it carries throughout is identifiers
    only (`tenant_id`, `connection_id`, `trigger`), never tenant content."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.document_service.blob_sync.sync import run_sync
    from src.shared.data_plane import DataPlaneNotReady, DataPlaneUnavailable
    from src.shared.database import get_engine, get_resolver

    # Reopenable source-only documents processed from this worker re-acquire
    # their bytes through the registered provider seam.
    from src.document_service.blob_sync import reopen as _reopen  # noqa: F401

    async def _run_and_drain():
        try:
            return await _run_sync_and_drain()
        finally:
            await _dispose_tenant_engines([tenant_id])

    async def _run_sync_and_drain():
        # Routed through EngineResolver (ADR-017): this tenant's ledger and document
        # rows live wherever its data plane resolves, not always the platform database.
        engine = await get_resolver().resolve(tenant_id)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        # The connection row and integration profile are control-plane tables: they live
        # on the platform database even when the tenant's own data plane is elsewhere.
        platform_session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        result = await run_sync(
            session_factory, tenant_id, connection_id, trigger,
            platform_session_factory=platform_session_factory,
        )
        # Ingestion dispatches OCR as a fire-and-forget asyncio task (today's
        # in-process dispatcher). asyncio.run() tears its loop down the instant
        # this coroutine returns, which orphans and cancels any such task
        # mid-flight — exactly the failure mode that silently lost OCR work.
        # Draining every other pending task here before returning closes that
        # gap without changing the dispatcher's own fire-and-forget contract.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return result

    try:
        result = asyncio.run(_run_and_drain())
    except (DataPlaneUnavailable, DataPlaneNotReady) as exc:
        if self.request.retries < settings.data_plane_task_max_retries:
            raise self.retry(exc=exc, countdown=_data_plane_retry_countdown(self.request.retries))
        logger.warning(
            "blob_sync_parked_data_plane_unavailable",
            extra={"tenant_id": tenant_id, "connection_id": connection_id, "retries": self.request.retries},
        )
        return {"run_id": None, "outcome": "failed_retryable", "reason": "data_plane_unavailable"}
    return {
        "run_id": result.run_id,
        "outcome": result.outcome,
        "reason": result.reason,
    }


# Registers `provision_tenant_data_plane` on this same Celery app (ADR-017, task
# 10.1) — `-A src.document_service.blob_sync.tasks` is the worker's entry module,
# so a task defined elsewhere is invisible to the worker until something imports
# it. Deliberately at the bottom: `data_plane.tasks` imports `celery_app` back
# from this module, and by this point that name is already bound.
from src.document_service.data_plane import tasks as _data_plane_tasks  # noqa: E402,F401
