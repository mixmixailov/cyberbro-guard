from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

APP_DB_PATH = Path("data") / "app.db"


def _get_conn() -> sqlite3.Connection:
    APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
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
                raw_json TEXT
            );
            """
        )
        conn.commit()
    logger.info("SQLite initialized at %s", APP_DB_PATH)


def execute(query: str, params: Iterable[Any] = ()) -> int:
    with _get_conn() as conn:
        cursor = conn.execute(query, tuple(params))
        conn.commit()
        lastrowid = cursor.lastrowid or 0
        return int(lastrowid) if lastrowid > 0 else cursor.rowcount


def fetchone(query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    with _get_conn() as conn:
        cursor = conn.execute(query, tuple(params))
        row = cursor.fetchone()
        return dict(row) if row else None


def fetchall(query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with _get_conn() as conn:
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


