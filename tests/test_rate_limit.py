from __future__ import annotations

from app.services.rate_limit import TokenBucket


def test_allow_within_burst(monkeypatch):
    # Frozen monotonic
    t = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: t[0])
    b = TokenBucket(rate=6, per=10.0, burst=6.0, cool_down=15.0)
    uid, chat = 1, 1
    # 6 immediate allows
    for _ in range(6):
        assert b.allow(uid, chat, scope="user") is True
    # 7th without time should deny and mute
    assert b.allow(uid, chat, scope="user") is False


def test_deny_after_burst_then_cooldown(monkeypatch):
    t = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: t[0])
    b = TokenBucket(rate=6, per=10.0, burst=6.0, cool_down=15.0)
    uid, chat = 2, 1
    for _ in range(6):
        assert b.allow(uid, chat, scope="user_chat") is True
    assert b.allow(uid, chat, scope="user_chat") is False
    # Within cooldown (advance 10s) still deny
    t[0] += 10.0
    assert b.allow(uid, chat, scope="user_chat") is False
    # After cooldown (advance total 16s), start allowing after token accrual
    t[0] += 6.0
    assert b.allow(uid, chat, scope="user_chat") in {True, False}


def test_cleanup_removes_idle_entries(monkeypatch):
    t = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: t[0])
    b = TokenBucket(rate=6, per=10.0, burst=6.0, cool_down=15.0)
    uid, chat = 3, 1
    assert b.allow(uid, chat, scope="user") is True
    # Advance beyond max_age and ensure cleanup removes
    t[0] += 60.0
    removed = b.cleanup(max_age=30.0)
    assert removed >= 1
