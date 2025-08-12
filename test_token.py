import asyncio
import logging
from telegram import Bot

from app.config import get_settings


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    settings = get_settings()
    if not settings.BOT_TOKEN:
        logging.error("BOT_TOKEN is empty. Check your .env or environment variables.")
        return

    bot = Bot(token=settings.BOT_TOKEN)
    me = await bot.get_me()
    logging.info("Bot info: id=%s, username=@%s, name=%s", me.id, me.username, me.first_name)


if __name__ == "__main__":
    asyncio.run(main())



