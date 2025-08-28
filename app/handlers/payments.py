from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from app.config import get_settings
from app.db.payment_audit import log_action
from app.db.payments import record_refunded_payment, record_star_transaction
from app.db.queries import ai_get_usage
from app.db.subscriptions import get_subscription
from app.metrics import payments_total
from app.services.payments import (
    handle_pre_checkout,
    handle_successful_payment,
    init_plans,
    refund_last,
    send_pro_invoice,
)
from app.utils.lang import t

logger = logging.getLogger(__name__)


async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not (user and msg):
        return
    s = get_settings()
    sub = get_subscription(int(user.id), "pro")
    # If in group, also show AI quota usage for the chat
    quota_line = ""
    if getattr(update.effective_chat, "type", None) in {"group", "supergroup"}:
        try:
            used = ai_get_usage(int(update.effective_chat.id))
            quota_line = f"\nAI quota: {used}/{int(s.AI_MONTHLY_QUOTA)}"
        except Exception:
            quota_line = ""
    if sub and sub.get("until"):
        await msg.reply_text(
            t(
                "plan.pro",
                lang=getattr(user, "language_code", None) or s.DEFAULT_LOCALE,
                until=sub.get("until"),
            )
            + quota_line
        )
    else:
        await msg.reply_text(
            t("plan.free", lang=getattr(user, "language_code", None) or s.DEFAULT_LOCALE)
            + quota_line
        )


async def buy_pro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_pro_invoice(update, context)


async def refund_last_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Only in private
    if getattr(update.effective_chat, "type", None) != "private":
        return
    await refund_last(update, context)


async def handle_star_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle StarTransaction updates from Telegram.

    StarTransaction represents various Star-related events:
    - User purchases Stars
    - Stars used for payments
    - Other Star operations
    """
    msg = update.message
    user = update.effective_user

    if not (msg and user and hasattr(msg, "star_transaction")):
        return

    star_tx = msg.star_transaction
    if not star_tx:
        return

    uid = int(user.id)

    try:
        # Record StarTransaction for audit trail
        payment_id = record_star_transaction(
            tg_id=uid,
            transaction_data=star_tx.to_dict(),
        )

        if payment_id:
            log_action(payment_id, "star_transaction_recorded")
            payments_total.labels("star_transaction").inc()

        logger.info(
            "StarTransaction processed: user_id=%d, tx_id=%s, payment_id=%d",
            uid,
            star_tx.id,
            payment_id,
        )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "StarTransaction processing error: user_id=%d, tx_id=%s, error=%s",
            uid,
            getattr(star_tx, "id", "unknown"),
            exc,
        )
        payments_total.labels("star_transaction_error").inc()


async def handle_refunded_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle RefundedPayment updates from Telegram.

    RefundedPayment is sent when a previous payment is refunded:
    - Automatic refunds (policy violations)
    - Manual refunds (user request)
    - System refunds (errors)
    """
    msg = update.message
    user = update.effective_user

    if not (msg and user and hasattr(msg, "refunded_payment")):
        return

    refunded = msg.refunded_payment
    if not refunded:
        return

    uid = int(user.id)
    charge_id = getattr(refunded, "telegram_payment_charge_id", None)

    try:
        # Record RefundedPayment for audit and user account updates
        payment_id = record_refunded_payment(
            tg_id=uid,
            refund_data=refunded.to_dict(),
        )

        if payment_id:
            log_action(payment_id, "refund_processed")
            payments_total.labels("refunded").inc()

        logger.info(
            "RefundedPayment processed: user_id=%d, charge_id=%s, payment_id=%d",
            uid,
            charge_id,
            payment_id,
        )

        # Notify user about refund
        try:
            amount = getattr(refunded, "total_amount", 0)
            currency = getattr(refunded, "currency", "XTR")
            await msg.reply_text(
                f"💫 Возврат обработан: {amount} {currency}\n"
                f"Средства будут зачислены в течение нескольких минут."
            )
        except Exception as notify_exc:
            logger.warning(
                "Failed to notify user about refund: user_id=%d, error=%s", uid, notify_exc
            )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "RefundedPayment processing error: user_id=%d, charge_id=%s, error=%s",
            uid,
            charge_id,
            exc,
        )
        payments_total.labels("refund_error").inc()

        # Best-effort notification about refund processing error
        try:
            await msg.reply_text(
                "⚠️ Ошибка обработки возврата. Обратитесь в поддержку если средства не поступили."
            )
        except Exception:
            pass


def register(app: Application) -> None:
    s = get_settings()
    init_plans()
    app.add_handler(CommandHandler("plan", plan_cmd))
    if s.PAYMENTS_STARS_ENABLED:
        app.add_handler(CommandHandler("buy_pro", buy_pro_cmd))
        app.add_handler(CommandHandler("refund_last", refund_last_cmd))
        app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))

        # Extended Star payment handlers
        app.add_handler(
            MessageHandler(
                filters.MessageFilter(lambda msg: hasattr(msg, "star_transaction")),
                handle_star_transaction,
            )
        )
        app.add_handler(
            MessageHandler(
                filters.MessageFilter(lambda msg: hasattr(msg, "refunded_payment")),
                handle_refunded_payment,
            )
        )
