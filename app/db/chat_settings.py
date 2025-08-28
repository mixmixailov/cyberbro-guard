from __future__ import annotations

from typing import Any

from app.config import get_settings

from .queries import get_chat_settings, upsert_chat_settings


def get_effective_settings(chat_id: int) -> dict[str, Any]:
    """Merge per-chat settings from DB with global defaults from env.

    DB nulls are ignored; only non-null override globals.
    """
    s = get_settings()
    defaults: dict[str, Any] = {
        "flood_n": s.FLOOD_N,
        "flood_window_s": s.FLOOD_WINDOW_S,
        "repeat_n": s.REPEAT_N,
        "repeat_window_s": s.REPEAT_WINDOW_S,
        "link_policy": s.LINK_POLICY,
        "captcha_mode": "soft",
        "captcha_ttl_s": s.CAPTCHA_TTL_S,
        "punish_policy": "mute",
        "warns_limit": s.WARNS_LIMIT_24H,
        "ban_days": s.BAN_DAYS,
        "link_allowlist": "",
    }
    row = get_chat_settings(chat_id)
    if not row:
        return defaults
    merged = defaults.copy()
    for k, v in row.items():
        if k == "chat_id":
            continue
        if v is not None:
            merged[k] = v
    return merged


def parse_allowlist_csv(text: str) -> str:
    items = [p.strip().lower() for p in (text or "").split(",") if p.strip()]
    # simple normalization: keep domain chars, dots and dashes
    normalized = []
    for it in items:
        it = it.replace("http://", "").replace("https://", "").replace("www.", "")
        normalized.append("".join(ch for ch in it if ch.isalnum() or ch in {".", "-"}))
    return ",".join(sorted(set(filter(None, normalized))))


def set_settings(chat_id: int, values: dict[str, Any]) -> None:
    # Clean allowlist if present
    if "link_allowlist" in values and isinstance(values["link_allowlist"], str):
        values = {**values, "link_allowlist": parse_allowlist_csv(values["link_allowlist"])}
    upsert_chat_settings(chat_id, values)
