from celery import Celery
from celery.signals import celeryd_init
from src.shared.config import settings
from src.shared.observability import init_observability


@celeryd_init.connect(weak=False)
def _init_worker_observability(**_):
    """Wire this worker's telemetry when it starts as a worker.

    Bound to the signal rather than run at import because `training_service/main.py`
    imports this module for its `celery_app` handle: initialising here unconditionally
    would stamp the API process's spans with the worker's service name, since
    `init_tracing` is deliberately idempotent and the first caller wins.

    `celeryd_init` rather than `worker_process_init` so it fires once under both pools
    the compose file uses — `--concurrency=1` prefork and `--pool=solo`. The SDK's batch
    span processor re-arms its export thread across a fork on its own.

    A worker runs no HTTP server, so `init_observability` gives it OTLP metric export
    instead of a scrape endpoint: adding an HTTP listener to a worker widens its attack
    surface for no operational gain.
    """
    init_observability("celery_worker")


celery_app = Celery(
    "training_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    imports=["src.training_service.worker"],
)
