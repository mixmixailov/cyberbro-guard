from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException

from .config import get_settings


router = APIRouter(prefix="/admin", tags=["admin"])  # type: ignore[call-arg]


def _require_token(token_hdr: str | None) -> None:
    expected = (os.environ.get("ADMIN_PANEL_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=403, detail="admin disabled")
    actual = (token_hdr or "").strip()
    if not actual or actual != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/status")
def status(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    _require_token(x_admin_token)
    s = get_settings()
    # Snapshot of key flags
    return {
        "debug": s.DEBUG,
        "use_webhook": s.USE_WEBHOOK,
        "use_polling": s.USE_POLLING,
        "ai_enabled": s.AI_MODERATION_ENABLED,
        "ai_fail_open": s.AI_MODERATION_FAIL_OPEN,
        "rate_limit_scope": s.RATE_LIMIT_SCOPE,
        "sched_enabled": s.SCHED_ENABLED,
    }


@router.post("/toggles")
def toggles(payload: Dict[str, Any], x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    _require_token(x_admin_token)
    # Allow subset of env-toggles at runtime (process-level)
    allowed_keys = {
        "AI_MODERATION_ENABLED",
        "AI_MODERATION_FAIL_OPEN",
        "USE_WEBHOOK",
        "USE_POLLING",
        "SCHED_ENABLED",
        "RATE_LIMIT_SCOPE",
    }
    changed: Dict[str, Any] = {}
    for k, v in (payload or {}).items():
        if k not in allowed_keys:
            continue
        if isinstance(v, bool):
            os.environ[k] = "true" if v else "false"
        else:
            os.environ[k] = str(v)
        changed[k] = os.environ[k]
    # Return fresh snapshot
    return {"ok": True, "changed": changed, "settings": status(x_admin_token)}













