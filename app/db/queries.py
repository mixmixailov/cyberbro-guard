from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import json

from .session import execute, fetchone


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def ensure_user(tg_id: int, lang: str | None = None) -> dict[str, Any]:
    # Try insert; ignore on conflict
    execute(
        "INSERT OR IGNORE INTO users (tg_id, created_at, lang, plan) VALUES (?, ?, ?, 'free')",
        (tg_id, _now_iso(), lang),
    )
    user = get_user_by_tg_id(tg_id)
    return user if user else {"tg_id": tg_id}


def get_user_by_tg_id(tg_id: int) -> dict[str, Any] | None:
    return fetchone(
        "SELECT id, tg_id, created_at, lang, plan, until FROM users WHERE tg_id = ?",
        (tg_id,),
    )


def upsert_user_by_tg_id(tg_id: int, lang: str | None = None) -> dict[str, Any]:
    return ensure_user(tg_id, lang)


def create_payment(
    tg_id: int,
    amount_cents: int,
    currency: str,
    provider: str | None,
    status: str | None,
    raw_json: str | None,
) -> int:
    return execute(
        """
        INSERT INTO payments (tg_id, amount_cents, currency, provider, status, created_at, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (tg_id, amount_cents, currency, provider, status, _now_iso(), raw_json),
    )


def upgrade_user_to_pro(tg_id: int, days: int = 30) -> None:
    """Set user's plan to PRO and extend until by given days from now."""
    until_iso = (datetime.utcnow() + timedelta(days=days)).isoformat(timespec="seconds")
    # Ensure user exists first
    ensure_user(tg_id)
    execute(
        "UPDATE users SET plan = 'pro', until = ? WHERE tg_id = ?",
        (until_iso, tg_id),
    )


def get_user_state(user_id: int, chat_id: int) -> dict[str, Any] | None:
    row = fetchone(
        "SELECT user_id, chat_id, warns_24h, last_msgs FROM user_state WHERE user_id = ? AND chat_id = ?",
        (user_id, chat_id),
    )
    if not row:
        return None
    try:
        row["last_msgs"] = json.loads(row.get("last_msgs") or "{}")
    except Exception:
        row["last_msgs"] = {}
    return row


def upsert_user_state(user_id: int, chat_id: int, values: dict[str, Any]) -> None:
    current = get_user_state(user_id, chat_id) or {"warns_24h": 0, "last_msgs": {}}
    merged = {**current, **values, "user_id": user_id, "chat_id": chat_id}
    execute(
        """
        INSERT INTO user_state (user_id, chat_id, warns_24h, last_msgs)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, chat_id) DO UPDATE SET
            warns_24h=excluded.warns_24h,
            last_msgs=excluded.last_msgs
        """,
        (
            user_id,
            chat_id,
            int(merged.get("warns_24h") or 0),
            json.dumps(merged.get("last_msgs") or {}),
        ),
    )


def add_warn_and_maybe_ban(user_id: int, chat_id: int) -> tuple[int, int, bool]:
    """Increment warns_24h, reset window if >24h, return (new_count, threshold, banned)."""
    state = get_user_state(user_id, chat_id) or {"warns_24h": 0, "last_msgs": {}}
    meta = state.get("last_msgs") or {}
    now = datetime.now(timezone.utc)
    ts_iso = meta.get("warns_updated_at")
    if ts_iso:
        try:
            prev = datetime.fromisoformat(ts_iso)
            if (now - prev).total_seconds() > 24 * 3600:
                state["warns_24h"] = 0
        except Exception:
            state["warns_24h"] = 0
    meta["warns_updated_at"] = now.isoformat()
    state["warns_24h"] = int(state.get("warns_24h") or 0) + 1
    state["last_msgs"] = meta
    upsert_user_state(user_id, chat_id, state)
    # threshold from globals for now; TODO per-chat setting
    from app.config import get_settings  # local import to avoid cycles

    threshold = int(get_settings().WARNS_LIMIT_24H)
    banned = state["warns_24h"] >= threshold
    return int(state["warns_24h"]), threshold, banned

def upsert_chat(chat_id: int, title: str | None, chat_type: str | None, locale: str | None, enabled: bool) -> None:
    execute(
        """
        INSERT INTO chats (id, title, type, enabled, locale, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET title=excluded.title, type=excluded.type, enabled=excluded.enabled, locale=excluded.locale
        """,
        (chat_id, title, chat_type, int(enabled), locale, _now_iso()),
    )


def get_chat(chat_id: int) -> dict[str, Any] | None:
    return fetchone("SELECT id, title, type, enabled, locale, created_at FROM chats WHERE id = ?", (chat_id,))


def get_chat_settings(chat_id: int) -> dict[str, Any] | None:
    return fetchone(
        """
        SELECT chat_id, flood_n, flood_window_s, repeat_n, repeat_window_s, link_policy,
               captcha_mode, captcha_ttl_s, punish_policy, warns_limit, ban_days, link_allowlist
        FROM chat_settings WHERE chat_id = ?
        """,
        (chat_id,),
    )


def upsert_chat_settings(chat_id: int, values: dict[str, Any]) -> None:
    current = get_chat_settings(chat_id) or {}
    merged = {**current, **values, "chat_id": chat_id}
    execute(
        """
        INSERT INTO chat_settings (
            chat_id, flood_n, flood_window_s, repeat_n, repeat_window_s, link_policy,
            captcha_mode, captcha_ttl_s, punish_policy, warns_limit, ban_days, link_allowlist
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            flood_n=excluded.flood_n,
            flood_window_s=excluded.flood_window_s,
            repeat_n=excluded.repeat_n,
            repeat_window_s=excluded.repeat_window_s,
            link_policy=excluded.link_policy,
            captcha_mode=excluded.captcha_mode,
            captcha_ttl_s=excluded.captcha_ttl_s,
            punish_policy=excluded.punish_policy,
            warns_limit=excluded.warns_limit,
            ban_days=excluded.ban_days,
            link_allowlist=excluded.link_allowlist
        """,
        (
            chat_id,
            merged.get("flood_n"),
            merged.get("flood_window_s"),
            merged.get("repeat_n"),
            merged.get("repeat_window_s"),
            merged.get("link_policy"),
            merged.get("captcha_mode"),
            merged.get("captcha_ttl_s"),
            merged.get("punish_policy"),
            merged.get("warns_limit"),
            merged.get("ban_days"),
            merged.get("link_allowlist"),
        ),
    )


# --- AI usage (monthly per chat) ---

def _period_now() -> str:
    dt = datetime.utcnow()
    return dt.strftime("%Y-%m")


def ai_increment(chat_id: int, inc: int = 1) -> int:
    period = _period_now()
    execute(
        "INSERT INTO ai_usage (chat_id, period, ai_calls) VALUES (?, ?, 0) ON CONFLICT(chat_id, period) DO NOTHING",
        (chat_id, period),
    )
    return execute(
        "UPDATE ai_usage SET ai_calls = ai_calls + ? WHERE chat_id = ? AND period = ?",
        (int(inc), chat_id, period),
    )


def ai_get_usage(chat_id: int, period: str | None = None) -> int:
    p = period or _period_now()
    row = fetchone("SELECT ai_calls FROM ai_usage WHERE chat_id = ? AND period = ?", (chat_id, p))
    return int((row or {}).get("ai_calls") or 0)






