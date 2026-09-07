"""Log records leave the process, not just the container's stdout.

Verification row 32.

The gap this covers was found after implementation: `loki` was running, provisioned as a
Grafana datasource and receiving nothing, because every process wrote records to stdout
and no process exported them. Nothing failed, because every log scenario asserted on
*emission* — a record on a stream — and none on *delivery*. Grafana's trace-to-logs link
is unusable in that state, which is most of the reason `trace_id` is on every record.

The OTLP exporter package ships in the service images, so these tests substitute an
in-memory exporter for it: what needs asserting is that a record leaves this process with
its context intact, redacted, and without the exporter's own failures feeding back into
it — none of which is a property of the transport.
"""

import io
import json
import logging

import pytest

from src.shared.config import settings
from src.shared.observability import logging_config
from src.shared.observability.context import CONTEXT_FIELDS, reset_request_id, set_request_id
from src.shared.observability.logging_config import build_otlp_log_handler, configure_logging

pytestmark = [pytest.mark.verification]

ENDPOINT = "otel-collector:4317"


@pytest.fixture
def root_logging_restored():
    """`configure_logging` calls `basicConfig(force=True)`, which detaches pytest's own
    root handlers along with everything else."""
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    saved_filters = list(root.filters)
    try:
        yield
    finally:
        for handler in root.handlers:
            if handler not in saved_handlers:
                handler.close()
        root.handlers = saved_handlers
        root.filters = saved_filters
        root.setLevel(saved_level)


@pytest.fixture
def exported(monkeypatch, root_logging_restored):
    """Configure a process the way `init_observability` does, with an in-memory exporter
    standing in for OTLP, and hand back both destinations."""
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import InMemoryLogExporter, SimpleLogRecordProcessor

    exporter = InMemoryLogExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))

    monkeypatch.setattr(settings, "otlp_endpoint", ENDPOINT)
    monkeypatch.setattr(logging_config, "build_log_provider", lambda _service: provider)

    stdout = io.StringIO()

    def _configure(service_name="gateway"):
        configure_logging(service_name, stream=stdout)
        return exporter, stdout

    return _configure


def _bodies(exporter):
    return [json.loads(item.log_record.body) for item in exporter.get_finished_logs()]


def _attributes(exporter):
    return [dict(item.log_record.attributes) for item in exporter.get_finished_logs()]


class TestExportIsConfiguredByTheEndpointAlone:
    """The one setting that turns all three signals off stays the one setting."""

    def test_no_handler_is_built_when_the_endpoint_is_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "otlp_endpoint", "")
        assert build_otlp_log_handler("gateway") is None

    def test_an_endpoint_attaches_a_second_handler(self, exported):
        exported("gateway")
        assert len(logging.getLogger().handlers) == 2, (
            "stdout and the collector, in that order — dropping stdout would take the "
            "records out of `docker logs` to buy nothing"
        )

    def test_an_unavailable_exporter_does_not_stop_the_process_logging(
        self, monkeypatch, root_logging_restored
    ):
        """A telemetry backend that will not start is not an outage."""

        def _explode(_service):
            raise ImportError("opentelemetry.exporter is not installed in this image")

        monkeypatch.setattr(settings, "otlp_endpoint", ENDPOINT)
        monkeypatch.setattr(logging_config, "build_log_provider", _explode)

        stdout = io.StringIO()
        configure_logging("gateway", stream=stdout)
        logging.getLogger("src.gateway.main").info("service_started")

        assert len(logging.getLogger().handlers) == 1
        assert "service_started" in stdout.getvalue()


class TestRecordsReachTheCollector:
    """Row 32 — delivery, not emission."""

    def test_a_record_is_exported_and_written_to_stdout(self, exported):
        exporter, stdout = exported("gateway")
        logging.getLogger("src.gateway.api").info("request_handled")

        bodies = _bodies(exporter)
        assert len(bodies) == 1
        assert bodies[0]["event"] == "request_handled"
        assert bodies[0]["service"] == "gateway"
        assert "request_handled" in stdout.getvalue()

    def test_the_exported_body_is_the_json_line_grafana_matches_on(self, exported):
        """The provisioned Loki datasource derives its trace link from `"trace_id": "..."`
        in the record body. A bare message body breaks that link silently."""
        exporter, _ = exported("gateway")
        logging.getLogger("src.gateway.api").info("request_handled")

        body = exporter.get_finished_logs()[0].log_record.body
        assert json.loads(body)
        for field in CONTEXT_FIELDS:
            assert f'"{field}"' in body

    def test_context_fields_travel_as_attributes(self, exported):
        """A log store queries on attributes, not on the body text, so the correlation
        fields have to be attributes as well as body keys."""
        exporter, _ = exported("chat_api")
        token = set_request_id("abc-123")
        try:
            logging.getLogger("src.chat_api.api").info("answer_returned", extra={"rows": 3})
        finally:
            reset_request_id(token)

        attributes = _attributes(exporter)[0]
        assert attributes["request_id"] == "abc-123"
        assert attributes["service"] == "chat_api"
        assert attributes["rows"] == 3

    def test_null_context_values_are_not_exported_as_attributes(self, exported):
        """They stay present-and-null in the body, where a query can filter on them. As
        OTLP attributes they are neither valid nor useful, and the SDK warns on each."""
        exporter, _ = exported("gateway")
        logging.getLogger("src.gateway.main").info("service_started")

        attributes = _attributes(exporter)[0]
        assert "tenant_id" not in attributes
        assert _bodies(exporter)[0]["tenant_id"] is None


class TestTheExportPathIsRedactedToo:
    """Redaction that only holds on the stdout path is not redaction — the exported copy
    is the one that lands in a queryable store and outlives the container."""

    def test_a_prohibited_field_is_stripped_from_the_exported_record(self, exported):
        exporter, _ = exported("chat_api")
        logging.getLogger("src.chat_api.services.sql_generator").warning(
            "sql_attempt", extra={"sql": "SELECT name FROM candidates WHERE email = 'a@b.c'"}
        )

        attributes = _attributes(exporter)[0]
        assert attributes["sql"] == logging_config.REDACTED
        assert "candidates" not in json.dumps(attributes)

    def test_a_prohibited_value_interpolated_into_the_message_is_stripped(self, exported):
        exporter, _ = exported("chat_api")
        logging.getLogger("src.chat_api.services.sql_generator").warning(
            "sql_attempt sql=%s attempt=%s", "SELECT name FROM candidates", 1
        )

        body = _bodies(exporter)[0]
        assert "candidates" not in json.dumps(body)
        assert logging_config.REDACTED in body["message"]


class TestTheExporterDoesNotFeedItself:
    """An unreachable collector makes the exporter log its failure. Exporting that record
    generates another failure, and the process spends a telemetry outage in a loop."""

    def test_exporter_records_are_not_exported(self, exported):
        exporter, stdout = exported("gateway")
        logging.getLogger("opentelemetry.exporter.otlp.proto.grpc.exporter").error(
            "Failed to export logs to otel-collector:4317, error code: DEADLINE_EXCEEDED"
        )

        assert _bodies(exporter) == []
        assert "Failed to export logs" in stdout.getvalue(), (
            "the failure still has to be visible somewhere"
        )

    def test_application_records_are_unaffected(self, exported):
        exporter, _ = exported("gateway")
        logging.getLogger("src.gateway.api").info("request_handled")

        assert len(_bodies(exporter)) == 1
