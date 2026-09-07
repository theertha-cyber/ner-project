import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

INTERNAL_RATE_LIMIT = 60
INTERNAL_WINDOW = 60
WIDGET_RATE_LIMIT = 20
WIDGET_WINDOW = 60


def _count_rejection(key: str) -> None:
    """Count one rejection, splitting the bucket key into its scope and tenant.

    Keys are built as `internal:<tenant_id>` and `widget:<tenant_id>`, so the two parts
    the counter needs are already there and nothing new has to be threaded through the
    call sites.

    `ner_rate_limit_rejections_total` is one of the five families on the tenant-label
    allowlist: "which tenant is being throttled" is exactly the question this counter
    exists to answer, and it is not answerable from a trace, since a rejected request is
    the one that produces the least trace.

    Note that `get_headers` also calls `check`, so a caller already over its limit is
    counted when its headers are built as well as when its request is refused. That is
    existing behaviour — `get_headers` consumes budget today — and is left alone here,
    because this change measures and does not alter what it measures.
    """
    try:
        from src.shared.observability.domain_metrics import record_rate_limit_rejection

        scope, _, tenant_id = key.partition(":")
        record_rate_limit_rejection(tenant_id or None, scope)
    except Exception:
        pass


class SlidingWindowRateLimiter:
    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int, window: int) -> tuple[bool, int, int]:
        now = time.time()
        window_start = now - window

        timestamps = self._buckets[key]
        timestamps[:] = [t for t in timestamps if t > window_start]

        remaining = max(0, limit - len(timestamps))
        reset_at = int(window_start + window)

        if len(timestamps) >= limit:
            retry_after = int(timestamps[0] + window - now)
            logger.warning("Rate limit exceeded for %s", key)
            _count_rejection(key)
            return False, remaining, reset_at, retry_after

        timestamps.append(now)
        return True, remaining, reset_at, 0

    def get_headers(self, key: str, limit: int, window: int) -> dict:
        _, remaining, reset_at, _ = self.check(key, limit, window)
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_at),
        }


rate_limiter = SlidingWindowRateLimiter()
