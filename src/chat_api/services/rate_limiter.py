import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

INTERNAL_RATE_LIMIT = 60
INTERNAL_WINDOW = 60
WIDGET_RATE_LIMIT = 20
WIDGET_WINDOW = 60


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
