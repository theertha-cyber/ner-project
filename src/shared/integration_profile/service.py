"""Developer-managed operations on a tenant's integration profile.

Nothing here is reachable from a tenant-facing API. Profiles are platform configuration:
a tenant admin cannot create, edit, activate, or retire one.
"""

import json

from sqlalchemy import text

from src.document_service.ingestion.contract import assert_source_id_available
from src.shared.document_retention import RETENTION_MODES
from src.shared.integration_profile.adapters import (
    SUPPORTED_ADAPTERS,
    unsupported_selections,
)
from src.shared.integration_profile.config_schema import (
    ProfileValidationError,
    validate_configuration,
    validate_secret_references,
)
from src.shared.integration_profile.secrets import (
    SecretResolutionError,
    resolve_for_tenant,
    sanitised_reason,
)
from src.shared.integration_profile.status import (
    STATUS_ACTIVE,
    STATUS_ERROR,
    STATUS_VALIDATED,
    TransitionRejected,
    assert_transition,
)
from src.shared.integration_profile.store import PROFILE_TABLE, load_profile

SELECTION_COLUMNS = (
    "source_adapter",
    "content_store_adapter",
    "relational_adapter",
    "index_adapter",
)


class ProfileNotFound(Exception):
    def __init__(self, tenant_id: str):
        super().__init__(f"no integration profile recorded for tenant {tenant_id}")


async def write_profile(
    session,
    tenant_id: str,
    *,
    selections: dict | None = None,
    retention_mode: str | None = None,
    configuration: dict | None = None,
    secret_references: dict | None = None,
) -> None:
    """Record a profile. Validation is by declared schema, never by value inspection.

    A non-default adapter selection is *recordable* — the profile is where the target
    architecture is written down. Whether it can be activated is a separate question,
    answered by `validate_profile` and `activate_profile`.
    """
    selections = dict(selections or {})
    for slot, value in selections.items():
        if slot not in SUPPORTED_ADAPTERS:
            raise ProfileValidationError(f"unknown adapter slot '{slot}'")
        if value not in SUPPORTED_ADAPTERS[slot]:
            raise ProfileValidationError(
                f"'{value}' is not a declared adapter for '{slot}'"
            )

    if retention_mode is not None and retention_mode not in RETENTION_MODES:
        raise ProfileValidationError(f"'{retention_mode}' is not a declared retention mode")

    # Configuration and secret references are validated per adapter kind against a closed
    # key set, so an unknown key or a literal in a secret field is refused before the row
    # is written — not stored and discovered later.
    configuration = configuration or {}
    secret_references = secret_references or {}
    for adapter_kind, values in configuration.items():
        validate_configuration(adapter_kind, values)
    for adapter_kind, values in secret_references.items():
        validate_secret_references(adapter_kind, values)

    source_adapter = selections.get("source_adapter")
    if source_adapter is not None:
        # A configured source may not claim the identifier platform upload reserves.
        assert_source_id_available(source_adapter)

    assignments = ["updated_at = NOW()"]
    params: dict = {"tid": tenant_id}
    for slot in SELECTION_COLUMNS:
        if slot in selections:
            assignments.append(f"{slot} = :{slot}")
            params[slot] = selections[slot]
    if retention_mode is not None:
        assignments.append("retention_mode = :retention_mode")
        params["retention_mode"] = retention_mode
    if configuration:
        assignments.append("configuration = CAST(:configuration AS JSONB)")
        params["configuration"] = json.dumps(configuration)
    if secret_references:
        assignments.append("secret_references = CAST(:secret_references AS JSONB)")
        params["secret_references"] = json.dumps(secret_references)

    result = await session.execute(
        text(
            f"UPDATE {PROFILE_TABLE} SET {', '.join(assignments)} WHERE tenant_id = :tid"
        ),
        params,
    )
    if result.rowcount == 0:
        columns = ["tenant_id"] + [k for k in params if k != "tid"]
        placeholders = [":tid"] + [
            f"CAST(:{k} AS JSONB)" if k in ("configuration", "secret_references") else f":{k}"
            for k in params
            if k != "tid"
        ]
        await session.execute(
            text(
                f"INSERT INTO {PROFILE_TABLE} ({', '.join(columns)}) "
                f"VALUES ({', '.join(placeholders)})"
            ),
            params,
        )
    await session.commit()


async def _set_status(session, tenant_id: str, status: str, reason: str | None) -> None:
    await session.execute(
        text(
            f"UPDATE {PROFILE_TABLE} SET status = :status, status_reason = :reason, "
            f"updated_at = NOW() WHERE tenant_id = :tid"
        ),
        {"status": status, "reason": reason, "tid": tenant_id},
    )
    await session.commit()


async def validate_profile(session, tenant_id: str) -> None:
    """Move a profile to `validated` once its selections and references check out.

    Every recorded secret reference is resolved here, because that is what a readiness
    check means. A reference that will not resolve moves the profile to `error` with a
    sanitised reason rather than failing the request path of an unrelated tenant.
    """
    profile = await load_profile(session, tenant_id)
    assert_transition(profile.status, STATUS_VALIDATED)

    if profile.secret_references:
        try:
            resolve_for_tenant(profile)
        except SecretResolutionError as exc:
            await _set_status(session, tenant_id, STATUS_ERROR, sanitised_reason(exc))
            raise

    await _set_status(session, tenant_id, STATUS_VALIDATED, None)


async def activate_profile(session, tenant_id: str) -> None:
    """Activate a validated profile, unless it selects something not yet executable."""
    profile = await load_profile(session, tenant_id)
    assert_transition(profile.status, STATUS_ACTIVE)

    unsupported = unsupported_selections(profile.selections())
    if unsupported:
        named = ", ".join(f"{slot}={profile.selections()[slot]}" for slot in unsupported)
        raise TransitionRejected(
            profile.status,
            STATUS_ACTIVE,
            f"selection recorded but not yet supported: {named}",
        )

    await _set_status(session, tenant_id, STATUS_ACTIVE, None)


async def transition_profile(
    session, tenant_id: str, requested: str, reason: str | None = None
) -> None:
    """Any other permitted move, including `→ retired` and pause/resume."""
    profile = await load_profile(session, tenant_id)
    assert_transition(profile.status, requested)
    await _set_status(session, tenant_id, requested, reason)


async def record_resolution_failure(
    session, tenant_id: str, error: SecretResolutionError
) -> None:
    """An unresolvable reference errors one tenant's profile, never the process."""
    profile = await load_profile(session, tenant_id)
    assert_transition(profile.status, STATUS_ERROR)
    await _set_status(session, tenant_id, STATUS_ERROR, sanitised_reason(error))
