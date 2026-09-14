"""`sql_attempt` records the shape of the query, never the query.

Verification row 12. Supersedes `tests/test_chat_api_sql_logging.py`, which pinned the
opposite behaviour.

That earlier test was right about the problem it was solving — the line was unreachable,
because nothing configured logging — and wrong about the fix. Making the line reachable
made it a leak: the generated SQL carries literal filter values drawn from extracted
resume data, so `sql_attempt … sql=SELECT … WHERE entity_value = 'Priya Raman'` put tenant
personal data into an application log. ADR-001 extends tenant isolation to logs, and Exit
Gate 3 requires an automated scan rather than review.

Reachability is now pinned in `tests/shared/test_observability_logging.py`; what is
pinned here is that the line answers the questions it was actually read for — which
attempt, what outcome, what defect class, how many rows, how long — without the statement.
"""

import io
import json
import logging
from types import SimpleNamespace

import pytest

from src.chat_api.services.sql_generator import SQLGenerator
from src.shared.observability.logging_config import build_handler

# `asyncio_mode = auto` (pytest.ini) collects the async tests here; an explicit asyncio
# mark would also be applied to this module's sync tests and warn.
pytestmark = [pytest.mark.verification]

SCHEMA = "tenant_acme"
LEAKED_VALUE = "Priya Raman"
GOOD_SQL = (
    "SELECT e.document_id, d.filename AS document_name, e.entity_value "
    "FROM document_entities e JOIN documents d ON d.id = e.document_id "
    f"WHERE e.entity_type = 'PROGRAMMING_LANGUAGE' AND e.entity_value = '{LEAKED_VALUE}' LIMIT 100"
)
BAD_TABLE_SQL = "SELECT * FROM pg_authid LIMIT 10"

SHAPE_FIELDS = ("attempt", "max_attempts", "outcome", "rows", "duration_ms", "schema")


class _FakeResult:
    def __init__(self, rows=(), columns=()):
        self._rows, self._columns = list(rows), list(columns)

    def fetchall(self):
        return list(self._rows)

    def keys(self):
        return list(self._columns)

    def first(self):
        return None


class FakeSession:
    """Answers the profile queries from canned tables and every data query with one row."""

    def __init__(self):
        self.statements: list[str] = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        if "SELECT DISTINCT entity_type" in sql:
            return _FakeResult([("PROGRAMMING_LANGUAGE",), ("NAME",)], ["entity_type"])
        if "ROW_NUMBER() OVER" in sql:
            return _FakeResult([], ["entity_type", "normalized_value"])
        if sql.strip().upper().startswith("SET"):
            return _FakeResult()
        return _FakeResult(
            [("doc-1", "Resume 4.pdf", "Python")],
            ["document_id", "document_name", "entity_value"],
        )

    async def rollback(self):
        return None


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        nxt = self.responses.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=nxt))])


def _generator(*responses) -> SQLGenerator:
    generator = SQLGenerator()
    generator.client = FakeLLM(*responses)
    return generator


def _sql_attempt_records(caplog):
    return [record for record in caplog.records if getattr(record, "event", None) == "sql_attempt"
            or record.getMessage().startswith("sql_attempt")]


class TestTheAttemptIsLoggedByShape:
    async def test_a_successful_attempt_records_every_shape_field(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.chat_api.services.sql_generator"):
            await _generator(GOOD_SQL).generate_and_execute("who knows python", FakeSession(), SCHEMA)

        record = _sql_attempt_records(caplog)[-1]
        assert record.levelno == logging.INFO
        for field in SHAPE_FIELDS:
            assert hasattr(record, field), f"`{field}` is one of the questions this line is read for"
        assert record.attempt == 1
        assert record.rows == 1
        assert record.schema == SCHEMA
        assert isinstance(record.duration_ms, int)

    async def test_a_failed_attempt_still_logs_at_warning(self, caplog):
        """A rejected statement has to be visible even when INFO is turned off."""
        with caplog.at_level(logging.WARNING, logger="src.chat_api.services.sql_generator"):
            try:
                await _generator(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL).generate_and_execute(
                    "who knows python", FakeSession(), SCHEMA
                )
            except Exception:
                pass

        records = _sql_attempt_records(caplog)
        assert records, "a rejected attempt must still be logged"
        assert all(record.levelno == logging.WARNING for record in records)
        assert all(getattr(record, "outcome", None) for record in records)


class TestTheStatementNeverReachesTheRecord:
    async def test_no_record_carries_the_generated_sql(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="src.chat_api.services.sql_generator"):
            await _generator(GOOD_SQL).generate_and_execute("who knows python", FakeSession(), SCHEMA)

        for record in caplog.records:
            rendered = record.getMessage() + json.dumps(
                {key: str(value) for key, value in record.__dict__.items()}
            )
            assert LEAKED_VALUE not in rendered, "an extracted entity value reached a log record"
            assert "document_entities" not in rendered, "the generated statement reached a log record"

    async def test_the_emitted_json_carries_shape_and_not_content(self, caplog):
        """End to end through the real handler, since that is what `docker logs` sees."""
        buffer = io.StringIO()
        handler = build_handler("chat_api", stream=buffer)
        logger = logging.getLogger("src.chat_api.services.sql_generator")
        saved, saved_propagate = list(logger.handlers), logger.propagate
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        try:
            await _generator(GOOD_SQL).generate_and_execute("who knows python", FakeSession(), SCHEMA)
        finally:
            logger.handlers, logger.propagate = saved, saved_propagate

        emitted = buffer.getvalue()
        assert LEAKED_VALUE not in emitted
        assert "SELECT" not in emitted

        record = next(
            json.loads(line)
            for line in emitted.splitlines()
            if line.strip() and json.loads(line).get("event") == "sql_attempt"
        )
        assert record["outcome"] == "success"
        assert record["rows"] == 1
        assert record["event"] == "sql_attempt"
        assert "sql" not in record
