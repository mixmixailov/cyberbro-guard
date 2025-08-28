import logging
import asyncio
import os
from collections import deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect
from telegram import Update
from telegram.ext import Application
from .config import get_settings
from .handlers import setup_handlers
from .logging_conf import setup_logging
from .middleware.correlation import CorrelationMiddleware
from .utils.logging import set_update_context
from .db import init_db
from .db.session import execute as db_execute
from .health import router as health_router
from .metrics import router as metrics_router
from .admin import router as admin_router
from .metrics import attach_exporter
from .metrics import updates_total, webhook_dropped_total, webhook_errors_total, webhook_latency_seconds, timeit, sched_runs_total, sched_errors_total
from .services.idempotency import IdempotencyStore, make_key
from .services.idempotency_guard import with_idempotency
from .utils.security import verify_secret
from .services.rate_limit import TokenBucket
from .sched.ratelimit_cleanup import run_cleanup_job
from .utils.scheduler import Scheduler
from .services.subscriptions import run_reminders, expire_due, cleanup_old_data
from .services.send_queue import SendQueue
from .services.dlq import add_failed_update_to_dlq
from .sched.idempotency_purge import run_purge_job

logger = logging.getLogger(__name__)


application: Application | None = None  # PTB Application (module-level)
scheduler_ref: Scheduler | None = None
_seen_updates: set[int] = set()
_seen_queue: deque[int] = deque(maxlen=5000)
callback_bucket: TokenBucket | None = None
main_loop: asyncio.AbstractEventLoop | None = None
update_queue: asyncio.Queue[Update] | None = None
worker_task: asyncio.Task | None = None


def is_duplicate_update(update_id: int | None) -> bool:
    if update_id is None:
        return False
    if update_id in _seen_updates:
        return True
    _seen_updates.add(update_id)
    _seen_queue.append(update_id)
    if len(_seen_updates) > 6000:
        # Trim set using queue order
        while len(_seen_updates) > 5000 and _seen_queue:
            old = _seen_queue.popleft()
            _seen_updates.discard(old)
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global application, main_loop
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)
    # Require token in non-DEBUG environments (empty allowed for local mock run)
    settings.require_token()
    # Log webhook secret state (without revealing it)
    try:
        _enabled = bool((settings.WEBHOOK_SECRET or "").strip())
        logger.info("webhook_secret_enabled=%s", _enabled)
    except Exception:
        pass
    # Optional TZ handling removed from config spec; keep if needed via OS env
    if tz := os.environ.get("TZ"):
        os.environ["TZ"] = tz

    logger.info("Service starting...")
    # Secrets sanity
    if not settings.WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET is empty; callback signatures will be weak. Set WEBHOOK_SECRET.")
    # Init DB (DDL only, no migrations yet) — sync, run in thread
    await asyncio.to_thread(init_db)
    # Optional forward-only migrations
    if settings.AUTO_MIGRATE:
        try:
            from pathlib import Path
            from .utils.migrate import migrate as run_migrate
            project_root = Path(__file__).resolve().parents[1]
            migrations_dir = str(project_root / "db" / "migrations")
            await asyncio.to_thread(run_migrate, migrations_dir)
        except Exception as exc:  # noqa: BLE001
            logger.error("AUTO_MIGRATE failed: %s", exc)
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
            .build()
        )
        await application.initialize()
        setup_handlers(application)
        # Опциональная регистрация вебхука при наличии PUBLIC_URL и включённом режиме webhook
        try:
            if settings.USE_WEBHOOK and settings.PUBLIC_URL:
                url = str(settings.PUBLIC_URL).rstrip("/") + str(settings.WEBHOOK_PATH)
                if not url.endswith("/webhook"):
                    raise ValueError(f"WEBHOOK_URL must end with /webhook, got: {url}")
                await application.bot.set_webhook(
                    url=url,
                    secret_token=(settings.WEBHOOK_SECRET or None),
                    allowed_updates=list(settings.ALLOWED_UPDATES),
                )
                # NOTE: Telegram Bot API: header name is X-Telegram-Bot-Api-Secret-Token (see Bot API docs).
                logger.info("webhook_set url=%s", url)
        except Exception as exc:  # noqa: BLE001
            logger.error("set_webhook failed: %s", exc)
        await application.start()
        logger.info("PTB Application started")
        # Initialize send queue
        try:
            sq = SendQueue(application.bot)
            await sq.start()
            application.bot_data["send_queue"] = sq
            logger.info("SendQueue started")
        except Exception as exc:  # noqa: BLE001
            logger.error("SendQueue start failed: %s", exc)
        # Start polling if enabled
        global update_queue, worker_task
        if settings.USE_POLLING:
            async def _polling() -> None:
                assert application is not None
                try:
                    await application.run_polling(allowed_updates=list(settings.ALLOWED_UPDATES))
                except Exception as exc:  # noqa: BLE001
                    logger.error("polling error: %s", exc, exc_info=True)
            worker_task = asyncio.create_task(_polling())
        else:
            # Create background worker queue and task for webhook mode
            update_queue = asyncio.Queue(maxsize=1000)
            async def _worker() -> None:
                assert application is not None
                max_attempts = 3  # Max retry attempts before moving to DLQ
                
                while True:
                    upd = await update_queue.get()
                    attempt_count = 0
                    last_error = None
                    
                    # Retry loop with DLQ fallback
                    while attempt_count < max_attempts:
                        attempt_count += 1
                        try:
                            # Correlate ids for logs
                            try:
                                set_update_context(
                                    upd.update_id,
                                    getattr(upd.effective_chat, "id", None),
                                    getattr(upd.effective_user, "id", None),
                                )
                            except Exception:
                                pass
                            tmo = float(get_settings().WEBHOOK_HANDLE_TIMEOUT_S)
                            async with asyncio.timeout(tmo):
                                await application.process_update(upd)
                            # Success - break out of retry loop
                            break
                            
                        except Exception as exc:  # noqa: BLE001
                            last_error = exc
                            logger.warning(
                                "Update processing failed (attempt %d/%d): %s", 
                                attempt_count, max_attempts, exc,
                                extra={
                                    "update_id": getattr(upd, "update_id", None),
                                    "attempt": attempt_count,
                                    "max_attempts": max_attempts
                                }
                            )
                            
                            # If this was the last attempt, move to DLQ
                            if attempt_count >= max_attempts:
                                try:
                                    update_data = upd.to_dict() if hasattr(upd, "to_dict") else {"update": str(upd)}
                                    dlq_id = add_failed_update_to_dlq(
                                        update_data=update_data,
                                        error=last_error,
                                        attempts=attempt_count
                                    )
                                    logger.error(
                                        "Update moved to DLQ after %d failed attempts",
                                        max_attempts,
                                        extra={
                                            "dlq_id": dlq_id,
                                            "update_id": getattr(upd, "update_id", None),
                                            "error": str(last_error)
                                        }
                                    )
                                except Exception as dlq_error:  # noqa: BLE001
                                    logger.error("Failed to add update to DLQ: %s", dlq_error)
                            else:
                                # Wait before retry (simple exponential backoff)
                                wait_time = 2 ** (attempt_count - 1)  # 1s, 2s, 4s...
                                await asyncio.sleep(wait_time)
                    
                    finally:
                        update_queue.task_done()
            worker_task = asyncio.create_task(_worker())

    logger.info("Service ready.")

    try:
        # Start scheduler jobs if enabled
        if settings.SCHED_ENABLED:
            global scheduler_ref
            scheduler_ref = Scheduler()
            # capture main event loop
            try:
                main_loop = asyncio.get_running_loop()
            except RuntimeError:
                main_loop = None
            # async job: submit to main loop from scheduler thread
            def _run_reminders_job() -> None:
                try:
                    if application is not None and main_loop is not None:
                        asyncio.run_coroutine_threadsafe(run_reminders(application), main_loop)
                except Exception as exc:  # noqa: BLE001
                    logger.error("reminders submit error: %s", exc)
            scheduler_ref.add_cron(_run_reminders_job, settings.SCHED_CRON_REMINDERS, name="renewal_reminders")  # type: ignore[arg-type]
            # sync jobs: call directly in scheduler thread
            scheduler_ref.add_cron(expire_due, settings.SCHED_CRON_EXPIRE, name="expire_subscriptions")
            scheduler_ref.add_cron(cleanup_old_data, settings.SCHED_CRON_CLEANUP, name="cleanup_old_data")
            scheduler_ref.add_cron(run_purge_job, "*/10 * * * *", name="idmp_purge")
            scheduler_ref.start()
        # Initialize callback rate limit bucket
        global callback_bucket
        callback_bucket = TokenBucket(rate=6, per=10.0, burst=6.0, cool_down=15.0)
        if scheduler_ref:
            scheduler_ref.add_cron(lambda: run_cleanup_job(callback_bucket, 10.0), "*/1 * * * *", name="ratelimit_cleanup")
        # Optional: self-test reply to admin to verify pipeline end-to-end
        try:
            if settings.WEBHOOK_FORCE_REPLY_TEST and application is not None and settings.ADMIN_IDS:
                admin_id = next(iter(settings.ADMIN_IDS))
                await application.bot.send_message(chat_id=admin_id, text="CyberBro Guard: self-test ping")
                logger.info("Self-test message sent to admin_id=%s", admin_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("self-test send failed: %s", exc)
        yield
    finally:
        if application:
            logger.info("Stopping PTB application...")
            # Stop send queue
            try:
                sq = application.bot_data.get("send_queue")
                if sq is not None:
                    await sq.stop()
            except Exception:
                pass
            await application.stop()
            await application.shutdown()
            logger.info("PTB application stopped.")
        if worker_task:
            try:
                worker_task.cancel()
            except Exception:
                pass
        if scheduler_ref:
            try:
                scheduler_ref.shutdown()
            except Exception:
                pass


app = FastAPI(lifespan=lifespan)
app.include_router(health_router)
app.add_middleware(CorrelationMiddleware)
attach_exporter(app)
app.include_router(admin_router)

@timeit(webhook_latency_seconds, "updates")
@app.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
):
    """Маршрут для приёма апдейтов от Telegram."""
    global application

    try:
        logger.info("HTTP %s %s hit: ct=%s", request.method, request.url.path, request.headers.get("content-type"))
        # Проверка секрета вебхука
        settings = get_settings()
        # NOTE: Telegram Bot API: header name is X-Telegram-Bot-Api-Secret-Token (see Bot API docs).
        if not verify_secret(x_telegram_bot_api_secret_token, settings.WEBHOOK_SECRET):
            logger.warning("Invalid webhook secret token")
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=403)
        # Content-Type must be application/json
        ct = (request.headers.get("content-type") or "").lower()
        if "application/json" not in ct:
            webhook_dropped_total.labels("bad_content_type").inc()
            return JSONResponse({"ok": False, "error": "unsupported media type"}, status_code=415)
        # Ограничение размера тела по Content-Length (быстро) и фактическому телу
        try:
            cl = int(request.headers.get("content-length") or 0)
        except Exception:
            cl = 0
        max_body = int(settings.MAX_WEBHOOK_BODY)
        if cl and cl > max_body:
            webhook_dropped_total.labels("too_large").inc()
            return JSONResponse({"ok": False, "error": "payload too large"}, status_code=413)
        body = await request.body()
        if len(body) > max_body:
            webhook_dropped_total.labels("too_large").inc()
            return JSONResponse({"ok": False, "error": "payload too large"}, status_code=413)
        data = await request.json()
        update = None
        app_ref = application
        if app_ref is not None:
            update = Update.de_json(data, app_ref.bot)
        # Allowed updates filter
        try:
            upd_type = (
                "message" if "message" in data else (
                    "edited_message" if "edited_message" in data else (
                        "callback_query" if "callback_query" in data else (
                            "chat_member" if "chat_member" in data else (
                                "my_chat_member" if "my_chat_member" in data else (
                                    "message_reaction" if "message_reaction" in data else (
                                        "chat_join_request" if "chat_join_request" in data else (
                                            "pre_checkout_query" if "pre_checkout_query" in data else "other"
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        except Exception:
            upd_type = "other"
        if upd_type not in get_settings().ALLOWED_UPDATES:
            webhook_dropped_total.labels("not_allowed").inc()
            return {"ok": True}
        # Correlate ids for logs
        try:
            if update is not None:
                set_update_context(
                    update.update_id,
                    getattr(update.effective_chat, "id", None),
                    getattr(update.effective_user, "id", None),
                )
        except Exception:
            pass
        # Ограничение длины текста/подписи
        try:
            if update is not None and update.message and update.message.text and len(update.message.text) > 4096:
                update.message.text = update.message.text[:4096]
            if update is not None and update.message and update.message.caption and len(update.message.caption) > 4096:
                update.message.caption = update.message.caption[:4096]
        except Exception:
            pass
        # Idempotency guard
        try:
            if is_duplicate_update(getattr(update, "update_id", None) if update is not None else data.get("update_id")):
                webhook_dropped_total.labels("duplicate").inc()
                return {"ok": True}
        except Exception:
            pass
        # Metrics: updates
        try:
            chat_type = None
            if update is not None and update.effective_chat is not None:
                chat_type = getattr(update.effective_chat, "type", None)
            updates_total.labels(upd_type, chat_type or "unknown").inc()
        except Exception:
            pass
        # Log update meta
        try:
            uid = getattr(update, "update_id", None) if update is not None else data.get("update_id")
            logger.info("update meta: id=%s type=%s", uid, upd_type)
        except Exception:
            pass
        # Idempotency persisted; enqueue to background worker queue (if PTB ready)
        store = IdempotencyStore()
        ukey = make_key("update", str((getattr(update, "update_id", None) if update is not None else data.get("update_id")) or "0"))
        async def enqueue() -> None:
            global update_queue, application
            # If queue exists (webhook mode) → enqueue; otherwise process directly in background
            if update is None:
                return
            # Inline processing for debug
            if get_settings().WEBHOOK_INLINE_PROCESS and application is not None:
                try:
                    await application.process_update(update)
                except Exception as exc:  # noqa: BLE001
                    logger.error("inline process_update error: %s", exc, exc_info=True)
                return
            if update_queue is not None:
                await update_queue.put(update)
                return
            # No queue (likely polling mode set by mistake with webhook) → process via task
            if application is not None:
                tmo = float(get_settings().WEBHOOK_HANDLE_TIMEOUT_S)
                async def _proc() -> None:
                    try:
                        async with asyncio.timeout(tmo):
                            await application.process_update(update)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("direct process_update error: %s", exc, exc_info=True)
                asyncio.create_task(_proc())
        await with_idempotency(ukey, enqueue, store)
        logger.info("HTTP %s %s ack 200: len=%s keys=%s", request.method, request.url.path, len(body), list(data.keys()))
        # Extended diagnostics only when DEBUG enabled
        if settings.DEBUG:
            try:
                upd_type = (
                    "message" if "message" in data else (
                        "callback_query" if "callback_query" in data else "other"
                    )
                )
                uid = ((data.get("message") or {}).get("from", {}) or (data.get("callback_query") or {}).get("from", {})).get("id")
                text = None
                if update is not None and update.message and update.message.text:
                    text = update.message.text
                elif update is not None and update.callback_query and update.callback_query.data:
                    text = update.callback_query.data
                logger.debug("Webhook detail: type=%s uid=%s text=%s", upd_type, uid, text)
            except Exception:  # noqa: BLE001
                pass
        # Быстрый ACK — обработка продолжается в фоне
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001 - логируем всё, сервер не падает
        logger.error("/webhook processing error: %s", exc, exc_info=True)
        try:
            webhook_errors_total.labels("exception").inc()
        except Exception:
            pass
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
        return JSONResponse({
            "running": application is not None,
            "public_base": bool(settings.PUBLIC_BASE),
            "debug": settings.DEBUG,
            "webhook": webhook_url,
        })
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
