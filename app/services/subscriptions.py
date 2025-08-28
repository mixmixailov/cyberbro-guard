from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram.ext import Application

from app.db.subscriptions import find_due_reminders, mark_reminder_sent, get_subscription, find_due_expire
from app.db.subscriptions import get_subscription as db_get_subscription
from app.db.session import execute
from app.utils.lang import t
from app.metrics import sched_runs_total, sched_errors_total
from app.config import get_settings


logger = logging.getLogger(__name__)


async def run_reminders(app: Application) -> None:
    """One-shot send of T-3/T-1/T0 reminders. To be scheduled periodically."""
    job = "renewal_reminders"
    sched_runs_total.labels(job).inc()
    try:
        due = find_due_reminders()
        for r in due:
            sub_id = int(r["id"])  # type: ignore[index]
            uid = int(r["tg_id"])  # type: ignore[index]
            if r.get("t3"):
                await app.bot.send_message(uid, t("payment.reminder.t3"))
                mark_reminder_sent(sub_id, "t3")
            if r.get("t1"):
                await app.bot.send_message(uid, t("payment.reminder.t1"))
                mark_reminder_sent(sub_id, "t1")
            if r.get("t0"):
                await app.bot.send_message(uid, t("payment.reminder.t0"))
                mark_reminder_sent(sub_id, "t0")
    except Exception as exc:  # noqa: BLE001
        sched_errors_total.labels(job).inc()
        logger.error("reminders run error: %s", exc)


def expire_due() -> None:
    """Expire subscriptions with until <= now()."""
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # Clear users plan where until passed
    execute("UPDATE users SET plan='free', until=NULL WHERE until IS NOT NULL AND until <= ?", (now_iso,))
    # Optionally add audit log write here later


def cleanup_old_data() -> None:
    s = get_settings()
    # user_state: 7 days default — we rely on warns_24h and last_msgs timestamps
    execute(
        "DELETE FROM user_state WHERE (SELECT COALESCE(MAX(created_at), '1970-01-01') FROM (SELECT 0)) IS NULL",
        (),
    )
    # subscription_reminders: older than N days by joining with subscriptions.until as guard (best-effort)
    execute(
        "DELETE FROM subscription_reminders WHERE rowid IN (SELECT r.rowid FROM subscription_reminders r JOIN subscriptions s ON s.id = r.subscription_id WHERE s.until <= datetime('now', ?))",
        (f"-{int(s.CLEANUP_REMINDERS_DAYS)} days",),
    )
    # support_tickets: closed older than N days
    execute(
        "DELETE FROM support_tickets WHERE status='closed' AND created_at <= datetime('now', ?)",
        (f"-{int(s.CLEANUP_TICKETS_DAYS)} days",),
    )

    # ai_usage: drop rows older than 120 days (safety)
    try:
        execute("DELETE FROM ai_usage WHERE period < strftime('%Y-%m', date('now', '-120 days'))", ())
    except Exception:
        pass


