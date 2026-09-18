"""Tenant-scoped connection lifecycle operations (CAP-2).

Every operation binds to the authenticated tenant supplied by the caller — the
service never reads a tenant identifier from a payload, because there is none.
Single-record access constrains both `id` and `tenant_id`, so another tenant's
identifier resolves to "not found" with no metadata disclosure.

Only finite safe evidence is ever written: outcome/reason classes, correlation
timestamps, and a configuration digest used to detect "still-current" test
evidence. Configuration *values* and secret-reference *values* are write-only;
no read path selects them into a response.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.shared.config import settings
from src.shared.data_plane import (
    MODE_TENANT_OWNED,
    get_data_plane_record,
    invalidate as invalidate_data_plane_record,
    mark_paused,
    mark_provisioning,
    mark_ready_from_paused,
    mark_retired,
)
from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.providers import (
    PROVIDER_AZURE_BLOB,
    PROVIDER_AZURE_POSTGRESQL,
    PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
    PROVIDER_SECRET_KIND,
    ConnectionValidationError,
    validate_configuration,
    validate_provider,
    validate_secret_references,
)
from src.shared.data_sources.store import (
    CONNECTIONS_TABLE,
    IDEMPOTENCY_TABLE,
    IDEMPOTENCY_TTL_HOURS,
)
from src.shared.data_sources.testing import run_secure_test
from src.shared.integration_profile.secrets import (
    SecretResolutionError,
    resolve_for_tenant,
)
from src.shared.observability.domain_metrics import (
    record_data_source_lifecycle,
    record_data_source_test,
)
from src.shared.tenant_schema import schema_for_tenant

logger = logging.getLogger(__name__)

# Mirrors `blob_sync.ledger.RUNS_TABLE`; a literal keeps this shared layer free of
# the worker import.
SYNC_RUNS_TABLE = "azure_blob_sync_runs"
_REPORTED_SYNC_OUTCOMES = sorted(lc.SYNC_OUTCOMES - {lc.SYNC_OUTCOME_NEVER_RUN})

LIST_SORTS = frozenset({"last_activity", "created_at", "provider", "status"})
LIST_ORDERS = frozenset({"asc", "desc"})

SORT_COLUMNS = {
    # Dynamic sort identifiers are allowlisted to these expressions, never
    # interpolated raw (baseline `parameterized-queries-only`).
    "last_activity": "GREATEST(updated_at, COALESCE(last_test_at, updated_at), "
    "COALESCE(activated_at, updated_at))",
    "created_at": "created_at",
    "provider": "provider",
    "status": "status",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_body_digest(configuration: dict, secret_references: dict) -> str:
    """Digest over configuration plus secret-reference *field names*.

    Names, never reference values: the digest detects "configuration changed since
    the test ran" without retaining anything sensitive.
    """
    canonical = json.dumps(
        {"configuration": configuration, "secret_fields": sorted(secret_references)},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _shared_environment() -> bool:
    return settings.environment.lower() not in ("development", "local", "test", "testing", "")


def _secret_values(tenant_id: str, provider: str, secret_references: dict) -> dict:
    """Resolve a connection's references through the tenant-bound secret seam.

    Only references recorded on this tenant's connection resolve, and resolution
    uses the registered resolvers (`env` locally; Vault in shared environments).
    Raises `SecretResolutionError` with a failure class, never a value.
    """
    namespace = type(
        "_ConnectionSecrets",
        (),
        {
            "tenant_id": tenant_id,
            "secret_references": {
                PROVIDER_SECRET_KIND[provider]: dict(secret_references)
            },
        },
    )()
    context = resolve_for_tenant(namespace, PROVIDER_SECRET_KIND[provider])
    return dict(context.values)


async def _invalidate_tenant_engines(tenant_id: str) -> None:
    """Disposes this process's cached engines for `tenant_id` after a pause, replace,
    or retire (Design D4). Deferred import: `src.shared.database` imports this
    package's provider validation indirectly via `data_plane.py`'s callers, so a
    module-level import here risks a cycle as the module set grows."""
    from src.shared.database import get_resolver

    await get_resolver().invalidate_tenant(tenant_id)


async def _check_data_plane_draft_allowed(
    session, tenant_id: str, secret_references: dict
) -> None:
    """The three `azure_postgresql_data_plane`-specific draft checks (ADR-017,
    tenant-data-source-control-plane spec): feature flag, tenant mode, and no secret
    reference shared with the tenant's read-only `azure_postgresql` connection. Raises
    `lc.LifecycleRejected` with the finite safe code; no row is written on rejection."""
    if not settings.tenant_owned_data_plane_enabled:
        raise lc.LifecycleRejected(
            "TENANT_OWNED_DATA_PLANE_DISABLED",
            "tenant-owned data planes are disabled in this environment",
        )

    record = await get_data_plane_record(tenant_id, session)
    if record.mode != MODE_TENANT_OWNED:
        raise lc.LifecycleRejected(
            "DATA_PLANE_NOT_TENANT_OWNED",
            "an azure_postgresql_data_plane connection requires a tenant_owned data plane",
        )

    password_ref = (secret_references or {}).get("password_ref")
    if password_ref:
        existing = (
            await session.execute(
                text(
                    f"SELECT secret_references FROM {CONNECTIONS_TABLE} "
                    f"WHERE tenant_id = :tid AND provider = :provider "
                    f"AND status != '{lc.STATUS_RETIRED}'"
                ),
                {"tid": tenant_id, "provider": PROVIDER_AZURE_POSTGRESQL},
            )
        ).fetchall()
        for row in existing:
            if (row.secret_references or {}).get("password_ref") == password_ref:
                raise lc.LifecycleRejected(
                    "SECRET_REFERENCE_SHARED_ACROSS_PURPOSES",
                    "this secret reference is already used by the tenant's read-only "
                    "azure_postgresql connection",
                )


def _uses_env_scheme(secret_references: dict) -> bool:
    return any(
        isinstance(value, str) and value.startswith("env://")
        for value in (secret_references or {}).values()
    )


def _emit(action: str, tenant_id: str, connection_id, provider: str, outcome: str,
          reason: str = "none") -> None:
    logger.info(
        "data_source_lifecycle",
        extra={
            "action": action,
            "tenant_id": tenant_id,
            "connection_id": str(connection_id),
            "provider": provider,
            "outcome": outcome,
            "reason_code": reason,
        },
    )
    record_data_source_lifecycle(provider, action, outcome)


async def _fetch(session, tenant_id: str, connection_id: str):
    result = await session.execute(
        text(
            f"SELECT * FROM {CONNECTIONS_TABLE} "
            f"WHERE id = CAST(:cid AS UUID) AND tenant_id = :tid"
        ),
        {"cid": str(connection_id), "tid": tenant_id},
    )
    return result.fetchone()


async def get_connection(session, tenant_id: str, connection_id: str):
    """Tenant-qualified lookup. Absence — including another tenant's id — is None."""
    try:
        uuid.UUID(str(connection_id))
    except (ValueError, AttributeError, TypeError):
        return None
    return await _fetch(session, tenant_id, str(connection_id))


async def create_connection(
    session,
    tenant_id: str,
    provider: str,
    configuration: dict,
    secret_references: dict,
):
    """Create a `draft` connection. Closed-schema validation precedes the write."""
    validate_provider(provider)
    configuration = validate_configuration(provider, configuration)
    secret_references = validate_secret_references(provider, secret_references)

    if provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE:
        await _check_data_plane_draft_allowed(session, tenant_id, secret_references)

    connection_id = uuid.uuid4()
    now = _utcnow()
    await session.execute(
        text(
            f"INSERT INTO {CONNECTIONS_TABLE} "
            f"(id, tenant_id, provider, configuration, secret_references, status, "
            f"last_test_outcome, last_test_reason, activation_outcome, "
            f"activation_reason, activation_evidence, created_at, updated_at) "
            f"VALUES (CAST(:cid AS UUID), :tid, :provider, "
            f"CAST(:configuration AS JSONB), CAST(:secret_references AS JSONB), "
            f"'{lc.STATUS_DRAFT}', '{lc.TEST_OUTCOME_NOT_RUN}', '{lc.TEST_REASON_NONE}', "
            f"'{lc.ACTIVATION_OUTCOME_INACTIVE}', '{lc.ACTIVATION_REASON_NONE}', "
            f"'[]'::jsonb, :now, :now)"
        ),
        {
            "cid": str(connection_id),
            "tid": tenant_id,
            "provider": provider,
            "configuration": json.dumps(configuration),
            "secret_references": json.dumps(secret_references),
            "now": now,
        },
    )
    await session.commit()
    _emit("create", tenant_id, connection_id, provider, "success")
    return await _fetch(session, tenant_id, str(connection_id))


async def list_connections(
    session,
    tenant_id: str,
    *,
    q: str | None = None,
    provider: str | None = None,
    status: str | None = None,
    sort: str = "last_activity",
    order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list, int]:
    """Bounded allowlisted listing. Values parameterized; sort/order allowlisted."""
    if sort not in LIST_SORTS:
        raise ConnectionValidationError("sort", f"'{sort}' is not an allowed sort field")
    if order not in LIST_ORDERS:
        raise ConnectionValidationError("order", f"'{order}' is not an allowed sort order")
    if provider is not None:
        validate_provider(provider)
    if status is not None and status not in lc.STATUSES:
        raise ConnectionValidationError("status", f"'{status}' is not a connection status")
    if page < 1:
        raise ConnectionValidationError("page", "'page' must be >= 1")
    if not 1 <= page_size <= 100:
        raise ConnectionValidationError("page_size", "'page_size' must be 1-100")
    if q is not None and not 1 <= len(q) <= 100:
        raise ConnectionValidationError("q", "'q' must be 1-100 characters")

    clauses = ["tenant_id = :tid"]
    params: dict = {"tid": tenant_id}
    if provider is not None:
        clauses.append("provider = :provider")
        params["provider"] = provider
    if status is not None:
        clauses.append("status = :status")
        params["status"] = status
    if q is not None:
        # Server-generated identifier search: the connection id rendered as text.
        clauses.append("id::text ILIKE :q")
        params["q"] = f"%{q}%"
    where = " AND ".join(clauses)
    direction = "ASC" if order == "asc" else "DESC"

    total = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM {CONNECTIONS_TABLE} WHERE {where}"), params
        )
    ).scalar() or 0
    rows = (
        await session.execute(
            text(
                f"SELECT * FROM {CONNECTIONS_TABLE} WHERE {where} "
                f"ORDER BY {SORT_COLUMNS[sort]} {direction}, id ASC "
                f"LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": (page - 1) * page_size},
        )
    ).fetchall()
    return list(rows), int(total)


def _require(row, tenant_id: str):
    if row is None:
        raise lc.LifecycleRejected("CONNECTION_NOT_FOUND", "connection not found")
    return row


async def update_connection(
    session, tenant_id: str, connection_id: str, body: dict
):
    """Merge supplied fields over current values, revalidate, and return to draft.

    Omitted provider fields retain current values; `null` is invalid. Accepted
    from `draft`, `paused`, or `error` only; evidence is cleared.
    """
    row = _require(await get_connection(session, tenant_id, connection_id), tenant_id)
    if row.status not in lc.UPDATABLE_STATUSES:
        raise lc.LifecycleRejected(
            "INVALID_LIFECYCLE_TRANSITION",
            f"connection in '{row.status}' cannot be updated",
        )
    if not isinstance(body, dict):
        raise ConnectionValidationError(None, "request body must be a JSON object")
    unknown = set(body) - {"configuration", "secret_references"}
    if unknown:
        raise ConnectionValidationError(
            sorted(unknown)[0], f"'{sorted(unknown)[0]}' is not an updatable field"
        )
    if "configuration" not in body and "secret_references" not in body:
        raise ConnectionValidationError(
            None, "one of 'configuration' or 'secret_references' is required"
        )
    configuration = dict(row.configuration or {})
    secret_references = dict(row.secret_references or {})
    if "configuration" in body:
        patch = body["configuration"]
        if not isinstance(patch, dict):
            raise ConnectionValidationError(
                "configuration", "'configuration' must be an object"
            )
        if any(value is None for value in patch.values()):
            raise ConnectionValidationError(
                "configuration", "'configuration' fields must not be null"
            )
        configuration.update(patch)
    if "secret_references" in body:
        patch = body["secret_references"]
        if not isinstance(patch, dict):
            raise ConnectionValidationError(
                "secret_references", "'secret_references' must be an object"
            )
        if any(value is None for value in patch.values()):
            raise ConnectionValidationError(
                "secret_references", "'secret_references' fields must not be null"
            )
        secret_references.update(patch)

    configuration = validate_configuration(row.provider, configuration)
    secret_references = validate_secret_references(row.provider, secret_references)

    await session.execute(
        text(
            f"UPDATE {CONNECTIONS_TABLE} SET configuration = CAST(:configuration AS JSONB), "
            f"secret_references = CAST(:secret_references AS JSONB), "
            f"status = '{lc.STATUS_DRAFT}', "
            f"last_test_outcome = '{lc.TEST_OUTCOME_NOT_RUN}', "
            f"last_test_reason = '{lc.TEST_REASON_NONE}', last_test_at = NULL, "
            f"test_config_digest = NULL, "
            f"activation_outcome = '{lc.ACTIVATION_OUTCOME_INACTIVE}', "
            f"activation_reason = '{lc.ACTIVATION_REASON_NONE}', activated_at = NULL, "
            f"activation_evidence = '[]'::jsonb, updated_at = NOW() "
            f"WHERE id = CAST(:cid AS UUID) AND tenant_id = :tid"
        ),
        {
            "configuration": json.dumps(configuration),
            "secret_references": json.dumps(secret_references),
            "cid": str(row.id),
            "tid": tenant_id,
        },
    )
    await session.commit()
    _emit("update", tenant_id, row.id, row.provider, "success")
    return await _fetch(session, tenant_id, str(row.id))


async def test_connection(session, tenant_id: str, connection_id: str):
    """Run the secure test and record only the finite outcome.

    The endpoint itself completes normally in every finished case — a failed test
    is a `200 Connection` in `error`, not a request error — because the *test*
    ran. Only state violations raise.
    """
    row = _require(await get_connection(session, tenant_id, connection_id), tenant_id)
    if row.status not in lc.TESTABLE_STATUSES:
        raise lc.LifecycleRejected(
            "INVALID_LIFECYCLE_TRANSITION",
            f"connection in '{row.status}' cannot be tested",
        )
    provider = row.provider
    configuration = dict(row.configuration or {})
    secret_references = dict(row.secret_references or {})

    async def _record(outcome: str, reason: str, status: str) -> None:
        digest = (
            _canonical_body_digest(configuration, secret_references)
            if outcome == lc.TEST_OUTCOME_PASSED
            else None
        )
        await session.execute(
            text(
                f"UPDATE {CONNECTIONS_TABLE} SET status = :status, "
                f"last_test_outcome = :outcome, last_test_reason = :reason, "
                f"last_test_at = NOW(), test_config_digest = :digest, "
                f"updated_at = NOW() "
                f"WHERE id = CAST(:cid AS UUID) AND tenant_id = :tid"
            ),
            {
                "status": status,
                "outcome": outcome,
                "reason": reason,
                "digest": digest,
                "cid": str(row.id),
                "tid": tenant_id,
            },
        )
        await session.commit()
        record_data_source_test(provider, outcome, reason)

    try:
        validate_configuration(provider, configuration)
        validate_secret_references(provider, secret_references)
    except ConnectionValidationError:
        await _record(lc.TEST_OUTCOME_FAILED, lc.TEST_REASON_VALIDATION_FAILED, lc.STATUS_ERROR)
        _emit("test", tenant_id, row.id, provider, "error", lc.TEST_REASON_VALIDATION_FAILED)
        return await _fetch(session, tenant_id, str(row.id))

    try:
        secret_values = _secret_values(tenant_id, provider, secret_references)
    except SecretResolutionError:
        await _record(lc.TEST_OUTCOME_FAILED, lc.TEST_REASON_SECRET_UNAVAILABLE, lc.STATUS_ERROR)
        _emit("test", tenant_id, row.id, provider, "error", lc.TEST_REASON_SECRET_UNAVAILABLE)
        return await _fetch(session, tenant_id, str(row.id))

    expected_store_id = None
    if provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE:
        # A replacement or credential-rotation test must reach the *same* store the
        # tenant is already recorded against (tenant-residency-store-provisioning
        # spec's "Replacement connections must point at the same store") — a first
        # activation draft has no recorded store yet, so this is `None` then and the
        # tester falls back to "any recognized marker is fine".
        dp_row = (
            await session.execute(
                text("SELECT store_id FROM public.tenant_data_planes WHERE tenant_id = :tid"),
                {"tid": tenant_id},
            )
        ).fetchone()
        expected_store_id = str(dp_row.store_id) if dp_row and dp_row.store_id else None

    result = await run_secure_test(
        provider, configuration, secret_values, tenant_id=tenant_id, expected_store_id=expected_store_id
    )
    if result.passed:
        await _record(lc.TEST_OUTCOME_PASSED, lc.TEST_REASON_NONE, lc.STATUS_VALIDATED)
        _emit("test", tenant_id, row.id, provider, "success")
    else:
        await _record(lc.TEST_OUTCOME_FAILED, result.reason_code, lc.STATUS_ERROR)
        _emit("test", tenant_id, row.id, provider, "error", result.reason_code)
    return await _fetch(session, tenant_id, str(row.id))


async def _mark_activation_blocked(session, tenant_id: str, row, reason: str) -> None:
    await session.execute(
        text(
            f"UPDATE {CONNECTIONS_TABLE} SET activation_outcome = "
            f"'{lc.ACTIVATION_OUTCOME_BLOCKED}', activation_reason = :reason, "
            f"updated_at = NOW() WHERE id = CAST(:cid AS UUID) AND tenant_id = :tid"
        ),
        {"reason": reason, "cid": str(row.id), "tid": tenant_id},
    )
    await session.commit()


def _evidence_current(row, configuration: dict, secret_references: dict) -> bool:
    return (
        (row.last_test_outcome or "") == lc.TEST_OUTCOME_PASSED
        and (row.test_config_digest or "")
        == _canonical_body_digest(configuration, secret_references)
    )


async def activate_connection(
    session, tenant_id: str, connection_id: str, activation_evidence
):
    """Activate after the full prerequisite gate, enforcing the active limit.

    Permitted from `validated`, or from `paused` with still-current passed test
    evidence. Unmet prerequisites leave the connection inactive and expose only
    the finite blocking class.
    """
    row = _require(await get_connection(session, tenant_id, connection_id), tenant_id)
    provider = row.provider
    configuration = dict(row.configuration or {})
    secret_references = dict(row.secret_references or {})

    if row.status == lc.STATUS_ACTIVE:
        return row
    if row.status not in (lc.STATUS_VALIDATED, lc.STATUS_PAUSED):
        code = (
            "TEST_FAILED"
            if (row.last_test_outcome or "") == lc.TEST_OUTCOME_FAILED
            else "TEST_REQUIRED"
        )
        raise lc.LifecycleRejected(
            code, "activation requires a current passed connection test"
        )
    if row.status == lc.STATUS_PAUSED and not _evidence_current(
        row, configuration, secret_references
    ):
        raise lc.LifecycleRejected(
            "TEST_REQUIRED", "activation requires a current passed connection test"
        )
    if provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE:
        from src.shared.integration_profile.store import load_profile

        profile = await load_profile(session, tenant_id)
        if profile.retention_mode == "platform_blob":
            await _mark_activation_blocked(
                session, tenant_id, row, lc.ACTIVATION_REASON_RETENTION_MODE_NOT_PERMITTED
            )
            _emit("activate", tenant_id, row.id, provider, "rejected",
                  lc.ACTIVATION_REASON_RETENTION_MODE_NOT_PERMITTED)
            raise lc.LifecycleRejected(
                "RETENTION_MODE_NOT_PERMITTED",
                "activation is blocked while the tenant's retention mode is platform_blob",
            )
    if (
        not isinstance(activation_evidence, list)
        or sorted(activation_evidence) != sorted(lc.REQUIRED_ACTIVATION_EVIDENCE)
        or len(activation_evidence) != len(lc.REQUIRED_ACTIVATION_EVIDENCE)
    ):
        await _mark_activation_blocked(
            session, tenant_id, row, lc.ACTIVATION_REASON_PREREQUISITE_MISSING
        )
        _emit("activate", tenant_id, row.id, provider, "rejected",
              lc.ACTIVATION_REASON_PREREQUISITE_MISSING)
        raise lc.LifecycleRejected(
            "ACTIVATION_PREREQUISITE_MISSING",
            "activation requires network and governance approval evidence",
        )
    try:
        _secret_values(tenant_id, provider, secret_references)
    except SecretResolutionError:
        await _mark_activation_blocked(
            session, tenant_id, row, lc.ACTIVATION_REASON_SECRET_UNAVAILABLE
        )
        _emit("activate", tenant_id, row.id, provider, "rejected",
              lc.ACTIVATION_REASON_SECRET_UNAVAILABLE)
        raise lc.LifecycleRejected(
            "ACTIVATION_PREREQUISITE_MISSING",
            "activation requires a resolvable secret reference",
        )
    if _shared_environment() and _uses_env_scheme(secret_references):
        # `env://` resolves local-Compose `.env` only; shared environments require
        # Vault resolution before activation.
        await _mark_activation_blocked(
            session, tenant_id, row, lc.ACTIVATION_REASON_PREREQUISITE_MISSING
        )
        _emit("activate", tenant_id, row.id, provider, "rejected",
              lc.ACTIVATION_REASON_PREREQUISITE_MISSING)
        raise lc.LifecycleRejected(
            "ACTIVATION_PREREQUISITE_MISSING",
            "shared environments require Vault secret resolution for activation",
        )

    now = _utcnow()
    try:
        if row.replaces_connection_id is not None:
            # The same transaction retires the same-provider active predecessor,
            # then activates the successor. A non-active predecessor is left
            # exactly as it is. Both statements join the session's open
            # transaction and commit together below.
            await session.execute(
                text(
                    f"UPDATE {CONNECTIONS_TABLE} SET status = '{lc.STATUS_RETIRED}', "
                    f"activation_outcome = '{lc.ACTIVATION_OUTCOME_INACTIVE}', "
                    f"activation_reason = '{lc.ACTIVATION_REASON_NONE}', "
                    f"updated_at = NOW() "
                    f"WHERE id = CAST(:pred AS UUID) AND tenant_id = :tid "
                    f"AND provider = :provider AND status = '{lc.STATUS_ACTIVE}'"
                ),
                {
                    "pred": str(row.replaces_connection_id),
                    "tid": tenant_id,
                    "provider": provider,
                },
            )
        result = await session.execute(
            text(
                f"UPDATE {CONNECTIONS_TABLE} SET status = '{lc.STATUS_ACTIVE}', "
                f"activation_outcome = '{lc.ACTIVATION_OUTCOME_ACTIVE}', "
                f"activation_reason = '{lc.ACTIVATION_REASON_NONE}', "
                f"activated_at = :now, "
                f"activation_evidence = CAST(:evidence AS JSONB), updated_at = :now "
                f"WHERE id = CAST(:cid AS UUID) AND tenant_id = :tid "
                f"AND status IN ('{lc.STATUS_VALIDATED}', '{lc.STATUS_PAUSED}')"
            ),
            {
                "now": now,
                "evidence": json.dumps(sorted(activation_evidence)),
                "cid": str(row.id),
                "tid": tenant_id,
            },
        )
        if result.rowcount == 0:
            await session.rollback()
            raise lc.LifecycleRejected(
                "INVALID_LIFECYCLE_TRANSITION",
                f"connection in '{row.status}' cannot be activated",
            )
        await session.commit()
    except IntegrityError:
        # The partial unique index fired: another active connection of this
        # provider already exists for this tenant. The incumbent is unchanged.
        await session.rollback()
        await _mark_activation_blocked(
            session, tenant_id, row, lc.ACTIVATION_REASON_ACTIVE_PROVIDER_EXISTS
        )
        _emit("activate", tenant_id, row.id, provider, "rejected",
              lc.ACTIVATION_REASON_ACTIVE_PROVIDER_EXISTS)
        raise lc.LifecycleRejected(
            "ACTIVE_PROVIDER_EXISTS",
            f"tenant already has an active '{provider}' connection",
        )

    if provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE and row.replaces_connection_id is not None:
        # Replacement activation (tenant-residency-store-provisioning spec's
        # "Credential rotation keeps the tenant ready"): the successor's own
        # connection test already verified the store identity matches
        # (`data_plane_tester._target_schema_outcome`, task 10.3), so this is a
        # rebind, never a re-provisioning — `tenant_data_planes.connection_id` is
        # repointed at the successor and the resolver's engine cache is
        # invalidated so the next request builds an engine from the new
        # credentials. Status (`ready`) and `store_id`/`schema_revision` are left
        # untouched: the store itself did not change.
        await session.execute(
            text(
                "UPDATE public.tenant_data_planes SET connection_id = CAST(:cid AS UUID), "
                "updated_at = NOW() WHERE tenant_id = :tid"
            ),
            {"cid": str(row.id), "tid": tenant_id},
        )
        await session.commit()
        invalidate_data_plane_record(tenant_id)
        await _invalidate_tenant_engines(tenant_id)
    elif provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE and row.replaces_connection_id is None:
        if row.status == lc.STATUS_VALIDATED:
            # First activation: enqueue provisioning (Design D6). The task itself
            # (schema/baseline/role creation on the tenant's own store) is
            # `provision_tenant_data_plane`, task group 10.1.
            await mark_provisioning(session, tenant_id, str(row.id))
            await session.commit()
            try:
                from src.document_service.blob_sync.tasks import celery_app as _document_celery_app

                _document_celery_app.send_task(
                    "provision_tenant_data_plane", args=[tenant_id], queue="data_plane"
                )
            except Exception:
                logger.warning(
                    "data_plane_provisioning_enqueue_failed",
                    extra={"tenant_id": tenant_id},
                )
        elif row.status == lc.STATUS_PAUSED:
            # Re-activation of an already-provisioned store: straight to ready, no
            # re-provisioning (tenant-residency-store-provisioning spec's "Credential
            # rotation keeps the tenant ready"). Store identity is unchanged from
            # the connection just reactivated, not a fresh secret — the identity
            # check applies to a *replacement* draft's own connection test (Design
            # D3, task 10.3), which already ran before this connection reached
            # `validated`/`paused`.
            await mark_ready_from_paused(session, tenant_id)
            await session.commit()
        await _invalidate_tenant_engines(tenant_id)

    _emit("activate", tenant_id, row.id, provider, "success")
    return await _fetch(session, tenant_id, str(row.id))


async def pause_connection(session, tenant_id: str, connection_id: str):
    """Pause an active connection. Blob scheduling derives from status, so pausing
    disables it with no separate flag to drift."""
    row = _require(await get_connection(session, tenant_id, connection_id), tenant_id)
    if row.status != lc.STATUS_ACTIVE:
        raise lc.LifecycleRejected(
            "INVALID_LIFECYCLE_TRANSITION",
            f"connection in '{row.status}' cannot be paused",
        )
    await session.execute(
        text(
            f"UPDATE {CONNECTIONS_TABLE} SET status = '{lc.STATUS_PAUSED}', "
            f"activation_outcome = '{lc.ACTIVATION_OUTCOME_INACTIVE}', "
            f"activation_reason = '{lc.ACTIVATION_REASON_NONE}', updated_at = NOW() "
            f"WHERE id = CAST(:cid AS UUID) AND tenant_id = :tid"
        ),
        {"cid": str(row.id), "tid": tenant_id},
    )
    if row.provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE:
        await mark_paused(session, tenant_id)
    await session.commit()
    if row.provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE:
        await _invalidate_tenant_engines(tenant_id)
    _emit("pause", tenant_id, row.id, row.provider, "success")
    return await _fetch(session, tenant_id, str(row.id))


async def request_manual_sync(session, tenant_id: str, connection_id: str, enqueue) -> dict:
    """Enqueue a manual Blob synchronization, bypassing the scheduler cadence.

    Blob-provider and active-lifecycle gating happen here for a fast safe
    rejection; the worker re-checks both before executing, so a state race
    stays safe. `enqueue` is an injected `(tenant_id, connection_id, trigger)`
    callable so this layer stays free of broker configuration. Returns the
    safe trigger descriptor; raises `LifecycleRejected` with a finite code
    otherwise.
    """
    row = _require(await get_connection(session, tenant_id, connection_id), tenant_id)
    if row.provider != PROVIDER_AZURE_BLOB:
        _emit("sync", tenant_id, row.id, row.provider, "rejected", "unsupported_provider")
        raise lc.LifecycleRejected(
            "UNSUPPORTED_PROVIDER",
            "manual sync applies to Azure Blob connections only",
        )
    if row.status != lc.STATUS_ACTIVE:
        _emit("sync", tenant_id, row.id, row.provider, "rejected", "inactive_connection")
        raise lc.LifecycleRejected(
            "INACTIVE_CONNECTION",
            "manual sync requires an active connection",
        )
    try:
        # Literal mirrors `blob_sync.TRIGGER_MANUAL`; a literal keeps this
        # shared layer free of the worker import (same pattern as the
        # declared `BLOB_SYNC_TRIGGERS` set in domain_metrics).
        enqueue(tenant_id, str(row.id), "manual")
    except Exception as exc:
        logger.warning(
            "manual_sync_enqueue_failed",
            extra={"action": "sync", "error_type": type(exc).__name__},
        )
        _emit("sync", tenant_id, row.id, row.provider, "error", "broker_unavailable")
        raise lc.LifecycleRejected(
            "SYNC_UNAVAILABLE",
            "the sync queue is temporarily unavailable",
        )
    _emit("sync", tenant_id, row.id, row.provider, "success")
    return {
        "connection_id": str(row.id),
        "trigger": "manual",
        "outcome": "enqueued",
        "enqueued_at": _utcnow().isoformat(),
    }


async def latest_sync_outcomes(session, tenant_id: str, connection_ids) -> dict:
    """Latest completed Blob sync run per connection, as safe classes only.

    Reads the tenant's run ledger (CAP-3) in one query for any number of
    connections. A tenant whose sync tables were never created has no runs, so
    the table is looked up first rather than created on a read path. Runs still
    in progress (no `completed_at`) and outcomes outside the finite set are
    skipped. Returns `{connection_id: {"outcome", "completed_at"}}`; connections
    that never finished a run are absent.
    """
    ids = [str(cid) for cid in connection_ids]
    if not ids:
        return {}
    table = f"{schema_for_tenant(tenant_id)}.{SYNC_RUNS_TABLE}"
    exists = (
        await session.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": table})
    ).scalar()
    if not exists:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT DISTINCT ON (connection_id) connection_id, outcome, completed_at "
                f"FROM {table} "
                "WHERE connection_id = ANY(:ids) AND completed_at IS NOT NULL "
                "AND outcome = ANY(:outcomes) "
                "ORDER BY connection_id, started_at DESC"
            ),
            {"ids": ids, "outcomes": _REPORTED_SYNC_OUTCOMES},
        )
    ).fetchall()
    return {row[0]: {"outcome": row[1], "completed_at": row[2]} for row in rows}


async def replace_connection(
    session,
    tenant_id: str,
    connection_id: str,
    provider: str,
    configuration: dict,
    secret_references: dict,
):
    """Create a linked successor draft. The predecessor is unchanged until the
    successor activates, and a failed replacement leaves it unchanged."""
    row = _require(await get_connection(session, tenant_id, connection_id), tenant_id)
    if row.status == lc.STATUS_RETIRED:
        raise lc.LifecycleRejected(
            "RETIRED_CONNECTION", "a retired connection cannot be replaced"
        )
    validate_provider(provider)
    if provider != row.provider:
        raise ConnectionValidationError(
            "provider", "a replacement must use the predecessor's provider"
        )
    configuration = validate_configuration(provider, configuration)
    secret_references = validate_secret_references(provider, secret_references)

    successor_id = uuid.uuid4()
    now = _utcnow()
    await session.execute(
        text(
            f"INSERT INTO {CONNECTIONS_TABLE} "
            f"(id, tenant_id, provider, configuration, secret_references, status, "
            f"last_test_outcome, last_test_reason, activation_outcome, "
            f"activation_reason, activation_evidence, replaces_connection_id, "
            f"created_at, updated_at) "
            f"VALUES (CAST(:sid AS UUID), :tid, :provider, "
            f"CAST(:configuration AS JSONB), CAST(:secret_references AS JSONB), "
            f"'{lc.STATUS_DRAFT}', '{lc.TEST_OUTCOME_NOT_RUN}', '{lc.TEST_REASON_NONE}', "
            f"'{lc.ACTIVATION_OUTCOME_INACTIVE}', '{lc.ACTIVATION_REASON_NONE}', "
            f"'[]'::jsonb, CAST(:pred AS UUID), :now, :now)"
        ),
        {
            "sid": str(successor_id),
            "tid": tenant_id,
            "provider": provider,
            "configuration": json.dumps(configuration),
            "secret_references": json.dumps(secret_references),
            "pred": str(row.id),
            "now": now,
        },
    )
    await session.execute(
        text(
            f"UPDATE {CONNECTIONS_TABLE} SET replaced_by_connection_id = "
            f"CAST(:sid AS UUID), updated_at = NOW() "
            f"WHERE id = CAST(:pred AS UUID) AND tenant_id = :tid"
        ),
        {"sid": str(successor_id), "pred": str(row.id), "tid": tenant_id},
    )
    await session.commit()
    _emit("replace", tenant_id, successor_id, provider, "success")
    return await _fetch(session, tenant_id, str(successor_id))


async def retire_connection(session, tenant_id: str, connection_id: str, confirm) -> object:
    """Retire with explicit confirmation. Terminal; an active connection must be
    paused first, and safe history is preserved on the row."""
    row = _require(await get_connection(session, tenant_id, connection_id), tenant_id)
    if confirm is not True:
        raise lc.LifecycleRejected(
            "RETIRE_CONFIRMATION_REQUIRED",
            "retirement requires explicit confirmation",
        )
    if row.status == lc.STATUS_RETIRED:
        raise lc.LifecycleRejected(
            "RETIRED_CONNECTION", "connection is already retired"
        )
    if row.status not in lc.RETIRABLE_STATUSES:
        raise lc.LifecycleRejected(
            "RETIRED_CONNECTION",
            f"connection in '{row.status}' must be paused before retirement",
        )
    await session.execute(
        text(
            f"UPDATE {CONNECTIONS_TABLE} SET status = '{lc.STATUS_RETIRED}', "
            f"activation_outcome = '{lc.ACTIVATION_OUTCOME_INACTIVE}', "
            f"activation_reason = '{lc.ACTIVATION_REASON_NONE}', updated_at = NOW() "
            f"WHERE id = CAST(:cid AS UUID) AND tenant_id = :tid"
        ),
        {"cid": str(row.id), "tid": tenant_id},
    )
    if row.provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE:
        # No DDL/DML against the tenant store: this touches the control-plane row
        # only. Content remaining in the tenant store is the customer's to delete.
        await mark_retired(session, tenant_id)
    await session.commit()
    if row.provider == PROVIDER_AZURE_POSTGRESQL_DATA_PLANE:
        await _invalidate_tenant_engines(tenant_id)
    _emit("retire", tenant_id, row.id, row.provider, "success")
    return await _fetch(session, tenant_id, str(row.id))


# --- Idempotency ------------------------------------------------------------------------

async def check_replay(
    session, tenant_id: str, method: str, path: str, key: str, body_digest: str
) -> tuple[str, int, dict] | None:
    """Look up a live idempotency record.

    Returns `("replay", status, body)` for the same scope and body digest,
    `("reused", 0, {})` for the same key with a different body, or None when no
    live record exists. Expired records are removed on read.
    """
    result = await session.execute(
        text(
            f"SELECT body_digest, response_status, response_body, created_at "
            f"FROM {IDEMPOTENCY_TABLE} "
            f"WHERE tenant_id = :tid AND method = :method AND path = :path "
            f"AND idempotency_key = :key"
        ),
        {"tid": tenant_id, "method": method, "path": path, "key": key},
    )
    found = result.fetchone()
    if found is None:
        return None
    age_hours = (_utcnow() - found.created_at).total_seconds() / 3600.0
    if age_hours >= IDEMPOTENCY_TTL_HOURS:
        await session.execute(
            text(
                f"DELETE FROM {IDEMPOTENCY_TABLE} "
                f"WHERE tenant_id = :tid AND method = :method AND path = :path "
                f"AND idempotency_key = :key"
            ),
            {"tid": tenant_id, "method": method, "path": path, "key": key},
        )
        await session.commit()
        return None
    if found.body_digest != body_digest:
        return ("reused", 0, {})
    return ("replay", int(found.response_status), dict(found.response_body))


async def store_replay(
    session,
    tenant_id: str,
    method: str,
    path: str,
    key: str,
    body_digest: str,
    response_status: int,
    response_body: dict,
) -> None:
    """Persist the digest and the replayable *safe* response. Never secret values:
    the response body is the safe `Connection` shape by construction."""
    await session.execute(
        text(
            f"INSERT INTO {IDEMPOTENCY_TABLE} "
            f"(tenant_id, method, path, idempotency_key, body_digest, "
            f"response_status, response_body) "
            f"VALUES (:tid, :method, :path, :key, :digest, :status, "
            f"CAST(:body AS JSONB)) "
            f"ON CONFLICT (tenant_id, method, path, idempotency_key) DO NOTHING"
        ),
        {
            "tid": tenant_id,
            "method": method,
            "path": path,
            "key": key,
            "digest": body_digest,
            "status": response_status,
            "body": json.dumps(response_body),
        },
    )
    await session.commit()
