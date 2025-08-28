from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.config import get_settings


async def admin_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return False
    settings = get_settings()
    if int(user.id) in settings.ADMIN_IDS:
        return True
    try:
        m = await context.bot.get_chat_member(chat.id, user.id)
        return m.status in {"creator", "administrator"}
    except Exception:
        return False




































