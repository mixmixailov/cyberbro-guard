from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Tuple

from prometheus_client import Counter, Gauge

abuse_rate_total = Counter(
    "cyberbro_abuse_rate_limit_total",
    "Rate limit decisions",
    labelnames=("action",),
)
abuse_muted_gauge = Gauge(
    "cyberbro_abuse_muted_users",
    "Currently muted users count",
)


@dataclass
class _Entry:
    tokens: float
    last_ts: float
    muted_until: float


class TokenBucket:
    def __init__(self, rate: float, per: float, burst: float, cool_down: float) -> None:
        self.rate = rate
        self.per = per
        self.capacity = burst
        self.cool_down = cool_down
        self._store: Dict[Tuple[int, int], _Entry] = {}

    def _key(self, user_id: int, chat_id: int | None, scope: str) -> Tuple[int, int]:
        return (user_id, chat_id or 0) if scope == "user_chat" else (user_id, 0)

    def allow(self, user_id: int, chat_id: int | None, scope: str = "user") -> bool:
        now = time.monotonic()
        key = self._key(user_id, chat_id, scope)
        ent = self._store.get(key)
        if ent is None:
            ent = _Entry(tokens=self.capacity, last_ts=now, muted_until=0.0)
            self._store[key] = ent
        # cooldown check
        if ent.muted_until and now < ent.muted_until:
            abuse_rate_total.labels("deny").inc()
            return False
        # refill
        elapsed = max(0.0, now - ent.last_ts)
        refill = (self.rate / self.per) * elapsed
        ent.tokens = min(self.capacity, ent.tokens + refill)
        ent.last_ts = now
        if ent.tokens >= 1.0:
            ent.tokens -= 1.0
            abuse_rate_total.labels("allow").inc()
            return True
        # Exhausted → penalize
        ent.muted_until = now + self.cool_down
        # Update gauge: count muted
        abuse_muted_gauge.set(sum(1 for e in self._store.values() if e.muted_until > now))
        abuse_rate_total.labels("deny").inc()
        return False

    def penalize(self, user_id: int, chat_id: int | None, scope: str = "user") -> None:
        now = time.monotonic()
        key = self._key(user_id, chat_id, scope)
        ent = self._store.get(key)
        if ent is None:
            ent = _Entry(tokens=0.0, last_ts=now, muted_until=now + self.cool_down)
            self._store[key] = ent
        else:
            ent.muted_until = now + self.cool_down
        abuse_muted_gauge.set(sum(1 for e in self._store.values() if e.muted_until > now))

    def cleanup(self, max_age: float) -> int:
        now = time.monotonic()
        to_del = []
        for k, e in self._store.items():
            if (now - e.last_ts) > max_age and e.muted_until < now:
                to_del.append(k)
        for k in to_del:
            del self._store[k]
        # recalc gauge
        abuse_muted_gauge.set(sum(1 for e in self._store.values() if e.muted_until > now))
        return len(to_del)
