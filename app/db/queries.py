from __future__ import annotations

from datetime import datetime
from typing import Any

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




