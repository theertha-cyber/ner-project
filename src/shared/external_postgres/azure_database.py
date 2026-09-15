"""Production `ExternalDatabase` seam: a tenant's real Azure Database for
PostgreSQL over asyncpg (CAP-4, ADR-013).

Introspection and execution both run against the live server named by the
tenant's CAP-2 connection configuration; the password is never accepted here
as a literal — callers resolve `secret_references.password_ref` (the same
`env://`-style resolver blob sync uses) and pass the resolved value in.
Every execution runs inside a read-only transaction with a server-side
statement timeout, so a validator gap degrades to a database error rather
than a write.
"""

from __future__ import annotations

import re
import ssl as ssl_module

import asyncpg

from src.shared.external_postgres.drift import ExternalDatabase

_NAMED_PLACEHOLDER_RE = re.compile(r"%\(([^)]+)\)s")

CONNECT_TIMEOUT_SECONDS = 10.0


def _to_positional(statement: str, params: dict) -> tuple[str, list]:
    """Rewrites the connector's `%(name)s` placeholders into asyncpg's
    positional `$1, $2, ...` form. Values are bound, never interpolated."""
    values: list = []

    def _replace(match: "re.Match[str]") -> str:
        values.append(params[match.group(1)])
        return f"${len(values)}"

    converted = _NAMED_PLACEHOLDER_RE.sub(_replace, statement)
    return converted, values


def _ssl_context(sslmode: str | None):
    if sslmode in (None, "disable"):
        return False
    # Azure Database for PostgreSQL always requires TLS; both "require" and
    # "verify-full" get a validating context here (no lesser, unverified path).
    return ssl_module.create_default_context()


class AzureExternalDatabase(ExternalDatabase):
    """Live seam for one tenant's `azure_postgresql` connection.

    Constructed per call from the connection's own configuration and a
    resolved password — never pooled across tenants, never cached beyond one
    request's lifetime.
    """

    def __init__(self, configuration: dict, password: str):
        self._host = configuration["host"].strip()
        self._port = int(configuration.get("port", 5432))
        self._database = configuration["database"].strip()
        self._username = configuration["username"].strip()
        self._sslmode = configuration.get("sslmode", "require")
        self._password = password

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._username,
            password=self._password,
            ssl=_ssl_context(self._sslmode),
            timeout=CONNECT_TIMEOUT_SECONDS,
        )

    async def introspect(self, relations: list[str]) -> dict[str, list[str]]:
        """Live `{relation: [columns]}` for the named relations, `public` schema only."""
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = ANY($1::text[])",
                list(relations),
            )
        finally:
            await conn.close()
        result: dict[str, list[str]] = {name: [] for name in relations}
        for row in rows:
            result[row["table_name"]].append(row["column_name"])
        return result

    async def execute(self, statement: str, params: dict, timeout_ms: int,
                      row_cap: int) -> list[dict]:
        """Runs one already-validated, parameterized SELECT read-only, capped by
        `timeout_ms`. `timeout_ms` is the connector's own constant, never
        caller-supplied, so it is safe to inline into `SET LOCAL`."""
        converted, values = _to_positional(statement, params)
        conn = await self._connect()
        try:
            async with conn.transaction(readonly=True):
                await conn.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
                rows = await conn.fetch(converted, *values)
        finally:
            await conn.close()
        return [dict(row) for row in rows]


class ExternalDatabaseUnavailable(Exception):
    """A connection's own configuration or secret can't produce a live database."""


def build_live_database(tenant_id: str, configuration: dict,
                        secret_references: dict) -> AzureExternalDatabase:
    """Build a real asyncpg-backed database from a connection's own config and
    resolved secret. Raises `ExternalDatabaseUnavailable` for anything that
    keeps the connection from being usable — never half-configured. Mirrors
    `blob_sync.sync.build_live_provider`'s shape for the same reason: one
    documented way to turn a CAP-2 connection row into its live seam."""
    from src.shared.data_sources.providers import (
        PROVIDER_AZURE_POSTGRESQL,
        PROVIDER_SECRET_KIND,
    )
    from src.shared.integration_profile.secrets import (
        SecretResolutionError,
        resolve_for_tenant,
    )

    if not isinstance(configuration, dict) or not isinstance(secret_references, dict):
        raise ExternalDatabaseUnavailable("connection configuration unavailable")
    for field in ("host", "database", "username"):
        if not configuration.get(field):
            raise ExternalDatabaseUnavailable(f"{field} is not configured")

    adapter_kind = PROVIDER_SECRET_KIND[PROVIDER_AZURE_POSTGRESQL]
    namespace = type(
        "_PostgresConnectionSecrets",
        (),
        {"tenant_id": tenant_id, "secret_references": {adapter_kind: dict(secret_references)}},
    )()
    try:
        context = resolve_for_tenant(namespace, adapter_kind)
    except SecretResolutionError:
        raise ExternalDatabaseUnavailable("secret reference unresolvable") from None
    password = context.get("password_ref")
    if not password:
        raise ExternalDatabaseUnavailable("password secret unresolvable")

    return AzureExternalDatabase(configuration, password)


async def resolve_live_database(session, tenant_id: str) -> AzureExternalDatabase:
    """The tenant's active `azure_postgresql` connection as a live database, or
    raises. Composes `active_connection` (CAP-2 authority: an active,
    tenant-owned row — never caller input) with `build_live_database`."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL
    from src.shared.data_sources.resolver import active_connection

    connection = await active_connection(session, tenant_id, PROVIDER_AZURE_POSTGRESQL)
    if connection is None:
        raise ExternalDatabaseUnavailable("no active azure_postgresql connection")
    return build_live_database(
        tenant_id, connection.configuration, connection.secret_references
    )
