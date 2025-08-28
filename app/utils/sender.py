from __future__ import annotations

from typing import Any

from telegram.ext import ContextTypes


async def send_text(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs: Any
) -> None:
    sq = None
    try:
        if context and context.application:
            sq = context.application.bot_data.get("send_queue")
    except Exception:
        sq = None
    if sq is not None:
        await sq.send_text(chat_id, text, **kwargs)
    else:
        await context.bot.send_message(chat_id, text, **kwargs)
