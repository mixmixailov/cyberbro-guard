from __future__ import annotations

import asyncio
import logging
import time
import random
from dataclasses import dataclass
from typing import Any, Optional

from telegram.error import RetryAfter, TimedOut, NetworkError

from ..config import get_settings
from ..metrics import retry_total, backoff_seconds


logger = logging.getLogger(__name__)


@dataclass
class _Item:
    method: str
    chat_id: int
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class SendQueue:
    """Async send queue with jittered exponential backoff and rate limits.

    Goals:
    - ~30 msg/s global cap (sleep between sends)
    - ~1 msg/s per chat_id cap (spacing)
    - Handle RetryAfter/TimedOut/NetworkError with decorrelated jitter
    - Proper metrics and structured logging for retry attempts
    """

    def __init__(self, bot) -> None:  # type: ignore[no-untyped-def]
        self._bot = bot
        self._q: asyncio.Queue[_Item] = asyncio.Queue(maxsize=2000)
        self._task: Optional[asyncio.Task] = None
        self._last_by_chat: dict[int, float] = {}
        self._last_global: float = 0.0
        self._settings = get_settings()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:  # noqa: BLE001
                pass

    async def send_text(self, chat_id: int, text: str, **kwargs: Any) -> None:
        await self._q.put(_Item("send_message", chat_id, (text,), kwargs))

    async def edit_text(self, chat_id: int, message_id: int, text: str, **kwargs: Any) -> None:
        await self._q.put(_Item("edit_message_text", chat_id, (text,), {"message_id": message_id, **kwargs}))

    async def _worker(self) -> None:
        while True:
            item = await self._q.get()
            try:
                await self._send(item)
            except Exception as exc:  # noqa: BLE001
                logger.error("send failure chat=%s method=%s err=%s", item.chat_id, item.method, exc)
            finally:
                self._q.task_done()

    def _calculate_jittered_backoff(self, attempt: int, base_delay: float | None = None) -> float:
        """Calculate jittered exponential backoff delay using decorrelated jitter.
        
        Args:
            attempt: Current retry attempt (1-based)
            base_delay: Base delay override (for RetryAfter scenarios)
            
        Returns:
            Delay in seconds with jitter applied
        """
        if base_delay is not None:
            # RetryAfter scenario: use provided delay ±30% jitter
            jitter_range = base_delay * 0.3
            return base_delay + random.uniform(-jitter_range, jitter_range)
        
        # Regular exponential backoff with decorrelated jitter
        base = self._settings.BACKOFF_BASE
        max_delay = self._settings.BACKOFF_MAX
        
        if self._settings.BACKOFF_JITTER == "full":
            # Full jitter: random between 0 and exponential backoff
            exp_backoff = min(base * (2 ** (attempt - 1)), max_delay)
            return random.uniform(0, exp_backoff)
        elif self._settings.BACKOFF_JITTER == "decorrelated":
            # Decorrelated jitter: blend of previous delay and exponential
            if attempt == 1:
                return random.uniform(0, base)
            exp_backoff = min(base * (2 ** (attempt - 1)), max_delay)
            return random.uniform(base, exp_backoff * 3)
        else:
            # No jitter: pure exponential backoff
            return min(base * (2 ** (attempt - 1)), max_delay)

    async def _send(self, item: _Item) -> None:
        now = time.monotonic()
        # Per-chat spacing ~1 msg/s
        last = self._last_by_chat.get(item.chat_id, 0.0)
        delta = now - last
        if delta < 1.0:
            await asyncio.sleep(1.0 - delta)
        # Global cap ~30 msg/s
        gdelta = now - self._last_global
        if gdelta < (1.0 / 30.0):
            await asyncio.sleep((1.0 / 30.0) - gdelta)

        attempt = 0
        max_attempts = 5
        
        while True:
            attempt += 1
            try:
                if item.method == "send_message":
                    await self._bot.send_message(item.chat_id, *item.args, **item.kwargs)
                elif item.method == "edit_message_text":
                    await self._bot.edit_message_text(chat_id=item.chat_id, *item.args, **item.kwargs)
                else:
                    logger.warning("unknown send method: %s", item.method)
                    
                # Success: update rate limit trackers
                self._last_by_chat[item.chat_id] = time.monotonic()
                self._last_global = time.monotonic()
                return
                
            except RetryAfter as e:  # type: ignore[misc]
                retry_after = float(getattr(e, "retry_after", 1.0)) or 1.0
                wait_time = self._calculate_jittered_backoff(attempt, retry_after)
                wait_ms = int(wait_time * 1000)
                
                # Metrics and logging
                retry_total.labels(reason="rate_limit").inc()
                backoff_seconds.observe(wait_time)
                logger.info(
                    "Rate limit hit, backing off",
                    extra={
                        "chat_id": item.chat_id,
                        "method": item.method,
                        "attempt": attempt,
                        "retry_after": retry_after,
                        "wait_ms": wait_ms,
                        "reason": "rate_limit"
                    }
                )
                
                await asyncio.sleep(wait_time)
                continue
                
            except (TimedOut, NetworkError) as e:
                if attempt > max_attempts:
                    # Final attempt failed
                    retry_total.labels(reason="max_attempts_exceeded").inc()
                    logger.error(
                        "Send failed after max attempts",
                        extra={
                            "chat_id": item.chat_id,
                            "method": item.method,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "reason": "max_attempts_exceeded",
                            "error": str(e)
                        }
                    )
                    raise
                
                # Calculate backoff for network errors
                wait_time = self._calculate_jittered_backoff(attempt)
                wait_ms = int(wait_time * 1000)
                
                # Metrics and logging
                retry_total.labels(reason="network_error").inc()
                backoff_seconds.observe(wait_time)
                logger.warning(
                    "Network error, retrying with backoff",
                    extra={
                        "chat_id": item.chat_id,
                        "method": item.method,
                        "attempt": attempt,
                        "wait_ms": wait_ms,
                        "reason": "network_error",
                        "error": str(e)
                    }
                )
                
                await asyncio.sleep(wait_time)













