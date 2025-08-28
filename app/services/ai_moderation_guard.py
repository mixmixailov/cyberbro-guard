from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from prometheus_client import Counter, Gauge
from app.metrics import ai_latency_seconds


logger = logging.getLogger(__name__)


# Metrics (ai_latency_seconds is defined in app.metrics to avoid duplicates)
ai_errors_total = Counter(
    "cyberbro_ai_errors_total",
    "AI moderation errors",
    labelnames=("type",),
)
ai_breaker_state = Gauge(
    "cyberbro_ai_breaker_state",
    "Circuit breaker state (0 closed, 1 half-open, 2 open)",
)


def _now() -> float:
    return time.monotonic()


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    window_sec: float = 60.0
    open_duration: float = 120.0
    half_open_probe: int = 3
    _state: str = field(default="CLOSED", init=False)
    _failures: list[float] = field(default_factory=list, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _probes_left: int = field(default=0, init=False)

    def _set_state(self, state: str) -> None:
        self._state = state
        ai_breaker_state.set({"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}[state])

    def allow(self) -> bool:
        now = _now()
        # Slide window
        self._failures = [t for t in self._failures if now - t <= self.window_sec]
        if self._state == "OPEN":
            if self._opened_at is not None and (now - self._opened_at) >= self.open_duration:
                # Move to half-open
                self._set_state("HALF_OPEN")
                self._probes_left = self.half_open_probe
            else:
                return False
        if self._state == "HALF_OPEN":
            if self._probes_left <= 0:
                return False
            self._probes_left -= 1
            return True
        return True

    def record_success(self) -> None:
        if self._state in {"OPEN", "HALF_OPEN"}:
            # Close on any success during half-open
            self._set_state("CLOSED")
            self._opened_at = None
            self._probes_left = 0
        # Reset failures on success within window
        self._failures.clear()

    def record_failure(self) -> None:
        now = _now()
        self._failures.append(now)
        self._failures = [t for t in self._failures if now - t <= self.window_sec]
        if len(self._failures) >= self.failure_threshold:
            self._set_state("OPEN")
            self._opened_at = now


_CB = CircuitBreaker()


async def call_with_resilience(
    fn: Callable[[], Awaitable[Any]],
    *,
    timeout_s: float = 2.5,
    max_retries: int = 2,
    base_backoff: float = 0.3,
) -> tuple[bool, Any]:
    """Execute fn with timeout, bounded retries with jitter, and circuit breaker.

    Returns (ok, value). ok=False if breaker-open or all retries failed.
    """
    if not _CB.allow():
        logger.warning("ai breaker open; skipping call")
        return False, None
    start = time.perf_counter()
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            value = await asyncio.wait_for(fn(), timeout=timeout_s)
            # Success: close breaker and record latency
            _CB.record_success()
            ai_latency_seconds.observe(time.perf_counter() - start)
            return True, value
        except asyncio.TimeoutError:
            ai_errors_total.labels("timeout").inc()
            last_exc = asyncio.TimeoutError()
            _CB.record_failure()
            if attempt < max_retries:
                await asyncio.sleep(base_backoff * (1 + random.random()))
            continue
        except Exception as exc:  # noqa: BLE001
            ai_errors_total.labels("exception").inc()
            last_exc = exc
            _CB.record_failure()
            if attempt < max_retries:
                await asyncio.sleep(base_backoff * (1 + random.random()))
            continue
    # All attempts failed
    ai_latency_seconds.observe(time.perf_counter() - start)
    logger.error("ai call failed after retries err=%s", last_exc)
    return False, None


def record_ai_success(latency_start: float) -> None:
    _CB.record_success()
    ai_latency_seconds.observe(time.perf_counter() - latency_start)





