from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List, Tuple
from urllib.parse import urlparse

from telegram import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from app.db import get_chat
from app.db.chat_settings import get_effective_settings
from app.db.queries import add_warn_and_maybe_ban, get_user_state, upsert_user_state
from app.db.subscriptions import get_subscription  # make available for monkeypatch in tests
from app.services.ai_moderation import ModerationResult, get_provider
from app.services.ai_moderation_guard import call_with_resilience, record_ai_success
from app.utils.callbacks import CBPrefix, build_captcha_answer, parse_callback
from app.utils.lang import t

logger = logging.getLogger(__name__)


URL_RE = re.compile(r"https?://|t\.me/|telegram\.me/|discord\.gg/|\binvite\b", re.IGNORECASE)
MAX_MEDIA_BYTES = 10 * 1024 * 1024  # 10MB


@dataclass
class RingBuffer:
    timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=64))

    def push(self, ts: float) -> None:
        self.timestamps.append(ts)

    def count_since(self, ts_threshold: float) -> int:
        return sum(1 for x in self.timestamps if x >= ts_threshold)


class ModerationService:
    def __init__(self) -> None:
        self._flood_windows: Dict[Tuple[int, int], RingBuffer] = {}
        self._recent_messages: Dict[Tuple[int, int], Deque[Tuple[float, str]]] = {}
        self._processed_updates: set[int] = set()
        # Simple built-in deny lists (can be extended from DB later)
        self._profanity_ru = {"хуй", "пизда", "ебать", "сука"}
        self._profanity_en = {"fuck", "shit", "bitch"}
        self._deny_domains = {"scam.com", "phish.me"}

    def _key(self, user_id: int, chat_id: int) -> Tuple[int, int]:
        return (user_id, chat_id)

    def is_processed(self, update_id: int) -> bool:
        if update_id in self._processed_updates:
            return True
        self._processed_updates.add(update_id)
        if len(self._processed_updates) > 5000:
            # Prevent unbounded growth
            for _ in range(1000):
                try:
                    self._processed_updates.pop()
                except Exception:
                    break
        return False

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        msg = update.message
        chat = msg.chat
        user = msg.from_user
        if not (chat and user):
            return
        # Idempotency
        if update.update_id is not None and self.is_processed(update.update_id):
            return
        # Only in groups
        if chat.type not in {"group", "supergroup"}:
            return
        # AI moderation (inbound) — aggregate only, no PII in logs
        ai_provider = get_provider()
        if ai_provider and (msg.text or msg.caption):
            text = (msg.text or msg.caption or "").strip()
            # Check PRO subscription before calling AI
            is_pro = False
            try:
                sub = get_subscription(int(getattr(update.effective_user, "id", 0) or 0), "pro")
                is_pro = bool(sub and sub.get("until"))
            except Exception:
                is_pro = False
            if is_pro:
                # Quota check per chat
                try:
                    from app.config import get_settings as _gs
                    from app.db.queries import ai_get_usage, ai_increment

                    quota = int(_gs().AI_MONTHLY_QUOTA)
                    used = ai_get_usage(int(chat.id))
                    if used >= quota:
                        logger.info(
                            "ai.quota.exceeded chat=%s used=%s quota=%s", chat.id, used, quota
                        )
                        # fall back to classic moderation; no AI call
                        ai_provider = None
                except Exception:
                    pass
                start_ai = datetime.now(timezone.utc).timestamp()
                ok, value = await call_with_resilience(
                    lambda: asyncio.to_thread(ai_provider.moderate, text)
                )
                if ok and isinstance(value, ModerationResult):
                    try:
                        ai_increment(int(chat.id), 1)
                    except Exception:
                        pass
                    record_ai_success(start_ai)
                    ai_res = value
                    if not ai_res.allowed:
                        try:
                            await msg.delete()
                        except Exception:
                            pass
                        await self._warn_and_maybe_ban(update, context, reason="ai_block")
                        return
                    if ai_res.action == "flag":
                        logger.info("ai_flag chat=%s", chat.id)
                else:
                    # Breaker open or failures → conservative fallback
                    logger.warning("ai.fallback.breaker_open chat=%s", chat.id)
                    # Will adjust effective settings only if moderation enabled later
            else:
                # AI enabled but user is not PRO → skip AI path
                from app.metrics import ai_skipped_total

                ai_skipped_total.labels("not_pro").inc()
                logger.info(
                    "ai.pro_only uid=%s chat=%s",
                    getattr(update.effective_user, "id", None),
                    getattr(update.effective_chat, "id", None),
                )

        # Moderation must be enabled for chat
        try:
            chat_row = get_chat(int(chat.id))
        except Exception:
            # DB not initialized yet; treat as moderation disabled for safety
            return
        if not (chat_row and chat_row.get("enabled")):
            return

        # Per-chat settings
        s = get_effective_settings(chat.id)
        now = datetime.now(timezone.utc)

        # 1) Media size limits (images/GIF/video)
        try:
            too_large = False
            size = 0
            if msg.photo:
                try:
                    size = max([p.file_size or 0 for p in msg.photo])
                except Exception:
                    size = 0
            elif msg.animation:
                size = int(getattr(msg.animation, "file_size", 0) or 0)
            elif msg.video:
                size = int(getattr(msg.video, "file_size", 0) or 0)
            if size and size > MAX_MEDIA_BYTES:
                too_large = True
            if too_large:
                try:
                    await msg.delete()
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "delete large media failed chat=%s uid=%s err=%s", chat.id, user.id, exc
                    )
                try:
                    await context.bot.send_message(chat.id, t("moderation.media_too_large"))
                except Exception:
                    pass
                await self._warn_and_maybe_ban(update, context, reason="media")
                return
        except Exception as exc:  # noqa: BLE001
            logger.error("media check failed chat=%s uid=%s err=%s", chat.id, user.id, exc)

        # 1.5) Text normalization + basic profanity
        raw_text = msg.text or msg.caption or ""
        norm = unicodedata.normalize("NFKC", raw_text).strip()
        text = norm.lower()
        # collapse invisible/zero-width
        text = "".join(ch for ch in text if unicodedata.category(ch) not in {"Cf"})
        # profanity check (lightweight)
        try:
            words = {w.strip(".,!?:;()[]{}\"'") for w in text.split()}
            if words & self._profanity_ru or words & self._profanity_en:
                await self._warn_and_maybe_ban(update, context, reason="profanity")
                return
        except Exception:
            pass

        # 2) Anti-links for newcomers/non-trusted
        urls: List[str] = []
        if msg.entities:
            for e in msg.entities:
                t = getattr(e, "type", "")
                if t == "url":
                    try:
                        urls.append((raw_text or "")[e.offset : e.offset + e.length])
                    except Exception:
                        pass
                elif t == "text_link":
                    u = getattr(e, "url", None)
                    if u:
                        urls.append(u)
        if msg.caption_entities:
            for e in msg.caption_entities:
                t = getattr(e, "type", "")
                if t == "url":
                    try:
                        urls.append((msg.caption or "")[e.offset : e.offset + e.length])
                    except Exception:
                        pass
                elif t == "text_link":
                    u = getattr(e, "url", None)
                    if u:
                        urls.append(u)

        found_link = bool(text and URL_RE.search(text)) or bool(urls)
        if found_link:
            if await self._should_block_link(context, msg, s, now, urls):
                try:
                    await msg.delete()
                except Exception as exc:  # noqa: BLE001
                    logger.error("delete link failed chat=%s uid=%s err=%s", chat.id, user.id, exc)
                try:
                    await context.bot.send_message(chat.id, t("moderation.link_restricted"))
                except Exception:
                    pass
                await self._warn_and_maybe_ban(update, context, reason="link")
                return

        # 2) Anti-flood
        rb = self._flood_windows.setdefault(self._key(user.id, chat.id), RingBuffer())
        rb.push(now.timestamp())
        window_start = now.timestamp() - float(s.get("flood_window_s", 10))
        if rb.count_since(window_start) > int(s.get("flood_n", 6)):
            await self._warn_and_maybe_ban(update, context, reason="flood")
            return

        # 3) Anti-repeat
        if text:
            dq = self._recent_messages.setdefault(self._key(user.id, chat.id), deque(maxlen=20))
            dq.append((now.timestamp(), text.strip()))
            repeat_window = float(s.get("repeat_window_s", 60))
            repeat_n = int(s.get("repeat_n", 3))
            threshold = now.timestamp() - repeat_window
            recent_same = [t for t, v in dq if t >= threshold and v == text.strip()]
            if len(recent_same) >= repeat_n:
                await self._warn_and_maybe_ban(update, context, reason="repeat")

    async def _should_block_link(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        msg: Message,
        s: dict,
        now: datetime,
        urls: List[str] | None = None,
    ) -> bool:
        allowlist = {
            d.strip().lower() for d in (s.get("link_allowlist") or "").split(",") if d.strip()
        }
        text = (msg.text or msg.caption or "").lower()
        # If any URL domain is in allowlist, allow
        if allowlist:
            # check text include
            if any(dom in text for dom in allowlist):
                return False
            # check parsed urls
            for u in urls or []:
                try:
                    parsed = urlparse(u if re.match(r"^[a-z]+://", u, re.I) else f"http://{u}")
                    host = (parsed.netloc or parsed.path or "").lower()
                    if any(host.endswith(dom) or dom in host for dom in allowlist):
                        return False
                except Exception:
                    continue
        # deny domains
        for u in urls or []:
            try:
                parsed = urlparse(u if re.match(r"^[a-z]+://", u, re.I) else f"http://{u}")
                host = (parsed.netloc or parsed.path or "").lower()
                if any(host.endswith(dom) or dom in host for dom in self._deny_domains):
                    return True
            except Exception:
                continue
        # newcomers: joined <24h ago → block. PTB does not expose join date; we approximate by missing state → block
        state = get_user_state(int(msg.from_user.id), int(msg.chat.id))
        joined_at_iso = (state or {}).get("last_msgs", {}).get("joined_at") if state else None
        if not joined_at_iso:
            return True
        try:
            joined_at = datetime.fromisoformat(joined_at_iso)
        except Exception:
            return True
        return (now - joined_at) < timedelta(hours=24)

    async def _warn_and_maybe_ban(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str
    ) -> None:
        msg = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not (msg and chat and user):
            return
        try:
            new_count, threshold, banned = await asyncio.to_thread(
                add_warn_and_maybe_ban, int(user.id), int(chat.id)
            )
            await msg.reply_text(f"Warn ({reason}). {new_count}/{threshold}")
            if banned:
                until = datetime.now(timezone.utc) + timedelta(
                    days=int(get_effective_settings(chat.id).get("ban_days", 7))
                )
                try:
                    await context.bot.ban_chat_member(chat.id, user.id, until_date=until)
                except Exception as exc:  # noqa: BLE001
                    logger.error("ban failed chat=%s uid=%s err=%s", chat.id, user.id, exc)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "warn flow failed chat=%s uid=%s err=%s",
                getattr(chat, "id", None),
                getattr(user, "id", None),
                exc,
            )

    async def on_chat_member_update(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        # Welcome + captcha message
        if not update.chat_member:
            return
        if update.update_id is not None and self.is_processed(update.update_id):
            return
        chat = update.chat_member.chat
        user = update.chat_member.new_chat_member.user
        if not (chat and user):
            return
        if chat.type not in {"group", "supergroup"}:
            return
        chat_row = get_chat(int(chat.id))
        if not (chat_row and chat_row.get("enabled")):
            return
        # store join time
        now = datetime.now(timezone.utc)
        state = get_user_state(int(user.id), int(chat.id)) or {"last_msgs": {}}
        meta = state.get("last_msgs") or {}
        meta["joined_at"] = now.isoformat()
        upsert_user_state(int(user.id), int(chat.id), {"last_msgs": meta})
        # Send captcha with one button
        try:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="✅", callback_data=build_captcha_answer(True))]]
            )
            await context.bot.send_message(chat.id, t("captcha.prompt"), reply_markup=kb)
        except Exception:
            pass
        # schedule timeout → mute 24h
        await self._schedule_captcha_timeout(context, chat.id, user.id)

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.callback_query:
            return
        cq = update.callback_query
        # Abuse rate limit per user (optionally per chat)
        try:
            from app.config import get_settings
            from app.main import callback_bucket

            scope = get_settings().RATE_LIMIT_SCOPE
            uid = int(getattr(update.effective_user, "id", 0) or 0)
            chat_id = int(getattr(update.effective_chat, "id", 0) or 0)
            if callback_bucket and not callback_bucket.allow(uid, chat_id, scope=scope):
                try:
                    await cq.answer(t("abuse.rate_limit"), show_alert=False)
                except Exception:
                    pass
                return
        except Exception:
            pass
        data = cq.data or ""
        prefix, parts = parse_callback(data)
        if prefix != CBPrefix.CAPTCHA:
            return
        chat = update.effective_chat
        user = update.effective_user
        if not (chat and user):
            return
        # mark captcha ok for this user in this chat
        state = get_user_state(int(user.id), int(chat.id)) or {"last_msgs": {}}
        meta = state.get("last_msgs") or {}
        meta["captcha_ok"] = True
        upsert_user_state(int(user.id), int(chat.id), {"last_msgs": meta})
        try:
            await cq.answer()
        except Exception:
            pass
        try:
            await cq.message.edit_reply_markup(None)  # type: ignore[union-attr]
        except Exception:
            pass
        try:
            await context.bot.send_message(chat.id, t("captcha.ok"))
        except Exception:
            pass

    async def _schedule_captcha_timeout(
        self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int
    ) -> None:
        ttl = int(get_effective_settings(chat_id).get("captcha_ttl_s", 60))
        await asyncio.sleep(ttl)
        # if not passed (no flag stored) → mute 24h
        state = get_user_state(int(user_id), int(chat_id)) or {"last_msgs": {}}
        if not (state.get("last_msgs") or {}).get("captcha_ok"):
            until = datetime.now(timezone.utc) + timedelta(hours=24)
            perms = ChatPermissions(can_send_messages=False)
            try:
                await context.bot.restrict_chat_member(
                    chat_id, user_id, permissions=perms, until_date=until
                )
                await context.bot.send_message(chat_id, t("captcha.fail"))
            except Exception as exc:  # noqa: BLE001
                logger.error("captcha mute failed chat=%s uid=%s err=%s", chat_id, user_id, exc)
