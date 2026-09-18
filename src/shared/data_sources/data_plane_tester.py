"""The `azure_postgresql_data_plane` secure tester (ADR-017, Design D3, D11 — task 7.2).

Beyond the shared TLS-handshake test every provider gets, a data-plane draft is tested
against the finite residency-specific checks the routing and provisioning specs
require: server version, `vector` extension availability, schema `CREATE` privilege,
query-role creatability, and target-schema identity. Each fails to its own reason
class — never a raw driver message, which could carry the host name or a SQL error
quoting configuration back.

Runs synchronously via `asyncio.to_thread`: these are ordinary blocking psycopg2
calls, and the rest of the secure-test seam (`testing.py`) is a thin async wrapper
over exactly this kind of check.
"""

from __future__ import annotations

import asyncio
import logging

import psycopg2

from src.shared.config import settings
from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.testing import SecureTestResult
from src.shared.database import system_ca_bundle_path

logger = logging.getLogger(__name__)

MIN_SERVER_VERSION_NUM = 160000  # PostgreSQL 16.0


def _connection_string(configuration: dict, password: str) -> str:
    sslmode = configuration.get("sslmode", "verify-full")
    parts = [
        f"host={configuration['host']} port={configuration['port']}",
        f"dbname={configuration['database']} user={configuration['username']}",
        f"password={password} sslmode={sslmode}",
        f"connect_timeout={int(settings.data_plane_connect_timeout_seconds)}",
    ]
    if sslmode not in ("disable", "allow", "prefer"):
        # See `system_ca_bundle_path` (database.py): psycopg2-binary's bundled
        # OpenSSL resolves `sslrootcert=system` against its own compiled-in default
        # path, not the container's actual CA bundle — pass the real path instead.
        cafile = system_ca_bundle_path()
        if cafile:
            parts.append(f"sslrootcert={cafile}")
    return " ".join(parts)


def _vector_extension_available(cur) -> bool:
    # Azure Flexible Server allow-lists extensions via `azure.extensions`; a plain
    # self-hosted or local server (the Compose stand-in) has no such setting, so the
    # `pg_available_extensions` catalog is the fallback (Design D11).
    cur.execute("SELECT current_setting('azure.extensions', true)")
    row = cur.fetchone()
    allowlist = row[0] if row else None
    if allowlist is not None:
        names = {n.strip().upper() for n in allowlist.split(",")}
        if "VECTOR" in names:
            return True
    cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    if cur.fetchone() is not None:
        return True
    cur.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    return cur.fetchone() is not None


def _schema_create_privilege(cur) -> bool:
    cur.execute("SELECT has_database_privilege(current_user, current_database(), 'CREATE')")
    row = cur.fetchone()
    return bool(row and row[0])


def _query_role_available(cur) -> bool:
    # Either the connecting role can create the NOLOGIN query role itself, or that
    # role already exists (a DBA pre-created it — the documented fallback for a
    # customer who refuses to grant CREATEROLE, per Design's "Risks" register).
    cur.execute(
        "SELECT rolcreaterole OR rolsuper FROM pg_roles WHERE rolname = current_user"
    )
    row = cur.fetchone()
    if row and row[0]:
        return True
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (settings.sql_execution_role_name,))
    return cur.fetchone() is not None


def _target_schema_outcome(cur, tenant_id: str, expected_store_id: str | None) -> str | None:
    """Returns a failure reason, or `None` if the target schema is absent, empty, or
    carries the store identity this tenant already recorded (a same-store credential
    rotation or replacement — tenant-residency-store-provisioning spec's "Replacement
    connections must point at the same store").

    `expected_store_id`, when given, is the `store_id` the caller has on record for
    this tenant (its currently active data-plane connection's store) — the case a
    replacement or credential-rotation test needs. A bare first-activation draft has
    no prior identity, so the caller passes `None` and recognizing any marker is
    sufficient (`test_provisioning refuses a non-empty foreign schema` is the
    complementary "no marker at all" case, handled below unconditionally either
    way)."""
    schema = f"tenant_{tenant_id.replace('-', '_')}"
    cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (schema,))
    if cur.fetchone() is None:
        return None  # absent: fine, provisioning will create it

    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE'",
        (schema,),
    )
    if cur.fetchone() is None:
        return None  # empty schema: fine

    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = %s AND table_name = 'platform_store_meta'",
        (schema,),
    )
    if cur.fetchone() is None:
        return lc.TEST_REASON_TARGET_SCHEMA_NOT_EMPTY

    if expected_store_id is None:
        # A platform_store_meta table exists: this is a recognized store (already
        # provisioned by this platform), not a foreign schema. No specific identity
        # to compare against, so recognizing the marker is sufficient.
        return None

    cur.execute(f"SELECT store_id FROM {schema}.platform_store_meta LIMIT 1")
    row = cur.fetchone()
    if row is None or str(row[0]) != str(expected_store_id):
        return lc.TEST_REASON_STORE_IDENTITY_MISMATCH
    return None


def run_data_plane_test_sync(
    tenant_id: str, configuration: dict, secret_values: dict, expected_store_id: str | None = None
) -> SecureTestResult:
    password = secret_values.get("password_ref") or secret_values.get("password")
    if not password:
        return SecureTestResult(False, lc.TEST_REASON_SECRET_UNAVAILABLE)

    try:
        conn = psycopg2.connect(_connection_string(configuration, password))
    except psycopg2.OperationalError as exc:
        message = str(exc).lower()
        if "password" in message or "authentication" in message:
            return SecureTestResult(False, lc.TEST_REASON_AUTHORIZATION_FAILED)
        if "ssl" in message or "certificate" in message:
            return SecureTestResult(False, lc.TEST_REASON_TLS_VALIDATION_FAILED)
        return SecureTestResult(False, lc.TEST_REASON_CONNECTION_FAILED)
    except Exception:
        logger.debug("data_plane_secure_test_connect_failed", exc_info=True)
        return SecureTestResult(False, lc.TEST_REASON_CONNECTION_FAILED)

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SHOW server_version_num")
                version_num = int(cur.fetchone()[0])
                if version_num < MIN_SERVER_VERSION_NUM:
                    return SecureTestResult(False, lc.TEST_REASON_SERVER_VERSION_UNSUPPORTED)

                if not _vector_extension_available(cur):
                    return SecureTestResult(False, lc.TEST_REASON_VECTOR_EXTENSION_UNAVAILABLE)

                if not _schema_create_privilege(cur):
                    return SecureTestResult(False, lc.TEST_REASON_INSUFFICIENT_PRIVILEGE)

                if not _query_role_available(cur):
                    return SecureTestResult(False, lc.TEST_REASON_QUERY_ROLE_UNAVAILABLE)

                schema_failure = _target_schema_outcome(cur, tenant_id, expected_store_id)
                if schema_failure is not None:
                    return SecureTestResult(False, schema_failure)
    except Exception:
        logger.debug("data_plane_secure_test_check_failed", exc_info=True)
        return SecureTestResult(False, lc.TEST_REASON_CONNECTION_FAILED)
    finally:
        conn.close()

    return SecureTestResult(True, lc.TEST_REASON_NONE)


class DataPlaneSecureTester:
    """Registered for `azure_postgresql_data_plane` in `testing.py`'s tester registry.
    Declares `tenant_id` and `expected_store_id` so `run_secure_test` passes both
    through (the target-schema check needs the tenant's own schema name, and a
    replacement or credential-rotation test needs the store identity to verify
    against — tenant-residency-store-provisioning spec's "Replacement connections
    must point at the same store")."""

    async def run(
        self,
        provider: str,
        configuration: dict,
        secret_values: dict,
        tenant_id: str | None = None,
        expected_store_id: str | None = None,
    ) -> SecureTestResult:
        if tenant_id is None:
            return SecureTestResult(False, lc.TEST_REASON_VALIDATION_FAILED)
        return await asyncio.to_thread(
            run_data_plane_test_sync, tenant_id, configuration, secret_values, expected_store_id
        )
