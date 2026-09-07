"""Ambient request context for telemetry.

Threading `request_id`/`tenant_id`/`user_hash` through every call signature would touch
hundreds of functions and be forgotten by the next one written; `request.state` — the
mechanism the per-service middleware uses today — is only reachable where a `Request`
object is in scope, which excludes the service layer and the Celery workers, exactly
where the interesting records are emitted.

`contextvars` is the asyncio-safe store for that: set once by middleware (or by the
Celery task-start hook), read by the log filter and by outbound-call instrumentation,
and automatically inherited by tasks spawned from the request.

Getters return `None` outside a request. That is not the same as absent: the log
formatter emits all four keys with a null value so downstream queries can filter on
field presence without special-casing startup records.
"""

from contextvars import ContextVar, Token
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("ner_request_id", default=None)
_tenant_id: ContextVar[str | None] = ContextVar("ner_tenant_id", default=None)
_user_hash: ContextVar[str | None] = ContextVar("ner_user_hash", default=None)
_trace_id: ContextVar[str | None] = ContextVar("ner_trace_id", default=None)

CONTEXT_FIELDS = ("request_id", "tenant_id", "user_hash", "trace_id")


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str | None) -> Token:
    return _request_id.set(value)


def reset_request_id(token: Token) -> None:
    """Restore the value this context had before `set_request_id`.

    Resetting rather than clearing matters where one context legitimately nests inside
    another — a worker process reused across tasks, a test that drives several requests
    in one event loop — because clearing would leave the outer scope silently
    uncorrelated.
    """
    _request_id.reset(token)


def get_tenant_id() -> str | None:
    return _tenant_id.get()


def set_tenant_id(value: Any | None) -> Token:
    """Tenants are recorded as their UUID — the discriminator ADR-001 already uses for
    schema naming — never as a slug or display name, so telemetry introduces no new
    tenant identifier and no new name mapping to protect."""
    return _tenant_id.set(str(value) if value is not None else None)


def get_user_hash() -> str | None:
    return _user_hash.get()


def set_user_hash(value: str | None) -> Token:
    return _user_hash.set(value)


def set_trace_id(value: str | None) -> Token:
    return _trace_id.set(value)


def get_trace_id() -> str | None:
    """Prefer the currently active span over the stored value.

    The contextvar is what the Celery hook restores and what a caller can pin
    explicitly; the active span is authoritative while one is recording, which is what
    makes a record's `trace_id` equal to the trace id of the spans from the same
    request even when a child span opened after the middleware ran.
    """
    from opentelemetry import trace

    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        return format(span_context.trace_id, "032x")
    return _trace_id.get()


def current_context() -> dict[str, str | None]:
    """The four fields as the log formatter wants them — always present, null when
    there is no active request."""
    return {
        "request_id": get_request_id(),
        "tenant_id": get_tenant_id(),
        "user_hash": get_user_hash(),
        "trace_id": get_trace_id(),
    }


def reset_context() -> None:
    """Clear all four. Used by the Celery task-postrun hook, where the worker process
    is reused across tasks and a stale identifier would misattribute the next one."""
    _request_id.set(None)
    _tenant_id.set(None)
    _user_hash.set(None)
    _trace_id.set(None)
