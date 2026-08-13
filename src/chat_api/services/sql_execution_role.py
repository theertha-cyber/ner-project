"""Least-privilege role for generated-SQL execution.

`validate_sql` decides which tables a generated statement may name. This module
decides which tables the database will let it read at all, so the two controls fail
independently: a gap in table-reference resolution degrades into a permission error —
recorded as a structured retrieval failure — instead of a cross-tenant disclosure.

The grant list is derived from `WHITELISTED_TABLES` rather than restated, so a table
added to the whitelist cannot be forgotten here, and a table removed from it loses its
grant at the next provisioning run.

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

logger = logging.getLogger(__name__)

# Role and schema names are interpolated into DDL, so they are checked against the
# identifier grammar first. Both come from server configuration or from pg_namespace,
# never from a request — this is a guard against a typo becoming a syntax injection,
# not a substitute for that.
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9$]*")

TENANT_SCHEMA_PREFIX = "tenant_"


class InvalidIdentifierError(ValueError):
    pass


def _checked_identifier(value: str, kind: str) -> str:
    if not value or not _IDENTIFIER_RE.fullmatch(value):
        raise InvalidIdentifierError(f"{kind} '{value}' is not a bare SQL identifier")
    return value


def build_role_statements(role_name: str, schemas: list[str]) -> list[str]:
    """The full, idempotent provisioning script for the execution role.

    Returned rather than executed so it can be inspected, diffed, and asserted on
    without a database. Every statement is safe to re-run."""
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
        for table in sorted(WHITELISTED_TABLES):
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
    result = await session.execute(
        text(
            "SELECT nspname FROM pg_namespace WHERE nspname LIKE :prefix ORDER BY nspname"
        ),
        {"prefix": f"{TENANT_SCHEMA_PREFIX}%"},
    )
    return [row[0] for row in result.fetchall()]


async def provision_role(
    session: AsyncSession, role_name: str, schemas: list[str] | None = None
) -> list[str]:
    """Creates the role if absent and (re)applies its grants. Returns the schemas
    covered. Idempotent: safe to run on every deploy and after any tenant is added."""
    target_schemas = schemas if schemas is not None else await list_tenant_schemas(session)
    for statement in build_role_statements(role_name, target_schemas):
        await session.execute(text(statement))
    logger.info(
        "sql_execution_role provisioned role=%s schemas=%d", role_name, len(target_schemas)
    )
    return target_schemas


async def smoke_check_schema(session: AsyncSession, role_name: str, schema: str) -> None:
    """Reads one row from each whitelisted table in `schema` under the restricted role.

    Run before the toggle is enabled in any environment: a missing grant surfaces here
    as a permission error on a throwaway read, rather than in production as a
    structured retrieval failure on a user's question."""
    role = _checked_identifier(role_name, "role")
    schema_ident = _checked_identifier(schema, "schema")
    await session.execute(text("BEGIN READ ONLY"))
    try:
        await session.execute(text(f"SET LOCAL ROLE {role}"))
        for table in sorted(WHITELISTED_TABLES):
            table_ident = _checked_identifier(table, "table")
            await session.execute(text(f"SELECT 1 FROM {schema_ident}.{table_ident} LIMIT 1"))
    finally:
        await session.execute(text("ROLLBACK"))
