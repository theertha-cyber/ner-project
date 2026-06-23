import pytest
from src.chat_api.services.rate_limiter import SlidingWindowRateLimiter

pytestmark = [pytest.mark.verification]


class TestRateLimiter:
    def setup_method(self):
        self.limiter = SlidingWindowRateLimiter()

    def test_19_rate_limit_headers_on_success(self):
        headers = self.limiter.get_headers("test:tenant1", 60, 60)
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert headers["X-RateLimit-Limit"] == "60"

    def test_18_rate_limit_exceeded(self):
        key = "test:ratelimit"
        for _ in range(5):
            allowed, remaining, reset_at, retry_after = self.limiter.check(key, 5, 60)
            assert allowed is True
        allowed, remaining, reset_at, retry_after = self.limiter.check(key, 5, 60)
        assert allowed is False
        assert retry_after > 0

    def test_rate_limit_resets_after_window(self):
        key = "test:reset"
        self.limiter._buckets[key] = [0.0]
        allowed, remaining, reset_at, _ = self.limiter.check(key, 5, 1)
        assert allowed is True

    def test_different_keys_independent(self):
        for i in range(3):
            self.limiter.check(f"key_a:{i}", 2, 60)
        allowed_a, _, _, _ = self.limiter.check("key_a:0", 2, 60)
        allowed_b, _, _, _ = self.limiter.check("key_b", 2, 60)
        assert allowed_b is True

    def test_remaining_decreases(self):
        key = "test:remaining"
        _, remaining1, _, _ = self.limiter.check(key, 10, 60)
        _, remaining2, _, _ = self.limiter.check(key, 10, 60)
        assert remaining2 < remaining1
