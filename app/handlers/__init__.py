"""Handlers package setup for CyberBro Guard bot."""

import time
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler
from telegram.ext import ApplicationHandlerStop

from app.config import get_settings
from app.utils.lang import t

from .basic import register as register_basic
from .group import register as register_group
from .payments import register as register_payments
from .settings import register as register_settings
from app.services.moderation import ModerationService


async def _rate_limit_handler(update, context) -> None:  # type: ignore[no-untyped-def]
    user = getattr(update, "effective_user", None)
    message = getattr(update, "effective_message", None)
    if not user or not message:
        return
    settings = get_settings()
    now = time.monotonic()
    last = context.user_data.get("_last_cmd_ts", 0)
    if now - float(last) < 2.0:
        try:
            await message.reply_text(t("rate.limit", lang=getattr(user, "language_code", None) or settings.DEFAULT_LOCALE))
        finally:
            raise ApplicationHandlerStop
    context.user_data["_last_cmd_ts"] = now


def setup_handlers(app: Application) -> None:
    """Register all handlers on the provided PTB Application."""
    # Core routers
    app.add_handler(MessageHandler(filters.COMMAND, _rate_limit_handler), group=10)
    register_basic(app)
    register_group(app)
    register_payments(app)
    register_settings(app)
    # Support command in basic module
    from .basic import support_cmd
    app.add_handler(CommandHandler("support", support_cmd))
    # Moderation callbacks (captcha)
    service = ModerationService()
    app.add_handler(CallbackQueryHandler(service.on_callback), group=1)






