"""Structural document-scope enforcement for structured retrieval — verification.md
rows 16-21, 39, 40, 54.

The previous mechanism appended `(restrict results to document_id = '…')` to the
natural-language question and asked a second model to honour it, backed by a
post-execution row filter that ran *after* `LIMIT 100`. A tenant-wide query whose first
100 rows excluded the resolved document therefore post-filtered to zero — an empty
answer produced entirely by the scoping mechanism.

The relational surface widens the same hole rather than closing it: `apply_document_scope`
returns the statement untouched when it recognises no reference, so a scoped question against
`subject` would have been answered tenant-wide, silently, with a plausible number. Hence the
resolved scope map and the unscopeable-statement defect.
"""

from types import SimpleNamespace

import pytest

from src.chat_api.services.sql_generator import (
    DOCUMENT_SCOPE_PARAM,
    SQLAttemptOutcome,
    SQLGenerationFailed,
    SQLGenerator,
    apply_document_scope,
    document_scope_columns,
)
from src.shared.entity_views import EntityDefinitionSpec, build_query_surface
from src.shared.retrieval.tools.entity_tools import _scope_to_document_ids
from src.shared.retrieval.tools.base import ArgValidationError

from tests.test_chat_api_sql_retry import FakeLLM, FakeSession, SCHEMA, make_generator

pytestmark = [pytest.mark.verification]

SIMPLE_SQL = (
    "SELECT e.entity_value, d.filename AS document_name FROM document_entities e "
    "JOIN documents d ON d.id = e.document_id LIMIT 100"
)
AGGREGATE_SQL = (
    "SELECT entity_type, COUNT(*) FROM document_entities GROUP BY entity_type LIMIT 100"
)

SUBJECT_SQL = "SELECT s.document_id, s.filename, s.email FROM subject s LIMIT 100"
JOINED_SQL = (
    "SELECT s.filename, k.value FROM e_skill k "
    "JOIN subject s ON s.document_id = k.document_id LIMIT 100"
)
RELATIONAL_AGGREGATE_SQL = (
    "SELECT k.document_id, COUNT(*) AS n FROM e_skill k GROUP BY k.document_id LIMIT 100"
)

SURFACE = build_query_surface([
    EntityDefinitionSpec(name="Skill", sql_identifier="e_skill"),
    EntityDefinitionSpec(name="Email", sql_identifier="e_email", cardinality="single"),
])

# `public.entity_definitions` rows as the resolver reads them: by column name, the same
# access the driver's `Row` gives.
DEFINITION_ROWS = [
    SimpleNamespace(
        tenant_id="acme", name="Skill", sql_identifier="e_skill", cardinality="multi",
        value_kind=None, value_unit=None, description=None, examples=None,
        is_active=True, base_label_mapping=None,
    ),
]


def _scope(sql: str, surface=SURFACE) -> str:
    scoped, _count = apply_document_scope(sql, document_scope_columns(surface))
    return scoped


class TestScopeColumnMap:
    """The map is derived from the resolved surface, never restated beside it."""

    def test_static_tables_keep_their_columns(self):
        columns = document_scope_columns(None)
        assert columns["documents"] == "id"
        assert columns["document_entities"] == "document_id"

    def test_every_relation_on_the_surface_scopes_on_document_id(self):
        columns = document_scope_columns(SURFACE)
        assert columns["subject"] == "document_id"
        assert columns["e_skill"] == "document_id"

    def test_a_relation_off_the_surface_is_not_scopeable(self):
        # `e_email` is `single` now: its retained child table is off the surface, so it is
        # neither validated nor scopeable. Nothing may reach it at all.
        assert "e_email" not in document_scope_columns(SURFACE)


class TestScopeRewriting:
    def test_document_scope_applied_as_bound_predicate(self):
        """verification.md row 39 — the constraint is in the statement, bound, and does
        not depend on the generating model having honoured an instruction in prose."""
        scoped = _scope(SIMPLE_SQL)

        assert f"document_id = ANY(:{DOCUMENT_SCOPE_PARAM})" in scoped
        assert f"id = ANY(:{DOCUMENT_SCOPE_PARAM})" in scoped
        assert "'" not in scoped.split("FROM", 1)[1].replace("AS document_name", "")
        assert "restrict results to" not in scoped

    def test_alias_is_preserved(self):
        scoped = _scope(SIMPLE_SQL)
        # The aliases the statement declared still resolve.
        assert ") e " in scoped
        assert ") d " in scoped
        assert "AS document_entities" not in scoped

    def test_unaliased_reference_gets_the_table_name_as_its_alias(self):
        """A derived table needs a name; using the table's own keeps every qualified
        column reference in the statement resolving."""
        scoped = _scope(AGGREGATE_SQL)
        assert ") AS document_entities" in scoped

    def test_scope_survives_aggregation(self):
        """An aggregate projects no document_id, so a post-execution row filter could
        never have scoped it. The predicate applies underneath the GROUP BY."""
        scoped = _scope(AGGREGATE_SQL)
        assert scoped.index("ANY(") < scoped.index("GROUP BY")

    def test_scope_applied_before_row_limit_truncation(self):
        """verification.md row 40 — the predicate is inside the source, so the row limit
        applies to in-scope rows. Out-of-scope rows cannot fill the limit first."""
        scoped = _scope(SIMPLE_SQL)
        assert scoped.index(f"ANY(:{DOCUMENT_SCOPE_PARAM})") < scoped.rindex("LIMIT 100")

    def test_statement_without_scoped_tables_is_untouched(self):
        sql = "SELECT 1 LIMIT 1"
        assert apply_document_scope(sql, document_scope_columns(SURFACE)) == (sql, 0)


class TestScopeOverTheRelationalSurface:
    """verification.md rows 16-19 — the same rewrite, over the relations the prompt teaches."""

    def test_subject_is_constrained_by_a_bound_predicate(self):
        """Row 16 — and with no identifier literal anywhere in the statement text."""
        scoped = _scope(SUBJECT_SQL)

        assert f"FROM subject WHERE document_id = ANY(:{DOCUMENT_SCOPE_PARAM})" in scoped
        assert ") s " in scoped  # the statement's own alias still resolves
        assert "'" not in scoped

    def test_child_table_and_subject_are_both_constrained(self):
        """Row 17 — a scope that reached only one side of the join would not be a scope."""
        scoped = _scope(JOINED_SQL)

        assert scoped.count(f"ANY(:{DOCUMENT_SCOPE_PARAM})") == 2
        assert f"FROM e_skill WHERE document_id = ANY(:{DOCUMENT_SCOPE_PARAM})" in scoped
        assert f"FROM subject WHERE document_id = ANY(:{DOCUMENT_SCOPE_PARAM})" in scoped

    def test_scope_survives_relational_aggregation(self):
        """Row 18."""
        scoped = _scope(RELATIONAL_AGGREGATE_SQL)
        assert scoped.index("ANY(") < scoped.index("GROUP BY")

    def test_scope_precedes_the_row_limit(self):
        """Row 19."""
        scoped = _scope(JOINED_SQL)
        assert scoped.index(f"ANY(:{DOCUMENT_SCOPE_PARAM})") < scoped.rindex("LIMIT 100")

    def test_a_relation_off_the_surface_is_not_rewritten(self):
        scoped, count = apply_document_scope(
            "SELECT value FROM e_skill LIMIT 10", document_scope_columns(build_query_surface([]))
        )
        assert count == 0
        assert scoped == "SELECT value FROM e_skill LIMIT 10"


class TestScopeArgumentPlumbing:
    def test_tenant_scope_means_no_constraint(self):
        assert _scope_to_document_ids(None) is None
        assert _scope_to_document_ids({"type": "tenant"}) is None

    def test_document_scope_yields_the_identifiers(self):
        assert _scope_to_document_ids({"type": "document", "document_ids": ["D1", "D2"]}) == ["D1", "D2"]

    def test_unknown_scope_type_rejected(self):
        with pytest.raises(ArgValidationError):
            _scope_to_document_ids({"type": "galaxy"})

    def test_document_scope_without_identifiers_rejected(self):
        with pytest.raises(ArgValidationError):
            _scope_to_document_ids({"type": "document"})


@pytest.mark.asyncio
class TestScopeReachesExecution:
    async def test_scope_is_bound_not_interpolated(self):
        llm = FakeLLM(SIMPLE_SQL)
        session = FakeSession(data_results=[[("python", "Resume 1.pdf")]],
                              data_columns=("entity_value", "document_name"))

        rows = await make_generator(llm).generate_and_execute(
            "who knows python?", session, SCHEMA, document_ids=["D1", "D2"],
        )

        executed = session.data_queries[0]
        assert f":{DOCUMENT_SCOPE_PARAM}" in executed
        # The identifiers themselves never appear in the statement text.
        assert "D1" not in executed and "D2" not in executed
        assert rows == [{"entity_value": "python", "document_name": "Resume 1.pdf"}]

    async def test_absent_scope_leaves_the_statement_alone(self):
        llm = FakeLLM(SIMPLE_SQL)
        session = FakeSession(data_results=[[("python", "Resume 1.pdf")]],
                              data_columns=("entity_value", "document_name"))

        await make_generator(llm).generate_and_execute("who knows python?", session, SCHEMA)

        assert DOCUMENT_SCOPE_PARAM not in session.data_queries[0]

    async def test_generated_relations_are_scoped_at_execution(self):
        """Rows 16, 17 through the loop rather than through the rewrite alone: the scope map
        the attempt uses is the one resolved from this tenant's catalog."""
        llm = FakeLLM(JOINED_SQL)
        session = FakeSession(
            entity_definitions=DEFINITION_ROWS,
            data_results=[[("Resume 1.pdf", "python")]],
            data_columns=("filename", "value"),
        )

        await make_generator(llm).generate_and_execute(
            "which skills in this document?", session, SCHEMA, document_ids=["D1"],
        )

        executed = session.data_queries[0]
        assert executed.count(f"ANY(:{DOCUMENT_SCOPE_PARAM})") == 2

    async def test_scope_is_reapplied_to_every_retry(self):
        """Row 21."""
        llm = FakeLLM(SIMPLE_SQL, SIMPLE_SQL)
        session = FakeSession(
            data_results=[Exception("boom"), [("python", "Resume 1.pdf")]],
            data_columns=("entity_value", "document_name"),
        )

        await make_generator(llm).generate_and_execute(
            "who knows python?", session, SCHEMA, document_ids=["D1"],
        )

        assert len(session.data_queries) == 2
        assert all(f":{DOCUMENT_SCOPE_PARAM}" in q for q in session.data_queries)

    async def test_an_unscopeable_scoped_statement_is_a_defect_not_a_success(self):
        """Rows 20, 54 — the statement is not wrong, it is out of scope. Executing it would
        answer a document-scoped question tenant-wide, and the graph's secondary row filter
        cannot catch that: it only drops rows carrying a `document_id`."""
        unscopeable = "SELECT 1 AS n LIMIT 1"
        llm = FakeLLM(unscopeable, unscopeable, unscopeable)
        session = FakeSession(entity_definitions=DEFINITION_ROWS)
        sink: list = []

        with pytest.raises(SQLGenerationFailed):
            await make_generator(llm).generate_and_execute(
                "how many skills in this document?", session, SCHEMA,
                document_ids=["D1"], attempt_sink=sink,
            )

        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.EMPTY_WITH_DEFECT] * 3
        assert session.data_queries == []  # never executed tenant-wide
        assert all(a["defect"].startswith("scope:") for a in sink)

    async def test_an_unscopeable_statement_is_fine_without_a_scope(self):
        """The defect is about the scope, not about the statement."""
        llm = FakeLLM("SELECT 1 AS n LIMIT 1")
        session = FakeSession(data_results=[[(1,)]], data_columns=("n",))

        rows = await make_generator(llm).generate_and_execute("how many?", session, SCHEMA)

        assert rows == [{"n": 1}]

    async def test_scoped_statement_still_passes_validation(self):
        """The scope is applied after validation, so the whitelist decided on the
        statement the model wrote — and the rewrite can only ever narrow it."""
        generator = SQLGenerator.__new__(SQLGenerator)
        scoped = _scope(generator.validate_sql(SIMPLE_SQL))
        # Re-validating the rewritten statement must not reject it: every table it
        # names is still whitelisted.
        assert generator.validate_sql(scoped)

    async def test_scoped_relational_statement_still_passes_validation(self):
        generator = SQLGenerator.__new__(SQLGenerator)
        scoped = _scope(generator.validate_sql(JOINED_SQL, SURFACE))
        assert generator.validate_sql(scoped, SURFACE)
