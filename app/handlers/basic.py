from typing import Final
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
from app.db import upsert_user_by_tg_id


START_TEXT: Final[str] = "CyberBro Guard на связи."
logger = logging.getLogger(__name__)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("start_cmd from uid=%s", getattr(update.effective_user, "id", None))
    # Reply only (DB disabled temporarily for diagnostics)
    if update.message:
        await update.message.reply_text(START_TEXT)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", start_cmd))


