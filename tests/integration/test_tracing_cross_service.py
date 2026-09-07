"""One unit of work, one trace identifier, across processes — and on its log records.

Verification rows 18, 19 and 20.

Tracing is the signal that solves the ten-process problem: with it, "which service broke"
stops being the first question. The property that makes it work is context propagation —
the outbound `traceparent` on an HTTP call, and the Celery message headers on an enqueue —
and it is exercised here through the same instrumentation a live request uses, with an
in-memory exporter standing in for the collector.

Rows 18 and 19 additionally require evidence from the running stack (a trace retrieved
from Tempo). Row 20's comparison is fully automated here, because a `trace_id` on a log
record that does not match the span is a silent defect no dashboard would reveal.
"""

import io
import json
import logging

import httpx
import pytest
from fastapi import FastAPI
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.shared.config import settings
from src.shared.observability import ObservabilityMiddleware, propagation, tracing
from src.shared.observability.logging_config import build_handler

pytestmark = [pytest.mark.verification]

DOWNSTREAM_HOST = "document_service"


@pytest.fixture
def traced_pair(monkeypatch):
    """Two instrumented services and the spans both produce.

    A single in-memory exporter stands in for the collector: what matters is not where
    the spans land but whether both processes' spans agree on a trace identifier, and an
    exporter shared by both is the cheapest way to compare them. The provider is passed
    explicitly because the SDK allows one global provider per process.
    """
    monkeypatch.setattr(settings, "document_service_url", f"http://{DOWNSTREAM_HOST}")
    propagation.instrument_httpx()

    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    buffer = io.StringIO()
    downstream_logger = logging.getLogger("tests.tracing.downstream")
    downstream_logger.handlers = [build_handler("document_service", stream=buffer)]
    downstream_logger.setLevel(logging.INFO)
    downstream_logger.propagate = False

    downstream = FastAPI()

    @downstream.get("/inner")
    async def inner():
        downstream_logger.info("downstream_handled")
        return {"ok": True}

    downstream.add_middleware(ObservabilityMiddleware)
    tracing.instrument_app(downstream, tracer_provider=provider)

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
    tracing.instrument_app(upstream, tracer_provider=provider)

    yield upstream, exporter, buffer
    downstream_logger.handlers = []


async def _get(app, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        return await client.get(path)


def _records(buffer):
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


class TestOneTraceSpansTwoServices:
    """Row 18."""

    async def test_both_processes_produce_spans(self, traced_pair):
        upstream, exporter, _ = traced_pair
        await _get(upstream, "/outer")

        spans = exporter.get_finished_spans()
        assert len(spans) >= 2, "the onward call produced no span of its own"

    async def test_every_span_shares_one_trace_identifier(self, traced_pair):
        upstream, exporter, _ = traced_pair
        await _get(upstream, "/outer")

        trace_ids = {span.get_span_context().trace_id for span in exporter.get_finished_spans()}
        assert len(trace_ids) == 1, (
            "the downstream service started a new trace — context did not cross the hop, "
            "which is the exact failure this change exists to fix"
        )


class TestLogsJoinTraces:
    """Row 20 — a record's `trace_id` equals the trace id of the spans beside it."""

    async def test_the_record_carries_the_span_trace_id(self, traced_pair):
        upstream, exporter, buffer = traced_pair
        await _get(upstream, "/outer")

        records = _records(buffer)
        assert records, "the downstream service emitted no record to compare"

        expected = format(exporter.get_finished_spans()[0].get_span_context().trace_id, "032x")
        assert records[0]["trace_id"] == expected

    async def test_the_trace_id_is_not_null_inside_a_request(self, traced_pair):
        """A null here would make every log-to-trace link in Grafana dead, while every
        other assertion in this file still passed."""
        upstream, _, buffer = traced_pair
        await _get(upstream, "/outer")

        assert _records(buffer)[0]["trace_id"] is not None


class TestTraceExtendsIntoACeleryTask:
    """Row 19.

    The cross-process half needs the running stack and a real broker; see
    verification.md § Evidence Log. What is asserted here is the mechanism that carries
    it: the Celery instrumentor is registered in every process, so the enqueue writes
    `traceparent` into the message headers and the worker adopts it.
    """

    def test_the_celery_instrumentor_is_registered(self):
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        tracing.init_tracing("test-service")
        assert CeleryInstrumentor().is_instrumented_by_opentelemetry

    def test_both_workers_initialise_observability_before_running_tasks(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "src"
        for module in ("training_service/celery_app.py", "extraction_service/celery_app.py"):
            source = (root / module).read_text(encoding="utf-8")
            assert "celeryd_init" in source
            assert "init_observability(" in source
