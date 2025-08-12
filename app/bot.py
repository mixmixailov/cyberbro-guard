import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Простая проверка, что бот жив."""
    text = (
        "CyberBro Guard online.\n"
        "Добавь меня в группу и выдай права администратора, чтобы я мог модерировать."
    )
    if update.message:
        await update.message.reply_text(text)


def build_application() -> Application:
    """Создаёт PTB Application, регистрирует базовые хендлеры."""
    # Этот модуль больше не используется для конфигурации; актуальная сборка в app/main.py
    # Оставлен для совместимости/будущих расширений, если потребуется.
    application = Application.builder().updater(None).build()
    application.add_handler(CommandHandler("start", cmd_start))
    return application
