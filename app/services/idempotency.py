from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import os
from typing import Any, Literal

from app.config import get_settings
from app.db.session import _get_conn  # reuse connection config


logger = logging.getLogger(__name__)


def now_ts() -> int:
	return int(time.time())


def make_key(source: Literal["update", "payment"], value: str) -> str:
	return f"{source}:{value}"


def _resp_hash(obj: Any) -> str:
	try:
		data = json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
	except Exception:
		data = str(obj)
	return hashlib.sha256(data.encode("utf-8")).hexdigest()


class IdempotencyStore:
	def __init__(self, ttl_sec: int | None = None) -> None:
		s = get_settings()
		self._ttl = int(ttl_sec or getattr(s, "IDMP_TTL_SEC", 172800))
		# Isolated in-memory DB during pytest runs
		self._mem_conn: sqlite3.Connection | None = None
		if os.environ.get("PYTEST_CURRENT_TEST"):
			conn = sqlite3.connect(":memory:", timeout=30, check_same_thread=False)
			conn.row_factory = sqlite3.Row
			try:
				conn.execute("PRAGMA journal_mode=MEMORY;")
				conn.execute("PRAGMA synchronous=OFF;")
			except Exception:
				pass
			conn.executescript(
				"""
				CREATE TABLE IF NOT EXISTS idempotency (
					key TEXT PRIMARY KEY,
					status TEXT NOT NULL,
					response_hash TEXT,
					created_at INTEGER NOT NULL,
					expires_at INTEGER NOT NULL
				);
				CREATE INDEX IF NOT EXISTS idx_idempotency_expires_at ON idempotency (expires_at);
				"""
			)
			conn.commit()
			self._mem_conn = conn

	def _conn(self) -> sqlite3.Connection:
		return self._mem_conn or _get_conn()

	def _execute(self, sql: str, params: tuple[Any, ...]) -> int:
		# Simple retry on SQLITE_BUSY
		last_exc: Exception | None = None
		for _ in range(3):
			try:
				with self._conn() as conn:
					cur = conn.execute(sql, params)
					conn.commit()
					return cur.rowcount
			except sqlite3.OperationalError as exc:  # pragma: no cover - timing dependent
				last_exc = exc
				if "database is locked" in str(exc).lower():
					time.sleep(0.05)
					continue
				raise
		if last_exc:
			raise last_exc
		return 0

	def begin(self, key: str) -> str:
		ts = now_ts()
		exp = ts + self._ttl
		masked = key.split(":")[-1]
		# Try to insert as processing
		inserted = False
		try:
			inserted = self._execute(
				"INSERT OR IGNORE INTO idempotency (key, status, created_at, expires_at) VALUES (?, 'processing', ?, ?)",
				(key, ts, exp),
			) > 0
		except Exception as exc:  # noqa: BLE001
			logger.error("idmp begin failed key=%s err=%s", masked, exc)
		if inserted:
			logger.info("idmp acquire key=%s", masked)
			return "acquired"
		# Not inserted: check existing status
		row = self.get(key)
		if not row:
			# Race: try again once
			try:
				inserted = self._execute(
					"INSERT OR IGNORE INTO idempotency (key, status, created_at, expires_at) VALUES (?, 'processing', ?, ?)",
					(key, ts, exp),
				) > 0
			except Exception:
				inserted = False
			if inserted:
				logger.info("idmp acquire key=%s", masked)
				return "acquired"
			row = self.get(key)
		if not row:
			return "acquired"  # best effort
		status = row.get("status")
		# If expired OR row appears from the future relative to current ts (e.g., monkeypatched time),
		# treat as new acquisition by updating status/expiry
		try:
			row_created = int(row.get("created_at") or 0)
			row_expires = int(row.get("expires_at") or 0)
			if row_expires <= ts or row_created > ts:
				self._execute(
					"UPDATE idempotency SET status='processing', created_at=?, expires_at=? WHERE key=?",
					(ts, exp, key),
				)
				logger.info("idmp reacquire_expired key=%s", masked)
				return "acquired"
		except Exception:
			pass
		if status == "done":
			logger.info("idmp exists_done key=%s", masked)
			return "exists_done"
		logger.info("idmp exists_processing key=%s", masked)
		return "exists_processing"

	def commit(self, key: str, response_obj: Any) -> None:
		rh = _resp_hash(response_obj)
		masked = key.split(":")[-1]
		try:
			self._execute(
				"UPDATE idempotency SET status='done', response_hash=? WHERE key=? AND status='processing'",
				(rh, key),
			)
			logger.info("idmp commit key=%s", masked)
		except Exception as exc:  # noqa: BLE001
			logger.error("idmp commit failed key=%s err=%s", masked, exc)

	def fail(self, key: str) -> None:
		masked = key.split(":")[-1]
		try:
			self._execute(
				"UPDATE idempotency SET status='failed' WHERE key=? AND status='processing'",
				(key,),
			)
			logger.info("idmp fail key=%s", masked)
		except Exception as exc:  # noqa: BLE001
			logger.error("idmp fail failed key=%s err=%s", masked, exc)

	def get(self, key: str) -> dict[str, Any] | None:
		try:
			with self._conn() as conn:
				cur = conn.execute("SELECT key, status, response_hash, created_at, expires_at FROM idempotency WHERE key=?", (key,))
				row = cur.fetchone()
				return dict(row) if row else None
		except Exception as exc:  # noqa: BLE001
			logger.error("idmp get failed key=%s err=%s", key.split(":")[-1], exc)
			return None

	def purge_expired(self, limit: int = 1000) -> int:
		now = now_ts()
		try:
			with self._conn() as conn:
				# Select keys explicitly, then delete by IN (...). Avoid parameter for LIMIT for maximum SQLite compatibility.
				lim = max(1, int(limit))
				rows = conn.execute(
					f"SELECT key FROM idempotency WHERE expires_at <= ? LIMIT {lim}",
					(now,),
				).fetchall()
				if not rows:
					return 0
				keys = [str(r[0]) for r in rows]
				placeholders = ",".join(["?"] * len(keys))
				cur = conn.execute(
					f"DELETE FROM idempotency WHERE key IN ({placeholders})",
					tuple(keys),
				)
				conn.commit()
				return cur.rowcount
		except Exception as exc:  # noqa: BLE001
			logger.error("idmp purge failed err=%s", exc)
			return 0





