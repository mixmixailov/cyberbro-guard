from __future__ import annotations

from datetime import datetime
from typing import Any

from .session import execute, fetchone


def create_ticket(user_id: int, topic: str, status: str = "open") -> int:
    return execute(
        "INSERT INTO support_tickets (user_id, topic, status, created_at) VALUES (?, ?, ?, ?)",
        (user_id, topic, status, datetime.utcnow().isoformat(timespec="seconds")),
    )


def get_last_success_payment(uid: int) -> dict[str, Any] | None:
    # naive lookup by payments table status ok
    return fetchone(
        "SELECT id, raw_json FROM payments WHERE tg_id = ? AND status = 'ok' ORDER BY id DESC LIMIT 1",
        (uid,),
    )




































