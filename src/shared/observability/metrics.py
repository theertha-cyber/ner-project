"""RED metrics and database pool gauges.

Request rate, error count and duration come from `prometheus-fastapi-instrumentator`,
which derives them from the ASGI layer, so no route carries measurement code. The
duration histogram is what makes ADR-007's "P95 alert at >10s" obligation measurable at
all; the alert rule itself belongs to a later change.

**No metric family here carries a `tenant_id` label.** Prometheus label cardinality
multiplies by tenant count, and metric labels are visible to everyone with dashboard
access, which makes per-tenant consumption figures commercially sensitive. The families
that legitimately need the label arrive with the workload-instrumentation change, where
the allowlist governing them is defined too. Starting with none and adding deliberately
is far easier than removing a label already on a dashboard.

The two Celery workers run no HTTP server, so they export the equivalent metrics over
OTLP instead of exposing a scrape endpoint — adding an HTTP listener to a worker widens
its attack surface for no operational gain.
"""

import logging

from prometheus_client import REGISTRY
from prometheus_client.core import GaugeMetricFamily

from src.shared.config import settings

logger = logging.getLogger(__name__)


class DatabasePoolCollector:
    """Reports database connection usage at scrape time.

    The obvious implementation — read `pool.size()` and `pool.checkedout()` — reports
    nothing here. Every service builds its engine with `NullPool`, which holds no
    connections between checkouts and therefore implements neither method, so those two
    families were declared and then emitted with no samples at all: a metric that looks
    present on the endpoint and is silently always absent on the dashboard. Confirmed on
    the running stack, not inferred.

    So the count comes from SQLAlchemy's `checkout`/`checkin` events instead, which fire
    for every pool implementation including `NullPool`, and `ner_db_pool_size` is emitted
    only by a deployment whose pool can answer it. The pool class travels as a label
    because "2 connections in use" means something different under `NullPool` (two live
    sockets) than under `QueuePool` (two of N reserved).

    Pull-time rather than written on a timer: occupancy is only true at the instant it is
    read.
    """

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self.in_use = 0
        self._listening = False

    def _attach(self) -> str | None:
        """Bind to the engine's pool events, once, on the first scrape that finds one.

        Deferred rather than done in `init_db_pool_metrics`: that runs at import time and
        the engine is not built until the application's lifespan starts.
        """
        from sqlalchemy import event

        from src.shared.database import get_engine

        pool = get_engine().pool
        if self._listening:
            return type(pool).__name__

        @event.listens_for(pool, "checkout")
        def _on_checkout(*_):
            self.in_use += 1

        @event.listens_for(pool, "checkin")
        def _on_checkin(*_):
            self.in_use = max(0, self.in_use - 1)

        self._listening = True
        return type(pool).__name__

    def collect(self):
        in_use = GaugeMetricFamily(
            "ner_db_connections_in_use",
            "Database connections currently checked out of the engine",
            labels=["service", "pool_class"],
        )
        size = GaugeMetricFamily(
            "ner_db_pool_size",
            "Connections held by the SQLAlchemy pool, where the pool implementation "
            "reports one",
            labels=["service", "pool_class"],
        )
        try:
            pool_class = self._attach()
            if pool_class:
                in_use.add_metric([self.service_name, pool_class], self.in_use)

                from src.shared.database import get_engine

                pool = get_engine().pool
                if callable(getattr(pool, "size", None)):
                    size.add_metric([self.service_name, pool_class], pool.size())
        except Exception:
            # An engine that is not built yet is not a reason to fail the whole scrape —
            # a scraper polls a starting service well before its lifespan has run.
            logger.debug("db_pool_metrics_unavailable", exc_info=True)
        yield in_use
        yield size


_pool_collector: DatabasePoolCollector | None = None


def init_db_pool_metrics(service_name: str) -> None:
    """Register the pool collector once per process.

    Re-registering raises in `prometheus_client`, and a duplicate registration would take
    a service down at import time over a metric.
    """
    global _pool_collector
    if _pool_collector is not None:
        return
    _pool_collector = DatabasePoolCollector(service_name)
    try:
        REGISTRY.register(_pool_collector)
    except ValueError:
        logger.debug("db_pool_collector_already_registered")


def instrument_app(app, service_name: str) -> None:
    """Expose `/metrics` on a FastAPI service.

    The endpoint is mounted on the app directly and added to each service's exempt-path
    set: a scraper holds no JWT and resolves to no tenant, so requiring either would make
    the metrics unscrapeable.
    """
    from prometheus_fastapi_instrumentator import Instrumentator

    init_db_pool_metrics(service_name)

    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics"],
    )
    instrumentator.instrument(app)
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False, should_gzip=False)


def init_worker_metrics(service_name: str) -> None:
    """Periodic OTLP metric export for a process with no HTTP server."""
    if not settings.otlp_endpoint:
        return
    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource

        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=settings.otlp_endpoint, insecure=True)
        )
        metrics.set_meter_provider(
            MeterProvider(
                resource=Resource.create({"service.name": service_name}),
                metric_readers=[reader],
            )
        )
    except Exception:
        # Same rule as span export: a telemetry backend that will not start must not stop
        # the worker from consuming its queue.
        logger.warning("worker_metric_export_unavailable", exc_info=True)
