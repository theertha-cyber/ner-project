"""A telemetry outage must not become a platform outage.

Verification rows 21 and 28.

The failure mode being excluded is specific: a synchronous exporter pointed at a collector
that is down turns every request into a timeout, so an observability change takes the
platform with it. The design pins the answer — the span processor is batched and
asynchronous, and export runs on a background thread that cannot raise into the request
path.

Row 28's second half — health checks still passing with the `otel-collector` container
stopped — is a live-stack step; see verification.md § Evidence Log.
"""

import inspect

import httpx
import pytest

from src.shared.config import settings
from src.shared.observability import ObservabilityMiddleware, tracing

pytestmark = [pytest.mark.verification]

# A routable-looking address with nothing listening: the exporter resolves it and then
# fails to connect, which is what a stopped collector looks like from inside a service.
UNREACHABLE = "127.0.0.1:14317"


@pytest.fixture
def app_with_unreachable_collector(monkeypatch):
    """An app whose spans are exported to nothing.

    The provider is built and passed explicitly rather than installed globally: the SDK
    permits `set_tracer_provider` exactly once per process, so a test that relied on the
    global would silently assert against whichever provider an earlier test installed.
    """
    from fastapi import FastAPI

    monkeypatch.setattr(settings, "otlp_endpoint", UNREACHABLE)
    provider = tracing.build_tracer_provider("test-service")

    application = FastAPI()

    @application.get("/health")
    async def health():
        return {"status": "ok"}

    application.add_middleware(ObservabilityMiddleware)
    tracing.instrument_app(application, tracer_provider=provider)
    return application


async def _get(app, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


class TestRequestsSurviveAnUnreachableCollector:
    """Row 21."""

    async def test_a_request_is_served_normally(self, app_with_unreachable_collector):
        response = await _get(app_with_unreachable_collector, "/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_repeated_requests_do_not_degrade_into_failures(
        self, app_with_unreachable_collector
    ):
        """One request could pass before the exporter's first failed connection. A run of
        them is what catches an exporter that blocks once its queue fills."""
        for _ in range(10):
            response = await _get(app_with_unreachable_collector, "/health")
            assert response.status_code == 200

    async def test_the_correlation_header_still_comes_back(self, app_with_unreachable_collector):
        response = await _get(app_with_unreachable_collector, "/health")

        assert response.headers.get("X-Request-ID")

    async def test_no_unhandled_exception_reaches_the_caller(
        self, app_with_unreachable_collector, caplog
    ):
        await _get(app_with_unreachable_collector, "/health")

        assert not [record for record in caplog.records if record.levelname == "CRITICAL"]


class TestTheExporterIsAsynchronous:
    """Risk-register item 5 — the property that makes the above true, asserted directly
    rather than inferred from a passing request."""

    def test_the_span_processor_is_batched(self):
        source = inspect.getsource(tracing)

        assert "BatchSpanProcessor" in source
        assert "SimpleSpanProcessor" not in source, (
            "a simple processor exports on the calling thread, which puts collector "
            "latency directly into the request path"
        )


class TestExportIsDisabledByAnEmptyEndpoint:
    """The config-only rollback. If telemetry ever causes a production problem, unsetting
    the endpoint has to be sufficient — no code change, no different image."""

    async def test_no_exporter_is_installed_when_the_endpoint_is_empty(self, monkeypatch):
        from fastapi import FastAPI

        monkeypatch.setattr(settings, "otlp_endpoint", "")
        provider = tracing.build_tracer_provider("test-service")

        processor = getattr(provider, "_active_span_processor", None)
        assert not getattr(processor, "_span_processors", ()), (
            "an empty endpoint must be a full no-op"
        )

        application = FastAPI()

        @application.get("/health")
        async def health():
            return {"status": "ok"}

        tracing.instrument_app(application, tracer_provider=provider)
        assert (await _get(application, "/health")).status_code == 200

    async def test_an_endpoint_installs_one(self, monkeypatch):
        """The counterpart: a passing test above means nothing if export never happens."""
        monkeypatch.setattr(settings, "otlp_endpoint", UNREACHABLE)
        provider = tracing.build_tracer_provider("test-service")

        processor = getattr(provider, "_active_span_processor", None)
        assert getattr(processor, "_span_processors", ())
