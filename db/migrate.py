from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable

from app.db.session import _get_conn  # reuse sqlite config


logger = logging.getLogger(__name__)


def get_schema_version() -> int:
    with _get_conn() as conn:
        try:
            row = conn.execute("PRAGMA user_version;").fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0


def _set_schema_version(ver: int) -> None:
    with _get_conn() as conn:
        ver_int = int(ver)
        conn.execute(f"PRAGMA user_version={ver_int};")  # nosemgrep: PRAGMA with int-cast only
        conn.commit()


def list_migrations(migrations_dir: str) -> list[Path]:
    base = Path(migrations_dir)
    files = [p for p in base.glob("*.sql") if p.is_file()]
    # Sort by filename to enforce ascending order by prefix
    files.sort(key=lambda p: p.name)
    return files


def apply_migrations(migrations_dir: str) -> int:
    current = get_schema_version()
    files = list_migrations(migrations_dir)
    # pick those with numeric prefix > current
    pending: list[Path] = []
    for f in files:
        try:
            prefix = int(f.stem.split("_", 1)[0])
        except Exception:
            # skip files without numeric prefix
            continue
        if prefix > current:
            pending.append(f)
    if not pending:
        logger.info("migrations up-to-date ver=%s", current)
        return 0
    applied = 0
    with _get_conn() as conn:
        try:
            for f in pending:
                sql = f.read_text(encoding="utf-8")
                logger.info("apply %s", f.name)
                conn.executescript(sql)
                # set PRAGMA user_version to this migration's prefix
                ver = int(f.stem.split("_", 1)[0])
                conn.execute(f"PRAGMA user_version={ver};")  # nosemgrep: PRAGMA with int-cast only
                applied += 1
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            logger.error("migration failed: %s", exc)
            raise
    return applied


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SQLite forward-only migrator (PRAGMA user_version)")
    parser.add_argument("--dir", default=str(Path(__file__).resolve().parent / "migrations"))
    args = parser.parse_args(args=list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO)
    try:
        count = apply_migrations(args.dir)
        logger.info("applied=%s new_version=%s", count, get_schema_version())
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())






