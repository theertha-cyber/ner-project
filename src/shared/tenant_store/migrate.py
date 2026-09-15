"""Deploy-time tenant-store migration step (ADR-017, Design D5, D6, D11 — task group 10.4).

Run after `alembic upgrade head` (see the `db-init` service in `docker-compose.yml`).
For every `tenant_owned` tenant whose data plane is `ready` or `migration_required`,
connects to that tenant's active `azure_postgresql_data_plane` store and applies
pending tenant-store revisions. A store that is unreachable, or ends up below
`MIN_SUPPORTED_TENANT_STORE_REVISION`, is left/set `migration_required` with a safe
reason class — content routes fail closed for it — while every other store and the
platform startup itself proceed unaffected.

This module never raises out of `main()`: a per-tenant failure is caught, classified,
and recorded, never allowed to abort the run for other tenants or fail the deploy.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine, text

from src.shared.config import settings
from src.shared.data_plane import DATA_PLANE_SECRET_KIND
from src.shared.integration_profile.secrets import (
    SecretResolutionError,
    TenantSecretContext,
    resolve_for_tenant,
)
from src.shared.tenant_store import apply as apply_module
from src.shared.tenant_store.revisions import MIN_SUPPORTED_TENANT_STORE_REVISION, pending_revisions

logger = logging.getLogger(__name__)

READY = "ready"
MIGRATION_REQUIRED = "migration_required"


@dataclass(frozen=True)
class _ProfileShim:
    """The minimal shape `resolve_for_tenant` needs — a tenant id and a
    `{adapter_kind: {field: reference}}` map — built from a connection row rather than
    an integration profile, since this runs before the tenant's `search_path` is set."""

    tenant_id: str
    secret_references: dict


def _connection_url(configuration: dict, secrets: TenantSecretContext) -> str:
    password = secrets.get("password_ref") or secrets.get("password")
    return (
        f"postgresql://{configuration['username']}:{password}@"
        f"{configuration['host']}:{configuration['port']}/{configuration['database']}"
        f"?sslmode={configuration.get('sslmode', 'verify-full')}"
    )


def _migrate_one(platform_conn, tenant_id: str, connection_row) -> tuple[str, int | None]:
    """Returns `(outcome, revision)` — a safe outcome class (`up_to_date`,
    `migrated`, or a failure reason) and the store's resulting `schema_revision`,
    or `None` on a failure where no revision could be determined."""
    configuration = connection_row.configuration or {}
    secret_references = connection_row.secret_references or {}
    schema = f"tenant_{tenant_id.replace('-', '_')}"

    try:
        secrets = resolve_for_tenant(
            _ProfileShim(tenant_id=tenant_id, secret_references={DATA_PLANE_SECRET_KIND: secret_references}),
            DATA_PLANE_SECRET_KIND,
        )
    except SecretResolutionError:
        return "secret_unresolvable", None

    try:
        store_engine = create_engine(
            _connection_url(configuration, secrets),
            connect_args={"connect_timeout": int(settings.data_plane_connect_timeout_seconds)},
        )
        with store_engine.connect() as store_conn:
            # `Connection` autobegins a transaction on first `execute()` (SQLAlchemy
            # 2.0) — `read_store_identity` above already issued one, so an explicit
            # `with store_conn.begin():` here would raise `InvalidRequestError`
            # ("already initialized a SQLAlchemy Transaction()"). Commit explicitly
            # instead of nesting a second `begin()`.
            identity = apply_module.read_store_identity(store_conn, schema)
            current_revision = identity[1] if identity else 0
            pending = pending_revisions(current_revision)
            if not pending and current_revision >= MIN_SUPPORTED_TENANT_STORE_REVISION:
                return "up_to_date", current_revision
            _, new_revision = apply_module.apply(store_conn, schema, tenant_id)
            store_conn.commit()
        store_engine.dispose()
    except Exception:
        logger.warning("tenant-store migration failed", extra={"tenant_id": tenant_id}, exc_info=True)
        return "unreachable", None

    if new_revision < MIN_SUPPORTED_TENANT_STORE_REVISION:
        return "below_minimum_revision", new_revision
    return "migrated", new_revision


def main() -> int:
    """Returns 0 always — see module docstring. Prints one safe outcome line per tenant."""
    platform_engine = create_engine(settings.database_url_sync)
    exit_code = 0
    try:
        with platform_engine.connect() as platform_conn:
            tenants = platform_conn.execute(
                text(
                    """
                    SELECT dp.tenant_id, c.configuration, c.secret_references
                    FROM public.tenant_data_planes dp
                    JOIN public.tenant_data_source_connections c
                        ON c.id = dp.connection_id AND c.status = 'active'
                    WHERE dp.mode = 'tenant_owned'
                      AND dp.status IN (:ready, :migration_required)
                    """
                ),
                {"ready": READY, "migration_required": MIGRATION_REQUIRED},
            ).fetchall()

            for row in tenants:
                outcome, revision = _migrate_one(platform_conn, row.tenant_id, row)
                print(f"tenant_id={row.tenant_id} outcome={outcome}")
                new_status = READY if outcome in ("up_to_date", "migrated") else MIGRATION_REQUIRED
                set_clause = "status = :status, status_reason = :reason"
                params = {"status": new_status, "reason": outcome, "tid": row.tenant_id}
                if revision is not None:
                    set_clause += ", schema_revision = :revision"
                    params["revision"] = revision
                platform_conn.execute(
                    text(
                        f"UPDATE public.tenant_data_planes SET {set_clause} "
                        "WHERE tenant_id = :tid"
                    ),
                    params,
                )
                platform_conn.commit()
    except Exception:
        logger.error("tenant-store migration step failed to run", exc_info=True)
        exit_code = 0  # never block platform startup (Design D5/Risk: "Many residency tenants")
    finally:
        platform_engine.dispose()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
