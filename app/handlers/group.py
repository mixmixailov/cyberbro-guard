from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from telegram import ChatPermissions, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import get_settings
from app.db import get_chat, upsert_chat, upsert_chat_settings
from app.db.queries import add_warn_and_maybe_ban
from app.services.moderation import ModerationService
from app.utils.lang import t
from app.utils.sender import send_text

logger = logging.getLogger(__name__)


def _is_group(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type in {"group", "supergroup"})


def _is_admin(uid: Optional[int]) -> bool:
    if not uid:
        return False
    settings = get_settings()
    return int(uid) in settings.ADMIN_IDS


def _require_group_and_admin(update: Update) -> tuple[bool, int | None]:
    if not _is_group(update):
        return False, None
    uid = getattr(update.effective_user, "id", None)
    if not _is_admin(uid):
        return False, uid
    return True, uid


async def enable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ok, uid = _require_group_and_admin(update)
    if not ok:
        return
    chat = update.effective_chat
    settings = get_settings()
    assert chat is not None
    try:
        await context.application.bot.send_chat_action(chat_id=chat.id, action="typing")
    except Exception:
        pass
    try:
        await context.application.run_in_threadpool(
            upsert_chat,
            chat.id,
            getattr(chat, "title", None),
            chat.type,
            settings.DEFAULT_LOCALE,
            True,
        )
        await context.application.run_in_threadpool(
            upsert_chat_settings,
            chat.id,
            {
                "flood_n": settings.FLOOD_N,
                "flood_window_s": settings.FLOOD_WINDOW_S,
                "repeat_n": settings.REPEAT_N,
                "repeat_window_s": settings.REPEAT_WINDOW_S,
                "link_policy": settings.LINK_POLICY,
                "captcha_mode": "soft",
                "captcha_ttl_s": settings.CAPTCHA_TTL_S,
                "punish_policy": "mute",
                "warns_limit": settings.WARNS_LIMIT_24H,
                "ban_days": settings.BAN_DAYS,
                "link_allowlist": "",
            },
        )
        await send_text(context, chat.id, t("moderation.enabled"))
    except Exception as exc:  # noqa: BLE001
        logger.error("/enable error chat=%s by=%s err=%s", getattr(chat, "id", None), uid, exc)


async def disable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ok, uid = _require_group_and_admin(update)
    if not ok:
        return
    chat = update.effective_chat
    assert chat is not None
    try:
        await context.application.run_in_threadpool(
            upsert_chat,
            chat.id,
            getattr(chat, "title", None),
            chat.type,
            None,
            False,
        )
        await send_text(context, chat.id, t("moderation.disabled"))
    except Exception as exc:  # noqa: BLE001
        logger.error("/disable error chat=%s by=%s err=%s", getattr(chat, "id", None), uid, exc)


def _target_user_id(update: Update) -> Optional[int]:
    if update.effective_message and update.effective_message.reply_to_message:
        ru = update.effective_message.reply_to_message.from_user
        return getattr(ru, "id", None)
    return None


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_group(update):
        return
    chat = update.effective_chat
    assert chat is not None
    data = await context.application.run_in_threadpool(get_chat, chat.id)
    st = "on" if (data and data.get("enabled")) else "off"
    # recent actions preview not persisted; show effective settings snapshot
    from app.db.chat_settings import get_effective_settings as eff

    s = eff(chat.id)
    getattr(update.effective_user, "language_code", None) or get_settings().DEFAULT_LOCALE
    summary = (
        f"Status: {st}\n"
        f"Flood: {s.get('flood_n')}/{s.get('flood_window_s')}s\n"
        f"Repeat: {s.get('repeat_n')}/{s.get('repeat_window_s')}s\n"
        f"Links: {s.get('link_policy')}\n"
        f"Captcha TTL: {s.get('captcha_ttl_s')}s\n"
    )
    await update.effective_message.reply_text(summary)


async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ok, uid = _require_group_and_admin(update)
    if not ok:
        return
    chat = update.effective_chat
    assert chat is not None
    target = _target_user_id(update)
    if not target:
        return
    try:
        new_count, threshold, banned = await context.application.run_in_threadpool(
            add_warn_and_maybe_ban, int(target), int(chat.id)
        )
        if banned:
            until = datetime.now(timezone.utc) + timedelta(days=get_settings().BAN_DAYS)
            try:
                await context.bot.ban_chat_member(chat.id, target, until_date=until)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "ban after warn failed: chat=%s target=%s err=%s", chat.id, target, exc
                )
            await update.effective_message.reply_text(
                f"Warns: {new_count}/{threshold}. Banned for {get_settings().BAN_DAYS}d."
            )
        else:
            await update.effective_message.reply_text(f"Warns: {new_count}/{threshold}.")
    except Exception as exc:  # noqa: BLE001
        logger.error("/warn error chat=%s by=%s err=%s", chat.id, uid, exc)


async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ok, uid = _require_group_and_admin(update)
    if not ok:
        return
    chat = update.effective_chat
    assert chat is not None
    target = _target_user_id(update)
    if not target:
        return
    try:
        mins = int(context.args[0]) if context.args else 10
    except Exception:
        mins = 10
    until = datetime.now(timezone.utc) + timedelta(minutes=mins)
    perms = ChatPermissions(can_send_messages=False)
    try:
        await context.bot.restrict_chat_member(chat.id, target, permissions=perms, until_date=until)
        await update.effective_message.reply_text(f"Muted for {mins}m.")
    except Exception as exc:  # noqa: BLE001
        logger.error("/mute error chat=%s by=%s err=%s", chat.id, uid, exc)


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ok, uid = _require_group_and_admin(update)
    if not ok:
        return
    chat = update.effective_chat
    assert chat is not None
    target = _target_user_id(update)
    if not target:
        return
    try:
        days = int(context.args[0]) if context.args else get_settings().BAN_DAYS
    except Exception:
        days = get_settings().BAN_DAYS
    until = datetime.now(timezone.utc) + timedelta(days=days)
    try:
        await context.bot.ban_chat_member(chat.id, target, until_date=until)
        await update.effective_message.reply_text(f"Banned for {days}d.")
    except Exception as exc:  # noqa: BLE001
        logger.error("/ban error chat=%s by=%s err=%s", chat.id, uid, exc)


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ok, uid = _require_group_and_admin(update)
    if not ok:
        return
    chat = update.effective_chat
    assert chat is not None
    target = _target_user_id(update)
    if not target:
        return
    try:
        await context.bot.unban_chat_member(chat.id, target, only_if_banned=True)
        await update.effective_message.reply_text("Unbanned.")
    except Exception as exc:  # noqa: BLE001
        logger.error("/unban error chat=%s by=%s err=%s", chat.id, uid, exc)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("enable", enable_cmd))
    app.add_handler(CommandHandler("disable", disable_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))

    # Moderation message and member updates
    service = ModerationService()
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION), service.on_message
        ),
        group=10,
    )
    app.add_handler(
        ChatMemberHandler(service.on_chat_member_update, ChatMemberHandler.CHAT_MEMBER), group=10
    )
    app.add_handler(CallbackQueryHandler(service.on_callback), group=10)
