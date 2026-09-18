"""The per-tenant data-plane record: lookup, short-TTL cache, and typed errors
(ADR-017, Design D2, D4, D8).

`public.tenant_data_planes` is the one authoritative, content-free answer to "where
does this tenant's schema live, and can content routes use it right now" — read by the
resolver, the content-route gate (group 6), the provider control plane (group 7), and
the portal/admin-console APIs (groups 10, 13). This module is the single place that
table is read from and cached; nothing else selects from it directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text

from src.shared.config import settings

MODE_PLATFORM = "platform"
MODE_TENANT_OWNED = "tenant_owned"

# The connection provider a `tenant_owned` tenant's data-plane connection uses (Design
# D3), and the secret-reference "kind" its `password_ref` resolves under (matching
# `PROVIDER_SECRET_KIND` in `src/shared/data_sources/providers.py`, group 7). Defined
# here rather than there so the resolver and `tenant_store/migrate.py` — both of which
# need this before group 7's provider registration exists — depend on this module, not
# on each other's private constants.
DATA_PLANE_PROVIDER = "azure_postgresql_data_plane"
DATA_PLANE_SECRET_KIND = "tenant_postgresql_data_plane"

STATUS_AWAITING_STORE = "awaiting_store"
STATUS_PROVISIONING = "provisioning"
STATUS_PROVISIONING_FAILED = "provisioning_failed"
STATUS_READY = "ready"
STATUS_MIGRATION_REQUIRED = "migration_required"
STATUS_PAUSED = "paused"
STATUS_STORE_RETIRED = "store_retired"

HEALTH_HEALTHY = "healthy"
HEALTH_UNREACHABLE = "unreachable"
HEALTH_AUTH_FAILED = "auth_failed"
HEALTH_TIMEOUT = "timeout"


def data_plane_retry_countdown(retries: int) -> int:
    """Bounded exponential backoff for a `DataPlaneUnavailable`/`DataPlaneNotReady`
    retry (tenant-data-plane-failure-isolation spec's "Background tasks retry with
    bounded backoff and then park"): 5s, 10s, 20s, ... capped at 300s. Shared by every
    background task that retries on a data-plane failure, so the backoff shape stays
    one decision, not one per task."""
    return min(5 * (2**retries), 300)


class DataPlaneNotReady(Exception):
    """A `tenant_owned` tenant's data plane is not `ready` — content routes map this to
    409 `TENANT_DATA_PLANE_NOT_READY` (Design D9)."""

    def __init__(self, status_class: str):
        self.status_class = status_class
        super().__init__(f"data plane not ready: {status_class}")


class DataPlaneUnavailable(Exception):
    """A `ready` tenant's store could not be reached, authenticated, or timed out —
    content routes map this to 503 `TENANT_DATA_PLANE_UNAVAILABLE` (Design D8). The
    reason class is safe to log and return; the original driver message never is."""

    def __init__(self, reason_class: str):
        self.reason_class = reason_class
        super().__init__(f"data plane unavailable: {reason_class}")


@dataclass(frozen=True)
class DataPlaneRecord:
    tenant_id: str
    mode: str
    status: str
    connection_id: str | None
    store_id: str | None
    schema_revision: int | None
    status_reason: str
    # Opaque cache-key component (`updated_at`), not for display — bumped by any row
    # change, so an engine cached against a stale value is never reused after a pause,
    # replace, or retire is observed.
    updated_at_token: str
    # The last resolver-failure or probe-recorded outcome (`HEALTH_*` or `None` if
    # never recorded) — read by `require_data_plane_ready`'s circuit breaker
    # (task 11.3) so a tenant already known down is refused without a wasted
    # connection attempt on every request in between.
    health_outcome: str | None = None

    @property
    def is_platform(self) -> bool:
        return self.mode == MODE_PLATFORM

    @property
    def is_ready(self) -> bool:
        return self.status == STATUS_READY


_SELECT_SQL = text(
    "SELECT tenant_id, mode, status, connection_id, store_id, schema_revision, "
    "status_reason, updated_at, health_outcome FROM public.tenant_data_planes WHERE tenant_id = :tid"
)


def _row_to_record(row) -> DataPlaneRecord:
    return DataPlaneRecord(
        tenant_id=row.tenant_id,
        mode=row.mode,
        status=row.status,
        connection_id=str(row.connection_id) if row.connection_id else None,
        store_id=str(row.store_id) if row.store_id else None,
        schema_revision=row.schema_revision,
        status_reason=row.status_reason,
        updated_at_token=row.updated_at.isoformat() if row.updated_at else "",
        health_outcome=row.health_outcome,
    )


class _Cache:
    """Short-TTL in-process cache (default 15s, `NER_DATA_PLANE_CACHE_TTL_SECONDS`).
    Bounds how stale a paused/retired connection looks to a process that did not
    perform the transition itself — the acting process calls `invalidate()` directly."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, DataPlaneRecord]] = {}

    def get(self, tenant_id: str) -> DataPlaneRecord | None:
        entry = self._entries.get(tenant_id)
        if entry is None:
            return None
        fetched_at, record = entry
        if time.monotonic() - fetched_at > settings.data_plane_cache_ttl_seconds:
            return None
        return record

    def put(self, tenant_id: str, record: DataPlaneRecord) -> None:
        self._entries[tenant_id] = (time.monotonic(), record)

    def invalidate(self, tenant_id: str) -> None:
        self._entries.pop(tenant_id, None)

    def clear(self) -> None:
        self._entries.clear()


_cache = _Cache()


def invalidate(tenant_id: str) -> None:
    """Call from the acting process immediately after a pause, replace, retire, or
    provisioning-status transition (Design D4's "engine cache is invalidated on
    connection change" — this is that invalidation, one level up from the engine
    cache itself, which keys off `updated_at_token` and so self-invalidates once this
    fires)."""
    _cache.invalidate(tenant_id)


def _default_platform_record(tenant_id: str) -> DataPlaneRecord:
    # Every tenant existing before migration 043 is backfilled a record, and every
    # `tenant_owned` tenant is created with one atomically (group 9) — so a missing row
    # can only mean a tenant whose schema was cloned on the platform by a caller that
    # predates or bypasses that atomic creation (every pre-group-9 code path, and test
    # fixtures that insert `public.tenants` directly). That tenant's schema genuinely
    # is on the platform, so defaulting here is correct, not a guess — a `tenant_owned`
    # tenant is never created any way but atomically, so this default can never
    # mask one losing its record.
    return DataPlaneRecord(tenant_id, MODE_PLATFORM, STATUS_READY, None, None, None, "none", "")


async def get_data_plane_record(tenant_id: str, conn) -> DataPlaneRecord:
    """`conn` is an `AsyncConnection` or `AsyncSession` on the *platform* database."""
    cached = _cache.get(tenant_id)
    if cached is not None:
        return cached
    result = await conn.execute(_SELECT_SQL, {"tid": tenant_id})
    row = result.fetchone()
    record = _row_to_record(row) if row is not None else _default_platform_record(tenant_id)
    _cache.put(tenant_id, record)
    return record


# --- Compare-and-set status transitions (tenant-data-source-control-plane spec) -----------
# Every transition is a CAS (`UPDATE ... WHERE status = :expected`), so a concurrent
# activation, retry, or deploy run cannot race one into an inconsistent state. Each
# returns whether the row actually moved, and each invalidates this process's cache
# and the tenant's cached engines so the next resolution reflects the new state
# immediately (Design D4) rather than waiting out the TTL.


async def _cas_status(conn, tenant_id: str, expected: set[str] | str, new_status: str, reason: str, **extra_set) -> bool:
    expected_set = {expected} if isinstance(expected, str) else expected
    set_clauses = ["status = :new_status", "status_reason = :reason", "updated_at = NOW()"]
    params = {"tid": tenant_id, "new_status": new_status, "reason": reason, "expected": list(expected_set)}
    for key, value in extra_set.items():
        set_clauses.append(f"{key} = :{key}")
        params[key] = value
    result = await conn.execute(
        text(
            f"UPDATE public.tenant_data_planes SET {', '.join(set_clauses)} "
            "WHERE tenant_id = :tid AND status = ANY(:expected)"
        ),
        params,
    )
    moved = result.rowcount > 0
    if moved:
        invalidate(tenant_id)
    return moved


async def mark_paused(conn, tenant_id: str) -> bool:
    """Active connection paused -> data plane `paused` (content routes 409)."""
    return await _cas_status(conn, tenant_id, {STATUS_READY}, STATUS_PAUSED, "connection_paused")


async def mark_provisioning(conn, tenant_id: str, connection_id: str) -> bool:
    """First activation of a data-plane connection -> `provisioning`, binding the
    connection that provisioning will use. CAS from `awaiting_store` (first ever) or
    `provisioning_failed` (retry)."""
    return await _cas_status(
        conn, tenant_id,
        {STATUS_AWAITING_STORE, STATUS_PROVISIONING_FAILED},
        STATUS_PROVISIONING, "activation_enqueued",
        connection_id=connection_id,
    )


async def mark_ready_from_paused(conn, tenant_id: str) -> bool:
    """Re-activation of a previously-provisioned store -> `ready`. Caller verifies
    store identity and revision before calling (tenant-residency-store-provisioning
    spec's "Replacement connections must point at the same store")."""
    return await _cas_status(conn, tenant_id, {STATUS_PAUSED}, STATUS_READY, "reactivated")


async def mark_retired(conn, tenant_id: str) -> bool:
    """Retirement -> `store_retired`, terminal. No DDL/DML against the tenant store —
    this only ever touches the control-plane row."""
    return await _cas_status(
        conn, tenant_id,
        {STATUS_READY, STATUS_PAUSED, STATUS_MIGRATION_REQUIRED, STATUS_PROVISIONING_FAILED},
        STATUS_STORE_RETIRED, "retired",
    )


_VALID_HEALTH_OUTCOMES = {HEALTH_HEALTHY, HEALTH_UNREACHABLE, HEALTH_AUTH_FAILED, HEALTH_TIMEOUT}

_RECORD_HEALTH_SQL = text(
    "UPDATE public.tenant_data_planes SET health_outcome = :outcome, health_checked_at = NOW() "
    "WHERE tenant_id = :tid AND mode = :mode"
)


async def record_health(conn, tenant_id: str, outcome: str) -> None:
    """Records a resolver-failure or probe health outcome (tenant-data-plane-
    failure-isolation spec's "Per-tenant store health is a content-free control-
    plane signal"). Unconditional — health is an observability signal, not a
    lifecycle transition, so it is never gated by a CAS on `status`. A `platform`
    tenant's row (`mode = 'platform'`) is never updated: health tracking only
    means something for a store this platform does not itself operate."""
    if outcome not in _VALID_HEALTH_OUTCOMES:
        return
    await conn.execute(_RECORD_HEALTH_SQL, {"tid": tenant_id, "outcome": outcome, "mode": MODE_TENANT_OWNED})


def record_health_sync(conn, tenant_id: str, outcome: str) -> None:
    """`record_health` for a sync `Connection` (Celery workers, the health probe)."""
    if outcome not in _VALID_HEALTH_OUTCOMES:
        return
    conn.execute(_RECORD_HEALTH_SQL, {"tid": tenant_id, "outcome": outcome, "mode": MODE_TENANT_OWNED})


def get_data_plane_record_sync(tenant_id: str, conn) -> DataPlaneRecord:
    """`conn` is a sync `Connection` or `Session` on the *platform* database."""
    cached = _cache.get(tenant_id)
    if cached is not None:
        return cached
    result = conn.execute(_SELECT_SQL, {"tid": tenant_id})
    row = result.fetchone()
    record = _row_to_record(row) if row is not None else _default_platform_record(tenant_id)
    _cache.put(tenant_id, record)
    return record
