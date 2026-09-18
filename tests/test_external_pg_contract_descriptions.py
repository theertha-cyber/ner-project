"""Verification for optional contract relation/column descriptions.

Maps to
`openspec/changes/external-postgresql-chat-sql-generation/verification.md`
Section 1 rows 13-17, and Risk 4 in the Hallucination Risk Register.

Descriptions are context only: they must survive publish and appear in the
schema index (row 13), never influence the fingerprint (row 14), be rejected
for an undeclared column (row 15) or when overlong (row 16), and never break a
contract that declares none of them (row 17). An unknown relation key must
never survive `store_draft` (Risk 4).
"""

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
    accepted_contract,
    canonical_fingerprint,
    fetch_entries,
    publish_version,
    replace_version_entries,
    store_draft,
    validate_contract_document,
)
from src.shared.external_postgres.contract import CONTRACTS_TABLE

pytestmark = [pytest.mark.verification]

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

DESCRIBED_CONTRACT = {
    "version": 1,
    "relations": {
        "fisc_user_profile": {
            "columns": ["record_id", "pbwuserid", "claim_ind"],
            "primary_key": "record_id",
            "description": "User profiles: names, job, student data, claim/approver flags.",
            "column_descriptions": {"claim_ind": "'0'=Unclaimed, '1'=Claimed"},
        },
    },
    "joins": [],
}

BARE_CONTRACT = {
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


@pytest.fixture
async def session_factory():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def tenant_ctx(session_factory):
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
    yield {"tenant_id": tid, "schema": schema, "connections": created_connections}

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


async def _make_connection(session_factory, tenant_id, tracker):
    import json

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
                "status": lc.STATUS_ACTIVE,
            },
        )
        await session.commit()
    tracker.append(cid)
    return cid


async def _publish(session_factory, tenant_id, schema, connection_id, document):
    async with session_factory() as session:
        stored = await store_draft(session, tenant_id, connection_id, document)
        published = await publish_version(session, tenant_id, connection_id, stored["version"])
        await replace_version_entries(session, schema, connection_id, stored["version"], published["canonical"])
        await session.commit()
        return published


async def test_descriptions_retained_and_indexed(session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    published = await _publish(session_factory, tid, schema, cid, dict(DESCRIBED_CONTRACT))

    canonical_relation = published["canonical"]["relations"]["fisc_user_profile"]
    assert canonical_relation["description"] == DESCRIBED_CONTRACT["relations"]["fisc_user_profile"]["description"]
    assert canonical_relation["column_descriptions"] == {"claim_ind": "'0'=Unclaimed, '1'=Claimed"}

    async with session_factory() as session:
        entries = await fetch_entries(session, schema, cid, 1)
    entry = next(e for e in entries if e["relation"] == "fisc_user_profile")
    assert "User profiles: names, job, student data, claim/approver flags." in entry["entry"]
    assert "'0'=Unclaimed, '1'=Claimed" in entry["entry"]


async def test_descriptions_excluded_from_fingerprint(session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])

    without_descriptions = {
        "version": 1,
        "relations": {
            "fisc_user_profile": {
                "columns": ["record_id", "pbwuserid", "claim_ind"],
                "primary_key": "record_id",
            },
        },
        "joins": [],
    }
    fp_without = canonical_fingerprint(
        without_descriptions["relations"], without_descriptions["joins"]
    )
    fp_with = canonical_fingerprint(
        DESCRIBED_CONTRACT["relations"], DESCRIBED_CONTRACT["joins"]
    )
    assert fp_without == fp_with

    published = await _publish(session_factory, tid, schema, cid, dict(DESCRIBED_CONTRACT))
    assert published["fingerprint"] == fp_with


async def test_undeclared_column_description_rejected(session_factory, tenant_ctx):
    tid = tenant_ctx["tenant_id"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    document = {
        "version": 1,
        "relations": {
            "orders": {
                "columns": ["id", "total"],
                "column_descriptions": {"discount": "percentage off"},
            },
        },
        "joins": [],
    }
    validation = validate_contract_document(document)
    assert not validation.valid
    assert validation.reason == "invalid_shape"
    assert "relations.orders.column_descriptions.discount" in validation.field_errors
    assert not any("percentage off" in e for e in validation.field_errors)

    async with session_factory() as session:
        with pytest.raises(ContractRejected) as exc:
            await store_draft(session, tid, cid, document)
        await session.rollback()
    assert "relations.orders.column_descriptions.discount" in exc.value.field_errors


async def test_overlong_description_rejected(session_factory, tenant_ctx):
    tid = tenant_ctx["tenant_id"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    document = {
        "version": 1,
        "relations": {
            "orders": {"columns": ["id", "total"], "description": "x" * 2001},
        },
        "joins": [],
    }
    validation = validate_contract_document(document)
    assert not validation.valid
    assert validation.reason == "invalid_shape"

    async with session_factory() as session:
        with pytest.raises(ContractRejected) as exc:
            await store_draft(session, tid, cid, document)
        await session.rollback()
    assert exc.value.reason == "invalid_shape"


async def test_contract_without_descriptions_unchanged(session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    validation = validate_contract_document(dict(BARE_CONTRACT))
    assert validation.valid

    published = await _publish(session_factory, tid, schema, cid, dict(BARE_CONTRACT))
    assert "description" not in published["canonical"]["relations"]["orders"]
    assert "column_descriptions" not in published["canonical"]["relations"]["orders"]

    async with session_factory() as session:
        entries = await fetch_entries(session, schema, cid, 1)
        contract = await accepted_contract(session, tid, cid)
    assert {e["relation"] for e in entries} == {"orders", "customers"}
    assert contract["canonical"]["relations"]["orders"]["columns"] == ["id", "customer_id", "total"]


async def test_unknown_relation_key_dropped_from_canonical(session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    document = {
        "version": 1,
        "relations": {
            "orders": {
                "columns": ["id", "total"],
                "foo": "unexpected",
            },
        },
        "joins": [],
    }
    async with session_factory() as session:
        stored = await store_draft(session, tid, cid, document)
        published = await publish_version(session, tid, cid, stored["version"])
        await session.commit()
    assert "foo" not in published["canonical"]["relations"]["orders"]
    assert set(published["canonical"]["relations"]["orders"]) <= {
        "columns", "primary_key", "description", "column_descriptions",
    }
