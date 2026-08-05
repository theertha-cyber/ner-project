import time
import pytest
from src.shared.config import settings
from src.shared.database import _retrying


@pytest.mark.asyncio
async def test_retries_with_exponential_backoff_before_succeeding(monkeypatch):
    monkeypatch.setattr(settings, "retry_initial_delay_seconds", 0.05)
    monkeypatch.setattr(settings, "retry_backoff_multiplier", 2.0)
    monkeypatch.setattr(settings, "retry_max_delay_seconds", 0.2)
    monkeypatch.setattr(settings, "retry_max_total_seconds", 5.0)

    attempts = []

    @_retrying()
    async def flaky():
        attempts.append(time.monotonic())
        if len(attempts) < 3:
            raise ConnectionError("dependency not ready")
        return "connected"

    result = await flaky()

    assert result == "connected"
    assert len(attempts) == 3
    assert attempts[1] - attempts[0] >= 0.04
    assert attempts[2] - attempts[1] >= 0.08


@pytest.mark.asyncio
async def test_fatal_error_raised_after_retry_bound_exhausted(monkeypatch):
    monkeypatch.setattr(settings, "retry_initial_delay_seconds", 0.02)
    monkeypatch.setattr(settings, "retry_backoff_multiplier", 2.0)
    monkeypatch.setattr(settings, "retry_max_delay_seconds", 0.05)
    monkeypatch.setattr(settings, "retry_max_total_seconds", 0.2)

    @_retrying()
    async def always_fails():
        raise ConnectionError("dependency permanently unreachable")

    start = time.monotonic()
    with pytest.raises(ConnectionError, match="dependency permanently unreachable"):
        await always_fails()
    elapsed = time.monotonic() - start

    assert elapsed < 2.0
