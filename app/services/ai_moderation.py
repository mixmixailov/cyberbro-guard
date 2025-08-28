from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)


Action = Literal["block", "flag", "allow"]


@dataclass
class ModerationResult:
    allowed: bool
    action: Action
    reason: str | None = None


class ModerationProvider(ABC):
    @abstractmethod
    def moderate(self, text: str) -> ModerationResult:  # pragma: no cover - interface
        raise NotImplementedError


class OpenAIModerationProvider(ModerationProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def moderate(self, text: str) -> ModerationResult:
        # Use OpenAI moderation v1.0 endpoint; aggregate result only
        try:
            resp = requests.post(
                "https://api.openai.com/v1/moderations",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": "omni-moderation-latest", "input": text},
                timeout=2,
            )
            resp.raise_for_status()
            data = resp.json()
            flagged = bool((data.get("results") or [{}])[0].get("flagged", False))
            action_on_flag = get_settings().AI_MODERATION_ACTION_ON_FLAG.lower()
            if flagged:
                if action_on_flag == "block":
                    return ModerationResult(allowed=False, action="block", reason="flagged")
                if action_on_flag == "flag":
                    return ModerationResult(allowed=True, action="flag", reason="flagged")
                return ModerationResult(allowed=True, action="allow", reason="flagged")
            return ModerationResult(allowed=True, action="allow")
        except Exception as exc:  # noqa: BLE001
            # Fail-open or fail-closed per config
            fail_open = bool(get_settings().AI_MODERATION_FAIL_OPEN)
            logger.error("ai_moderation error: %s", exc)
            return ModerationResult(
                allowed=fail_open, action="allow" if fail_open else "block", reason="error"
            )


def get_provider() -> ModerationProvider | None:
    s = get_settings()
    if not s.AI_MODERATION_ENABLED:
        return None
    if s.AI_MODERATION_PROVIDER.lower() == "openai" and s.OPENAI_API_KEY:
        return OpenAIModerationProvider(s.OPENAI_API_KEY)
    return None
