"""Verification for contract-grounded external SQL generation (ADR-016).

Maps to
`openspec/changes/external-postgresql-chat-sql-generation/verification.md`
Section 1 rows 1-9, and Risk 1 in the Hallucination Risk Register.

Only the LLM call is faked (`FakeLLM`, scripted per attempt); contract
storage, the schema index, the AST validator, and the drift gate are the real
implementations, driven by the real test database. `resolve_live_database` is
patched to hand back a `FixtureExternalDatabase` — the same seam production
registers for a real Azure connection — so no live network call is made.
"""

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.chat_api.services import external_sql_generator as gen_mod
from src.chat_api.services.external_sql_generator import (
    EXTERNAL_SQL_SYSTEM_PROMPT,
    ExternalSQLGenerator,
)
from src.shared.config import settings
from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.store import CONNECTIONS_TABLE
from src.shared.external_postgres import (
    FixtureExternalDatabase,
    publish_version,
    replace_version_entries,
    store_draft,
)
from src.shared.external_postgres import validator as validator_mod
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

CONTRACT_V2 = {
    "version": 2,
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

LIVE_METADATA = {"fisc_user_profile": ["record_id", "pbwuserid", "claim_ind"]}

VALID_ANSWER = json.dumps(
    {"sql": "SELECT COUNT(*) FROM fisc_user_profile WHERE claim_ind = %(p1)s",
     "params": {"p1": "0"}}
)
UNAPPROVED_COLUMN_ANSWER = json.dumps(
    # A qualified reference so the validator can attribute it to a relation and
    # reject it — an unqualified bare column name is accepted permissively
    # (validator.py's documented degrade-to-database-error behaviour).
    {"sql": "SELECT p.ssn FROM fisc_user_profile AS p", "params": {}}
)
MISSING_PARAM_ANSWER = json.dumps(
    {"sql": "SELECT record_id FROM fisc_user_profile WHERE claim_ind = %(p2)s", "params": {}}
)


class FakeLLM:
    """Records every prompt's user content. Each queued response is either raw
    model output text or an Exception to raise on that attempt."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts: list[str] = []
        self.chat = SimpleNamespace(completions=self)

    @property
    def call_count(self) -> int:
        return len(self.prompts)

    async def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][-1]["content"])
        if not self.responses:
            raise RuntimeError("generation called more times than the test queued")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=nxt))])


class CountingFixtureExternalDatabase(FixtureExternalDatabase):
    """`FixtureExternalDatabase` that additionally counts `introspect` calls,
    so a test can assert the drift check ran exactly once (Risk 3)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.introspect_calls = 0

    async def introspect(self, relations):
        self.introspect_calls += 1
        return await super().introspect(relations)


def _patch_live_database(monkeypatch, database):
    async def _fake_resolve(session, tenant_id):
        return database

    monkeypatch.setattr(gen_mod, "resolve_live_database", _fake_resolve)


def _patch_live_database_unreachable(monkeypatch):
    async def _fake_resolve(session, tenant_id):
        raise AssertionError("resolve_live_database must not be called before a statement is accepted")

    monkeypatch.setattr(gen_mod, "resolve_live_database", _fake_resolve)


def make_generator(llm: FakeLLM, max_attempts: int | None = None) -> ExternalSQLGenerator:
    generator = ExternalSQLGenerator()
    generator.client = llm
    if max_attempts is not None:
        generator.max_attempts = max_attempts
    return generator


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
                "sec": json.dumps({"password_ref": "env://EXT_SQL_GEN_TEST_PASSWORD"}),
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


@pytest.fixture
async def executable_tenant(session_factory, tenant_ctx):
    tid, schema = tenant_ctx["tenant_id"], tenant_ctx["schema"]
    cid = await _make_connection(session_factory, tid, tenant_ctx["connections"])
    await _publish(session_factory, tid, schema, cid, dict(CONTRACT_V2))
    return tenant_ctx


async def test_prompt_uses_published_version_entries_only(session_factory, executable_tenant, monkeypatch):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM(VALID_ANSWER)
    generator = make_generator(llm)
    _patch_live_database(monkeypatch, FixtureExternalDatabase(metadata=dict(LIVE_METADATA), rows=[{"count": 3}]))

    async with session_factory() as session:
        answer = await generator.answer("how many unclaimed users", session, tid)

    assert answer.ok
    assert llm.call_count == 1
    prompt = llm.prompts[0]
    assert "fisc_user_profile" in prompt
    assert "User profiles: names, job, student data, claim/approver flags." in prompt
    assert "'0'=Unclaimed, '1'=Claimed" in prompt


async def test_placeholder_statement_accepted_and_value_bound(session_factory, executable_tenant, monkeypatch):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM(VALID_ANSWER)
    generator = make_generator(llm)
    db = FixtureExternalDatabase(metadata=dict(LIVE_METADATA), rows=[{"count": 5}])
    _patch_live_database(monkeypatch, db)

    async with session_factory() as session:
        answer = await generator.answer("how many unclaimed users", session, tid)

    assert answer.ok
    assert answer.rows == [{"count": 5}]
    assert db.executions[0]["params"] == {"p1": "0"}


async def test_malformed_output_never_executes(session_factory, executable_tenant, monkeypatch):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM("this is not json")
    generator = make_generator(llm, max_attempts=1)
    db = FixtureExternalDatabase(metadata=dict(LIVE_METADATA))
    _patch_live_database_unreachable(monkeypatch)

    async with session_factory() as session:
        answer = await generator.answer("how many unclaimed users", session, tid)

    assert not answer.ok
    assert answer.reason == "generation_exhausted"
    assert db.executions == []


async def test_missing_param_never_executes(session_factory, executable_tenant, monkeypatch):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM(MISSING_PARAM_ANSWER)
    generator = make_generator(llm, max_attempts=1)
    db = FixtureExternalDatabase(metadata=dict(LIVE_METADATA))
    _patch_live_database_unreachable(monkeypatch)

    async with session_factory() as session:
        answer = await generator.answer("who is unclaimed", session, tid)

    assert not answer.ok
    assert answer.reason == "generation_exhausted"
    assert db.executions == []


async def test_retry_prompt_carries_reason_and_reference(session_factory, executable_tenant, monkeypatch):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM(UNAPPROVED_COLUMN_ANSWER, VALID_ANSWER)
    generator = make_generator(llm)
    db = FixtureExternalDatabase(metadata=dict(LIVE_METADATA), rows=[{"count": 1}])
    _patch_live_database(monkeypatch, db)

    async with session_factory() as session:
        answer = await generator.answer("how many unclaimed users", session, tid)

    assert answer.ok
    assert llm.call_count == 2
    assert "unapproved_column" in llm.prompts[1]
    assert "ssn" in llm.prompts[1]
    # The first (rejected) attempt never touched the tenant database.
    assert db.executions == [] or len(db.executions) == 1


async def test_attempts_bounded_to_three(session_factory, executable_tenant, monkeypatch):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM(UNAPPROVED_COLUMN_ANSWER, UNAPPROVED_COLUMN_ANSWER, UNAPPROVED_COLUMN_ANSWER)
    generator = make_generator(llm)
    _patch_live_database_unreachable(monkeypatch)

    async with session_factory() as session:
        answer = await generator.answer("how many unclaimed users", session, tid)

    assert llm.call_count == 3
    assert answer.reason == "generation_exhausted"


async def test_accepted_statement_executes_once_after_drift(session_factory, executable_tenant, monkeypatch):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM(UNAPPROVED_COLUMN_ANSWER, VALID_ANSWER)
    generator = make_generator(llm)
    db = CountingFixtureExternalDatabase(metadata=dict(LIVE_METADATA), rows=[{"count": 2}])
    _patch_live_database(monkeypatch, db)

    async with session_factory() as session:
        answer = await generator.answer("how many unclaimed users", session, tid)

    assert answer.ok
    assert db.introspect_calls == 1
    assert len(db.executions) == 1


async def test_oversized_schema_context_fails_closed(session_factory, executable_tenant, monkeypatch):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM(VALID_ANSWER)
    generator = make_generator(llm)
    generator.max_context_chars = 1
    _patch_live_database_unreachable(monkeypatch)

    async with session_factory() as session:
        answer = await generator.answer("how many unclaimed users", session, tid)

    assert answer.reason == "schema_context_too_large"
    assert llm.call_count == 0


async def test_rejected_attempt_logs_no_sql_or_params(session_factory, executable_tenant, monkeypatch, caplog):
    tid = executable_tenant["tenant_id"]
    llm = FakeLLM(UNAPPROVED_COLUMN_ANSWER, VALID_ANSWER)
    generator = make_generator(llm)
    db = FixtureExternalDatabase(metadata=dict(LIVE_METADATA), rows=[{"count": 1}])
    _patch_live_database(monkeypatch, db)

    with caplog.at_level("INFO"):
        async with session_factory() as session:
            answer = await generator.answer("how many unclaimed users", session, tid)

    assert answer.ok
    rejection_records = [
        r for r in caplog.records
        if r.name == gen_mod.__name__ and getattr(r, "reason", None) == "unapproved_column"
    ]
    assert rejection_records
    assert rejection_records[0].attempt == 1
    for record in caplog.records:
        message = record.getMessage()
        assert "SELECT p.ssn" not in message
        assert '"params"' not in message


def test_prompt_functions_match_validator_allowlist():
    match = None
    for line in EXTERNAL_SQL_SYSTEM_PROMPT.splitlines():
        if "The only functions you may use are:" in line:
            match = line
            break
    assert match is not None
    functions_text = match.split(":", 1)[1].strip().rstrip(".")
    prompt_functions = {f.strip() for f in functions_text.split(",")}
    assert prompt_functions == validator_mod._ALLOWED_FUNCTIONS
