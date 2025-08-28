from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .session import execute, fetchone, fetchall


def ensure_plan(code: str, price_xtr: int, period_days: int) -> None:
    execute(
        """
        INSERT INTO plans (code, price_xtr, period_days)
        VALUES (?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET price_xtr=excluded.price_xtr, period_days=excluded.period_days
        """,
        (code, price_xtr, period_days),
    )


def upsert_subscription(tg_id: int, plan_code: str, period_days: int) -> int:
    now = datetime.utcnow()
    sub = fetchone("SELECT id, until FROM subscriptions WHERE tg_id = ? AND plan_code = ?", (tg_id, plan_code))
    if sub and sub.get("until"):
        try:
            until = datetime.fromisoformat(sub["until"])
        except Exception:
            until = now
        if until < now:
            until = now
        until = until + timedelta(days=period_days)
        execute("UPDATE subscriptions SET until = ? WHERE id = ?", (until.isoformat(timespec="seconds"), sub["id"]))
        return int(sub["id"])
    else:
        until = now + timedelta(days=period_days)
        return execute(
            "INSERT INTO subscriptions (tg_id, plan_code, until, created_at) VALUES (?, ?, ?, ?)",
            (tg_id, plan_code, until.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")),
        )


def get_subscription(tg_id: int, plan_code: str) -> dict[str, Any] | None:
    return fetchone("SELECT id, tg_id, plan_code, until FROM subscriptions WHERE tg_id = ? AND plan_code = ?", (tg_id, plan_code))


def find_due_reminders() -> list[dict[str, Any]]:
    """Return list of subscriptions with reminder flags to send.

    Simple approach: select all and filter in Python for MVP.
    """
    now = datetime.utcnow()
    rows = fetchall(
        """
        SELECT s.id, s.tg_id, s.plan_code, s.until, r.t3_sent, r.t1_sent, r.t0_sent
        FROM subscriptions s
        LEFT JOIN subscription_reminders r ON r.subscription_id = s.id
        """
    )
    result: list[dict[str, Any]] = []
    for r in rows:
        if not r.get("until"):
            continue
        try:
            until = datetime.fromisoformat(r["until"])  # type: ignore[index]
        except Exception:
            continue
        days_left = (until - now).days
        flags = {"t3": False, "t1": False, "t0": False}
        if days_left == 3 and not int(r.get("t3_sent") or 0):
            flags["t3"] = True
        if days_left == 1 and not int(r.get("t1_sent") or 0):
            flags["t1"] = True
        if days_left <= 0 and not int(r.get("t0_sent") or 0):
            flags["t0"] = True
        if any(flags.values()):
            result.append({**r, **flags})
    return result


def mark_reminder_sent(subscription_id: int, flag: str) -> None:
    execute(
        """
        INSERT INTO subscription_reminders (subscription_id, t3_sent, t1_sent, t0_sent)
        VALUES (?, 0, 0, 0)
        ON CONFLICT(subscription_id) DO NOTHING
        """,
        (subscription_id,),
    )
    column = {"t3": "t3_sent", "t1": "t1_sent", "t0": "t0_sent"}.get(flag)
    if column:
        # Safe whitelist; column name is validated explicitly
        assert column in {"t3_sent", "t1_sent", "t0_sent"}  # nosemgrep: trusted whitelist
        execute(f"UPDATE subscription_reminders SET {column} = 1 WHERE subscription_id = ?", (subscription_id,))


def find_due_expire() -> list[dict[str, Any]]:
    now = datetime.utcnow().isoformat(timespec="seconds")
    return fetchall(
        "SELECT id, tg_id, plan_code, until FROM subscriptions WHERE until IS NOT NULL AND until <= ?",
        (now,),
    )


