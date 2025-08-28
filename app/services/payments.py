from __future__ import annotations

import logging
from typing import Final
import asyncio
import json

from telegram import LabeledPrice, SuccessfulPayment, Update
from telegram.ext import ContextTypes

from app.config import get_settings
from app.db.payments import record_payment, seen_charge_id
from app.db.subscriptions import ensure_plan, upsert_subscription
from app.db.queries import upgrade_user_to_pro
from app.db.support import create_ticket, get_last_success_payment
from app.db.payment_audit import log_action
from app.metrics import payments_total
from app.services.idempotency import IdempotencyStore, make_key
from app.services.idempotency_guard import with_idempotency


logger = logging.getLogger(__name__)

PLAN_CODE: Final[str] = "pro"


def init_plans() -> None:
    s = get_settings()
    ensure_plan(PLAN_CODE, int(s.PRO_PRICE_XTR), int(s.PRO_PERIOD_DAYS))


async def send_pro_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if not (message and user):
        return
    s = get_settings()
    prices = [LabeledPrice(label="PRO", amount=int(s.PRO_PRICE_XTR))]
    title = "CyberBro Guard PRO"
    description = f"Подписка на {s.PRO_PERIOD_DAYS} дней"
    payload = f"buy_{PLAN_CODE}_{s.PRO_PERIOD_DAYS}d"
    currency = "XTR"
    provider_token = ""  # For Stars, provider_token is not required
    # Retry sendInvoice up to 3 times
    last_err: Exception | None = None
    for _ in range(3):
        try:
            await message.reply_invoice(
                title=title,
                description=description,
                payload=payload,
                provider_token=provider_token,
                currency=currency,
                prices=prices,
                start_parameter=payload,
                provider_data={"test": bool(s.PAYMENTS_STARS_TEST)},
            )
            last_err = None
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            await asyncio.sleep(0.3)
    if last_err is not None:
        logger.error("send_invoice failed after retries uid=%s err=%s", getattr(user, "id", None), last_err)
        try:
            await message.reply_text("Платежи временно недоступны.")
        except Exception:
            pass
        # Record failed attempt
        try:
            record_payment(
                tg_id=int(getattr(user, "id", 0) or 0),
                amount_cents=int(s.PRO_PRICE_XTR),
                currency="XTR",
                provider="stars",
                status="failed_api",
                raw={"error": str(last_err)},
            )
            payments_total.labels("failed_api").inc()
        except Exception:
            pass
        # Admin alert (best-effort)
        try:
            for admin_id in list(get_settings().ADMIN_IDS):
                try:
                    await context.bot.send_message(int(admin_id), "Invoice send failed (Stars). Check logs.")
                except Exception:
                    continue
        except Exception:
            pass
        if not s.PAYMENTS_FAIL_OPEN:
            return


async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.pre_checkout_query
    if not q:
        return
    try:
        await q.answer(ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("pre_checkout error uid=%s err=%s", getattr(update.effective_user, "id", None), exc)


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.successful_payment:
        return
    sp: SuccessfulPayment = msg.successful_payment
    uid = int(getattr(update.effective_user, "id", 0) or 0)
    charge_id = getattr(sp, "telegram_payment_charge_id", None)
    if charge_id and seen_charge_id(charge_id):
        return
    # Idempotency on payment charge id
    store = IdempotencyStore()
    pkey = make_key("payment", str(charge_id or "")) if charge_id else make_key("payment", f"{uid}:{int(sp.total_amount)}:{sp.currency}")
    async def _process() -> None:
        payment_id = 0
        try:
            payment_id = record_payment(
                tg_id=uid,
                amount_cents=int(sp.total_amount),
                currency=str(sp.currency),
                provider="stars",
                status="ok",
                raw=sp.to_dict(),
                charge_id=charge_id,
            )
            if payment_id:
                log_action(payment_id, "created")
            payments_total.labels("ok").inc()
        except Exception as exc:  # noqa: BLE001
            logger.error("record_payment error uid=%s err=%s", uid, exc)
    # Upgrade subscription
    async def _activate() -> None:
        try:
            s = get_settings()
            upsert_subscription(uid, PLAN_CODE, int(s.PRO_PERIOD_DAYS))
            await context.application.run_in_threadpool(upgrade_user_to_pro, uid, int(s.PRO_PERIOD_DAYS))
            try:
                await msg.reply_text(
                    f"Квитанция: план PRO, сумма {int(sp.total_amount)} {sp.currency}, срок {get_settings().PRO_PERIOD_DAYS} дней."
                )
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            logger.error("activate_pro error uid=%s err=%s", uid, exc)

    await with_idempotency(pkey, _process, store)
    await _activate()


async def refund_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if not (message and user):
        return
    s = get_settings()
    uid = int(user.id)
    # fetch last successful payment
    row = get_last_success_payment(uid)
    if not row:
        await message.reply_text("Нет успешных платежей для возврата.")
        return
    try:
        raw = row.get("raw_json") or "{}"
        data = json.loads(raw)
        charge_id = data.get("telegram_payment_charge_id")
        provider_charge_id = data.get("provider_payment_charge_id")
        if not charge_id:
            await message.reply_text("Чек недоступен для рефанда.")
            return
        # Enforce refund window by created_at policy if available
        created_at = data.get("date") or data.get("created_at")
        try:
            # try integer seconds first (Bot API messages often have date)
            if isinstance(created_at, int):
                from datetime import datetime, timezone
                ts = datetime.fromtimestamp(created_at, tz=timezone.utc)
            else:
                from datetime import datetime
                ts = datetime.fromisoformat(str(created_at)) if created_at else None
        except Exception:
            ts = None  # type: ignore[assignment]
        if ts is not None:
            from datetime import datetime, timezone, timedelta
            if datetime.now(timezone.utc) - ts > timedelta(hours=int(get_settings().REFUND_WINDOW_H)):
                await message.reply_text("Срок для возврата истёк.")
                return
        # Create support ticket and inform user
        create_ticket(uid, f"refund:{charge_id}")
        try:
            await context.bot.refund_star_payment(user.id, telegram_payment_charge_id=charge_id)
            await message.reply_text("Запрос на возврат Stars отправлен. Ожидайте уведомления.")
        except Exception as exc:  # noqa: BLE001
            logger.error("refund api error uid=%s err=%s", uid, exc)
            await message.reply_text("Не удалось инициировать возврат. Мы уже получили тикет и разберёмся.")
    except Exception as exc:  # noqa: BLE001
        logger.error("refund parse error uid=%s err=%s", uid, exc)
        await message.reply_text("Ошибка обработки последнего платежа.")


