"""Every process logs, at the configured level, with the context keys always present.

Verification rows 1, 3 and 5, plus risk-register items 5 and 7.

Before this change `logging.basicConfig` was called in `chat_api` and nowhere else. The
other nine processes left the root logger at WARNING with no handler — uvicorn configures
only its own three loggers — so every `logger.info` they emitted was constructed,
formatted and then dropped. The `sql_attempt` line was unreachable for exactly this
reason.

Row 5 is the subtle one: a record emitted with no active request carries all four context
keys with a *null* value rather than omitting them. Omitting them looks harmless and
breaks every downstream query that filters on field presence.
"""

import io
import json
import logging

import pytest

from src.shared.config import settings
from src.shared.observability.context import CONTEXT_FIELDS
from src.shared.observability.logging_config import configure_logging

pytestmark = [pytest.mark.verification]


@pytest.fixture
def root_logging_restored():
    """`configure_logging` calls `basicConfig(force=True)`, which detaches every root
    handler — pytest's own included. Without restoring them, this module would silently
    disable log capture for the rest of the session."""
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    saved_filters = list(root.filters)
    try:
        yield
    finally:
        root.handlers = saved_handlers
        root.filters = saved_filters
        root.setLevel(saved_level)


@pytest.fixture
def configured(root_logging_restored):
    """Configure the root logger the way a real process does and hand back its output."""
    buffer = io.StringIO()

    def _configure(service_name="document_service"):
        configure_logging(service_name, stream=buffer)
        return buffer

    return _configure


def _records(buffer):
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


class TestRecordsReachTheStream:
    """Row 1 — a service that previously had no handler now emits."""

    def test_an_info_record_from_a_previously_silent_service_is_written(self, configured):
        buffer = configured("document_service")
        # A logger under one of the six services that never called `basicConfig`.
        logging.getLogger("src.document_service.api.v1.documents").info("document_ingested")

        records = _records(buffer)
        assert len(records) == 1
        assert records[0]["event"] == "document_ingested"
        assert records[0]["service"] == "document_service"

    def test_the_root_logger_ends_up_with_exactly_one_stdout_handler(self, configured):
        configured("gateway")
        stdout_handlers = [
            handler
            for handler in logging.getLogger().handlers
            if type(handler) is logging.StreamHandler
        ]
        assert len(stdout_handlers) == 1, (
            "duplicate handlers double every record, which is how a JSON log store ends "
            "up double-counting error rates"
        )
        # The only other handler a configured process may carry is the OTLP exporter,
        # and only when `otlp_endpoint` is set — it writes to the collector, not to the
        # stream, so it does not duplicate anything in `docker logs`.
        assert len(logging.getLogger().handlers) <= (2 if settings.otlp_endpoint else 1)


class TestServerLoggersAreAdopted:
    """Uvicorn and Celery configure logging for themselves, and their records are the
    majority of what `docker logs` shows.

    Left alone they emit plain text past both the formatter and the redaction filter —
    and uvicorn's access line carries the full request path, query string included, which
    is precisely where a filter value ends up. Confirmed against the running stack before
    this was added: `INFO:     172.18.0.1:42374 - "GET /api/v1/... HTTP/1.1" 500` sat in
    the gateway's output beside correctly-formatted JSON records.
    """

    @pytest.mark.parametrize("name", ["uvicorn", "uvicorn.error", "uvicorn.access", "celery"])
    def test_the_server_logger_propagates_to_our_handler(self, configured, name):
        server_logger = logging.getLogger(name)
        server_logger.handlers = [logging.StreamHandler()]
        server_logger.propagate = False

        configured("gateway")

        assert server_logger.handlers == []
        assert server_logger.propagate is True

    def test_an_access_record_is_emitted_as_json(self, configured):
        buffer = configured("gateway")
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d', "172.18.0.1", "GET", "/api/v1/documents", "1.1", 200
        )

        records = _records(buffer)
        assert len(records) == 1
        assert records[0]["service"] == "gateway"

    def test_an_access_record_gets_a_usable_event_name(self, configured):
        """Deriving it from the message would make the client IP the event name — a
        useless grouping key, and a client address on every record besides."""
        buffer = configured("gateway")
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d', "172.18.0.1", "GET", "/api/v1/documents", "1.1", 200
        )

        assert _records(buffer)[0]["event"] == "http_access"

    def test_a_query_string_on_an_access_record_is_redacted(self, configured):
        """The reason this matters: an access line is the one record that quotes a
        caller-supplied URL back verbatim."""
        buffer = configured("gateway")
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d',
            "172.18.0.1", "GET", "/api/v1/search?text=Priya+Raman", "1.1", 200,
        )

        assert "Priya" not in buffer.getvalue()


class TestLogLevelIsConfigurable:
    """Row 3 — `NER_LOG_LEVEL` governs what is emitted."""

    def test_debug_is_suppressed_at_the_default_level(self, configured, monkeypatch):
        monkeypatch.setattr(settings, "log_level", "INFO")
        buffer = configured()
        logging.getLogger("src.gateway.api.v1.auth").debug("token_refreshed")

        assert _records(buffer) == []

    def test_debug_is_emitted_when_the_level_is_debug(self, configured, monkeypatch):
        monkeypatch.setattr(settings, "log_level", "DEBUG")
        buffer = configured()
        logging.getLogger("src.gateway.api.v1.auth").debug("token_refreshed")

        records = _records(buffer)
        assert len(records) == 1
        assert records[0]["level"] == "DEBUG"


class TestContextKeysOutsideARequest:
    """Row 5 — present, and null, when no request is active."""

    def test_all_four_keys_are_present_with_null_values(self, configured):
        buffer = configured("training_service")
        logging.getLogger("src.training_service.main").info("startup_complete")

        record = _records(buffer)[0]
        for field in CONTEXT_FIELDS:
            assert field in record, f"`{field}` must be present even at startup"
            assert record[field] is None, f"`{field}` must be null, not a placeholder"

    def test_the_record_is_a_single_line_of_json(self, configured):
        buffer = configured()
        logging.getLogger("src.training_service.main").info("startup_complete")

        assert len(buffer.getvalue().strip().splitlines()) == 1

    def test_the_baseline_fields_are_all_emitted(self, configured):
        buffer = configured("annotation_service")
        logging.getLogger("src.annotation_service.main").info("startup_complete")

        record = _records(buffer)[0]
        for field in ("ts", "level", "service", "event"):
            assert record.get(field) is not None
