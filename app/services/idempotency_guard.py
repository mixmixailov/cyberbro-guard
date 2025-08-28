from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from prometheus_client import Counter, Histogram

from app.services.idempotency import IdempotencyStore

idmp_acquire_total = Counter(
    "cyberbro_idmp_acquire_total",
    "Idempotency acquire results",
    labelnames=("result",),
)

idmp_handler_seconds = Histogram(
    "cyberbro_idmp_handler_seconds",
    "Idempotent handler duration seconds",
)


async def with_idempotency(
    key: str, handler: Callable[[], Awaitable[Any]], store: IdempotencyStore | None = None
) -> Any:
    s = store or IdempotencyStore()
    result = s.begin(key)
    idmp_acquire_total.labels(result).inc()
    if result == "exists_done":
        # No need to return the previous response body; we just short-circuit
        return None
    if result == "exists_processing":
        # Another worker is processing; best effort no-op
        return None
    start = time.perf_counter()
    try:
        out = await handler()
        s.commit(key, out if out is not None else {"status": "ok"})
        return out
    except Exception:
        s.fail(key)
        raise
    finally:
        idmp_handler_seconds.observe(time.perf_counter() - start)
