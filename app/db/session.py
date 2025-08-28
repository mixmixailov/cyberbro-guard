from __future__ import annotations

import logging
import sqlite3
import json
from pathlib import Path
from typing import Any, Iterable

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


