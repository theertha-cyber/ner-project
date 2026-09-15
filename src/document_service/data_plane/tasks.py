"""The tenant-store provisioning Celery task (ADR-017, Design D6 — task 10.1).

Runs on the `data_plane` queue served by the document-service Celery worker (same
broker as CAP-3's blob-sync app — `src.document_service.blob_sync.tasks.celery_app`).
Enqueued once, by `src.shared.data_sources.service.activate_connection`, on a
`tenant_owned` tenant's first `azure_postgresql_data_plane` activation, and again by
the tenant-admin retry endpoint (task 10.2) after a `provisioning_failed` outcome.

Idempotent end to end: every statement `apply.apply()` runs is `IF NOT EXISTS` or a
`pg_constraint` guard, `CREATE EXTENSION IF NOT EXISTS`, and the CAS status transition
only ever leaves `provisioning` for `ready` or `provisioning_failed` — a retry from
`provisioning_failed` re-enters this same function and finishes what a prior attempt
left half-done.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from sqlalchemy import create_engine, text

from src.document_service.blob_sync.tasks import celery_app
from src.shared.config import settings
from src.shared.data_plane import (
    DATA_PLANE_SECRET_KIND,
    HEALTH_AUTH_FAILED,
    HEALTH_HEALTHY,
    HEALTH_TIMEOUT,
    HEALTH_UNREACHABLE,
    STATUS_PROVISIONING,
    STATUS_READY,
    invalidate,
    record_health_sync,
)
from src.shared.database import get_resolver, system_ca_bundle_path
from src.shared.integration_profile.secrets import (
    SecretResolutionError,
    resolve_for_tenant,
)
from src.shared.tenant_store import apply as apply_module

logger = logging.getLogger(__name__)

DATA_PLANE_QUEUE = "data_plane"
TASK_NAME = "provision_tenant_data_plane"
HEALTH_PROBE_TASK_NAME = "probe_tenant_data_plane_health"

celery_app.conf.task_routes.setdefault(TASK_NAME, {"queue": DATA_PLANE_QUEUE})
celery_app.conf.task_routes.setdefault(HEALTH_PROBE_TASK_NAME, {"queue": DATA_PLANE_QUEUE})
celery_app.conf.beat_schedule = {
    **celery_app.conf.beat_schedule,
    "data-plane-health-probe": {
        "task": HEALTH_PROBE_TASK_NAME,
        "schedule": settings.data_plane_health_probe_interval_seconds,
    },
}


class _ProfileShim:
    """The minimal shape `resolve_for_tenant` needs, built from a connection row
    rather than an integration profile (matches `tenant_store/migrate.py`'s and
    `database.py`'s identical shims)."""

    def __init__(self, tenant_id: str, secret_references: dict):
        self.tenant_id = tenant_id
        self.secret_references = secret_references


def _platform_engine():
    return get_resolver().resolve_sync(None)


def _connection_url(configuration: dict, password: str) -> str:
    sslmode = configuration.get("sslmode", "verify-full")
    # See `database.py::_connection_url` — an unescaped `@`/`/`/`:` in the password
    # (routine in a real Azure-generated password) splits the URL's userinfo/host
    # boundary in the wrong place.
    url = (
        f"postgresql://{quote(configuration['username'], safe='')}:{quote(password, safe='')}@"
        f"{configuration['host']}:{configuration['port']}/{configuration['database']}"
        f"?sslmode={sslmode}"
    )
    if sslmode not in ("disable", "allow", "prefer"):
        # See `system_ca_bundle_path` (database.py): psycopg2-binary's bundled
        # OpenSSL does not resolve against the container's real CA bundle on its
        # own, so the actual path is passed explicitly.
        cafile = system_ca_bundle_path()
        if cafile:
            url += f"&sslrootcert={cafile}"
    return url


def _set_outcome(platform_conn, tenant_id: str, *, status: str, reason: str, **extra) -> None:
    set_clauses = ["status = :status", "status_reason = :reason", "updated_at = NOW()"]
    params = {"tid": tenant_id, "status": status, "reason": reason}
    for key, value in extra.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = value
    platform_conn.execute(
        text(
            f"UPDATE public.tenant_data_planes SET {', '.join(set_clauses)} "
            "WHERE tenant_id = :tid AND status = :expected_status"
        ),
        {**params, "expected_status": STATUS_PROVISIONING},
    )
    platform_conn.commit()
    invalidate(tenant_id)


@celery_app.task(bind=True, name=TASK_NAME, max_retries=0)
def provision_tenant_data_plane(self, tenant_id: str) -> dict:
    """Provisions `tenant_id`'s own store: `vector` extension, schema, baseline +
    revisions, `platform_store_meta`, and the chat query role. CAS `provisioning` ->
    `ready` on success, `provisioning` -> `provisioning_failed` with a finite reason on
    any failure — never left at `provisioning` (the CAS is unconditional on failure,
    only the *source* status is gated, so a task that starts twice concurrently is
    safe: the second CAS to `ready` or `provisioning_failed` is a no-op once the first
    has already moved the row)."""
    platform_engine = _platform_engine()
    schema = f"tenant_{tenant_id.replace('-', '_')}"
    outcome = "unknown_error"
    try:
        with platform_engine.connect() as platform_conn:
            dp_row = platform_conn.execute(
                text(
                    "SELECT connection_id, store_id FROM public.tenant_data_planes "
                    "WHERE tenant_id = :tid AND status = :status"
                ),
                {"tid": tenant_id, "status": STATUS_PROVISIONING},
            ).fetchone()
            if dp_row is None or dp_row.connection_id is None:
                logger.info(
                    "data_plane_provisioning_skipped",
                    extra={"tenant_id": tenant_id, "reason": "not_in_provisioning_state"},
                )
                return {"tenant_id": tenant_id, "outcome": "skipped"}

            conn_row = platform_conn.execute(
                text(
                    "SELECT configuration, secret_references FROM public.tenant_data_source_connections "
                    "WHERE id = :cid"
                ),
                {"cid": str(dp_row.connection_id)},
            ).fetchone()
            if conn_row is None:
                _set_outcome(platform_conn, tenant_id, status="provisioning_failed", reason="connection_missing")
                return {"tenant_id": tenant_id, "outcome": "connection_missing"}

            configuration = conn_row.configuration or {}
            secret_references = conn_row.secret_references or {}

            try:
                secrets = resolve_for_tenant(
                    _ProfileShim(tenant_id, {DATA_PLANE_SECRET_KIND: secret_references}),
                    DATA_PLANE_SECRET_KIND,
                )
            except SecretResolutionError:
                _set_outcome(platform_conn, tenant_id, status="provisioning_failed", reason="secret_unresolvable")
                return {"tenant_id": tenant_id, "outcome": "secret_unresolvable"}

            password = secrets.get("password_ref") or secrets.get("password")
            if not password:
                _set_outcome(platform_conn, tenant_id, status="provisioning_failed", reason="secret_unresolvable")
                return {"tenant_id": tenant_id, "outcome": "secret_unresolvable"}

            try:
                store_engine = create_engine(
                    _connection_url(configuration, password),
                    connect_args={"connect_timeout": int(settings.data_plane_connect_timeout_seconds)},
                )
                # `Connection` autobegins a transaction on first `execute()` (SQLAlchemy
                # 2.0), so every step below commits explicitly rather than opening a
                # nested `with store_conn.begin():` — issuing an explicit `begin()` on a
                # connection that has already autobegun (e.g. the `schema_has_foreign_
                # objects`/`read_store_identity` reads above it) raises
                # `InvalidRequestError`.
                with store_engine.connect() as store_conn:
                    if apply_module.schema_has_foreign_objects(store_conn, schema):
                        outcome = "target_schema_not_empty"
                        _set_outcome(platform_conn, tenant_id, status="provisioning_failed", reason=outcome)
                        return {"tenant_id": tenant_id, "outcome": outcome}

                    store_conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    store_conn.commit()

                    existing_identity = apply_module.read_store_identity(store_conn, schema)
                    expected_store_id = str(dp_row.store_id) if dp_row.store_id else None
                    if (
                        existing_identity is not None
                        and expected_store_id is not None
                        and existing_identity[0] != expected_store_id
                    ):
                        outcome = "store_identity_mismatch"
                        _set_outcome(platform_conn, tenant_id, status="provisioning_failed", reason=outcome)
                        return {"tenant_id": tenant_id, "outcome": outcome}

                    new_store_id, schema_revision = apply_module.apply(
                        store_conn, schema, tenant_id, store_id=expected_store_id
                    )
                    store_conn.commit()

                    # Chat query role, reusing the exact statement builder the
                    # platform's own fleet provisioning uses (sql_execution_role.py) —
                    # the tenant's generated entity tables are read from the platform
                    # control plane (Design D10), the grants applied to the store.
                    # `resolve_generated_tables` is async/AsyncSession-only, so the
                    # tenant's catalog is loaded here with a sync query and fed through
                    # the same pure `build_query_surface` it delegates to, keeping one
                    # implementation of "what counts as a generated table".
                    from src.chat_api.services.sql_execution_role import build_role_statements
                    from src.shared.entity_views import (
                        _QUERY_SURFACE_QUERY as ENTITY_QUERY_SURFACE_QUERY,
                        _spec_from_row,
                        build_query_surface,
                        schema_for_tenant,
                    )

                    definitions = [
                        _spec_from_row(row)
                        for row in platform_conn.execute(
                            text(ENTITY_QUERY_SURFACE_QUERY)
                        ).fetchall()
                        if schema_for_tenant(row.tenant_id) == schema
                    ]
                    generated = {schema: build_query_surface(definitions).table_names}
                    for statement in build_role_statements(
                        settings.sql_execution_role_name, [schema], generated
                    ):
                        store_conn.execute(text(statement))
                    store_conn.commit()

                store_engine.dispose()
            except Exception:
                logger.warning(
                    "data_plane_provisioning_store_failed",
                    extra={"tenant_id": tenant_id},
                    exc_info=True,
                )
                _set_outcome(platform_conn, tenant_id, status="provisioning_failed", reason="store_unreachable")
                return {"tenant_id": tenant_id, "outcome": "store_unreachable"}

            _set_outcome(
                platform_conn, tenant_id, status="ready", reason="provisioned",
                store_id=new_store_id, schema_revision=schema_revision,
            )
            outcome = "ready"
    except Exception:
        logger.error("data_plane_provisioning_failed", extra={"tenant_id": tenant_id}, exc_info=True)
        try:
            with platform_engine.connect() as platform_conn:
                _set_outcome(platform_conn, tenant_id, status="provisioning_failed", reason="unknown_error")
        except Exception:
            logger.error("data_plane_provisioning_outcome_write_failed", extra={"tenant_id": tenant_id}, exc_info=True)
        outcome = "unknown_error"

    return {"tenant_id": tenant_id, "outcome": outcome}


def _probe_one(tenant_id: str, connection_id: str, configuration: dict, secret_references: dict) -> str:
    """`SELECT 1` against one tenant's store. Returns a `HEALTH_*` outcome class,
    never a driver message (Design D8) — the caller records only this."""
    from src.shared.tenant_context import classify_driver_error

    try:
        secrets = resolve_for_tenant(
            _ProfileShim(tenant_id, {DATA_PLANE_SECRET_KIND: secret_references}), DATA_PLANE_SECRET_KIND
        )
    except SecretResolutionError:
        return HEALTH_AUTH_FAILED
    password = secrets.get("password_ref") or secrets.get("password")
    if not password:
        return HEALTH_AUTH_FAILED

    try:
        store_engine = create_engine(
            _connection_url(configuration, password),
            connect_args={"connect_timeout": int(settings.data_plane_connect_timeout_seconds)},
        )
        try:
            with store_engine.connect() as store_conn:
                store_conn.execute(text("SELECT 1"))
        finally:
            store_engine.dispose()
    except Exception as exc:
        reason = classify_driver_error(exc)
        return {
            "timeout": HEALTH_TIMEOUT,
            "auth_failed": HEALTH_AUTH_FAILED,
            "unreachable": HEALTH_UNREACHABLE,
        }.get(reason, HEALTH_UNREACHABLE)
    return HEALTH_HEALTHY


def _recover_stuck_documents(tenant_id: str) -> list[str]:
    """Resumes documents a worker abandoned mid-OCR when this tenant's store went
    down (tenant-data-plane-failure-isolation spec's recovery-sweep half of task
    11.3). Only a document that has sat in `processing` for longer than
    `data_plane_stuck_document_threshold_seconds` is touched — recent enough and
    it may still be genuinely in flight on a worker that was never affected by
    this tenant's outage, and stealing that one would race it.

    Resets the stale row to `pending` (the status `process_document`'s normal,
    non-`reprocess` claim path requires — see `ocr_worker.py`), then dispatches
    it through that exact path, so recovery is not a new, separately-tested code
    path: it is the same claim-and-process a fresh upload goes through, just
    triggered by a health transition instead of an upload request."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.document_service.services.ocr_worker import process_document
    from src.shared.database import get_resolver as get_async_resolver
    from src.shared.tenant_schema import schema_for_tenant

    schema = schema_for_tenant(tenant_id)

    async def _sweep() -> list[str]:
        engine = await get_async_resolver().resolve(tenant_id)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        f"UPDATE {schema}.documents SET status = 'pending' "
                        "WHERE status = 'processing' "
                        "AND updated_at < NOW() - make_interval(secs => :threshold) "
                        "RETURNING id"
                    ),
                    {"threshold": settings.data_plane_stuck_document_threshold_seconds},
                )
            ).fetchall()
            await session.commit()
        document_ids = [str(row.id) for row in rows]
        for document_id in document_ids:
            try:
                await process_document(document_id, tenant_id)
            except Exception:
                logger.warning(
                    "data_plane_recovery_dispatch_failed",
                    extra={"tenant_id": tenant_id, "document_id": document_id},
                    exc_info=True,
                )
        return document_ids

    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_sweep())
        # Called from a context that already has an event loop running (e.g. an
        # async test driving this sync task directly) -- asyncio.run() cannot
        # nest, so give the sweep its own loop on a separate thread instead.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, _sweep()).result()
    except Exception:
        logger.warning("data_plane_recovery_sweep_failed", extra={"tenant_id": tenant_id}, exc_info=True)
        return []


@celery_app.task(name=HEALTH_PROBE_TASK_NAME)
def probe_tenant_data_plane_health() -> dict:
    """Beat task (tenant-data-plane-failure-isolation spec's "Per-tenant store
    health is a content-free control-plane signal"): one lightweight `SELECT 1`
    per `ready` `tenant_owned` tenant, on the cadence the beat schedule sets -- that
    interval *is* the rate limit on health writes, so no per-tenant throttling is
    layered on top of it.

    A tenant whose store answers again after being recorded unreachable needs no
    *manual* operator action for content routes: the next real request already
    succeeds once the store is actually reachable, since content routes were never
    blocked by health, only by `status`. What a plain content route cannot do is
    resume a document a background worker abandoned mid-flight when the store went
    down -- recovery here also runs `_recover_stuck_documents` on exactly that
    transition (a prior outcome in `HEALTH_UNREACHABLE`/`HEALTH_AUTH_FAILED`/
    `HEALTH_TIMEOUT` moving to `HEALTH_HEALTHY`), sweeping that tenant's `documents`
    stuck in `processing` back to dispatchable.
    """
    platform_engine = get_resolver().resolve_sync(None)
    probed: list[str] = []
    recovered: dict[str, list[str]] = {}
    with platform_engine.connect() as platform_conn:
        tenants = platform_conn.execute(
            text(
                """
                SELECT dp.tenant_id, dp.connection_id, dp.health_outcome AS previous_health,
                       c.configuration, c.secret_references
                FROM public.tenant_data_planes dp
                JOIN public.tenant_data_source_connections c
                    ON c.id = dp.connection_id AND c.status = 'active'
                WHERE dp.mode = 'tenant_owned' AND dp.status = :ready
                """
            ),
            {"ready": STATUS_READY},
        ).fetchall()

        for row in tenants:
            outcome = _probe_one(
                row.tenant_id, str(row.connection_id), row.configuration or {}, row.secret_references or {}
            )
            record_health_sync(platform_conn, row.tenant_id, outcome)
            platform_conn.commit()
            probed.append(row.tenant_id)

            if outcome == HEALTH_HEALTHY and row.previous_health in (
                HEALTH_UNREACHABLE, HEALTH_AUTH_FAILED, HEALTH_TIMEOUT,
            ):
                resumed = _recover_stuck_documents(row.tenant_id)
                if resumed:
                    recovered[row.tenant_id] = resumed

    return {"probed": probed, "recovered": recovered}


RECONCILE_REGISTRY_TASK_NAME = "reconcile_tenant_document_registry"
_RECONCILE_INTERVAL_SECONDS = 300.0

celery_app.conf.task_routes.setdefault(RECONCILE_REGISTRY_TASK_NAME, {"queue": DATA_PLANE_QUEUE})
celery_app.conf.beat_schedule = {
    **celery_app.conf.beat_schedule,
    "tenant-document-registry-reconcile": {
        "task": RECONCILE_REGISTRY_TASK_NAME,
        "schedule": _RECONCILE_INTERVAL_SECONDS,
    },
}


@celery_app.task(name=RECONCILE_REGISTRY_TASK_NAME)
def reconcile_tenant_document_registry() -> dict:
    """Beat task (tenant-document-registry spec's "Drift is reconciled" and
    "Unreachable store does not erase registry rows"): re-derives every
    document row from each tenant's own store into the registry. A `tenant_owned`
    tenant whose store cannot be reached this cycle is skipped entirely — its
    existing registry rows are left exactly as they are, never cleared, so a
    transient outage never makes a tenant's document count look like zero."""
    from src.shared import tenant_document_registry as registry
    from src.shared.tenant_context import tenant_sync_session
    from src.shared.tenant_schema import schema_for_tenant

    platform_engine = get_resolver().resolve_sync(None)
    reconciled: list[str] = []
    skipped_unreachable: list[str] = []

    with platform_engine.connect() as platform_conn:
        platform_tenants = platform_conn.execute(
            text(
                """
                SELECT t.id AS tenant_id
                FROM public.tenants t
                LEFT JOIN public.tenant_data_planes dp ON dp.tenant_id = t.id
                WHERE COALESCE(dp.mode, 'platform') = 'platform'
                """
            )
        ).fetchall()
        for row in platform_tenants:
            schema = schema_for_tenant(row.tenant_id)
            has_documents_table = platform_conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = :s AND table_name = 'documents'"
                ),
                {"s": schema},
            ).fetchone()
            if not has_documents_table:
                continue
            try:
                registry.reconcile_schema_sync(platform_conn, platform_conn, tenant_id=row.tenant_id, schema=schema)
                reconciled.append(row.tenant_id)
            except Exception:
                # One tenant's schema drift (a legacy/pre-migration `documents`
                # shape missing a column this projection expects) must not abort
                # reconciliation for every other tenant — same isolation
                # principle as the `tenant_owned` loop below. The failed
                # statement leaves the shared connection's transaction aborted,
                # so it is rolled back before the next tenant's queries run on
                # it.
                platform_conn.rollback()
                logger.info("registry_reconcile_skipped_platform_tenant", extra={"tenant_id": row.tenant_id})
                skipped_unreachable.append(row.tenant_id)

        tenant_owned_ready = platform_conn.execute(
            text(
                "SELECT tenant_id FROM public.tenant_data_planes WHERE mode = 'tenant_owned' AND status = :ready"
            ),
            {"ready": STATUS_READY},
        ).fetchall()

    for row in tenant_owned_ready:
        tenant_id = row.tenant_id
        try:
            with tenant_sync_session(tenant_id) as tenant_session:
                schema = schema_for_tenant(tenant_id)
                with platform_engine.connect() as platform_conn:
                    registry.reconcile_schema_sync(
                        platform_conn, tenant_session, tenant_id=tenant_id, schema=schema
                    )
                    platform_conn.commit()
            reconciled.append(tenant_id)
        except Exception:
            logger.info("registry_reconcile_skipped_unreachable", extra={"tenant_id": tenant_id}, exc_info=True)
            skipped_unreachable.append(tenant_id)

    return {"reconciled": reconciled, "skipped_unreachable": skipped_unreachable}
