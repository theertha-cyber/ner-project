"""The generated SQL is logged but was never reachable.

`sql_generator` emits an `sql_attempt … sql=%s` line at INFO for every attempt, and
nothing in the codebase configured logging. Python's root logger defaults to WARNING with
no handlers, and uvicorn configures only its own three loggers, so the line was discarded
before it could reach `docker logs`. Diagnosing a wrong query meant inferring its shape
from row counts against the database.

These tests pin the emission, not the handler wiring: that the line exists, carries the
executed SQL and the row count, and rises to WARNING when the attempt failed.
"""

import logging
from types import SimpleNamespace

import pytest

from src.chat_api.services.sql_generator import SQLGenerator
from src.shared.config import settings

# `asyncio_mode = auto` (pytest.ini) collects the async tests here; an explicit asyncio
# mark would also be applied to this module's sync tests and warn.
pytestmark = [pytest.mark.verification]

SCHEMA = "tenant_acme"
GOOD_SQL = (
    "SELECT e.document_id, d.filename AS document_name, e.entity_value "
    "FROM document_entities e JOIN documents d ON d.id = e.document_id "
    "WHERE e.entity_type = 'PROGRAMMING_LANGUAGE' LIMIT 100"
)
BAD_TABLE_SQL = "SELECT * FROM pg_authid LIMIT 10"


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
        return _FakeResult([("doc-1", "Resume 4.pdf", "Python")],
                           ["document_id", "document_name", "entity_value"])

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


class TestGeneratedSQLIsLogged:
    async def test_successful_attempt_logs_the_executed_sql_at_info(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.chat_api.services.sql_generator"):
            await _generator(GOOD_SQL).generate_and_execute("who knows python", FakeSession(), SCHEMA)

        line = next(r for r in caplog.records if "sql_attempt" in r.getMessage())
        message = line.getMessage()
        assert line.levelno == logging.INFO
        assert "document_entities" in message, "the executed statement must appear in the line"
        assert "rows=1" in message
        assert f"schema={SCHEMA}" in message

    async def test_failed_attempt_logs_at_warning(self, caplog):
        """A rejected statement has to be visible even when INFO is turned off."""
        with caplog.at_level(logging.WARNING, logger="src.chat_api.services.sql_generator"):
            try:
                await _generator(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL).generate_and_execute(
                    "who knows python", FakeSession(), SCHEMA
                )
            except Exception:
                pass

        warnings = [r for r in caplog.records if "sql_attempt" in r.getMessage()]
        assert warnings, "a rejected attempt must still be logged"
        assert all(r.levelno == logging.WARNING for r in warnings)


class TestLogLevelIsConfigurable:
    def test_settings_expose_a_log_level_defaulting_to_info(self):
        """Without this the sql_attempt line stays below the root logger's threshold."""
        assert settings.log_level.upper() == "INFO"

    def test_configure_logging_puts_root_at_info_with_a_handler(self):
        """`configure_logging` in main.py is what makes the INFO line reachable — uvicorn
        never touches the root logger. Root state is global, so it is restored
        afterwards rather than left at whatever this test set it to."""
        from src.chat_api.main import configure_logging

        root = logging.getLogger()
        saved_level, saved_handlers = root.level, list(root.handlers)
        try:
            configure_logging()
            assert root.level <= logging.INFO
            assert root.handlers, "a handler is required for the line to reach stdout"
        finally:
            root.setLevel(saved_level)
            root.handlers = saved_handlers
