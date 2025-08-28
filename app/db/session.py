from __future__ import annotations

import logging
import sqlite3
import json
from pathlib import Path
from typing import Any, Iterable, Dict

logger = logging.getLogger(__name__)

APP_DB_PATH = Path("data") / "app.db"


def _get_conn(immediate: bool = False) -> sqlite3.Connection:
    """Get database connection with optional immediate transaction.
    
    Args:
        immediate: If True, starts transaction with BEGIN IMMEDIATE for
                  immediate RESERVED lock acquisition, preventing SQLITE_BUSY
                  errors during concurrent writes.
    """
    APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(APP_DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        
        if immediate:
            # Start transaction with immediate RESERVED lock
            # This prevents SQLITE_BUSY errors in high-concurrency scenarios
            conn.execute("BEGIN IMMEDIATE;")
            logger.debug("Started IMMEDIATE transaction")
    except Exception as e:
        logger.warning("Failed to configure SQLite connection: %s", e)
        if immediate:
            # If BEGIN IMMEDIATE failed, at least try regular transaction
            try:
                conn.execute("BEGIN;")
                logger.debug("Fallback to regular transaction")
            except Exception:
                pass
    return conn


def init_db() -> None:
    with _get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                lang TEXT,
                plan TEXT NOT NULL DEFAULT 'free',
                until TEXT
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                amount_cents INTEGER NOT NULL,
                currency TEXT NOT NULL,
                provider TEXT,
                status TEXT,
                created_at TEXT NOT NULL,
                raw_json TEXT,
                charge_id TEXT UNIQUE
            );
            
            CREATE INDEX IF NOT EXISTS idx_payments_charge_id ON payments(charge_id);
            CREATE INDEX IF NOT EXISTS idx_payments_tg_id ON payments(tg_id);
            CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY,
                title TEXT,
                type TEXT,
                enabled INTEGER NOT NULL DEFAULT 0,
                locale TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                flood_n INTEGER,
                flood_window_s INTEGER,
                repeat_n INTEGER,
                repeat_window_s INTEGER,
                link_policy TEXT,
                captcha_mode TEXT,
                captcha_ttl_s INTEGER,
                punish_policy TEXT,
                warns_limit INTEGER,
                ban_days INTEGER,
                link_allowlist TEXT,
                welcome_enabled INTEGER
            );

            CREATE TABLE IF NOT EXISTS user_state (
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                warns_24h INTEGER NOT NULL DEFAULT 0,
                last_msgs TEXT,
                PRIMARY KEY (user_id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS plans (
                code TEXT PRIMARY KEY,
                price_xtr INTEGER NOT NULL,
                period_days INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                plan_code TEXT NOT NULL,
                until TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(plan_code) REFERENCES plans(code)
            );

            CREATE TABLE IF NOT EXISTS subscription_reminders (
                subscription_id INTEGER PRIMARY KEY,
                t3_sent INTEGER NOT NULL DEFAULT 0,
                t1_sent INTEGER NOT NULL DEFAULT 0,
                t0_sent INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(subscription_id) REFERENCES subscriptions(id)
            );

            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS payment_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                ts TEXT NOT NULL,
                FOREIGN KEY(payment_id) REFERENCES payments(id)
            );
            """
        )
        conn.commit()
    logger.info("SQLite initialized at %s", APP_DB_PATH)


def execute(query: str, params: Iterable[Any] = (), immediate: bool = False) -> int:
    """Execute a query with optional immediate transaction.
    
    Args:
        query: SQL query to execute
        params: Query parameters
        immediate: If True, use BEGIN IMMEDIATE for critical writes
    """
    with _get_conn(immediate=immediate) as conn:
        cursor = conn.execute(query, tuple(params))
        conn.commit()
        lastrowid = cursor.lastrowid or 0
        return int(lastrowid) if lastrowid > 0 else cursor.rowcount


def fetchone(query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    """Fetch single row (read-only operations don't need immediate transactions)."""
    with _get_conn() as conn:
        cursor = conn.execute(query, tuple(params))
        row = cursor.fetchone()
        return dict(row) if row else None


def fetchall(query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    """Fetch all rows (read-only operations don't need immediate transactions)."""
    with _get_conn() as conn:
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def execute_immediate(query: str, params: Iterable[Any] = ()) -> int:
    """Execute query with BEGIN IMMEDIATE for critical writes.
    
    Use this for operations that must avoid SQLITE_BUSY errors:
    - Payment processing
    - User subscription updates  
    - Critical state changes
    """
    return execute(query, params, immediate=True)


def get_wal_info() -> Dict[str, Any]:
    """Get WAL file information and statistics.
    
    Returns:
        Dict with wal_pages, wal_size_bytes, main_db_size_bytes
    """
    try:
        with _get_conn() as conn:
            # Get WAL page count
            wal_pages_result = conn.execute("PRAGMA wal_checkpoint(PASSIVE);").fetchone()
            wal_pages = wal_pages_result[1] if wal_pages_result and len(wal_pages_result) > 1 else 0
            
            # Get database file sizes
            main_db_size = 0
            wal_size = 0
            
            if APP_DB_PATH.exists():
                main_db_size = APP_DB_PATH.stat().st_size
                
            wal_path = APP_DB_PATH.with_suffix('.db-wal')
            if wal_path.exists():
                wal_size = wal_path.stat().st_size
            
            return {
                "wal_pages": wal_pages,
                "wal_size_bytes": wal_size,
                "main_db_size_bytes": main_db_size,
                "wal_path": str(wal_path),
                "main_db_path": str(APP_DB_PATH)
            }
            
    except Exception as e:
        logger.error("Failed to get WAL info: %s", e)
        return {
            "wal_pages": 0,
            "wal_size_bytes": 0,
            "main_db_size_bytes": 0,
            "error": str(e)
        }


def checkpoint_wal(mode: str = "TRUNCATE") -> Dict[str, Any]:
    """Perform WAL checkpoint operation.
    
    Args:
        mode: Checkpoint mode - PASSIVE, FULL, RESTART, or TRUNCATE
        
    Returns:
        Dict with checkpoint results and timing
    """
    import time
    start_time = time.perf_counter()
    
    try:
        with _get_conn() as conn:
            # Get WAL info before checkpoint
            before_info = get_wal_info()
            
            # Perform checkpoint
            result = conn.execute(f"PRAGMA wal_checkpoint({mode});").fetchone()
            
            # Get WAL info after checkpoint
            after_info = get_wal_info()
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            logger.info(
                "WAL checkpoint completed",
                extra={
                    "mode": mode,
                    "duration_ms": round(duration_ms, 2),
                    "pages_before": before_info.get("wal_pages", 0),
                    "pages_after": after_info.get("wal_pages", 0),
                    "wal_size_before": before_info.get("wal_size_bytes", 0),
                    "wal_size_after": after_info.get("wal_size_bytes", 0)
                }
            )
            
            return {
                "success": True,
                "mode": mode,
                "duration_ms": round(duration_ms, 2),
                "pages_before": before_info.get("wal_pages", 0),
                "pages_after": after_info.get("wal_pages", 0),
                "wal_size_before": before_info.get("wal_size_bytes", 0),
                "wal_size_after": after_info.get("wal_size_bytes", 0),
                "result": result
            }
            
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            "WAL checkpoint failed",
            extra={
                "mode": mode,
                "duration_ms": round(duration_ms, 2),
                "error": str(e)
            }
        )
        return {
            "success": False,
            "mode": mode,
            "duration_ms": round(duration_ms, 2),
            "error": str(e)
        }


