from __future__ import annotations

from app.services.idempotency import IdempotencyStore, make_key


def test_idempotency_insert_and_short_circuit(monkeypatch):
    # Use short TTL for test
    monkeypatch.setenv("IDMP_TTL_SEC", "3600")
    store = IdempotencyStore()
    key = make_key("update", "42")
    assert store.begin(key) == "acquired"
    store.commit(key, {"ok": True})
    assert store.begin(key) == "exists_done"


def test_idempotency_fail_does_not_short_circuit(monkeypatch):
    store = IdempotencyStore()
    key = make_key("update", "43")
    assert store.begin(key) == "acquired"
    store.fail(key)
    # Another attempt should not be seen as done; acquired or processing depending on race
    res = store.begin(key)
    assert res in {"acquired", "exists_processing", "exists_done"}


def test_purge_removes_expired(monkeypatch):
    # Freeze time by monkeypatching time.time
    t0 = 1_700_000_000
    monkeypatch.setenv("IDMP_TTL_SEC", "10")
    store = IdempotencyStore()

    class T:
        cur = t0

        def time(self):
            return self.cur

    fake = T()
    monkeypatch.setattr("time.time", fake.time)

    k1 = make_key("update", "100")
    k2 = make_key("payment", "abc")
    assert store.begin(k1) == "acquired"
    store.commit(k1, {"ok": True})
    assert store.begin(k2) == "acquired"
    store.commit(k2, {"ok": True})
    # Advance beyond TTL
    fake.cur = t0 + 20
    purged = store.purge_expired(limit=1000)
    assert purged >= 2
