"""Verification for the relational answer channel — verification.md rows 54-58.

The vector guardrail is not enough on its own. `document_entities`, `document_chunks` and
`document_text_spans` are all reachable from generated SQL, so a `COUNT` over another
recruiter's extracted entities would answer a question the retriever would never have
answered. The rewrite mechanism is the one `apply_conversation_scope` established, chosen
because the scope has to survive aggregation, `GROUP BY` and `LIMIT` — none of which an
appended `WHERE` or a post-execution row filter does.
"""

import uuid

import pytest
from sqlalchemy import text

from src.chat_api.services.sql_generator import (
    CONVERSATION_SCOPE_PARAM,
    UPLOADER_SCOPE_PARAM,
    WHITELISTED_TABLES,
    apply_conversation_scope,
    apply_uploader_scope,
    conversation_scope_columns,
    uploader_scope_columns,
)
from src.shared.document_visibility import (
    NO_REQUESTING_USER,
    ROLE_TENANT_ADMIN,
    RequestingUser,
)

pytestmark = [pytest.mark.verification]

MINE = RequestingUser(user_id="recruiter-1", role="business_user")
ADMIN = RequestingUser(user_id="boss", role=ROLE_TENANT_ADMIN)


# --- Rewrite shape (no database needed) --------------------------------------------


class TestUploaderScopeRewrite:
    def test_a_relation_with_its_own_columns_is_constrained_directly(self):
        scoped, n, params = apply_uploader_scope("SELECT id FROM documents", MINE)
        assert n == 1
        assert "SELECT * FROM documents WHERE (ingested_by_kind <> 'human'" in scoped
        assert params == {UPLOADER_SCOPE_PARAM: "recruiter-1"}

    def test_a_relation_without_them_is_reached_through_documents(self):
        scoped, n, _ = apply_uploader_scope(
            "SELECT entity_value FROM document_entities", MINE
        )
        assert n == 1
        assert "document_id IN (SELECT id FROM documents WHERE" in scoped

    def test_chunks_are_constrained_directly_not_through_a_join(self):
        """Migration 056 denormalized the columns onto chunks precisely so this path
        needs no join."""
        scoped, _, _ = apply_uploader_scope("SELECT chunk_text FROM document_chunks", MINE)
        assert "SELECT id FROM documents" not in scoped
        assert "ingested_by_kind" in scoped

    def test_an_alias_is_preserved(self):
        scoped, n, _ = apply_uploader_scope(
            "SELECT e.entity_value FROM document_entities e", MINE
        )
        assert n == 1
        assert scoped.rstrip().endswith(" e")

    def test_an_admin_statement_is_left_untouched(self):
        sql = "SELECT COUNT(*) FROM document_entities"
        scoped, n, params = apply_uploader_scope(sql, ADMIN)
        assert (scoped, n, params) == (sql, 0, {})

    def test_no_requesting_user_narrows_to_source_system_content(self):
        scoped, n, params = apply_uploader_scope("SELECT COUNT(*) FROM document_entities", NO_REQUESTING_USER)
        assert n == 1
        assert "ingested_by_kind <> 'human'" in scoped
        assert "uploaded_by" not in scoped
        assert params == {}

    def test_the_user_is_bound_never_interpolated(self):
        hostile = RequestingUser(user_id="x'; DROP TABLE documents--", role="business_user")
        scoped, _, params = apply_uploader_scope("SELECT id FROM documents", hostile)
        assert "DROP TABLE" not in scoped
        assert params[UPLOADER_SCOPE_PARAM] == "x'; DROP TABLE documents--"

    def test_a_statement_touching_nothing_scopeable_is_unchanged(self):
        sql = "SELECT 1"
        assert apply_uploader_scope(sql, MINE) == (sql, 0, {})


# --- Row 55: scoped before aggregation ---------------------------------------------


class TestScopeSurvivesAggregationAndLimit:
    def test_a_count_is_scoped_inside_the_aggregate(self):
        """Row 55. `COUNT(*)` projects no document id, so a post-execution row filter
        has nothing to filter — the constraint has to be inside the relation."""
        scoped, n, _ = apply_uploader_scope(
            "SELECT COUNT(*) FROM document_entities WHERE entity_type = :t", MINE
        )
        assert n == 1
        assert scoped.index("SELECT * FROM document_entities WHERE") < scoped.index("WHERE entity_type")

    def test_a_group_by_is_scoped_before_grouping(self):
        scoped, n, _ = apply_uploader_scope(
            "SELECT entity_type, COUNT(*) FROM document_entities GROUP BY entity_type", MINE
        )
        assert n == 1
        assert scoped.index("ingested_by_kind") < scoped.index("GROUP BY")

    def test_a_trailing_limit_applies_after_the_scope(self):
        """Row 56. The limit must bound the visible rows, not be consumed by invisible
        ones — the failure this codebase has already had once, with the old
        post-execution filter."""
        scoped, n, _ = apply_uploader_scope(
            "SELECT entity_value FROM document_entities LIMIT 100", MINE
        )
        assert n == 1
        assert scoped.rstrip().endswith("LIMIT 100")
        assert scoped.index("ingested_by_kind") < scoped.index("LIMIT 100")


# --- Row 58: the two scopes compose ------------------------------------------------


class TestScopesCompose:
    def test_both_predicates_are_present_after_both_rewrites(self):
        """Row 58. Applied in the order the execution path applies them."""
        sql = "SELECT chunk_text FROM document_chunks LIMIT 100"
        conv_scoped, conv_n = apply_conversation_scope(sql, "conv-a", conversation_scope_columns())
        both, up_n, params = apply_uploader_scope(conv_scoped, MINE, uploader_scope_columns())

        assert conv_n == 1 and up_n == 1
        assert "conversation_id" in both
        assert "ingested_by_kind" in both
        assert params == {UPLOADER_SCOPE_PARAM: "recruiter-1"}

    def test_neither_scope_replaces_the_other(self):
        sql = "SELECT text FROM document_text_spans LIMIT 100"
        conv_scoped, _ = apply_conversation_scope(sql, "conv-a", conversation_scope_columns())
        both, _, _ = apply_uploader_scope(conv_scoped, MINE, uploader_scope_columns())

        # The second rewrite nests inside the first, so both predicates end up in the
        # statement rather than one overwriting the other. Asserting on the predicates
        # rather than on subquery counts, because the nesting shape is an implementation
        # detail of the rewrite order.
        assert "conversation_id" in both
        assert "ingested_by_kind" in both
        assert CONVERSATION_SCOPE_PARAM in both
        assert UPLOADER_SCOPE_PARAM in both

    def test_the_execution_path_applies_the_uploader_scope_unconditionally(self):
        """The mistake this guards is mirroring `apply_document_scope`, which runs only
        when a caller asked for it. A boundary that applies on request is not one."""
        import inspect

        from src.chat_api.services.sql_generator import SQLGenerator

        source = inspect.getsource(SQLGenerator._run_attempt)
        assert "apply_uploader_scope(" in source
        marker = source.index("apply_uploader_scope(")
        preceding = source[:marker].rstrip().rsplit("\n", 1)[-1].strip()
        assert not preceding.startswith("if "), (
            "the uploader scope must not be applied behind a condition"
        )


# --- Row 57: every scopeable relation is reached -----------------------------------


class TestUploaderScopeCoverageGuard:
    def test_every_whitelisted_table_is_uploader_scopeable(self):
        """Row 57. A relation the generated-SQL path can query and this scope cannot
        narrow is a cross-user read, exactly as the conversation guard says for ADR-014.
        """
        scopeable = uploader_scope_columns()
        missing = [t for t in WHITELISTED_TABLES if t not in scopeable]
        assert missing == [], (
            f"whitelisted but not uploader-scopeable: {missing}"
        )

    def test_the_two_scope_maps_cover_the_same_relations(self):
        """They are the same relations reached the same two ways; a divergence means one
        of them was updated and the other forgotten."""
        assert set(uploader_scope_columns()) == set(conversation_scope_columns())

    def test_a_surface_relation_is_scopeable(self):
        class _Surface:
            table_names = {"tenant_generated_table"}

        assert uploader_scope_columns(_Surface())["tenant_generated_table"] == "document_id"


# --- Row 54: against a real database ------------------------------------------------


@pytest.mark.integration
class TestScopedStatementAgainstPostgres:
    @pytest.mark.asyncio
    async def test_a_scoped_statement_returns_only_visible_rows(self, tenant_schema, engine):
        """Row 54 end to end: the rewritten statement is executed, not just inspected."""
        tenant_id, schema = tenant_schema
        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        mine, theirs = f"doc-{uuid.uuid4()}", f"doc-{uuid.uuid4()}"

        async with session_factory() as session:
            await session.execute(
                text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS ingested_by_kind VARCHAR(32)")
            )
            await session.execute(
                text(f"""
                    CREATE TABLE IF NOT EXISTS {schema}.document_entities (
                        id VARCHAR PRIMARY KEY,
                        document_id VARCHAR NOT NULL,
                        entity_type TEXT NOT NULL,
                        entity_value TEXT NOT NULL,
                        normalized_value TEXT NOT NULL,
                        confidence DOUBLE PRECISION NOT NULL
                    )
                """)
            )
            for doc_id, uploader in ((mine, "recruiter-1"), (theirs, "recruiter-2")):
                await session.execute(
                    text(f"""
                        INSERT INTO {schema}.documents
                            (id, tenant_id, filename, status, purpose, uploaded_by, ingested_by_kind)
                        VALUES (:id, :tid, :fn, 'processed', 'query', :up, 'human')
                    """),
                    {"id": doc_id, "tid": tenant_id, "fn": f"{uploader}.pdf", "up": uploader},
                )
                await session.execute(
                    text(f"""
                        INSERT INTO {schema}.document_entities
                            (id, document_id, entity_type, entity_value, normalized_value, confidence)
                        VALUES (:id, :doc, 'PERSON', :val, :val, 0.9)
                    """),
                    {"id": str(uuid.uuid4()), "doc": doc_id, "val": f"candidate-of-{uploader}"},
                )
            await session.commit()

            scoped, n, params = apply_uploader_scope(
                "SELECT entity_value FROM document_entities LIMIT 100", MINE
            )
            assert n == 1

            await session.execute(text(f"SET search_path TO {schema}"))
            rows = (await session.execute(text(scoped), params)).fetchall()

            # Row 55, in the same seeded schema: a `COUNT` projects no document id, so
            # this is the shape a post-execution row filter could never have fixed.
            counted_sql, _, count_params = apply_uploader_scope(
                "SELECT COUNT(*) AS n FROM document_entities", MINE
            )
            scoped_count = (await session.execute(text(counted_sql), count_params)).scalar()
            unscoped_count = (
                await session.execute(text("SELECT COUNT(*) FROM document_entities"))
            ).scalar()

        values = {r.entity_value for r in rows}
        assert "candidate-of-recruiter-1" in values
        assert "candidate-of-recruiter-2" not in values

        assert unscoped_count == 2
        assert scoped_count == 1, "the aggregate counted a document the user cannot see"
