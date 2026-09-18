"""Control-plane persistence names and the safe response shape (CAP-2).

The `Connection` response carries field *names*, finite outcome classes, linkage,
and timestamps. Configuration values, secret-reference values, endpoints,
connection strings, provider diagnostics, tenant content, SQL, prompts, and
answers are never read back out of these tables — there is deliberately no code
path that selects them into a response.
"""

from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.providers import (
    PROVIDER_AZURE_BLOB,
    PROVIDER_AZURE_POSTGRESQL,
)

CONNECTIONS_TABLE = "public.tenant_data_source_connections"
IDEMPOTENCY_TABLE = "public.tenant_data_source_idempotency"

# Idempotency replay window, hours.
IDEMPOTENCY_TTL_HOURS = 24


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def to_connection_dict(row, last_sync: dict | None = None) -> dict:
    """Render one connection row as the safe `Connection` response shape.

    `last_sync` is the latest completed run for a Blob connection
    (`service.latest_sync_outcomes`); without one the connection has never run.
    """
    provider = row.provider
    configuration = row.configuration or {}
    secret_references = row.secret_references or {}
    status = row.status

    if provider == PROVIDER_AZURE_POSTGRESQL:
        schedule = {"enabled": False, "cadence_minutes": None}
        extras: dict = {}
    else:
        schedule = {
            "enabled": status == lc.STATUS_ACTIVE,
            "cadence_minutes": lc.SYNC_CADENCE_MINUTES if status == lc.STATUS_ACTIVE else None,
        }
        extras = {
            "last_sync": {
                "outcome": last_sync["outcome"] if last_sync else lc.SYNC_OUTCOME_NEVER_RUN,
                "completed_at": _iso(last_sync["completed_at"]) if last_sync else None,
            }
        }

    body = {
        "id": str(row.id),
        "provider": provider,
        "status": status,
        # Names only. Values never leave the write path.
        "configured_fields": sorted(configuration.keys()),
        "secret_reference_fields": sorted(secret_references.keys()),
        "last_test": {
            "outcome": row.last_test_outcome or lc.TEST_OUTCOME_NOT_RUN,
            "reason_code": row.last_test_reason or lc.TEST_REASON_NONE,
            "tested_at": _iso(row.last_test_at),
        },
        "activation": {
            "outcome": row.activation_outcome or lc.ACTIVATION_OUTCOME_INACTIVE,
            "reason_code": row.activation_reason or lc.ACTIVATION_REASON_NONE,
            "activated_at": _iso(row.activated_at),
        },
        "schedule": schedule,
        "replaces_connection_id": (
            str(row.replaces_connection_id) if row.replaces_connection_id else None
        ),
        "replaced_by_connection_id": (
            str(row.replaced_by_connection_id) if row.replaced_by_connection_id else None
        ),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }
    body.update(extras)
    return body
