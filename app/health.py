from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import requests
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .config import get_settings
from .db.session import execute as db_execute


router = APIRouter()

_started_at = time.time()


def _version() -> str:
    return os.environ.get("APP_VERSION", "0.1.0")


@router.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": _version(),
        "uptime_s": int(time.time() - _started_at),
    }


@router.get("/readyz")
async def readyz() -> JSONResponse:
    settings = get_settings()
    # DB check
    try:
        await asyncio.to_thread(db_execute, "SELECT 1")
    except Exception:
        return JSONResponse({"ready": False, "db": False, "tg": None}, status_code=503)

    # Telegram API check (<=1s timeout)
    bot_token = settings.BOT_TOKEN
    if not bot_token:
        return JSONResponse({"ready": False, "db": True, "tg": False}, status_code=503)
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        resp = await asyncio.to_thread(requests.get, url, timeout=1)
        if not (resp.ok and resp.json().get("ok")):
            return JSONResponse({"ready": False, "db": True, "tg": False}, status_code=503)
    except Exception:
        return JSONResponse({"ready": False, "db": True, "tg": False}, status_code=503)

    return JSONResponse({"ready": True, "db": True, "tg": True}, status_code=200)


@router.get("/privacy")
async def privacy() -> dict[str, Any]:
    return {
        "service": "CyberBro Guard",
        "data": {
            "stored": [
                "per-chat moderation settings",
                "minimal user state (warn counters, captcha flags)",
                "payments/subscriptions metadata",
                "AI usage counters per chat per month",
            ],
            "logs": "No PII; tokens/emails masked; includes request/update correlation ids.",
            "retention": {
                "user_state": "~7 days",
                "subscription_reminders": "~30 days",
                "support_tickets": "closed > N days",
            },
        },
        "ai": {
            "enabled": True,
            "provider": "configurable",
            "policy": "Aggregated moderation; conservative fallback; soft monthly quotas per chat.",
        },
    }


