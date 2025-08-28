from __future__ import annotations

import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path

from app.db.session import _get_conn  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


def _current_version() -> int:
    with _get_conn() as conn:
        try:
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            return int(row[0]) if row else 0
        except Exception:
            # Table may not exist yet
            return 0


def _ensure_version_table() -> None:
    with _get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        conn.commit()


def _create_backup(db_path: Path, backup_retention: int = 7) -> Path:
    """Create a backup of the database with timestamp.

    Args:
        db_path: Path to the database file
        backup_retention: Number of backup files to retain

    Returns:
        Path to the created backup file
    """
    backup_dir = db_path.parent
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp-based backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{db_path.stem}.backup.{timestamp}.sqlite"
    backup_path = backup_dir / backup_filename

    # Create backup
    logger.info("Creating database backup: %s", backup_path)
    shutil.copy2(db_path, backup_path)

    file_size_mb = backup_path.stat().st_size / (1024 * 1024)
    logger.info("Database backup created: %s (%.2f MB)", backup_path, file_size_mb)

    # Cleanup old backups
    _cleanup_old_backups(backup_dir, db_path.stem, backup_retention)

    return backup_path


def _cleanup_old_backups(backup_dir: Path, db_name: str, retention_count: int) -> None:
    """Remove old backup files, keeping only the most recent ones.

    Args:
        backup_dir: Directory containing backup files
        db_name: Database name (without extension) to match backup files
        retention_count: Number of recent backups to keep
    """
    # Find all backup files for this database
    backup_pattern = f"{db_name}.backup.*.sqlite"
    backup_files = list(backup_dir.glob(backup_pattern))

    if len(backup_files) <= retention_count:
        logger.debug(
            "Found %d backup files, retention limit is %d - no cleanup needed",
            len(backup_files),
            retention_count,
        )
        return

    # Sort by modification time (newest first)
    backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Remove old backups
    files_to_remove = backup_files[retention_count:]
    for backup_file in files_to_remove:
        logger.info("Removing old backup: %s", backup_file)
        backup_file.unlink()

    logger.info(
        "Cleaned up %d old backup files, kept %d recent backups",
        len(files_to_remove),
        min(len(backup_files), retention_count),
    )


def _get_migration_description(migration_file: Path) -> str:
    """Extract description from migration file's first comment line."""
    try:
        with open(migration_file, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if first_line.startswith("--"):
                return first_line[2:].strip()
    except Exception:
        pass
    return "No description"


def _apply_sql_files(files: list[Path], dry_run: bool) -> int:
    applied = 0
    applied_names = []

    with _get_conn() as conn:
        try:
            if not dry_run:
                conn.execute("BEGIN")

            for f in files:
                migration_name = f.stem
                description = _get_migration_description(f)

                if dry_run:
                    logger.info("Would apply migration: %s - %s", migration_name, description)
                    continue

                sql = f.read_text(encoding="utf-8")
                logger.info("Applying migration: %s - %s", migration_name, description)

                conn.executescript(sql)
                # record version from filename prefix
                ver = int(f.stem.split("_", 1)[0])
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (ver,))
                applied += 1
                applied_names.append(migration_name)

                logger.info("Successfully applied: %s", migration_name)

            if not dry_run:
                conn.commit()
                if applied_names:
                    logger.info("Applied migrations: %s", ", ".join(applied_names))

        except Exception as exc:  # noqa: BLE001
            if not dry_run:
                conn.rollback()
            logger.error("Migration failed: %s", exc)
            if applied_names:
                logger.error("Successfully applied before failure: %s", ", ".join(applied_names))
            raise

    return applied


def migrate(
    migrations_dir: str, dry_run: bool = False, backup: bool = False, backup_retention: int = 7
) -> int:
    """Apply pending migrations from directory.

    Args:
        migrations_dir: Directory containing .sql migration files
        dry_run: If True, only show what would be applied without making changes
        backup: If True, create backup before applying migrations
        backup_retention: Number of backup files to retain

    Returns:
        Number of migrations applied
    """
    _ensure_version_table()
    current = _current_version()
    base = Path(migrations_dir)
    files = sorted([p for p in base.glob("*.sql") if p.is_file()], key=lambda p: p.name)
    pending = [p for p in files if int(p.stem.split("_", 1)[0]) > current]

    if not pending:
        logger.info("No migrations to apply. Current version=%s", current)
        return 0

    logger.info("Found %d pending migrations", len(pending))

    # Show migration plan
    for i, migration_file in enumerate(pending, 1):
        migration_name = migration_file.stem
        description = _get_migration_description(migration_file)
        logger.info("  %d. %s - %s", i, migration_name, description)

    if dry_run:
        logger.info("DRY RUN: Would apply %d migrations (no changes made)", len(pending))
        return len(pending)  # Return count for testing

    # Create backup if requested
    if backup:
        from app.db.session import APP_DB_PATH

        if APP_DB_PATH.exists():
            try:
                _create_backup(APP_DB_PATH, backup_retention)
                logger.info("Database backup completed before migration")
            except Exception as e:
                logger.error("Failed to create backup: %s", e)
                raise RuntimeError(f"Backup creation failed: {e}") from e
        else:
            logger.warning("Database file does not exist, skipping backup")

    return _apply_sql_files(pending, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite forward-only migrator with backup support")
    parser.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parents[2] / "db" / "migrations"),
        help="Directory containing migration files",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show migration plan without applying changes"
    )
    parser.add_argument(
        "--backup", action="store_true", help="Create database backup before applying migrations"
    )
    parser.add_argument(
        "--backup-retention",
        type=int,
        default=7,
        help="Number of backup files to retain (default: 7)",
    )

    args = parser.parse_args()

    # Setup logging with structured format
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        if args.dry_run:
            logger.info("Starting migration dry-run...")
        elif args.backup:
            logger.info("Starting migration with backup...")
        else:
            logger.info("Starting migration...")

        applied = migrate(args.dir, args.dry_run, args.backup, args.backup_retention)

        if args.dry_run:
            logger.info("Dry-run completed: would apply %d migration(s)", applied)
        else:
            logger.info("Migration completed: applied %d migration(s)", applied)

        return 0
    except Exception as e:
        logger.error("Migration failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
