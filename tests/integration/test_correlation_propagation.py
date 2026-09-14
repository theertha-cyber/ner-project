"""One identifier survives every hop.

Verification rows 6, 7 and 8.

This is the failure that exists on `main`: eight services each minted an `X-Request-ID`
and none forwarded it, so following one unit of work across a boundary was impossible.
The fix has to hold at three places — the inbound edge, the outbound HTTP call, and the
Celery enqueue — and a plausible-looking implementation that instruments only the first is
exactly the hallucination the risk register calls out (item 6).

The cross-service test runs two real ASGI applications through the real patched `httpx`,
so it exercises the same code path a live request takes. Rows 6 and 7 additionally
require live-stack evidence; see verification.md § Evidence Log.
"""

import io
import json
import logging

import httpx
import pytest
from fastapi import FastAPI

from src.shared.config import settings
from src.shared.observability import ObservabilityMiddleware, propagation
from src.shared.observability.context import get_request_id, reset_context
from src.shared.observability.logging_config import build_handler

pytestmark = [pytest.mark.verification]

INBOUND_ID = "abc-123"
DOWNSTREAM_HOST = "document_service"


@pytest.fixture(autouse=True)
def instrumented():
    """Install the httpx patch and the Celery hooks, as `init_observability` does."""
    propagation.instrument_httpx()
    propagation.instrument_celery()
    yield
    reset_context()


@pytest.fixture
def two_services(monkeypatch):
    """An upstream service that calls a downstream one, both correlation-instrumented.

    `document_service_url` is pointed at the stub's host so the forwarding rule — which
    stamps platform hosts and leaves third parties alone — resolves the same way it does
    in a real deployment.
    """
    monkeypatch.setattr(settings, "document_service_url", f"http://{DOWNSTREAM_HOST}")

    buffer = io.StringIO()
    handler = build_handler("document_service", stream=buffer)
    downstream_logger = logging.getLogger("tests.correlation.downstream")
    downstream_logger.handlers = [handler]
    downstream_logger.setLevel(logging.INFO)
    downstream_logger.propagate = False

    seen: dict[str, str | None] = {}

    downstream = FastAPI()

    @downstream.get("/inner")
    async def inner():
        downstream_logger.info("downstream_handled")
        return {"ok": True}

    @downstream.middleware("http")
    async def capture(request, call_next):
        seen["header"] = request.headers.get("X-Request-ID")
        return await call_next(request)

    downstream.add_middleware(ObservabilityMiddleware)

    upstream = FastAPI()

    @upstream.get("/outer")
    async def outer():
        transport = httpx.ASGITransport(app=downstream)
        async with httpx.AsyncClient(
            transport=transport, base_url=settings.document_service_url
        ) as client:
            await client.get("/inner")
        return {"ok": True}

    upstream.add_middleware(ObservabilityMiddleware)

    yield upstream, seen, buffer
    downstream_logger.handlers = []


async def _get(app, path, headers=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        return await client.get(path, headers=headers or {})


def _records(buffer):
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


class TestIdentifierSurvivesAServiceToServiceCall:
    """Row 6."""

    async def test_the_outbound_request_carries_the_inbound_identifier(self, two_services):
        upstream, seen, _ = two_services
        await _get(upstream, "/outer", headers={"X-Request-ID": INBOUND_ID})

        assert seen["header"] == INBOUND_ID

    async def test_the_receiving_service_logs_that_identifier(self, two_services):
        upstream, _, buffer = two_services
        await _get(upstream, "/outer", headers={"X-Request-ID": INBOUND_ID})

        records = _records(buffer)
        assert records, "the downstream service emitted nothing"
        assert all(record["request_id"] == INBOUND_ID for record in records)

    async def test_a_third_party_host_is_not_stamped(self, two_services, monkeypatch):
        """A correlation identifier is for this platform. Handing it to OpenAI or to
        MinIO leaks a little about internal request structure for no benefit."""
        captured: dict[str, str | None] = {}

        external = FastAPI()

        @external.get("/v1/chat")
        async def chat():
            return {"ok": True}

        @external.middleware("http")
        async def capture(request, call_next):
            captured["header"] = request.headers.get("X-Request-ID")
            return await call_next(request)

        upstream, _, _ = two_services

        from src.shared.observability.context import set_request_id

        set_request_id(INBOUND_ID)
        transport = httpx.ASGITransport(app=external)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.openai.com") as client:
            await client.get("/v1/chat")

        assert captured["header"] is None


class TestIdentifierIsGeneratedWhenAbsent:
    """Row 8."""

    async def test_a_request_with_no_header_gets_one_back(self, two_services):
        upstream, _, _ = two_services
        response = await _get(upstream, "/outer")

        generated = response.headers.get("X-Request-ID")
        assert generated
        assert len(generated) >= 8

    async def test_the_generated_identifier_is_forwarded_too(self, two_services):
        upstream, seen, _ = two_services
        response = await _get(upstream, "/outer")

        assert seen["header"] == response.headers["X-Request-ID"]

    async def test_an_injection_attempt_is_sanitised_not_echoed(self):
        """A caller-supplied value lands in log records and in a response header.
        Newlines in either are log injection and header splitting respectively."""
        from src.shared.observability.middleware import _sanitize

        assert "\n" not in _sanitize("abc\r\ninjected: yes")
        assert _sanitize("abc\r\ninjected: yes") == "abcinjected:yes"
        assert len(_sanitize("x" * 5000)) <= 128


class TestIdentifierSurvivesACeleryEnqueue:
    """Row 7 — published on enqueue, restored on task start.

    Driven through the Celery signals themselves rather than a live broker: the hooks are
    what this change owns, and a broker in a unit test would only prove Celery works.
    Live-stack evidence for this row is required separately.
    """

    def test_the_identifier_is_published_into_the_task_headers(self):
        from celery.signals import before_task_publish

        from src.shared.observability.context import set_request_id

        set_request_id(INBOUND_ID)
        headers: dict = {}
        before_task_publish.send(sender="tests.task", headers=headers, body=None)

        assert headers[propagation.CELERY_HEADER] == INBOUND_ID

    def test_no_identifier_publishes_no_header(self):
        from celery.signals import before_task_publish

        reset_context()
        headers: dict = {}
        before_task_publish.send(sender="tests.task", headers=headers, body=None)

        assert propagation.CELERY_HEADER not in headers

    def test_the_worker_restores_it_into_the_context(self):
        from types import SimpleNamespace

        from celery.signals import task_prerun

        reset_context()
        task = SimpleNamespace(request=SimpleNamespace(**{propagation.CELERY_HEADER: INBOUND_ID}))
        task_prerun.send(sender="tests.task", task=task)

        assert get_request_id() == INBOUND_ID

    def test_the_context_is_cleared_between_tasks(self):
        """Worker processes are reused. A value left behind would attribute the next
        task's records to the previous task's request."""
        from types import SimpleNamespace

        from celery.signals import task_postrun, task_prerun

        task = SimpleNamespace(request=SimpleNamespace(**{propagation.CELERY_HEADER: INBOUND_ID}))
        task_prerun.send(sender="tests.task", task=task)
        task_postrun.send(sender="tests.task", task=task)

        assert get_request_id() is None
