from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable

from app.db.session import _get_conn  # type: ignore[attr-defined]


logger = logging.getLogger(__name__)


def _current_version() -> int:
    with _get_conn() as conn:
        try:
            row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
            return int(row[0]) if row else 0
        except Exception:
            # Table may not exist yet
            return 0


def _ensure_version_table() -> None:
    with _get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        conn.commit()


def _apply_sql_files(files: list[Path], dry_run: bool) -> int:
    applied = 0
    with _get_conn() as conn:
        try:
            if not dry_run:
                conn.execute("BEGIN")
            for f in files:
                sql = f.read_text(encoding="utf-8")
                logger.info("Applying migration %s", f.name)
                if dry_run:
                    continue
                conn.executescript(sql)
                # record version from filename prefix
                ver = int(f.stem.split("_", 1)[0])
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (ver,))
                applied += 1
            if not dry_run:
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            if not dry_run:
                conn.rollback()
            logger.error("Migration failed: %s", exc)
            raise
    return applied


def migrate(migrations_dir: str, dry_run: bool = False) -> int:
    _ensure_version_table()
    current = _current_version()
    base = Path(migrations_dir)
    files = sorted([p for p in base.glob("*.sql") if p.is_file()], key=lambda p: p.name)
    pending = [p for p in files if int(p.stem.split("_", 1)[0]) > current]
    if not pending:
        logger.info("No migrations to apply. Current version=%s", current)
        return 0
    return _apply_sql_files(pending, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite forward-only migrator")
    parser.add_argument("--dir", default=str(Path(__file__).resolve().parents[2] / "db" / "migrations"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        applied = migrate(args.dir, args.dry_run)
        logger.info("Applied %s migration(s)", applied)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())




































