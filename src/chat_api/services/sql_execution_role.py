"""Least-privilege role for generated-SQL execution.

`validate_sql` decides which tables a generated statement may name. This module
decides which tables the database will let it read at all, so the two controls fail
independently: a gap in table-reference resolution degrades into a permission error —
recorded as a structured retrieval failure — instead of a cross-tenant disclosure.

The grant list is derived from `WHITELISTED_TABLES` rather than restated, so a table
added to the whitelist cannot be forgotten here, and a table removed from it loses its
grant at the next provisioning run.

The tenant's generated entity tables are added on top, resolved per schema from
`entity_definitions` by `resolve_generated_tables` — the *same* resolver that feeds
`validate_sql`'s whitelist. A table granted but not whitelisted is a query the
validator rejects for a table the role can read; whitelisted but not granted is a
query the validator accepts and the database refuses. Neither is visible in review, so
the two sets come from one call rather than being kept in step by discipline. An
inactive definition is excluded from both even though its table is retained — that
exclusion is what deactivation means for the query surface.

The role is `NOLOGIN`: nothing connects as it. The application's connection role is
granted membership and assumes it per statement via `SET LOCAL ROLE`, inside the
read-only transaction, so the privilege boundary and the transaction boundary are the
same boundary.
"""

import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.chat_api.services.sql_generator import WHITELISTED_TABLES
from src.shared.entity_views import resolve_generated_tables
from src.shared.data_plane import MODE_PLATFORM

logger = logging.getLogger(__name__)

# Role and schema names are interpolated into DDL, so they are checked against the
# identifier grammar first. Both come from server configuration or from pg_namespace,
# never from a request — this is a guard against a typo becoming a syntax injection,
# not a substitute for that.
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9$]*")

TENANT_SCHEMA_PREFIX = "tenant_"

# `pg_tables` rather than `information_schema.tables`: it matches physical tables only, which is
# exactly what the generated layer creates, and it is the catalog the grant guard already
# consults. The smoke check reads from it so the two agree on what exists.
_EXISTING_TABLES_QUERY = "SELECT tablename FROM pg_tables WHERE schemaname = :schema"


class InvalidIdentifierError(ValueError):
    pass


def _checked_identifier(value: str, kind: str) -> str:
    if not value or not _IDENTIFIER_RE.fullmatch(value):
        raise InvalidIdentifierError(f"{kind} '{value}' is not a bare SQL identifier")
    return value


def build_role_statements(
    role_name: str,
    schemas: list[str],
    generated_tables: dict[str, set[str]] | None = None,
) -> list[str]:
    """The full, idempotent provisioning script for the execution role.

    Returned rather than executed so it can be inspected, diffed, and asserted on
    without a database. Every statement is safe to re-run.

    `generated_tables` maps a schema to the entity tables that schema's active `multi`
    definitions own, as returned by `resolve_generated_tables`. Omitting it grants the static
    whitelist only, which is what a caller with no session can assert on. An active `single`
    definition contributes no name: its values are a column on `subject`, and any child table
    it retains from an earlier `multi` life is deliberately left ungranted."""
    role = _checked_identifier(role_name, "role")
    statements = [
        # NOLOGIN: the role is only ever assumed, never connected as.
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                CREATE ROLE {role} NOLOGIN NOINHERIT;
            END IF;
        END
        $$
        """.strip(),
        # The connection role must be a member to assume it.
        f"GRANT {role} TO CURRENT_USER",
        # Stated explicitly rather than relied upon: a role holds no table privilege in
        # `public` by default, and this keeps that true if a later change grants one
        # broadly. `public` holds tenants, tenant_users, widget_api_keys,
        # entity_definitions, and audit_events.
        f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}",
        f"REVOKE ALL ON SCHEMA public FROM {role}",
    ]

    for schema in schemas:
        schema_ident = _checked_identifier(schema, "schema")
        statements.append(f"GRANT USAGE ON SCHEMA {schema_ident} TO {role}")
        # Revoke first, then re-grant the current surface. Without this the grants are
        # append-only, and a generated table that leaves the surface -- its definition
        # deactivated, or its cardinality moved to `single` so its values live on `subject`
        # instead -- keeps the SELECT it was granted while it was on it. `validate_sql` would
        # still reject the query, but the grant and the whitelist are supposed to resolve from
        # one set, and a privilege outliving its reason is invisible to the next reader.
        # Idempotent, and atomic with the re-grant: `provision_role` runs the whole script in
        # the caller's transaction. Scoped to this role, so no other grantee is affected.
        statements.append(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema_ident} FROM {role}")
        schema_tables = set(WHITELISTED_TABLES) | set(
            (generated_tables or {}).get(schema_ident, set())
        )
        # SELECT only. The role never writes: the projection is written by the extraction
        # worker under the application's own role, inside its own transaction.
        for table in sorted(schema_tables):
            table_ident = _checked_identifier(table, "table")
            # `IF EXISTS` has no GRANT form; a schema provisioned from an older
            # template may legitimately lack a table, and that must not abort the run.
            statements.append(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_tables
                        WHERE schemaname = '{schema_ident}' AND tablename = '{table_ident}'
                    ) THEN
                        GRANT SELECT ON {schema_ident}.{table_ident} TO {role};
                    END IF;
                END
                $$
                """.strip()
            )

    return statements


async def list_tenant_schemas(session: AsyncSession) -> list[str]:
    """Platform tenant schemas only — the shape existing callers (tests passing an
    explicit schema list bypass this entirely) and `provision_role`'s fallback when
    `schemas` is omitted assume: one session, one database. `provision_role` itself
    additionally reaches `ready` `tenant_owned` tenants on their own stores; this
    helper is kept for the platform-only enumeration it already documented."""
    result = await session.execute(
        text(
            "SELECT t.id FROM public.tenants t "
            "JOIN public.tenant_data_planes dp ON dp.tenant_id = t.id "
            "WHERE dp.mode = :mode"
        ),
        {"mode": MODE_PLATFORM},
    )
    return [f"{TENANT_SCHEMA_PREFIX}{row[0].replace('-', '_')}" for row in result.fetchall()]


async def _list_active_tenants(session: AsyncSession) -> list[tuple[str, str, str]]:
    """`(tenant_id, mode, status)` for every active tenant (ADR-017 routing spec:
    "Fleet operations enumerate tenants from the control plane" — not `pg_namespace`,
    which cannot see a `tenant_owned` tenant's store at all)."""
    result = await session.execute(
        text(
            "SELECT t.id, dp.mode, dp.status FROM public.tenants t "
            "JOIN public.tenant_data_planes dp ON dp.tenant_id = t.id "
            "WHERE t.status = 'active'"
        )
    )
    return [(row[0], row[1], row[2]) for row in result.fetchall()]


async def provision_role(
    session: AsyncSession, role_name: str, schemas: list[str] | None = None
) -> list[str]:
    """Creates the role if absent and (re)applies its grants, one tenant at a time so a
    single tenant's failure (a schema mid-migration, a lock, an unreachable store) does
    not abort provisioning for every other tenant (ADR-017 routing spec: fleet
    operations "SHALL NOT abort the operation for other tenants").

    When `schemas` is omitted, every active tenant is reached: a `platform` tenant on
    `session` (the platform database — where its schema lives), a `ready` `tenant_owned`
    tenant on its own resolved store, and any other `tenant_owned` status skipped (there
    is no store to provision yet). Returns the schemas actually provisioned."""
    if schemas is not None:
        covered: list[str] = []
        for schema in schemas:
            try:
                generated = await resolve_generated_tables(session, [schema])
                for statement in build_role_statements(role_name, [schema], generated):
                    await session.execute(text(statement))
                covered.append(schema)
            except Exception:
                logger.exception("sql_execution_role provisioning failed for schema=%s", schema)
                await session.rollback()
        logger.info(
            "sql_execution_role provisioned role=%s schemas=%d/%d",
            role_name, len(covered), len(schemas),
        )
        return covered

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.shared.data_plane import DataPlaneNotReady, DataPlaneUnavailable, STATUS_READY
    from src.shared.database import get_resolver

    covered = []
    tenants = await _list_active_tenants(session)
    for tenant_id, mode, status in tenants:
        schema = f"{TENANT_SCHEMA_PREFIX}{tenant_id.replace('-', '_')}"
        if mode == MODE_PLATFORM:
            target_session = session
            owns_session = False
        elif status == STATUS_READY:
            try:
                engine = await get_resolver().resolve(tenant_id)
            except (DataPlaneNotReady, DataPlaneUnavailable) as exc:
                reason = getattr(exc, "reason_class", None) or getattr(exc, "status_class", "unavailable")
                logger.info(
                    "sql_execution_role provisioning skipped tenant=%s reason=%s", tenant_id, reason
                )
                continue
            target_session = async_sessionmaker(engine, expire_on_commit=False)()
            owns_session = True
        else:
            # Not ready yet (awaiting_store, provisioning, ...): nothing to grant on.
            continue

        try:
            # Control-plane read, always on the platform session (Design D10):
            # `entity_definitions` never exists on a tenant_owned store.
            generated = await resolve_generated_tables(session, [schema])
            for statement in build_role_statements(role_name, [schema], generated):
                await target_session.execute(text(statement))
            if owns_session:
                await target_session.commit()
            covered.append(schema)
        except (DataPlaneNotReady, DataPlaneUnavailable) as exc:
            reason = getattr(exc, "reason_class", None) or getattr(exc, "status_class", "unavailable")
            logger.info(
                "sql_execution_role provisioning skipped tenant=%s reason=%s", tenant_id, reason
            )
        except Exception:
            logger.exception("sql_execution_role provisioning failed for tenant=%s", tenant_id)
            await target_session.rollback()
        finally:
            if owns_session:
                await target_session.close()

    logger.info(
        "sql_execution_role provisioned role=%s schemas=%d/%d",
        role_name, len(covered), len(tenants),
    )
    return covered


class SmokeCheckFailed(RuntimeError):
    """A relation on the query surface the role could not read, named."""


async def smoke_check_schema(
    session: AsyncSession,
    role_name: str,
    schema: str,
    generated_tables: set[str] | None = None,
) -> None:
    """Reads one row from every relation on `schema`'s query surface under the restricted role.

    Every relation, not only the static whitelist: the generator now names the tenant's
    generated relations, so a generated relation the role cannot read is exactly as fatal as a
    static one it cannot read, and just as invisible until a user asks a question.

    `generated_tables` comes from `resolve_generated_tables` and is passed in rather than
    resolved here: the read runs under the restricted role, which holds no privilege on
    `public.entity_definitions`, so resolving inside the transaction would fail on the resolver
    rather than on the grant it is checking. Omitting it checks the static tables only.

    Only relations that actually exist are read, resolved from `pg_tables` under the connecting
    role before the transaction opens — the same catalog, and the same reasoning, as the
    `IF EXISTS` guard on each grant. A catalogued relation the reconciler has not created yet is
    not a provisioning failure: there is no grant to be missing, and failing on it would report
    an absent table as a permission problem and hide any real one behind it.

    Run before the toggle is enabled in any environment: a missing grant surfaces here as a
    permission error on a throwaway read, rather than in production as a structured retrieval
    failure on a user's question."""
    role = _checked_identifier(role_name, "role")
    schema_ident = _checked_identifier(schema, "schema")
    wanted = sorted(set(WHITELISTED_TABLES) | set(generated_tables or set()))

    result = await session.execute(text(_EXISTING_TABLES_QUERY), {"schema": schema_ident})
    existing = {row[0] for row in result.fetchall()}
    relations = [table for table in wanted if table in existing]
    skipped = [table for table in wanted if table not in existing]
    if skipped:
        logger.info(
            "sql_execution_role smoke_check schema=%s skipped_absent=%s",
            schema_ident, ",".join(skipped),
        )

    await session.execute(text("BEGIN READ ONLY"))
    try:
        await session.execute(text(f"SET LOCAL ROLE {role}"))
        for table in relations:
            table_ident = _checked_identifier(table, "table")
            try:
                await session.execute(
                    text(f"SELECT 1 FROM {schema_ident}.{table_ident} LIMIT 1")
                )
            except Exception as exc:
                # Named rather than propagated bare: the operator reading this has to know
                # which grant to fix, and a driver's message for a missing relation and for a
                # missing privilege do not read alike.
                raise SmokeCheckFailed(
                    f"{schema_ident}.{table_ident}: {type(exc).__name__}: {exc}"
                ) from exc
    finally:
        await session.execute(text("ROLLBACK"))
