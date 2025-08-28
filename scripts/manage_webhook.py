import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Final, Any

from telegram import Bot

WEBHOOK_PATH: Final[str] = "/webhook"
DEFAULT_ALLOWED: list[str] = [
    "message",
    "edited_message",
    "callback_query",
    "chat_member",
    "my_chat_member",
    "message_reaction",
    "chat_join_request",
    "pre_checkout_query",
]


def parse_allowed(arg: str | None) -> list[str]:
    if not arg:
        env_val = os.environ.get("ALLOWED_UPDATES", "").strip()
        if env_val:
            try:
                return json.loads(env_val)
            except Exception:
                # fallback: CSV
                return [x.strip() for x in env_val.split(",") if x.strip()]
        return DEFAULT_ALLOWED
    try:
        return list(json.loads(arg))
    except Exception:
        return DEFAULT_ALLOWED


async def get_info(bot: Bot) -> dict[str, Any]:
    info = await bot.get_webhook_info()
    d = info.to_dict() if info else {}
    # Keep only important fields
    return {
        "url": d.get("url"),
        "pending_update_count": d.get("pending_update_count"),
        "max_connections": d.get("max_connections"),
        "ip_address": d.get("ip_address"),
        "allowed_updates": d.get("allowed_updates"),
        "has_custom_certificate": d.get("has_custom_certificate"),
        "last_error_date": d.get("last_error_date"),
        "last_error_message": d.get("last_error_message"),
    }


async def cmd_set(bot: Bot, url: str, secret: str | None, allowed: list[str], drop_pending: bool, dry: bool) -> int:
    current = await get_info(bot)
    same_url = (current.get("url") or "") == url
    same_allowed = sorted(current.get("allowed_updates") or []) == sorted(allowed)
    if same_url and same_allowed:
        print("Webhook already set with same URL and allowed updates.")
        print(json.dumps(current, ensure_ascii=False, indent=2))
        # Note: Telegram does not expose secret_token in getWebhookInfo; treated as idempotent by URL/allowed
        return 0
    params: dict[str, Any] = {
        "url": url,
        "allowed_updates": allowed or DEFAULT_ALLOWED,
    }
    if secret:
        params["secret_token"] = secret
    if drop_pending:
        params["drop_pending_updates"] = True
    if dry:
        print("[dry-run] setWebhook params:")
        print(json.dumps(params, ensure_ascii=False, indent=2))
        return 0
    await bot.set_webhook(**params)
    print("Webhook set:")
    print(json.dumps(await get_info(bot), ensure_ascii=False, indent=2))
    return 0


async def cmd_delete(bot: Bot, drop_pending: bool, dry: bool) -> int:
    if dry:
        print(f"[dry-run] deleteWebhook drop_pending_updates={bool(drop_pending)}")
        return 0
    await bot.delete_webhook(drop_pending_updates=bool(drop_pending))
    print("Webhook deleted")
    return 0


async def cmd_info(bot: Bot) -> int:
    data = await get_info(bot)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


async def cmd_reset_with_drop(bot: Bot, url: str, secret: str | None, allowed: list[str], dry: bool) -> int:
    if dry:
        print("[dry-run] reset-with-drop")
    await cmd_delete(bot, drop_pending=True, dry=dry)
    return await cmd_set(bot, url, secret, allowed, drop_pending=True, dry=dry)


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manage Telegram webhook")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--set", action="store_true", help="Set webhook")
    g.add_argument("--delete", action="store_true", help="Delete webhook")
    g.add_argument("--info", action="store_true", help="Get webhook info")
    g.add_argument("--reset-with-drop", action="store_true", help="Delete then set webhook with drop_pending_updates=true")
    p.add_argument("--url", type=str, help="Webhook URL (e.g., https://host/webhook)")
    p.add_argument("--secret", type=str, help="Secret token for X-Telegram-Bot-Api-Secret-Token")
    p.add_argument("--allowed", type=str, help="JSON array of allowed_updates")
    p.add_argument("--drop-pending", action="store_true", help="Drop pending updates when setting webhook")
    p.add_argument("--dry", action="store_true", help="Dry-run: print actions without API calls")
    return p


async def main() -> int:
    logging.basicConfig(level=logging.INFO)
    args = build_argparser().parse_args()

    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("ERROR: BOT_TOKEN is not set in environment")
        return 1

    allowed = parse_allowed(args.allowed)
    if not allowed:
        print("ERROR: allowed_updates resolved to empty list. Set ALLOWED_UPDATES or --allowed.")
        return 2
    # Fallback URL if not provided: PUBLIC_BASE + /webhook
    url = args.url or (os.environ.get("PUBLIC_BASE", "").rstrip("/") + WEBHOOK_PATH if os.environ.get("PUBLIC_BASE") else None)

    bot = Bot(token=bot_token)

    if args.set:
        if not url:
            print("ERROR: --url or PUBLIC_BASE must be provided for --set")
            return 2
        return await cmd_set(bot, url, args.secret or os.environ.get("WEBHOOK_SECRET"), allowed, args.drop_pending, args.dry)
    if args.delete:
        return await cmd_delete(bot, args.drop_pending, args.dry)
    if args.info:
        return await cmd_info(bot)
    if args.reset_with_drop:
        if not url:
            print("ERROR: --url or PUBLIC_BASE must be provided for --reset-with-drop")
            return 2
        return await cmd_reset_with_drop(bot, url, args.secret or os.environ.get("WEBHOOK_SECRET"), allowed, args.dry)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))






