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


def is_admin(user_id: int | None) -> bool:
    """Check if user ID is in admin list."""
    if not user_id:
        return False
    settings = get_settings()
    return int(user_id) in settings.ADMIN_IDS


def is_admin_request(update: Update) -> bool:
    """Check if request comes from admin user."""
    user = update.effective_user
    if not user:
        return False
    return is_admin(user.id)


def admin_only(func):
    """Decorator to restrict access to admin users only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin_request(update):
            if update.message:
                await update.message.reply_text("❌ This command is only available to administrators.")
            return
        return await func(update, context)
    return wrapper








































