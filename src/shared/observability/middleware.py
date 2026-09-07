"""The one correlation middleware, mounted by every FastAPI service.

Eight near-identical `src/*/middleware/tenant_context.py` files each generated their own
`X-Request-ID` and set it on the response, and because they were written independently
none of them forwarded it. Correlation is a property of the whole system, so it gets
exactly one implementation.

**Scope is correlation and telemetry only.** Token decoding, tenant resolution and
authorization stay in each service's own middleware and are deliberately not moved here:
tenant enforcement is the platform's core security property under ADR-001, and
consolidating it as a side effect of an observability change is how that property gets
silently regressed.

The inbound identifier is accepted so a caller can correlate with their own logs, and is
never read as a tenancy or authorization input — see `_sanitize`.
"""

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.shared.observability.context import reset_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"

# Long enough for a UUID, a ULID or a caller's own trace identifier; short enough that a
# caller cannot push megabytes into every log line the request produces.
MAX_REQUEST_ID_LENGTH = 128

# A caller-supplied value ends up inside log records and response headers. Restricting it
# to identifier characters removes newline-based log injection and header splitting at
# the point of ingest, which is cheaper than trusting every downstream consumer to escape
# it. Rejecting a non-conforming value outright would break callers for no security gain,
# so it is sanitized instead.
_DISALLOWED = re.compile(r"[^A-Za-z0-9._:-]")


def _sanitize(raw: str | None) -> str:
    if not raw:
        return str(uuid.uuid4())
    cleaned = _DISALLOWED.sub("", raw[:MAX_REQUEST_ID_LENGTH])
    return cleaned or str(uuid.uuid4())


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Bind the correlation identifier for the duration of one request."""

    async def dispatch(self, request: Request, call_next):
        request_id = _sanitize(request.headers.get(REQUEST_ID_HEADER))
        token = set_request_id(request_id)
        # `request.state` is kept in step because the per-service error handlers and the
        # exception handler in each `main.py` still read `request.state.request_id` when
        # building an error body.
        request.state.request_id = request_id
        # `trace_id` is deliberately not set here. FastAPI instrumentation opens the
        # server span outside this middleware, so `get_trace_id()` reads it from the
        # active span — which stays correct for a child span opened later in the request,
        # where a value pinned at ingress would not be.
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
