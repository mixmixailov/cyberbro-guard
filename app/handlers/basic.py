from typing import Final
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters
import asyncio
from app.db import upsert_user_by_tg_id
from app.db.queries import upgrade_user_to_pro


START_TEXT: Final[str] = "CyberBro Guard на связи."
logger = logging.getLogger(__name__)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("start_cmd from uid=%s", getattr(update.effective_user, "id", None))
    # Reply only (DB disabled temporarily for diagnostics)
    if update.message:
        await update.message.reply_text(START_TEXT)
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
    app.add_handler(CommandHandler("plan", plan_cmd))
    app.add_handler(CommandHandler("buy_pro", buy_pro_cmd))
    app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))


async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("plan_cmd from uid=%s", getattr(update.effective_user, "id", None))
    user = update.effective_user
    if not user or not update.effective_message:
        return
    try:
        db_user = await asyncio.to_thread(
            upsert_user_by_tg_id,
            user.id,
            getattr(user, "language_code", None),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("plan_cmd upsert failed uid=%s err=%s", getattr(user, "id", None), exc)
        await update.effective_message.reply_text("Не удалось получить данные тарифа. Попробуйте позже.")
        return

    plan = (db_user.get("plan") or "free").lower()
    until = db_user.get("until")
    if plan == "pro":
        text = f"Ваш тариф: PRO\nДействует до: {until if until else 'не указано'}"
    else:
        text = "Ваш тариф: FREE\n" \
               "Доступ к расширенным функциям в PRO. Оформление пока недоступно (заглушка)."
    await update.effective_message.reply_text(text)


async def buy_pro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("buy_pro_cmd from uid=%s", getattr(update.effective_user, "id", None))
    if not update.effective_message:
        return
    # Mock invoice data (test)
    title = "CyberBro Guard PRO"
    description = "Подписка на 30 дней"
    payload = "buy_pro_30d"
    currency = "USD"
    prices = [
        {"label": "Subscription", "amount": 499}
    ]  # amount in minor units (e.g., cents)
    try:
        await update.effective_message.reply_invoice(
            title=title,
            description=description,
            payload=payload,
            provider_token="TEST:MOCK",  # mock token for test only
            currency=currency,
            prices=prices,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("buy_pro invoice error uid=%s err=%s", getattr(update.effective_user, "id", None), exc)
        await update.effective_message.reply_text("Платежи временно недоступны.")


async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    if not query:
        return
    try:
        await query.answer(ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("precheckout error uid=%s err=%s", getattr(update.effective_user, "id", None), exc)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.successful_payment:
        return
    uid = getattr(update.effective_user, "id", None)
    try:
        await asyncio.to_thread(upgrade_user_to_pro, int(uid), 30)
        await msg.reply_text("Оплата успешно получена. Тариф PRO активирован на 30 дней.")
    except Exception as exc:  # noqa: BLE001
        logger.error("successful_payment upgrade error uid=%s err=%s", uid, exc)
        await msg.reply_text("Оплата получена, но возникла ошибка при активации тарифа. Мы разберёмся.")


