from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.db.chat_settings import get_effective_settings, set_settings
from app.services.payments import send_pro_invoice
from app.utils.admin import admin_required
from app.utils.callbacks import (
    CBPrefix,
    build_settings_adjust,
    build_settings_allowlist,
    build_settings_info,
    build_settings_set,
    build_settings_toggle,
    parse_callback,
)
from app.utils.lang import t
from app.utils.sender import send_text

logger = logging.getLogger(__name__)


SET_KEYS_NUM = [
    ("FLOOD_N", "flood_n", 1),
    ("FLOOD_WINDOW_S", "flood_window_s", 1),
    ("REPEAT_N", "repeat_n", 1),
    ("REPEAT_WINDOW_S", "repeat_window_s", 5),
    ("CAPTCHA_TTL_S", "captcha_ttl_s", 5),
    ("WARNS_LIMIT_24H", "warns_limit", 1),
    ("BAN_DAYS", "ban_days", 1),
]


def _menu(chat_id: int) -> InlineKeyboardMarkup:
    s = get_effective_settings(chat_id)
    rows = []
    rows.append(
        [
            InlineKeyboardButton(
                text=f"Moderation: {'ON' if s else 'OFF'}",
                callback_data=build_settings_toggle("enabled", True),
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"Welcome: {'ON' if s.get('welcome_enabled', 1) else 'OFF'}",
                callback_data=build_settings_toggle(
                    "welcome_enabled", not s.get("welcome_enabled", 1)
                ),
            )
        ]
    )
    for env_key, db_key, step in SET_KEYS_NUM:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{env_key}: {s.get(db_key)}",
                    callback_data=build_settings_set(db_key, str(s.get(db_key))),
                ),
                InlineKeyboardButton(
                    text="-", callback_data=build_settings_adjust(db_key, "dec", step)
                ),
                InlineKeyboardButton(
                    text="+", callback_data=build_settings_adjust(db_key, "inc", step)
                ),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"LINK_POLICY: {s.get('link_policy')}",
                callback_data=build_settings_set("link_policy", s.get("link_policy", "restricted")),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text="Allowlist links", callback_data=build_settings_allowlist()),
        ]
    )
    # Moderation reasons preview (localized keys)
    rows.append(
        [
            InlineKeyboardButton(
                text="Reasons: spam/toxic/nsfw", callback_data=build_settings_info()
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_required(update, context):
        if update.effective_message:
            await update.effective_message.reply_text(t("insufficient.rights"))
        return
    chat = update.effective_chat
    if not chat or chat.type not in {"group", "supergroup"}:
        return
    await update.effective_message.reply_text(t("settings.title"), reply_markup=_menu(chat.id))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Rate limit abuse for callbacks on settings too
    try:
        from app.config import get_settings
        from app.main import callback_bucket

        scope = get_settings().RATE_LIMIT_SCOPE
        uid = int(getattr(update.effective_user, "id", 0) or 0)
        chat_id = int(getattr(update.effective_chat, "id", 0) or 0)
        if callback_bucket and not callback_bucket.allow(uid, chat_id, scope=scope):
            if update.callback_query:
                await update.callback_query.answer(t("abuse.rate_limit"), show_alert=False)
            return
    except Exception:
        pass
    if not await admin_required(update, context):
        if update.callback_query:
            await update.callback_query.answer(t("insufficient.rights"), show_alert=True)
        return
    cq = update.callback_query
    if not cq:
        return
    prefix, parts = parse_callback(cq.data or "")
    if prefix != CBPrefix.SETTINGS or not parts:
        return
    chat = update.effective_chat
    if not chat:
        return

    try:
        action = parts[0]
        if action == "toggle" and len(parts) >= 3:
            feature, val = parts[1], parts[2]
            if feature == "enabled":
                from app.db.queries import upsert_chat

                await context.application.run_in_threadpool(
                    upsert_chat,
                    chat.id,
                    getattr(chat, "title", None),
                    chat.type,
                    None,
                    bool(int(val)),
                )
            else:
                set_settings(chat.id, {feature: int(val)})
        elif action == "adj" and len(parts) >= 4:
            key, op, step = parts[1], parts[2], int(parts[3])
            current = get_effective_settings(chat.id).get(key)
            if isinstance(current, int):
                set_settings(chat.id, {key: max(0, current + (step if op == "inc" else -step))})
        elif action == "set" and len(parts) >= 3:
            key, value = parts[1], parts[2]
            set_settings(chat.id, {key: value})
        elif action == "allowlist":
            # Enter allowlist edit mode for this chat via chat_data flag
            try:
                context.chat_data["_allowlist_edit"] = True
            except Exception:
                pass
            await cq.answer(t("settings.allowlist.prompt"), show_alert=True)
        elif action == "info":
            # Show localized reasons preview
            lang = getattr(update.effective_user, "language_code", None)
            text = (
                f"{t('ai.reason.spam', lang=lang)}\n"
                f"{t('ai.reason.toxic', lang=lang)}\n"
                f"{t('ai.reason.nsfw', lang=lang)}\n"
                f"{t('ai.fallback.breaker_open', lang=lang)}\n"
                f"{t('abuse.rate_limit', lang=lang)}"
            )
            try:
                await cq.message.edit_text(text)  # type: ignore[union-attr]
            except Exception:
                await cq.answer(text, show_alert=True)
        elif action == "open":
            # Open main settings menu
            await cq.message.edit_text(t("settings.title"), reply_markup=_menu(chat.id))  # type: ignore[union-attr]
        elif action == "help":
            lang = getattr(update.effective_user, "language_code", None)
            is_private = getattr(update.effective_chat, "type", None) == "private"
            help_text = t("help.private", lang=lang) if is_private else t("help.group", lang=lang)
            try:
                await cq.message.edit_text(help_text)  # type: ignore[union-attr]
            except Exception:
                await send_text(context, chat.id, help_text)
        elif action == "buy":
            # Try to send invoice (falls back to hint)
            try:
                await send_pro_invoice(update, context)
            except Exception:
                await send_text(context, chat.id, "Use /buy_pro to purchase PRO")
        # refresh menu
        await cq.message.edit_reply_markup(_menu(chat.id))  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001
        logger.error("settings callback error: %s", exc)
        try:
            await cq.answer("Error", show_alert=True)
        except Exception:
            pass


def register(app: Application) -> None:
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CallbackQueryHandler(on_callback))

    # Message handler to catch allowlist edit (per-chat flag)
    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # type: ignore[no-redef]
        if not update.effective_message or not update.effective_chat:
            return
        chat = update.effective_chat
        flag = bool(context.chat_data.get("_allowlist_edit"))
        if not flag:
            return
        # apply and clear flag
        set_settings(chat.id, {"link_allowlist": update.effective_message.text or ""})
        try:
            context.chat_data.pop("_allowlist_edit", None)
        except Exception:
            pass
        await update.effective_message.reply_text("Allowlist updated.")

    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, on_text))
