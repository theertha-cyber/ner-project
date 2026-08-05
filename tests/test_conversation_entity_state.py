import pytest
from sqlalchemy import text

from src.chat_api.services import conversation_entity_state as conv_state
from src.chat_api.services.entity_resolver import Candidate

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


@pytest.fixture
async def state_schema(engine, setup_database, tenant_schema):
    tid, schema = tenant_schema
    async with engine.begin() as conn:
        await conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.conversation_entity_state (
                conversation_id VARCHAR PRIMARY KEY,
                pending_original_message TEXT,
                pending_mention TEXT,
                pending_candidates JSONB,
                pending_reask_count INTEGER NOT NULL DEFAULT 0,
                resolved_document_id VARCHAR,
                resolved_entity_value TEXT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
    yield tid, schema
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP TABLE IF EXISTS {schema}.conversation_entity_state"))


class TestPendingClarificationLifecycle:
    """Covers verification.md rows 39, 41, 46, 47, 48, 49."""

    async def test_write_then_read_in_separate_session(self, engine, state_schema, db_session):
        tid, schema = state_schema
        candidates = [Candidate(document_id="doc-1", name="Sreelakshmi R", organization="SEO Technologies")]
        await conv_state.store_pending_clarification(db_session, schema, "conv-1", "Tell me about Sreelakshmi", "Sreelakshmi", candidates)
        await db_session.commit()

        from sqlalchemy.ext.asyncio import async_sessionmaker
        other_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with other_factory() as other_session:
            read_back = await conv_state.read_state(other_session, schema, "conv-1")

        assert read_back.pending_original_message == "Tell me about Sreelakshmi"
        assert read_back.pending_mention == "Sreelakshmi"
        assert len(read_back.pending_candidates) == 1
        assert read_back.pending_candidates[0].document_id == "doc-1"

    async def test_second_clarification_replaces_first(self, state_schema, db_session):
        tid, schema = state_schema
        c1 = [Candidate(document_id="doc-1", name="A")]
        c2 = [Candidate(document_id="doc-2", name="B"), Candidate(document_id="doc-3", name="C")]
        await conv_state.store_pending_clarification(db_session, schema, "conv-1", "first question", "A", c1)
        await conv_state.store_pending_clarification(db_session, schema, "conv-1", "second question", "B", c2)

        count = await db_session.execute(text(f"SELECT COUNT(*) FROM {schema}.conversation_entity_state WHERE conversation_id = 'conv-1'"))
        assert count.scalar() == 1

        state = await conv_state.read_state(db_session, schema, "conv-1")
        assert state.pending_original_message == "second question"
        assert len(state.pending_candidates) == 2

    async def test_reask_then_abandon(self, state_schema, db_session):
        tid, schema = state_schema
        candidates = [Candidate(document_id="doc-1", name="A"), Candidate(document_id="doc-2", name="B")]
        await conv_state.store_pending_clarification(db_session, schema, "conv-1", "q", "A", candidates)

        state = await conv_state.read_state(db_session, schema, "conv-1")
        assert state.pending_reask_count == 0

        await conv_state.increment_reask(db_session, schema, "conv-1", state.pending_reask_count)
        state = await conv_state.read_state(db_session, schema, "conv-1")
        assert state.pending_reask_count == 1
        assert state.has_pending_clarification

        await conv_state.clear_pending(db_session, schema, "conv-1")
        state = await conv_state.read_state(db_session, schema, "conv-1")
        assert not state.has_pending_clarification

    async def test_binding_set_after_selection_and_pending_cleared(self, state_schema, db_session):
        tid, schema = state_schema
        candidates = [Candidate(document_id="doc-1", name="A")]
        await conv_state.store_pending_clarification(db_session, schema, "conv-1", "q", "A", candidates)
        await conv_state.set_binding(db_session, schema, "conv-1", "doc-1", "A")
        await conv_state.clear_pending(db_session, schema, "conv-1")

        state = await conv_state.read_state(db_session, schema, "conv-1")
        assert not state.has_pending_clarification
        assert state.has_binding
        assert state.resolved_document_id == "doc-1"


class TestBindingLifecycle:
    """Covers verification.md rows 54-58 at the persistence layer."""

    async def test_set_and_read_binding(self, state_schema, db_session):
        tid, schema = state_schema
        await conv_state.set_binding(db_session, schema, "conv-1", "doc-1", "Sreelakshmi R")
        state = await conv_state.read_state(db_session, schema, "conv-1")
        assert state.has_binding
        assert state.resolved_document_id == "doc-1"
        assert state.resolved_entity_value == "Sreelakshmi R"

    async def test_replace_binding(self, state_schema, db_session):
        tid, schema = state_schema
        await conv_state.set_binding(db_session, schema, "conv-1", "doc-1", "A")
        await conv_state.set_binding(db_session, schema, "conv-1", "doc-9", "Arjun")
        state = await conv_state.read_state(db_session, schema, "conv-1")
        assert state.resolved_document_id == "doc-9"

    async def test_clear_binding(self, state_schema, db_session):
        tid, schema = state_schema
        await conv_state.set_binding(db_session, schema, "conv-1", "doc-1", "A")
        await conv_state.clear_binding(db_session, schema, "conv-1")
        state = await conv_state.read_state(db_session, schema, "conv-1")
        assert not state.has_binding


class TestTenantIsolation:
    """Covers verification.md row 40."""

    async def test_pending_state_is_schema_scoped(self, engine, setup_database, tenant_schema, db_session):
        tid_a, schema_a = tenant_schema
        schema_b = "tenant_isolation_check_b"
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_b}"))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema_b}.conversation_entity_state (
                    conversation_id VARCHAR PRIMARY KEY, pending_original_message TEXT, pending_mention TEXT,
                    pending_candidates JSONB, pending_reask_count INTEGER NOT NULL DEFAULT 0,
                    resolved_document_id VARCHAR, resolved_entity_value TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema_a}.conversation_entity_state (
                    conversation_id VARCHAR PRIMARY KEY, pending_original_message TEXT, pending_mention TEXT,
                    pending_candidates JSONB, pending_reask_count INTEGER NOT NULL DEFAULT 0,
                    resolved_document_id VARCHAR, resolved_entity_value TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
        try:
            await conv_state.set_binding(db_session, schema_a, "conv-shared-id", "doc-1", "A")
            state_b = await conv_state.read_state(db_session, schema_b, "conv-shared-id")
            assert not state_b.has_binding
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_b} CASCADE"))
                await conn.execute(text(f"DROP TABLE IF EXISTS {schema_a}.conversation_entity_state"))
