"""Shared observability: one entry point, called once per process.

Ten deployable processes — eight FastAPI services and two Celery workers — each call
`init_observability(service_name)` at start. That call is the whole per-service edit;
everything else lives here.

Why one module rather than a documented convention: the repository already demonstrates
the alternative's failure mode. Eight copies of `tenant_context.py` each generated a
request identifier, and because they were written independently, none forwarded it, so an
identifier did not survive a single hop. Correlation is a property of the whole system,
so it has exactly one implementation.

Order matters in `init_observability`: logging first, so a failure in tracing setup is
itself logged through the configured handler rather than into a root logger that has none.
"""

from src.shared.observability.context import (
    current_context,
    get_request_id,
    get_tenant_id,
    get_trace_id,
    get_user_hash,
    reset_context,
    set_request_id,
    set_tenant_id,
    set_user_hash,
)
from src.shared.observability.identity import hash_user_id
from src.shared.observability.middleware import ObservabilityMiddleware

__all__ = [
    "init_observability",
    "ObservabilityMiddleware",
    "hash_user_id",
    "current_context",
    "get_request_id",
    "get_tenant_id",
    "get_trace_id",
    "get_user_hash",
    "set_request_id",
    "set_tenant_id",
    "set_user_hash",
    "reset_context",
]


def init_observability(service_name: str, app=None) -> None:
    """Configure logging, tracing, metrics and correlation propagation for one process.

    `app` is supplied by the eight FastAPI services and omitted by the two Celery
    workers, which have no HTTP server: they export metrics over OTLP instead of exposing
    a scrape endpoint.
    """
    from src.shared.observability import metrics, propagation, tracing
    from src.shared.observability.logging_config import configure_logging

    configure_logging(service_name)
    tracing.init_tracing(service_name)
    propagation.instrument_httpx()
    propagation.instrument_celery()

    if app is not None:
        tracing.instrument_app(app)
        metrics.instrument_app(app, service_name)
        app.add_middleware(ObservabilityMiddleware)
    else:
        metrics.init_worker_metrics(service_name)
