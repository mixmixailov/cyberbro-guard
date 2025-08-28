from __future__ import annotations

import hmac


def verify_secret(header_value: str | None, env_secret: str | None) -> bool:
    """Constant-time compare of webhook secret header.

    If env_secret is empty/None, validation is disabled and returns True.
    """
    expected = (env_secret or "").strip()
    if expected == "":
        return True
    actual = (header_value or "").strip()
    try:
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False
