from __future__ import annotations

import hashlib
import hmac
import time
from enum import Enum
from typing import List, Tuple

from app.config import get_settings


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"


class CBPrefix(str, Enum):
    SETTINGS = "s"
    CAPTCHA = "c"
    MODERATION = "m"


def _sign(payload: str) -> str:
    secret = get_settings().WEBHOOK_SECRET or ""
    if not secret:
        return "0"
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:12]


def build_v1(parts: List[str]) -> str:
    ts = str(int(time.time()))
    body = ":".join(["v1", ts, *parts])
    sig = _sign(body)
    return f"{body}:{sig}"


def verify_v1(payload: str) -> Tuple[bool, List[str]]:
    parts = (payload or "").split(":")
    if not parts or parts[0] != "v1" or len(parts) < 4:
        return False, []
    sig = parts[-1]
    body = ":".join(parts[:-1])
    expected = _sign(body)
    # Signature check (if secret set)
    if (get_settings().WEBHOOK_SECRET or "") and not hmac.compare_digest(sig, expected):
        return False, []
    # TTL check
    try:
        ts = int(parts[1])
        now = int(time.time())
        ttl = int(get_settings().CALLBACK_TTL_S)
        if now - ts > ttl or ts > now + 60:
            return False, []
    except Exception:
        return False, []
    # Return logical parts without version and ts and without signature
    return True, parts[2:-1]


def build_settings_toggle(feature: str, value: bool) -> str:
    return build_v1([CBPrefix.SETTINGS, "toggle", feature, str(int(value))])


def build_captcha_answer(ok: bool) -> str:
    return build_v1([CBPrefix.CAPTCHA, "ans", str(int(ok))])


def parse_callback(data: str) -> tuple[str, list[str]]:
    ok, parts = verify_v1(data)
    if not ok or not parts:
        return "", []
    return parts[0], parts[1:]


def build_settings_adjust(key: str, op: str, step: int) -> str:
    # op in {inc, dec}
    return build_v1([CBPrefix.SETTINGS, "adj", key, op, str(step)])


def build_settings_set(key: str, value: str) -> str:
    return build_v1([CBPrefix.SETTINGS, "set", key, value])


def build_settings_allowlist() -> str:
    return build_v1([CBPrefix.SETTINGS, "allowlist", "edit"])


def build_settings_info() -> str:
    return build_v1([CBPrefix.SETTINGS, "info"])


def build_settings_open() -> str:
    return build_v1([CBPrefix.SETTINGS, "open"])


def build_settings_help() -> str:
    return build_v1([CBPrefix.SETTINGS, "help"])


def build_settings_buy() -> str:
    return build_v1([CBPrefix.SETTINGS, "buy"])
