"""Verification for the contract-governed external PostgreSQL query path (CAP-4).

Maps to `openspec/changes/cap-4-contract-governed-external-postgresql-query-path/verification.md`
Section 1 rows 1-13.

Live Azure Database for PostgreSQL verification is deferred per run
provisioning (no approved test instance), so the `ExternalDatabase` seam runs
`FixtureExternalDatabase` instances -- exactly the seam production uses for
the Azure-backed connector. Every other layer (contract store, validator,
drift gate, resolver, index) runs against the real test database.

Teardown removes exactly what each test created: contract rows, connection
rows, tenant schemas, and index entries. Nothing leaks into the shared dataset.
"""

import json
import logging
import pathlib
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.shared.config import settings
from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.store import CONNECTIONS_TABLE
from src.shared.external_postgres import (
    ContractRejected,
    DriftBlocked,
    FixtureExternalDatabase,
    ValidationRejected,
    accepted_contract,
    drift_check,
    execute_external_query,
    fetch_entries,
    is_external_request_executable,
    list_versions,
    publish_version,
    replace_version_entries,
    resolve_external_capability,
    store_draft,
    validate_contract_document,
    validate_statement,
)
from src.shared.external_postgres import connector as conn_mod
from src.shared.external_postgres import drift as drift_mod
from src.shared.external_postgres import validator as validator_mod
from src.shared.external_postgres.capability import (
    NO_PUBLISHED_CONTRACT,
    NOT_ACTIVE,
)
from src.shared.external_postgres.contract import CONTRACTS_TABLE
from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]

SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"

VALID_CONTRACT = {
    "version": 1,
    "relations": {
        "orders": {"columns": ["id", "customer_id", "total"], "primary_key": "id"},
        "customers": {"columns": ["id", "name"], "primary_key": "id"},
    },
    "joins": [
        {"left": "orders", "right": "customers",
         "left_key": "customer_id", "right_key": "id"}
    ],
}

LIVE_METADATA = {"orders": ["id", "customer_id", "total"], "customers": ["id", "name"]}

APPROVED_SELECT = (
    "SELECT c.name, COUNT(o.id) FROM orders AS o "
    "JOIN customers AS c ON o.customer_id = c.id "
    "WHERE c.name = %(name)s GROUP BY c.name"
)

CONTRACTS_DDL = f"""
CREATE TABLE IF NOT EXISTS {CONTRACTS_TABLE} (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    connection_id VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    canonical JSONB NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    validation_state VARCHAR(32) NOT NULL DEFAULT 'draft',
    validation_reason VARCHAR(64) NOT NULL DEFAULT 'none',
    published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    UNIQUE (tenant_id, connection_id, version)
)
"""

# Full CAP-2 control-plane DDL (alembic 040), restated so this file is
# self-sufficient on a database where the baseline migrations have not run.
# `IF NOT EXISTS` keeps it a no-op where the migrated table already exists,
# and the shape is identical so co-running CAP-2 tests are unaffected.
CONNECTIONS_DDL = f"""
CREATE TABLE IF NOT EXISTS {CONNECTIONS_TABLE} (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    provider VARCHAR(32) NOT NULL
        CHECK (provider IN ('azure_blob', 'azure_postgresql')),
    configuration JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    secret_references JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'validated', 'active', 'paused', 'error', 'retired')),
    last_test_outcome VARCHAR(32) NOT NULL DEFAULT 'not_run',
    last_test_reason VARCHAR(64) NOT NULL DEFAULT 'none',
    last_test_at TIMESTAMPTZ,
    test_config_digest VARCHAR(64),
    activation_outcome VARCHAR(32) NOT NULL DEFAULT 'inactive',
    activation_reason VARCHAR(64) NOT NULL DEFAULT 'none',
    activated_at TIMESTAMPTZ,
    activation_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    replaces_connection_id UUID,
    replaced_by_connection_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

INDEX_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.external_pg_schema_index (
    connection_id VARCHAR NOT NULL,
    contract_version INTEGER NOT NULL,
    relation_name VARCHAR(256) NOT NULL,
    entry_text TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (connection_id, contract_version, relation_name)
)
"""


@pytest.fixture
async def session_factory():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def tenant_ctx(session_factory):
    """One isolated tenant schema plus tracked contract/connection rows."""
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    tid = uuid.uuid4().hex
    schema = f"tenant_{tid}"
    created_connections: list[str] = []
    async with engine.connect() as conn:
        await conn.execute(text(CONNECTIONS_DDL))
        await conn.execute(text(CONTRACTS_DDL))
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(text(INDEX_DDL.format(schema=schema)))
    yield {"tenant_id": tid, "schema": schema,
           "connections": created_connections}

    async with engine.connect() as conn:
        await conn.execute(
            text(f"DELETE FROM {CONTRACTS_TABLE} WHERE tenant_id = :tid"),
            {"tid": tid},
        )
        for cid in created_connections:
            await conn.execute(
                text(f"DELETE FROM {CONNECTIONS_TABLE} WHERE id = CAST(:id AS UUID)"),
                {"id": cid},
            )
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    await engine.dispose()


async def _make_connection(session_factory, tenant_id, tracker,
                           status=lc.STATUS_ACTIVE):
    cid = str(uuid.uuid4())
    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {CONNECTIONS_TABLE} "
                "(id, tenant_id, provider, configuration, secret_references, status) "
                "VALUES (CAST(:id AS UUID), :tid, 'azure_postgresql', "
                "CAST(:cfg AS JSONB), CAST(:sec AS JSONB), :status)"
            ),
            {
                "id": cid,
                "tid": tenant_id,
                "cfg": json.dumps({"host": "h", "database": "d",
                                   "username": "u", "port": 5432,
                                   "sslmode": "verify-full"}),
                "sec": json.dumps({"password_ref": "env://CAP4_TEST_PG_PASSWORD"}),
                "status": status,
            },
        )
        await session.commit()
    tracker.append(cid)
    return cid


async def _publish(session_factory, tenant_id, schema, connection_id,
                   document=None):
    async with session_factory() as session:
        stored = await store_draft(session, tenant_id, connection_id,
                                   document or dict(VALID_CONTRACT))
        published = await publish_version(session, tenant_id, connection_id,
                                          stored["version"])
        await replace_version_entries(session, schema, connection_id,
                                      stored["version"], published["canonical"])
        await session.commit()
        return published


# --- Row 1: valid contract publish + tenant-isolated index ----------------------

async def test_valid_contract_publish_creates_tenant_index(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    async with session_factory() as session:
        stored = await store_draft(session, tid, cid, dict(VALID_CONTRACT))
        assert stored["validation_state"] == "validated"
        published = await publish_version(session, tid, cid, 1)
        count = await replace_version_entries(session, schema, cid, 1,
                                              published["canonical"])
        await session.commit()
    assert count == 2
    async with session_factory() as session:
        entries = await fetch_entries(session, schema, cid, 1)
        assert {e["relation"] for e in entries} == {"orders", "customers"}
        assert "customer_id" in entries[0]["entry"] or "customer_id" in entries[1]["entry"]
        # Invisible to another tenant: contract lookup and index both miss.
        assert await accepted_contract(session, "someone-else", cid) is None
        history = await list_versions(session, "someone-else", cid)
        assert history["total"] == 0


# --- Row 2: invalid contract rejected safely ------------------------------------

INVALID_DOCUMENTS = [
    {"version": 1, "relations": {}, "joins": []},
    {"version": 1,
     "relations": {"orders": {"columns": ["9bad"], "primary_key": "9bad"}},
     "joins": []},
    {"version": 1,
     "relations": {"orders": {"columns": ["id"], "primary_key": "id"}},
     "joins": [{"left": "orders", "right": "ghost",
                "left_key": "id", "right_key": "id"}]},
    {"version": 1,
     "relations": {"orders": {"columns": ["id"], "primary_key": "id"},
                   "customers": {"columns": ["id"], "primary_key": "id"}},
     "joins": [{"left": "orders", "right": "customers",
                "left_key": "nope", "right_key": "id"}]},
]


async def test_invalid_contract_rejected_with_finite_reason(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    for bad in INVALID_DOCUMENTS:
        validation = validate_contract_document(bad)
        assert not validation.valid
        assert validation.reason in (
            "invalid_shape", "undeclared_join_key", "unknown_relation",
            "invalid_json",
        )
        async with session_factory() as session:
            with pytest.raises(ContractRejected):
                await store_draft(session, tid, cid, bad)
            await session.rollback()
    async with session_factory() as session:
        history = await list_versions(session, tid, cid)
        assert history["total"] == 0
        assert await fetch_entries(session, schema, cid, 1) == []


# --- Row 3: cross-tenant denial ---------------------------------------------------

async def test_cross_tenant_contract_and_index_denied(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    await _publish(session_factory, tid, schema, cid)
    async with session_factory() as session:
        assert await accepted_contract(session, "tenant-b", cid) is None
        history = await list_versions(session, "tenant-b", cid)
        assert history["total"] == 0
        capability = await resolve_external_capability(session, "tenant-b")
        assert capability == {"executable": False, "reason": NOT_ACTIVE}
        assert not await is_external_request_executable(session, "tenant-b", cid)


# --- Rows 4-6: drift gate ----------------------------------------------------------

async def test_drift_mismatch_blocks_without_execution(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid)
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    drifted = FixtureExternalDatabase(
        metadata={"orders": ["id", "customer_id"], "customers": ["id", "name"]})
    with pytest.raises(DriftBlocked) as exc:
        await execute_external_query(drifted, contract, APPROVED_SELECT,
                                     {"name": "acme"})
    assert exc.value.outcome == "drift_mismatch"
    assert drifted.executions == []


async def test_unavailable_metadata_blocks_distinctly(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid)
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    down = FixtureExternalDatabase(metadata=dict(LIVE_METADATA), available=False)
    with pytest.raises(DriftBlocked) as exc:
        await execute_external_query(down, contract, APPROVED_SELECT,
                                     {"name": "acme"})
    assert exc.value.outcome == "metadata_unavailable"
    assert down.executions == []


async def test_replacement_contract_restores_execution(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    await _publish(session_factory, tid, schema, cid)
    evolved = {
        "version": 2,
        "relations": {
            "orders": {"columns": ["id", "customer_id"], "primary_key": "id"},
            "customers": {"columns": ["id", "name"], "primary_key": "id"},
        },
        "joins": [{"left": "orders", "right": "customers",
                   "left_key": "customer_id", "right_key": "id"}],
    }
    published = await _publish(session_factory, tid, schema, cid, evolved)
    live = FixtureExternalDatabase(
        metadata={"orders": ["id", "customer_id"], "customers": ["id", "name"]},
        rows=[{"name": "acme", "count": 2}],
    )
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    assert await drift_check(live, contract) == "clean"
    result = await execute_external_query(
        live, contract,
        "SELECT c.name, COUNT(o.id) FROM orders AS o "
        "JOIN customers AS c ON o.customer_id = c.id "
        "WHERE c.name = %(name)s GROUP BY c.name",
        {"name": "acme"},
    )
    assert result["row_count"] == 1


# --- Rows 7-10: execution, validator, literals, cap/timeout -------------------------

async def test_approved_join_aggregation_executes(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid)
    live = FixtureExternalDatabase(metadata=dict(LIVE_METADATA),
                                   rows=[{"name": "acme", "count": 3}])
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    result = await execute_external_query(live, contract, APPROVED_SELECT,
                                          {"name": "acme"})
    assert result["rows"] == [{"name": "acme", "count": 3}]
    assert result["truncated"] is False
    assert live.executions != []


DISALLOWED = [
    ("DELETE FROM orders", "write_or_ddl"),
    ("SELECT id FROM orders; SELECT id FROM customers", "multiple_statements"),
    ("SELECT id FROM orders UNION SELECT id FROM customers", "union_or_setop"),
    ("SELECT id FROM (SELECT id FROM orders)", "subquery"),
    ("WITH x AS (SELECT id FROM orders) SELECT id FROM x", "cte"),
    ("SELECT ROW_NUMBER() OVER (ORDER BY id) FROM orders", "window_function"),
    ("SELECT password FROM users", "unapproved_relation"),
    ("SELECT id FROM pg_authid", "unapproved_relation"),
    ("SELECT id FROM orders WHERE total > 5", "inline_literal"),
    ("SET ROLE postgres", "role_switch"),
    ("SELECT o.id FROM orders AS o JOIN users AS u ON o.id = u.id",
     "unapproved_relation"),
]


async def test_disallowed_statements_rejected_safely(
        session_factory, tenant_ctx, caplog):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid)
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    for statement, reason in DISALLOWED:
        live = FixtureExternalDatabase(metadata=dict(LIVE_METADATA))
        with pytest.raises((ValidationRejected, DriftBlocked)) as exc:
            await execute_external_query(live, contract, statement, {})
        if isinstance(exc.value, ValidationRejected):
            assert exc.value.reason == reason
        assert live.executions == []
    # Rejection telemetry carries the reason class, never the statement text.
    rejected_logs = [r for r in caplog.records
                     if getattr(r, "reason", None) is not None
                     or "rejected" in r.getMessage()]
    assert rejected_logs != []
    for record in caplog.records:
        assert "DROP TABLE" not in record.getMessage()
        assert "pg_authid" not in record.getMessage()


async def test_inline_literals_bound_or_rejected(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid)
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    live = FixtureExternalDatabase(metadata=dict(LIVE_METADATA))
    with pytest.raises(ValidationRejected) as exc:
        await execute_external_query(
            live, contract,
            "SELECT id FROM orders WHERE total > 5", {})
    assert exc.value.reason == "inline_literal"
    assert live.executions == []
    # The placeholder form validates and binds without interpolation.
    live_ok = FixtureExternalDatabase(metadata=dict(LIVE_METADATA),
                                      rows=[{"id": 1}])
    result = await execute_external_query(
        live_ok, contract,
        "SELECT id FROM orders WHERE total > %(min_total)s",
        {"min_total": 5},
    )
    assert result["row_count"] == 1
    assert live_ok.executions[0]["params"] == {"min_total": 5}


async def test_server_row_cap_and_timeout_enforced(
        session_factory, tenant_ctx):
    assert conn_mod.ROW_CAP == 100
    assert conn_mod.STATEMENT_TIMEOUT_MS == 10_000
    assert conn_mod.clamp_limit("SELECT id FROM orders") == \
        "SELECT id FROM orders LIMIT 100"
    assert conn_mod.clamp_limit("SELECT id FROM orders LIMIT 500") == \
        "SELECT id FROM orders LIMIT 100"
    assert conn_mod.clamp_limit("SELECT id FROM orders LIMIT 10") == \
        "SELECT id FROM orders LIMIT 10"
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid)
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    live = FixtureExternalDatabase(
        metadata=dict(LIVE_METADATA),
        rows=[{"id": i} for i in range(150)],
    )
    result = await execute_external_query(
        live, contract, "SELECT id FROM orders", {})
    assert result["row_count"] == 100
    assert result["truncated"] is True
    assert live.executions[0]["row_cap"] == 100


# --- Rows 11-12: no retention, server-side resolution ----------------------------------

async def test_external_rows_never_retained(session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid)
    live = FixtureExternalDatabase(
        metadata=dict(LIVE_METADATA),
        rows=[{"name": "acme", "count": 3}],
    )
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    await execute_external_query(live, contract, APPROVED_SELECT, {"name": "acme"})
    async with session_factory() as session:
        tables = (await session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = :s"),
            {"s": schema},
        )).fetchall()
        names = {r.tablename for r in tables}
        assert "external_pg_schema_index" in names
        assert "orders" not in names and "customers" not in names
        index_rows = (await session.execute(
            text(f"SELECT COUNT(*) FROM {schema}.external_pg_schema_index")
        )).scalar()
        assert index_rows == 2


async def test_capability_resolves_per_authenticated_tenant(
        session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    async with session_factory() as session:
        # Active connection but no published contract yet: not executable.
        capability = await resolve_external_capability(session, tid)
        assert capability["executable"] is False
        assert capability["reason"] == NO_PUBLISHED_CONTRACT
    await _publish(session_factory, tid, schema, cid)
    async with session_factory() as session:
        capability = await resolve_external_capability(session, tid)
        assert capability["executable"] is True
        assert capability["connection_id"] == cid
        assert await is_external_request_executable(session, tid, cid) is True
        # Another tenant cannot borrow it.
        assert await is_external_request_executable(session, "tenant-b", cid) is False
    # A paused connection is not executable even with a published contract.
    async with session_factory() as session:
        await session.execute(
            text(f"UPDATE {CONNECTIONS_TABLE} SET status = 'paused' "
                 "WHERE id = CAST(:id AS UUID)"),
            {"id": cid},
        )
        await session.commit()
        capability = await resolve_external_capability(session, tid)
        assert capability == {"executable": False, "reason": NOT_ACTIVE}


# --- Row 13: rejected SQL records reason class only -------------------------------------

async def test_rejected_sql_records_reason_class_only(
        session_factory, tenant_ctx, caplog):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid)
    contract = {"canonical": published["canonical"],
                "fingerprint": published["fingerprint"]}
    live = FixtureExternalDatabase(metadata=dict(LIVE_METADATA))
    evil = "DROP TABLE document_entities"
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ValidationRejected):
            await execute_external_query(live, contract, evil, {})
    assert live.executions == []
    for record in caplog.records:
        assert evil not in record.getMessage()
        assert evil not in str(getattr(record, "args", ""))
    reasons = [getattr(r, "reason", None) for r in caplog.records]
    assert "write_or_ddl" in reasons


# --- Metric contract: label sets mirror the external_postgres modules -------------------

def test_metric_label_sets_mirror_module_constants():
    assert conn_mod.EXECUTION_OUTCOMES <= dm.EXTERNAL_PG_OUTCOMES
    assert set(drift_mod.DRIFT_OUTCOMES) <= (dm.EXTERNAL_PG_REASONS | {"clean"})
    assert validator_mod.REJECTION_REASONS <= dm.EXTERNAL_PG_REASONS
    assert "tenant_id" not in dm.EXTERNAL_PG_QUERY.label_names


# --- Static telemetry scan: no prohibited payload classes on new paths -------------------

def test_new_paths_emit_no_prohibited_payloads():
    # Parameterized DDL with allowlisted identifiers is the baseline-compliant
    # pattern (every value travels as a bound parameter), so the scan targets
    # value interpolation and secret/endpoint handling, not SQL text itself.
    import re
    prohibited_res = [
        r"\bprint\s*\(", r"\btraceback\b", r"\bexc_info\s*=\s*True",
        r"\bsecret_value\b", r"\bpassword_value\b",
        r"\bconnection_string_value\b", r"\bprovider_error\b",
        r"\bendpoint_value\b",
    ]
    # Value interpolation into executed text (DDL here interpolates only the
    # allowlisted table/schema identifiers via plain f-strings, never values).
    interpolation_res = [r"\.format\s*\(", r"text\s*\(\s*f['\"]",
                         r"execute\s*\(\s*f['\"]"]
    offenders = []
    for module in ("contract.py", "validator.py", "drift.py", "connector.py",
                   "capability.py", "index.py"):
        path = SRC_ROOT / "shared" / "external_postgres" / module
        source = path.read_text(encoding="utf-8")
        for pattern in prohibited_res:
            if re.search(pattern, source):
                offenders.append(f"{module}: {pattern}")
        if module in ("connector.py", "validator.py"):
            for pattern in interpolation_res:
                if re.search(pattern, source):
                    offenders.append(f"{module}: {pattern}")
    assert offenders == []
