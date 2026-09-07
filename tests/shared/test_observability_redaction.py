"""A prohibited field cannot reach an emitted record.

Verification row 13.

The control has to be a filter rather than a convention, because the convention already
failed: `sql_generator` logged the generated SQL — carrying literal filter values drawn
from extracted resume data — at INFO, and that line passed code review. So the assertion
here is not "call sites behave" but "a misbehaving call site is contained".

Both shapes are covered: a structured `extra` field, and a value interpolated into the
message under a `key=value` run, which is this codebase's dominant logging style.
"""

import io
import json
import logging

import pytest

from src.shared.observability.logging_config import (
    REDACTED,
    SENSITIVE_FIELDS,
    build_handler,
)

pytestmark = [pytest.mark.verification]

LEAKED = "Priya Raman"
LEAKED_SQL = "SELECT entity_value FROM document_entities WHERE entity_value = 'Priya Raman'"


@pytest.fixture
def emit():
    """Emit through the real handler `init_observability` installs and return the records
    it wrote, parsed. Capturing with `caplog` instead would test pytest's handler, which
    carries none of the filters that are the thing under test."""
    buffer = io.StringIO()
    handler = build_handler("test-service", stream=buffer)
    logger = logging.getLogger("tests.redaction")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    def _emit(message, *args, **kwargs):
        buffer.truncate(0)
        buffer.seek(0)
        logger.info(message, *args, **kwargs)
        return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]

    yield _emit
    logger.handlers = []


class TestStructuredFieldsAreStripped:
    @pytest.mark.parametrize("field", sorted(SENSITIVE_FIELDS))
    def test_every_prohibited_field_name_is_stripped(self, field, emit):
        records = emit("probe", extra={field: LEAKED})

        assert len(records) == 1
        record = records[0]
        assert record[field] == REDACTED
        assert LEAKED not in json.dumps(record)

    def test_a_permitted_field_survives(self, emit):
        """Redaction must not swallow the shape fields that replace the content — an
        event with nothing left on it is no more diagnosable than no event."""
        records = emit("sql_attempt", extra={"rows": 12, "duration_ms": 41, "outcome": "success"})

        assert records[0]["rows"] == 12
        assert records[0]["duration_ms"] == 41
        assert records[0]["outcome"] == "success"


class TestLibrariesThatLogContentAsTheMessage:
    """The denylist reaches field names and `key=value` runs. A statement echoed as the
    entire message matches neither, so those loggers are held below the level that emits
    it."""

    @pytest.mark.parametrize(
        "name", ["sqlalchemy.engine", "sqlalchemy.engine.Engine", "asyncpg", "openai"]
    )
    def test_the_logger_is_pinned_above_info(self, name):
        import logging as logging_module

        from src.shared.observability.logging_config import configure_logging

        root = logging_module.getLogger()
        saved_handlers, saved_level = list(root.handlers), root.level
        try:
            configure_logging("gateway", stream=io.StringIO())
            assert logging_module.getLogger(name).level >= logging_module.WARNING, (
                f"`{name}` at INFO echoes statements and bound parameters as the message, "
                "which no field-name denylist can redact"
            )
        finally:
            root.handlers, root.level = saved_handlers, saved_level

    def test_a_debug_root_level_does_not_unpin_them(self, monkeypatch):
        """The failure mode this exists for: someone sets `NER_LOG_LEVEL=DEBUG` to
        diagnose something and turns on full SQL echo across all ten services."""
        import logging as logging_module

        from src.shared.config import settings
        from src.shared.observability.logging_config import configure_logging

        monkeypatch.setattr(settings, "log_level", "DEBUG")
        root = logging_module.getLogger()
        saved_handlers, saved_level = list(root.handlers), root.level
        try:
            configure_logging("gateway", stream=io.StringIO())
            assert root.level == logging_module.DEBUG
            assert logging_module.getLogger("sqlalchemy.engine").level >= logging_module.WARNING
        finally:
            root.handlers, root.level = saved_handlers, saved_level


class TestInterpolatedMessagesAreStripped:
    def test_a_value_interpolated_under_a_prohibited_key_is_stripped(self, emit):
        records = emit("sql_attempt schema=%s rows=%d sql=%s", "tenant_acme", 3, LEAKED_SQL)

        message = records[0]["message"]
        assert "sql=[redacted]" in message
        assert LEAKED not in json.dumps(records[0])
        assert "document_entities" not in message
        # The shape around it survives, so the line stays useful.
        assert "schema=tenant_acme" in message
        assert "rows=3" in message

    def test_a_key_that_merely_ends_in_a_prohibited_word_is_left_alone(self, emit):
        """`max_tokens=4` is a shape field, not a credential. A word-boundary miss here
        would quietly redact half the platform's diagnostics."""
        records = emit("llm_call max_tokens=%d", 4)

        assert "max_tokens=4" in records[0]["message"]

    def test_a_message_with_no_assignment_is_untouched(self, emit):
        records = emit("extraction_started")

        assert records[0]["message"] == "extraction_started"
