import logging
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application
from .config import get_settings
from .handlers import setup_handlers
from .logging_conf import setup_logging
from .db import init_db
from .db.session import execute as db_execute

logger = logging.getLogger(__name__)


application: Application | None = None  # PTB Application (module-level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global application
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)
    # Optional TZ handling removed from config spec; keep if needed via OS env
    if tz := os.environ.get("TZ"):
        os.environ["TZ"] = tz

    logger.info("Service starting...")
    # Init DB (DDL only, no migrations yet) — sync, run in thread
    await asyncio.to_thread(init_db)
    # Log env file resolution and critical env values
    logger.info("Config snapshot: BOT_TOKEN=%s, PUBLIC_BASE=%s, DEBUG=%s",
                "***SET***" if bool(settings.BOT_TOKEN) else "<EMPTY>",
                bool(settings.PUBLIC_BASE),
                settings.DEBUG)
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN пуст. HTTP-сервер стартует, но бот не активен. Укажи BOT_TOKEN в переменных окружения.")
        application = None
    else:
        application = (
            Application.builder()
            .token(settings.BOT_TOKEN)
            .updater(None)
            .build()
        )
        await application.initialize()
        setup_handlers(application)
        # Настраиваем вебхук, если указан публичный URL: проверяем текущий и выставляем при необходимости
        if settings.PUBLIC_BASE:
            desired_url = settings.PUBLIC_BASE.rstrip("/") + "/webhook"
            info = await application.bot.get_webhook_info()
            if info and info.url == desired_url:
                logger.info("Webhook already set: %s", info.url)
            else:
                await application.bot.set_webhook(
                    url=desired_url, drop_pending_updates=True
                )
                logger.info("Webhook set to %s", desired_url)
        await application.start()
        logger.info("PTB Application started")

    logger.info("Service ready.")

    try:
        yield
    finally:
        if application:
            logger.info("Stopping PTB application...")
            await application.stop()
            await application.shutdown()
            logger.info("PTB application stopped.")


app = FastAPI(lifespan=lifespan)

 

@app.get("/healthz")
async def healthz():
    settings = get_settings()
    if settings.DEBUG:
        logger.debug("/healthz called")
    return {"status": "ok"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Маршрут для приёма апдейтов от Telegram."""
    global application
    if application is None:
        return JSONResponse({"ok": False, "error": "bot not ready"}, status_code=503)

    try:
        logger.info("Webhook hit: ct=%s", request.headers.get("content-type"))
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        logger.info("Update queued: keys=%s", list(data.keys()))
        # Extended diagnostics only when DEBUG enabled
        settings = get_settings()
        if settings.DEBUG:
            try:
                upd_type = (
                    "message" if "message" in data else (
                        "callback_query" if "callback_query" in data else "other"
                    )
                )
                uid = (
                    (data.get("message") or {}).get("from", {}).get("id")
                    or (data.get("callback_query") or {}).get("from", {}).get("id")
                )
                text = None
                if update.message and update.message.text:
                    text = update.message.text
                elif update.callback_query and update.callback_query.data:
                    text = update.callback_query.data
                logger.debug("Webhook detail: type=%s uid=%s text=%s", upd_type, uid, text)
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - логируем всё, сервер не падает
        logger.error("/webhook processing error: %s", exc)
        return JSONResponse({"ok": False}, status_code=200)


@app.get("/status")
async def status():
    settings = get_settings()
    if settings.DEBUG:
        logger.debug("/status called")
    if not settings.BOT_TOKEN:
        return JSONResponse({"running": False, "public_base": bool(settings.PUBLIC_BASE), "debug": settings.DEBUG}, status_code=503)
    global application
    try:
        if application is not None:
            info = await application.bot.get_webhook_info()
            webhook_url = info.url if info else None
        else:
            webhook_url = None
        return JSONResponse({"running": application is not None, "public_base": bool(settings.PUBLIC_BASE), "debug": settings.DEBUG})
    except Exception as exc:  # noqa: BLE001
        logger.error("/status error: %s", exc)
        return JSONResponse({"running": False, "public_base": bool(settings.PUBLIC_BASE), "debug": settings.DEBUG}, status_code=503)


@app.get("/db_health")
async def db_health():
    try:
        # Run a simple SELECT 1 via sync DB layer in a thread
        await asyncio.to_thread(db_execute, "SELECT 1")
        return {"db": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.error("/db_health error: %s", exc)
        return JSONResponse({"db": "error"}, status_code=500)


@app.get("/tg_webhook_info")
async def tg_webhook_info():
    global application
    if application is None:
        return JSONResponse({"error": "bot not ready"}, status_code=503)
    try:
        info = await application.bot.get_webhook_info()
        return JSONResponse(info.to_dict())
    except Exception as exc:  # noqa: BLE001
        logger.error("/tg_webhook_info error: %s", exc)
        return JSONResponse({"error": "failed to fetch webhook info"}, status_code=500)
