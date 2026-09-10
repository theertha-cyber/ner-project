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
from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.providers import (
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

logger = logging.getLogger(__name__)

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

    result = await run_secure_test(provider, configuration, secret_values)
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
    await session.commit()
    _emit("pause", tenant_id, row.id, row.provider, "success")
    return await _fetch(session, tenant_id, str(row.id))


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
    await session.commit()
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
