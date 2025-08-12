import asyncio
import json
import logging
import os
import sys
from typing import Final

from telegram import Bot

WEBHOOK_PATH: Final[str] = "/webhook"


async def cmd_set(bot: Bot, public_base: str) -> None:
    url = public_base.rstrip("/") + WEBHOOK_PATH
    await bot.set_webhook(
        url=url,
        allowed_updates=["message", "callback_query"],
    )
    print("Webhook was set")
    print(url)


async def cmd_get(bot: Bot) -> None:
    info = await bot.get_webhook_info()
    data = info.to_dict() if info else {}
    print(json.dumps(data, ensure_ascii=False, indent=2))


async def cmd_delete(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    print("Webhook was deleted")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2 or sys.argv[1] not in {"set", "get", "delete"}:
        print("Usage: python scripts/manage_webhook.py [set|get|delete]")
        sys.exit(1)

    command = sys.argv[1]
    bot_token = os.environ.get("BOT_TOKEN")
    public_base = os.environ.get("PUBLIC_BASE")

    if not bot_token:
        print("ERROR: BOT_TOKEN is not set in environment")
        sys.exit(1)

    bot = Bot(token=bot_token)

    if command == "set":
        if not public_base:
            print("ERROR: PUBLIC_BASE is not set in environment")
            sys.exit(1)
        await cmd_set(bot, public_base)
    elif command == "get":
        await cmd_get(bot)
    elif command == "delete":
        await cmd_delete(bot)


if __name__ == "__main__":
    asyncio.run(main())






