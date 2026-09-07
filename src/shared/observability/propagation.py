"""Carry the correlation identifier across process boundaries.

Two hops exist in this platform and both are patched once here rather than at each call
site. There are fourteen `httpx.AsyncClient(...)` constructions across `src/`, written
independently over months; a convention that each of them must add a header is the same
convention that produced eight divergent request-ID generators in the first place.

- **HTTP**: `httpx.Client.send` / `AsyncClient.send` is the single funnel every
  `get`/`post`/`stream`/`request` call converges on, so the header is injected there.
  Only calls to a known platform service are stamped — a correlation identifier is not
  something to hand to OpenAI or to MinIO.
- **Celery**: the identifier is published as a task header on enqueue and restored into
  the contextvar on task start, so a worker's records carry the identifier of the request
  that queued the work.
"""

import logging
import time
from urllib.parse import urlsplit

from src.shared.config import settings
from src.shared.observability.domain_metrics import (
    record_celery_duration,
    record_celery_failure,
    record_celery_retry,
    record_celery_wait,
    record_celery_worker_up,
    register_queue_depth_gauge,
)
from src.shared.observability.context import (
    get_request_id,
    reset_context,
    set_request_id,
    set_trace_id,
)

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
CELERY_HEADER = "x_request_id"
# Enqueue time, stamped on the same header dict the correlation identifier travels in.
# Wait time cannot be derived any other way: Redis does not record when a message
# arrived, and Celery's own `task_received`/`task_published` events need the events
# subsystem enabled and a consumer process — two new operational surfaces for one number.
CELERY_ENQUEUED_HEADER = "x_enqueued_at"

_http_patched = False
_celery_patched = False


def _platform_hosts() -> set[str]:
    """Hosts belonging to this platform, derived from the inter-service URL settings.

    Derived rather than hardcoded so a deployment that renames a service host — which
    docker-compose already does, pointing every URL at a container name — keeps working
    without a code change.
    """
    urls = (
        settings.document_service_url,
        settings.extraction_service_url,
        settings.training_service_url,
        settings.model_serving_url,
        settings.chat_api_url,
        settings.analytics_service_url,
    )
    hosts = set()
    for url in urls:
        if not url:
            continue
        parsed = urlsplit(url)
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    return hosts


def _should_forward(request) -> bool:
    host = request.url.host
    return bool(host) and host.lower() in _platform_hosts()


def instrument_httpx() -> None:
    """Stamp outbound platform calls with the ambient correlation identifier.

    Patching `send` rather than `build_request` covers `client.send(request)` call sites
    too, and leaves an explicitly-supplied header alone so a caller can override it.
    """
    global _http_patched
    if _http_patched:
        return
    _http_patched = True

    import httpx

    original_sync_send = httpx.Client.send
    original_async_send = httpx.AsyncClient.send

    def _stamp(request) -> None:
        request_id = get_request_id()
        if not request_id:
            return
        if REQUEST_ID_HEADER in request.headers:
            return
        if not _should_forward(request):
            return
        request.headers[REQUEST_ID_HEADER] = request_id

    def send(self, request, *args, **kwargs):
        _stamp(request)
        return original_sync_send(self, request, *args, **kwargs)

    async def async_send(self, request, *args, **kwargs):
        _stamp(request)
        return await original_async_send(self, request, *args, **kwargs)

    httpx.Client.send = send
    httpx.AsyncClient.send = async_send


def instrument_celery() -> None:
    """Publish the identifier on enqueue and restore it on task start.

    `before_task_publish` carries it in the message headers rather than in the task
    arguments, so no task signature changes and a task enqueued by an older producer
    still runs.
    """
    global _celery_patched
    if _celery_patched:
        return
    _celery_patched = True

    try:
        from celery import signals
    except ImportError:  # a process without Celery installed has no hop to instrument
        return

    @signals.before_task_publish.connect(weak=False)
    def _publish_request_id(headers=None, **_):
        request_id = get_request_id()
        if headers is None:
            return
        if request_id:
            headers[CELERY_HEADER] = request_id
        # The hook already exists and already writes headers, so the enqueue timestamp is
        # a field rather than a mechanism.
        headers[CELERY_ENQUEUED_HEADER] = time.time()

    @signals.task_prerun.connect(weak=False)
    def _restore_request_id(task=None, **_):
        request_id = None
        request = getattr(task, "request", None)
        if request is not None:
            request_id = getattr(request, CELERY_HEADER, None)
            if request_id is None:
                request_id = (getattr(request, "headers", None) or {}).get(CELERY_HEADER)
        set_request_id(request_id)
        set_trace_id(None)
        _task_started[_task_key(task)] = time.monotonic()
        _record_wait(task)

    @signals.task_postrun.connect(weak=False)
    def _clear_request_id(task=None, **_):
        started = _task_started.pop(_task_key(task), None)
        if started is not None:
            record_celery_duration(_queue_of(task), time.monotonic() - started)
        # Worker processes are reused across tasks, so a value left behind would
        # misattribute the next task's records to the previous task's request.
        reset_context()

    @signals.task_retry.connect(weak=False)
    def _count_retry(sender=None, **_):
        record_celery_retry(_queue_of(sender))

    @signals.task_failure.connect(weak=False)
    def _count_failure(sender=None, exception=None, **_):
        # The exception *class*. A task failure message routinely carries the offending
        # value — a document id, a filename, a driver error quoting a literal.
        record_celery_failure(_queue_of(sender), exception or "other")

    @signals.celeryd_init.connect(weak=False)
    def _worker_up(**_):
        record_celery_worker_up(_configured_queue(), True)

    @signals.worker_shutdown.connect(weak=False)
    def _worker_down(**_):
        record_celery_worker_up(_configured_queue(), False)


# Wall time at task start, keyed by task id. A dict rather than a contextvar: `task_prerun`
# and `task_postrun` are separate signal callbacks and do not share a context.
_task_started: dict[str, float] = {}


def _task_key(task) -> str:
    request = getattr(task, "request", None)
    return str(getattr(request, "id", None) or id(task))


def _configured_queue() -> str:
    """The queue this process's worker consumes, from configuration."""
    return settings.extraction_celery_queue or "celery"


def _queue_of(task) -> str:
    """The queue a task arrived on, falling back to Celery's own default.

    Read off the delivery info rather than from configuration, because a process that
    consumes two queues would otherwise attribute every task to one of them.
    """
    request = getattr(task, "request", None)
    delivery = getattr(request, "delivery_info", None) or {}
    return delivery.get("routing_key") or getattr(request, "queue", None) or "celery"


def _record_wait(task) -> None:
    """Time between enqueue and start, from the header stamped on publish.

    Clock skew between the enqueuing service and the worker is the known weakness. Both
    run in one compose stack locally and will run in one cluster in production, so skew is
    bounded by NTP, and this is a distribution read for "is the queue backing up" rather
    than a precise per-task figure. A negative result is clamped and counted, so skew
    becomes visible instead of silently dragging the histogram left.
    """
    request = getattr(task, "request", None)
    if request is None:
        return
    enqueued = getattr(request, CELERY_ENQUEUED_HEADER, None)
    if enqueued is None:
        enqueued = (getattr(request, "headers", None) or {}).get(CELERY_ENQUEUED_HEADER)
    if enqueued is None:
        # A task enqueued by a producer that predates this header. Not an error: the
        # header is additive and an older message must still run.
        return
    try:
        record_celery_wait(_queue_of(task), time.time() - float(enqueued))
    except (TypeError, ValueError):
        logger.debug("celery_wait_unreadable")


def register_queue_depth(queue: str) -> None:
    """Report `queue`'s depth at scrape time, reading the broker's list length.

    Called on the **producer** side — the service that enqueues — and never in a worker.
    Depth is a property of the queue, not of a worker: every worker reporting it would
    produce N identical series differing only by instance, and a dashboard would then have
    to pick one arbitrarily or sum them into a number that means nothing. Wait time and
    execution duration are per-task and stay in the worker, where the task runs.

    Read at scrape time rather than on a timer, following the pattern the foundation
    established for `DatabasePoolCollector`: occupancy is only true at the instant it is
    read. See design Decision 6.
    """

    def _depth() -> int:
        import redis

        client = redis.Redis.from_url(settings.celery_broker_url)
        try:
            return int(client.llen(queue))
        finally:
            client.close()

    register_queue_depth_gauge(queue, _depth)
