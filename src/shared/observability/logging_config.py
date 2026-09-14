"""Structured logging: one root configuration, context injection, and redaction.

Two problems this closes.

First, only `chat_api` ever called `basicConfig`. The other nine processes left the root
logger at WARNING with no handler — uvicorn configures its own three loggers and nothing
else — so every `logger.info` they emitted was discarded before reaching stdout.

Second, records carried sensitive content. `sql_generator` logged the generated SQL at
INFO, and that SQL carries literal filter values drawn from extracted resume data.
Redaction is therefore a filter installed unconditionally by `init_observability`, not a
convention call sites have to remember: the leak that exists today passed code review, so
review is demonstrably not the control.

A denylist contains structured fields reliably and interpolated message strings only
partially. `_KEY_VALUE_PATTERN` covers this codebase's dominant `key=value` message
style — the shape the `sql_attempt` line used — but structured fields remain the required
pattern for anything touching sensitive values.

Records go to two handlers: stdout always, and the OTLP collector whenever
`otlp_endpoint` is set. Stdout alone reaches `docker logs` and nothing else — Loki sat
provisioned and empty for exactly that reason — and a record only joins its trace in
Grafana once it is in a log store next to the spans. Both handlers carry the same two
filters, so redaction is not a property of the stdout path.
"""

import logging
import re
import sys
from typing import Any

from pythonjsonlogger import json as jsonlogger

from src.shared.config import settings
from src.shared.observability.context import CONTEXT_FIELDS, current_context

logger = logging.getLogger(__name__)

REDACTED = "[redacted]"

# Field names whose values may never appear in telemetry. Deliberately blunt: `text` and
# `content` are generic enough to catch fields nobody thought to enumerate, and losing an
# occasional harmless value costs less than one leaked document body.
SENSITIVE_FIELDS = frozenset(
    {
        "sql",
        "prompt",
        "answer",
        "content",
        "text",
        "document_text",
        # A real call site in the extraction worker printed `text_preview=<80 chars of
        # the document>`. `text=` does not match `text_preview=`, so the variants get
        # named explicitly rather than the pattern being widened — widening it to any key
        # containing "text" would swallow `context=`, which is shape, not content.
        "text_preview",
        "preview",
        "snippet",
        "excerpt",
        "entity_value",
        "password",
        "token",
        "authorization",
        "api_key",
    }
)

# `sql=SELECT ...` in an already-interpolated message. Anchored on a word boundary so
# `max_tokens=4` is not mistaken for `token=`, and greedy to end-of-string because the
# values being caught (SQL, prompts) contain spaces.
_KEY_VALUE_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(SENSITIVE_FIELDS)) + r")=(?!\s*$).*?(?=\s+\w+=|$)",
    re.IGNORECASE | re.DOTALL,
)

# Loggers a server framework configures for itself. Uvicorn's `dictConfig` and Celery's
# logging setup both attach their own handlers and set `propagate = False`, so without
# this their records bypass the JSON formatter *and* the redaction filter — and uvicorn's
# access line carries the full request path, query string included, which is exactly where
# a filter value ends up.
_SERVER_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "gunicorn",
    "gunicorn.error",
    "gunicorn.access",
    "celery",
    "celery.app.trace",
    "celery.worker",
)

# Loggers that emit sensitive content as the message itself, where the denylist cannot
# reach it. `sqlalchemy.engine.Engine` echoes every statement *and its bound parameters*
# once its level reaches INFO — so a well-meaning `NER_LOG_LEVEL=DEBUG` would silently
# reinstate the exact leak this change closes, in every service at once, with no `sql=`
# key for the filter to catch. Pinned to WARNING independently of the root level; a
# developer who genuinely wants statement echo can still set it explicitly in a shell.
_SENSITIVE_LIBRARY_LOGGERS = (
    "sqlalchemy.engine",
    "sqlalchemy.engine.Engine",
    "sqlalchemy.pool",
    "asyncpg",
    "openai",
    "httpcore",
)

# Records whose message is a format string with no leading event name of its own.
# Uvicorn's access line begins with the client address, which would otherwise become the
# `event` — useless to group by, and a client IP on every record besides.
_EXPLICIT_EVENTS = {"uvicorn.access": "http_access"}

# Attributes `logging` puts on every record itself. Anything outside this set was passed
# by the call site as an `extra` and belongs in the JSON output.
_STANDARD_RECORD_ATTRS = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
        "pathname", "process", "processName", "relativeCreated", "stack_info",
        "taskName", "thread", "threadName",
    }
)


class RedactionFilter(logging.Filter):
    """Strip prohibited values from every record, whatever the call site passed.

    Runs as a filter rather than inside the formatter so that it applies to the console
    formatter and to any handler a library attached, not only to the JSON path.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__):
            if key.lower() in SENSITIVE_FIELDS:
                record.__dict__[key] = REDACTED

        # Interpolate now: the message is what would be written, and redacting after
        # interpolation is the only way to catch a value that arrived through `args`.
        try:
            message = record.getMessage()
        except Exception:  # a broken format string is the call site's bug, not a leak
            return True
        if "=" in message:
            redacted = _KEY_VALUE_PATTERN.sub(lambda m: f"{m.group(1)}={REDACTED}", message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
        return True


class ContextFilter(logging.Filter):
    """Attach the four correlation fields to every record.

    Always all four, always present. A record emitted at process startup carries them
    with null values rather than omitting them, so a log query that filters on field
    presence does not silently drop startup records.
    """

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service_name
        for key, value in current_context().items():
            setattr(record, key, value)
        if not hasattr(record, "event"):
            record.event = _derive_event(record)
        return True


def _derive_event(record: logging.LogRecord) -> str:
    """The event name, from `extra={"event": ...}` when given and otherwise from the
    first token of the message.

    The existing call sites already write `logger.warning("sql_attempt schema=%s ...")`,
    so deriving from the first token gives them a usable `event` without touching every
    one of them.
    """
    explicit = _EXPLICIT_EVENTS.get(record.name)
    if explicit:
        return explicit
    try:
        message = record.getMessage()
    except Exception:
        return record.name
    first = message.split(maxsplit=1)
    return first[0] if first else record.name


class JsonFormatter(jsonlogger.JsonFormatter):
    """Single-line JSON with `ts`, `level`, `service`, `event` and the four context
    fields, plus whatever `extra` the call site passed."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["ts"] = self.formatTime(record, self.datefmt)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["service"] = getattr(record, "service", None)
        log_record["event"] = getattr(record, "event", None)
        for field in CONTEXT_FIELDS:
            log_record[field] = getattr(record, field, None)
        log_record.pop("taskName", None)


class ConsoleFormatter(logging.Formatter):
    """Human-readable rendering for a developer reading `docker logs` directly.

    Same fields, same redaction — only the serialization differs, selected by
    `NER_LOG_FORMAT=console`.
    """

    default_fmt = "%(asctime)s %(levelname)-7s %(service)s %(name)s %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.default_fmt)

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        context = " ".join(
            f"{key}={value}" for key, value in current_context().items() if value is not None
        )
        return f"{base} [{context}]" if context else base


def _build_formatter() -> logging.Formatter:
    if settings.log_format.lower() == "console":
        return ConsoleFormatter()
    return JsonFormatter("%(message)s")


def build_handler(service_name: str, stream=None) -> logging.StreamHandler:
    """The one handler every process logs through.

    Both filters live here rather than on the root logger: a `Logger`-level filter runs
    only for records logged directly on that logger, not for records propagated up from
    `src.chat_api.services.sql_generator` and its siblings, so root-level filters would
    silently redact nothing. A handler filter runs for every record that reaches it.
    """
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(_build_formatter())
    # Context first, so `event` is derived before redaction can rewrite the message.
    handler.addFilter(ContextFilter(service_name))
    handler.addFilter(RedactionFilter())
    return handler


_celery_logging_suppressed = False


def _adopt_server_loggers() -> None:
    """Route uvicorn's and Celery's own records through this process's handler.

    Uvicorn configures logging when its `Config` is built, which happens before it
    imports the application — so by the time `init_observability` runs at import time,
    uvicorn's handlers are already attached and its loggers are marked non-propagating.
    Detaching them here is what makes `docker logs` one format rather than two.
    """
    for name in _SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True


def _pin_sensitive_library_loggers() -> None:
    """Hold libraries that log sensitive content as the message at WARNING.

    The redaction filter works on field names and on `key=value` runs. A statement echoed
    as the whole message matches neither, so the only control available is not to emit it.
    """
    for name in _SENSITIVE_LIBRARY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _suppress_celery_logging_setup() -> None:
    """Stop Celery reconfiguring logging after us.

    Connecting any receiver to `setup_logging` makes Celery skip its own logging
    configuration entirely — the documented way to keep an application's configuration in
    place. Without it Celery reinstalls its handlers after `celeryd_init` has run, and the
    worker's records revert to plain text.
    """
    global _celery_logging_suppressed
    if _celery_logging_suppressed:
        return
    try:
        from celery.signals import setup_logging
    except ImportError:  # a process without Celery has nothing to suppress
        return
    setup_logging.connect(lambda **_: None, weak=False)
    _celery_logging_suppressed = True


class ExportFeedbackFilter(logging.Filter):
    """Keep the exporter's own records out of the exporter.

    When the collector is unreachable the OTLP exporter logs the failure — at ERROR, once
    per retry. Feeding those records back into the same exporter makes every failed export
    generate another record to fail on: a telemetry outage would become a busy loop, which
    is the failure mode design Decision 7 exists to prevent. They still reach stdout.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith("opentelemetry")


def build_log_provider(service_name: str):
    """The logger provider that batches records to the collector.

    Split out from `build_otlp_log_handler` so a test can substitute an in-memory exporter:
    the OTLP exporter package ships in the service images and is not needed to assert that
    a record leaves this process with the right content.
    """
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    provider = LoggerProvider(resource=Resource.create({"service.name": service_name}))
    # Batched, like the span processor and for the same reason: export happens on a
    # background thread, so an unreachable collector cannot block or fail a request.
    provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(endpoint=settings.otlp_endpoint, insecure=True)
        )
    )
    return provider


def _otlp_handler_class():
    """`LoggingHandler`, minus the null attributes.

    Built lazily because the class is only importable where the OTel SDK is installed.
    The override exists because `ContextFilter` deliberately sets all four context fields
    on every record, null included, and the SDK warns once per null attribute value — a
    warning per record, from a process that is currently trying to ship records.

    The SDK marks this handler deprecated in favour of the one in
    `opentelemetry-instrumentation-logging`, which is not in this project's lock file.
    Taking the deprecation is a one-line swap later; adding a dependency to close a gap
    found after implementation is not.
    """
    from opentelemetry.sdk._logs import LoggingHandler

    class _OtlpLogHandler(LoggingHandler):
        @staticmethod
        def _get_attributes(record: logging.LogRecord):
            attributes = LoggingHandler._get_attributes(record)
            return {key: value for key, value in attributes.items() if value is not None}

    return _OtlpLogHandler


def build_otlp_log_handler(service_name: str, provider=None) -> logging.Handler | None:
    """The second handler, or `None` when log export is off or unavailable.

    Off is the normal state of a bare-metal run and of the test suite: an empty
    `otlp_endpoint` disables all three signals with one setting, and is the rollback if
    export ever misbehaves in production.

    The JSON formatter is attached deliberately, so the exported body is the same single
    line stdout gets rather than the bare message. Grafana's provisioned Loki datasource
    derives its trace link from `"trace_id": "..."` in the record body; the OTLP record
    also carries the trace context natively, and the body is what the link matches on.
    """
    if not settings.otlp_endpoint:
        return None
    try:
        handler = _otlp_handler_class()(
            level=logging.NOTSET,
            logger_provider=provider if provider is not None else build_log_provider(service_name),
        )
    except Exception:
        # Same rule as span and metric export: a telemetry backend that will not start
        # must not stop the process from serving. stdout still has every record.
        logger.warning("log_export_unavailable", exc_info=True)
        return None

    handler.setFormatter(JsonFormatter("%(message)s"))
    handler.addFilter(ContextFilter(service_name))
    handler.addFilter(RedactionFilter())
    handler.addFilter(ExportFeedbackFilter())
    return handler


def configure_logging(service_name: str, stream=None) -> None:
    """Configure the root logger for this process. The only `basicConfig` in `src/`.

    `force=True` because `basicConfig` is otherwise a no-op once anything has attached a
    root handler — which would silently make the effective level depend on import order.
    """
    handlers: list[logging.Handler] = [build_handler(service_name, stream)]
    otlp_handler = build_otlp_log_handler(service_name)
    if otlp_handler is not None:
        handlers.append(otlp_handler)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )
    _adopt_server_loggers()
    _pin_sensitive_library_loggers()
    _suppress_celery_logging_setup()
