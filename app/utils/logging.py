from __future__ import annotations

import contextvars
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

# Correlation context
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
update_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "update_id", default=None
)
chat_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar("chat_id", default=None)
user_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar("user_id", default=None)

# Observability context
area_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("area", default=None)
job_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("job_id", default=None)


def set_request_id(request_id: str | None) -> None:
    request_id_var.set(request_id)


def set_update_context(update_id: int | None, chat_id: int | None, user_id: int | None) -> None:
    update_id_var.set(update_id)
    chat_id_var.set(chat_id)
    user_id_var.set(user_id)


def set_area(area: str | None) -> None:
    """Set current processing area for observability."""
    area_var.set(area)


def set_job_id(job_id: str | None) -> None:
    """Set current job/task ID for observability."""
    job_id_var.set(job_id)


def get_area() -> str | None:
    """Get current processing area."""
    return area_var.get()


def get_job_id() -> str | None:
    """Get current job/task ID.""" 
    return job_id_var.get()


EMAIL_RE = re.compile(r"([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
PHONE_RE = re.compile(r"\b(?:\+?\d[\s\-]?)?(?:\(?\d{2,3}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{2,4}\b")
TOKEN_RE = re.compile(r"\b(?:Bearer|Bot)\s+([A-Za-z0-9:_\-]{16,})\b", re.IGNORECASE)


def _mask_tail(s: str, keep: int = 4) -> str:
    if len(s) <= keep:
        return "*" * len(s)
    return "*" * (len(s) - keep) + s[-keep:]


def mask_pii(text: str) -> str:
    masked = EMAIL_RE.sub(lambda m: f"***@{m.group(2)}", text)
    masked = TOKEN_RE.sub(lambda m: f"{m.group(0).split()[0]} {_mask_tail(m.group(1))}", masked)
    # phones: rough masking keeping last 4
    masked = PHONE_RE.sub(lambda m: _mask_tail(m.group(0)), masked)
    return masked


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        message = super().format(record)
        
        # Import here to avoid circular imports
        from app.utils.diag import get_trace_id, get_issue_id, get_hypothesis_id
        
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "area": area_var.get(),
            "chat_id": chat_id_var.get(),
            "job_id": job_id_var.get(),
            "issue_id": get_issue_id(),
            "trace_id": get_trace_id(),
            "logger": record.name,
            "msg": mask_pii(message),
            "request_id": request_id_var.get(),
            "update_id": update_id_var.get(),
            "user_id": user_id_var.get(),
            "hypothesis_id": get_hypothesis_id(),
        }
        
        # Include any extra fields from the log record
        if hasattr(record, "extra") and record.extra:
            payload.update(record.extra)
            
        return json.dumps(payload, ensure_ascii=False)


def install_json_logging(debug: bool = False) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if debug else logging.INFO)
