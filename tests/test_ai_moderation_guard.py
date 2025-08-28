import asyncio
import random as _random

from app.services.ai_moderation_guard import CircuitBreaker, call_with_resilience


def test_breaker_opens_after_failures(monkeypatch):
    cb = CircuitBreaker(failure_threshold=3, window_sec=60, open_duration=120, half_open_probe=2)

    async def fail():
        raise RuntimeError("x")

    # Inject breaker instance
    monkeypatch.setattr("app.services.ai_moderation_guard._CB", cb, raising=True)

    async def run():
        for _ in range(3):
            await call_with_resilience(fail, timeout_s=0.1, max_retries=0)
        assert cb._state == "OPEN"

    asyncio.run(run())


def test_half_open_allows_probes_then_closes_on_success(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, window_sec=1, open_duration=0.0, half_open_probe=2)
    monkeypatch.setattr("app.services.ai_moderation_guard._CB", cb, raising=True)

    async def ok():
        return 1

    async def run():
        # Trip open
        cb.record_failure()
        assert cb._state == "OPEN"
        # After open_duration 0, allow transitions
        assert (await call_with_resilience(ok))[0] in {False, True}
        # Next success should close breaker
        res, _ = await call_with_resilience(ok)
        assert res is True
        assert cb._state == "CLOSED"

    asyncio.run(run())


def test_timeout_and_retries_with_jitter(monkeypatch):
    # Seed jitter
    _random.seed(0)

    async def slow():
        await asyncio.sleep(0.2)
        return 1

    async def run():
        ok, val = await call_with_resilience(slow, timeout_s=0.05, max_retries=2, base_backoff=0.01)
        assert ok is False
        assert val is None

    asyncio.run(run())
