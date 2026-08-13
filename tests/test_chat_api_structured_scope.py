"""Structural document-scope enforcement for structured retrieval — verification.md
rows 39, 40.

The previous mechanism appended `(restrict results to document_id = '…')` to the
natural-language question and asked a second model to honour it, backed by a
post-execution row filter that ran *after* `LIMIT 100`. A tenant-wide query whose first
100 rows excluded the resolved document therefore post-filtered to zero — an empty
answer produced entirely by the scoping mechanism.
"""

import pytest

from src.chat_api.services.sql_generator import (
    DOCUMENT_SCOPE_PARAM,
    SQLGenerator,
    apply_document_scope,
)
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


class TestScopeRewriting:
    def test_document_scope_applied_as_bound_predicate(self):
        """verification.md row 39 — the constraint is in the statement, bound, and does
        not depend on the generating model having honoured an instruction in prose."""
        scoped = apply_document_scope(SIMPLE_SQL)

        assert f"document_id = ANY(:{DOCUMENT_SCOPE_PARAM})" in scoped
        assert f"id = ANY(:{DOCUMENT_SCOPE_PARAM})" in scoped
        assert "'" not in scoped.split("FROM", 1)[1].replace("AS document_name", "")
        assert "restrict results to" not in scoped

    def test_alias_is_preserved(self):
        scoped = apply_document_scope(SIMPLE_SQL)
        # The aliases the statement declared still resolve.
        assert ") e " in scoped
        assert ") d " in scoped
        assert "AS document_entities" not in scoped

    def test_unaliased_reference_gets_the_table_name_as_its_alias(self):
        """A derived table needs a name; using the table's own keeps every qualified
        column reference in the statement resolving."""
        scoped = apply_document_scope(AGGREGATE_SQL)
        assert ") AS document_entities" in scoped

    def test_scope_survives_aggregation(self):
        """An aggregate projects no document_id, so a post-execution row filter could
        never have scoped it. The predicate applies underneath the GROUP BY."""
        scoped = apply_document_scope(AGGREGATE_SQL)
        assert scoped.index("ANY(") < scoped.index("GROUP BY")

    def test_scope_applied_before_row_limit_truncation(self):
        """verification.md row 40 — the predicate is inside the source, so the row limit
        applies to in-scope rows. Out-of-scope rows cannot fill the limit first."""
        scoped = apply_document_scope(SIMPLE_SQL)
        assert scoped.index(f"ANY(:{DOCUMENT_SCOPE_PARAM})") < scoped.rindex("LIMIT 100")

    def test_statement_without_scoped_tables_is_untouched(self):
        sql = "SELECT 1 LIMIT 1"
        assert apply_document_scope(sql) == sql


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

    async def test_scope_is_reapplied_to_every_retry(self):
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

    async def test_scoped_statement_still_passes_validation(self):
        """The scope is applied after validation, so the whitelist decided on the
        statement the model wrote — and the rewrite can only ever narrow it."""
        generator = SQLGenerator.__new__(SQLGenerator)
        scoped = apply_document_scope(generator.validate_sql(SIMPLE_SQL))
        # Re-validating the rewritten statement must not reject it: every table it
        # names is still whitelisted.
        assert generator.validate_sql(scoped)
