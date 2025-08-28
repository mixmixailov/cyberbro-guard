import asyncio
import logging
from typing import Final

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import get_settings
from app.db import upsert_user_by_tg_id
from app.utils.callbacks import build_settings_buy, build_settings_help, build_settings_open
from app.utils.lang import t
from app.utils.sender import send_text

START_TEXT: Final[str] = t("start.welcome")
logger = logging.getLogger(__name__)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("start_cmd from uid=%s", getattr(update.effective_user, "id", None))
    if update.message:
        # choose language by user, fallback to default
        lang = (
            getattr(update.effective_user, "language_code", None) or get_settings().DEFAULT_LOCALE
        )
        if getattr(update.effective_chat, "type", None) == "private":
            ikb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(text="🚀 Start", callback_data=build_settings_open())],
                    [InlineKeyboardButton(text="⚙️ Settings", callback_data=build_settings_open())],
                    [InlineKeyboardButton(text="ℹ️ Help", callback_data=build_settings_help())],
                    [InlineKeyboardButton(text="💳 Buy PRO", callback_data=build_settings_buy())],
                ]
            )
            try:
                # Use send queue if available
                await send_text(
                    context,
                    update.effective_chat.id,
                    t("start.welcome", lang=lang),
                    reply_markup=ikb,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("reply_text failed: %s", exc, exc_info=True)
        else:
            try:
                await send_text(context, update.effective_chat.id, t("start.welcome", lang=lang))
            except Exception as exc:  # noqa: BLE001
                logger.error("reply_text failed: %s", exc, exc_info=True)
    # Upsert user in background (non-blocking)
    user = update.effective_user
    if user:
        try:
            await asyncio.to_thread(
                upsert_user_by_tg_id,
                user.id,
                getattr(user, "language_code", None),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("start_cmd upsert failed uid=%s err=%s", user.id, exc)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("support", support_cmd))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = getattr(user, "language_code", None) or get_settings().DEFAULT_LOCALE
    msg = update.effective_message
    chat_type = getattr(update.effective_chat, "type", None)
    if not msg:
        return
    if chat_type == "private":
        await msg.reply_text(t("help.private", lang=lang))
    else:
        await msg.reply_text(t("help.group", lang=lang))


async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = getattr(user, "language_code", None) or get_settings().DEFAULT_LOCALE
    if update.effective_message:
        await update.effective_message.reply_text(t("support.info", lang=lang))

    # Note: payments handlers manage invoices and successful_payment
