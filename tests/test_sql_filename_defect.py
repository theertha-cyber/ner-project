"""A query that constrains `documents.filename` to a person's name returns zero rows
while looking correct — filenames are "Resume 4.pdf", not "Arjun". That was classified
SUCCESS and never retried, so the chat answer fell back to prose with no entity data
in it at all. Observed SQL:

    ... WHERE de.entity_type = 'TOOL_FRAMEWORK' AND d.filename ILIKE '%arjun%'
"""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_OPENAI_API_KEY", "test-key")

import pytest

from src.chat_api.services.sql_generator import (
    _FILENAME_DEFECT_PREFIX,
    SQLAttempt,
    SQLAttemptOutcome,
    SQLGenerator,
    _filename_filter_literals,
    _render_attempt_feedback,
)
from src.shared.entity_views import EntityDefinitionSpec, build_query_surface


class TestFilenameFilterLiterals:
    def test_ilike_literal_is_extracted_without_wildcards(self):
        sql = "SELECT 1 FROM documents d WHERE d.filename ILIKE '%arjun%' LIMIT 100"
        assert _filename_filter_literals(sql) == ["arjun"]

    def test_equality_literal_is_extracted(self):
        sql = "SELECT 1 FROM documents WHERE filename = 'Resume 4.pdf' LIMIT 100"
        assert _filename_filter_literals(sql) == ["Resume 4.pdf"]

    def test_query_with_no_filename_filter_yields_nothing(self):
        sql = "SELECT d.filename AS document_name FROM documents d LIMIT 100"
        assert _filename_filter_literals(sql) == []

    def test_selecting_filename_is_not_a_filter(self):
        sql = (
            "SELECT de.entity_value, d.filename AS document_name FROM document_entities de "
            "JOIN documents d ON d.id = de.document_id WHERE de.entity_type = 'TOOL_FRAMEWORK' LIMIT 100"
        )
        assert _filename_filter_literals(sql) == []


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    """Answers the existence probe from a set of filenames the tenant supposedly has."""

    def __init__(self, filenames):
        self.filenames = filenames
        self.probes = []

    async def execute(self, statement, params=None):
        if params and "pattern" in params:
            literal = params["pattern"].strip("%").lower()
            self.probes.append(literal)
            match = any(literal in f.lower() for f in self.filenames)
            return _FakeResult((1,) if match else None)
        return _FakeResult(None)


@pytest.mark.asyncio
class TestFilenameDefectDetection:
    async def test_person_name_not_in_any_filename_is_a_defect(self):
        gen = SQLGenerator.__new__(SQLGenerator)
        session = _FakeSession(["Resume 4.pdf", "Resume - Hannah.pdf"])
        sql = (
            "SELECT de.entity_value FROM document_entities de JOIN documents d "
            "ON d.id = de.document_id WHERE de.entity_type = 'TOOL_FRAMEWORK' "
            "AND d.filename ILIKE '%arjun%' LIMIT 100"
        )
        defect = await gen._filename_defect(sql, session, "tenant_x")
        assert defect == f"{_FILENAME_DEFECT_PREFIX}arjun"

    async def test_a_filename_that_really_exists_is_not_a_defect(self):
        """'list the tools in Resume 4.pdf' is a legitimate filename query — a zero-row
        result from it is a real answer and must not trigger a retry."""
        gen = SQLGenerator.__new__(SQLGenerator)
        session = _FakeSession(["Resume 4.pdf"])
        sql = "SELECT 1 FROM documents d WHERE d.filename ILIKE '%Resume 4%' LIMIT 100"
        assert await gen._filename_defect(sql, session, "tenant_x") is None

    async def test_query_without_a_filename_filter_never_probes(self):
        gen = SQLGenerator.__new__(SQLGenerator)
        session = _FakeSession(["Resume 4.pdf"])
        sql = "SELECT entity_value FROM document_entities WHERE entity_type = 'TOOL_FRAMEWORK' LIMIT 100"
        assert await gen._filename_defect(sql, session, "tenant_x") is None
        assert session.probes == []


class TestRetryFeedbackExplainsTheRightDefect:
    """The defect classes changed with the query model; the feedback has to change with them.

    The filename defect survives unaltered — a name is no likelier to be in a filename on the
    relational surface than it was in the EAV one — but its remedy is now a relation or column
    on that surface, not a second join of the entity store. The entity-type defect is gone: the
    generator is never told to filter on `entity_type`, so a defect reported in those terms
    would send the retry to a query model the validator rejects.
    """

    def test_filename_defect_feedback_points_at_the_relation_holding_names(self):
        feedback = _render_attempt_feedback([
            SQLAttempt(
                attempt=1, max_attempts=3, outcome=SQLAttemptOutcome.EMPTY_WITH_DEFECT,
                sql="SELECT 1 FROM subject s WHERE s.filename ILIKE '%arjun%' LIMIT 100",
                row_count=0, defect=f"{_FILENAME_DEFECT_PREFIX}arjun",
            )
        ])

        assert "filename to match 'arjun'" in feedback
        assert "not the subject's name" in feedback
        assert "match the relation or column that holds names instead" in feedback
        assert "entity_type" not in feedback

    def test_no_feedback_branch_reports_a_defect_in_entity_type_terms(self):
        surface = build_query_surface([
            EntityDefinitionSpec(name="Skill", sql_identifier="e_skill"),
        ])
        attempts = [
            SQLAttempt(
                attempt=1, max_attempts=3, outcome=SQLAttemptOutcome.EMPTY_WITH_DEFECT,
                sql="SELECT value FROM e_skill LIMIT 100", row_count=0,
                defect="wrong_relation:oracle|e_employer",
            ),
            SQLAttempt(
                attempt=2, max_attempts=3, outcome=SQLAttemptOutcome.EMPTY_WITH_DEFECT,
                sql="SELECT 1 AS n LIMIT 1", row_count=0, defect="scope:subject, e_skill",
            ),
            SQLAttempt(
                attempt=3, max_attempts=3, outcome=SQLAttemptOutcome.VALIDATION_ERROR,
                sql="SELECT value FROM e_unknown LIMIT 100",
                error="Table 'e_unknown' is not in the whitelist",
            ),
        ]

        feedback = _render_attempt_feedback(attempts, surface)

        assert "entity_type" not in feedback
        assert "document_entities" not in feedback
        # Each branch still explains itself, in relational terms.
        assert "e_employer" in feedback
        assert "restricted to specific documents" in feedback
        assert "The relations you may query are: e_skill, subject." in feedback
