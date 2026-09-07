"""OpenTelemetry tracing, wired once per process.

Spans come from auto-instrumentation — FastAPI, SQLAlchemy, asyncpg, httpx, redis and
Celery — so no route or query needs per-call-site code, and a request that crosses a
service boundary or an enqueue lands in one trace.

Two properties the design pins down explicitly:

- Export is asynchronous. `BatchSpanProcessor` hands spans to a background thread, so an
  unreachable collector cannot block or fail a request. A telemetry outage must not
  become a platform outage.
- An empty `otlp_endpoint` is a full no-op. That is the state of a bare-metal run and of
  the test suite, and it is the one-setting rollback if export ever causes a problem in
  production — no code change, no redeploy of a different image.
"""

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.shared.config import settings

logger = logging.getLogger(__name__)

_instrumented = False


def _register_instrumentors() -> None:
    """Register the auto-instrumentors, each independently.

    One instrumentor failing — a library absent from this particular process's image, a
    version skew — must not cost the process every other signal, so each is attempted on
    its own and a failure is logged rather than raised.
    """
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    for name, instrumentor in (
        ("sqlalchemy", SQLAlchemyInstrumentor()),
        ("asyncpg", AsyncPGInstrumentor()),
        ("httpx", HTTPXClientInstrumentor()),
        ("redis", RedisInstrumentor()),
        ("celery", CeleryInstrumentor()),
    ):
        try:
            instrumentor.instrument()
        except Exception:
            logger.warning("instrumentation_skipped library=%s", name, exc_info=True)


def build_tracer_provider(service_name: str) -> TracerProvider:
    """Construct this process's provider, with an exporter only if one is configured.

    Kept separate from `init_tracing` because the global provider can be set exactly once
    per process — the SDK refuses a second `set_tracer_provider` — so construction is the
    only part that can be asserted on directly.
    """
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if settings.otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True))
        )
    return provider


def init_tracing(service_name: str) -> None:
    """Install the tracer provider and register auto-instrumentation.

    Idempotent: a second call in the same process is a no-op, which matters because
    `training_service` imports its own Celery app and would otherwise instrument twice.
    """
    global _instrumented
    if _instrumented:
        return
    _instrumented = True

    trace.set_tracer_provider(build_tracer_provider(service_name))
    _register_instrumentors()


def instrument_app(app, tracer_provider=None) -> None:
    """Attach FastAPI instrumentation to one application.

    Separate from `init_tracing` because it needs the app object, which the Celery
    workers do not have. `tracer_provider` overrides the global one — used by tests that
    need a provider of their own, since the global is set once per process.
    """
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    try:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/health/live,/metrics",
            tracer_provider=tracer_provider,
        )
    except Exception:
        logger.warning("instrumentation_skipped library=fastapi", exc_info=True)
