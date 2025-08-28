from __future__ import annotations

from datetime import datetime

from .session import execute


def log_action(payment_id: int, action: str) -> int:
    return execute(
        "INSERT INTO payment_audit (payment_id, action, ts) VALUES (?, ?, ?)",
        (payment_id, action, datetime.utcnow().isoformat(timespec="seconds")),
    )








































