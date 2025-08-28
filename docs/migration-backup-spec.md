# Migration Backup v1 - Technical Specification

## Overview

**Feature**: Automatic Database Backup for Forward-Only Migrations  
**Version**: v1.0  
**Status**: Implementation  
**Target**: Production-safe database migrations with automatic backup and recovery capabilities

## Problem Statement

### Current Issues
1. **No Backup Protection**: Migrations run without automatic database backups
2. **No Dry-Run Capability**: Cannot preview migration changes before applying
3. **Manual Backup Process**: Developers must remember to create backups manually
4. **Backup Accumulation**: No automatic cleanup of old backup files
5. **Production Risk**: Potential data loss during failed migrations

### Goals
- **Automatic Backup**: Create timestamped backups before applying migrations
- **Dry-Run Preview**: Show migration plan without making database changes
- **Backup Management**: Automatic retention and cleanup of backup files
- **Production Safety**: Fail-safe migration process with recovery options
- **Developer Experience**: Simple CLI interface with clear feedback

## Technical Requirements

### Functional Requirements

#### FR1: Automatic Backup Creation
- **Timestamped Backups**: Format `db.sqlite.backup.YYYYMMDD_HHMMSS.sqlite`
- **Pre-Migration Timing**: Backups created before any migration execution
- **Error Handling**: Migration fails if backup creation fails
- **File Size Logging**: Report backup file size for monitoring

#### FR2: Dry-Run Migration Preview
- **Plan Display**: Show list of pending migrations with descriptions
- **No Database Changes**: Guarantee no modifications in dry-run mode
- **Description Extraction**: Parse migration descriptions from SQL comments
- **Return Count**: Return number of migrations that would be applied

#### FR3: Backup Retention Management
- **Configurable Retention**: Keep N most recent backup files (default: 7)
- **Automatic Cleanup**: Remove old backups after new backup creation
- **Database-Specific**: Only clean backups for the current database
- **Safe Deletion**: Preserve backups during retention period

#### FR4: Enhanced CLI Interface
- **Backup Flag**: `--backup` to enable backup creation
- **Dry-Run Flag**: `--dry-run` to preview without changes
- **Retention Control**: `--backup-retention N` to customize retention
- **Combined Usage**: Support `--backup --dry-run` for complete preview

#### FR5: Improved Logging and Feedback
- **Structured Logging**: Clear timestamps and operation details
- **Migration Progress**: Individual migration status and descriptions
- **Backup Information**: Paths, file sizes, and retention actions
- **Error Details**: Comprehensive error reporting with context

### Technical Specifications

#### Backup File Naming Convention
```
Format: {db_name}.backup.{timestamp}.sqlite
Example: app.backup.20241201_143052.sqlite

Components:
- db_name: Original database filename without extension
- timestamp: YYYYMMDD_HHMMSS format for sorting
- extension: .sqlite for consistency
```

#### CLI Interface
```bash
# Basic migration (no backup)
python -m app.utils.migrate

# Migration with backup
python -m app.utils.migrate --backup

# Dry-run preview
python -m app.utils.migrate --dry-run

# Combined backup and dry-run
python -m app.utils.migrate --backup --dry-run

# Custom backup retention
python -m app.utils.migrate --backup --backup-retention 10

# Specify migrations directory
python -m app.utils.migrate --dir /path/to/migrations --backup
```

#### Configuration Parameters
```python
# Environment variable or config setting
BACKUP_RETENTION: int = 7  # Number of backup files to retain

# CLI argument defaults
--backup-retention: default=7
--dir: default=db/migrations/
```

#### Migration Description Format
```sql
-- Create users table with authentication fields
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
```

### Performance Requirements

#### PR1: Backup Performance
- **Creation Speed**: < 5 seconds for databases up to 100MB
- **Storage Overhead**: Backup files use standard filesystem compression
- **Memory Usage**: < 50MB additional memory during backup operation
- **I/O Impact**: Minimal impact on concurrent database operations

#### PR2: Migration Performance
- **Dry-Run Speed**: < 1 second for 100 migration files
- **Plan Generation**: Instant parsing of migration descriptions
- **CLI Responsiveness**: < 2 seconds startup time
- **Logging Overhead**: < 5% performance impact

#### PR3: Cleanup Performance
- **Retention Processing**: < 1 second for 100 backup files
- **File Operations**: Efficient sorting and deletion
- **Concurrent Safety**: No interference with ongoing backups
- **Error Recovery**: Graceful handling of filesystem errors

## Implementation Details

### Core Components

#### Backup Creation (`_create_backup`)
```python
def _create_backup(db_path: Path, backup_retention: int = 7) -> Path:
    """Create timestamped database backup with automatic cleanup.
    
    Args:
        db_path: Path to the database file
        backup_retention: Number of backup files to retain
        
    Returns:
        Path to the created backup file
        
    Raises:
        RuntimeError: If backup creation fails
    """
    # Generate timestamp-based filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{db_path.stem}.backup.{timestamp}.sqlite"
    backup_path = db_path.parent / backup_filename
    
    # Create backup using shutil.copy2 (preserves metadata)
    shutil.copy2(db_path, backup_path)
    
    # Log backup information
    file_size_mb = backup_path.stat().st_size / (1024 * 1024)
    logger.info("Database backup created: %s (%.2f MB)", backup_path, file_size_mb)
    
    # Cleanup old backups
    _cleanup_old_backups(backup_path.parent, db_path.stem, backup_retention)
    
    return backup_path
```

#### Backup Cleanup (`_cleanup_old_backups`)
```python
def _cleanup_old_backups(backup_dir: Path, db_name: str, retention_count: int) -> None:
    """Remove old backup files, keeping only the most recent ones.
    
    Strategy:
    1. Find all backup files for the specific database
    2. Sort by modification time (newest first)
    3. Remove files beyond retention count
    4. Log cleanup actions
    """
    backup_pattern = f"{db_name}.backup.*.sqlite"
    backup_files = list(backup_dir.glob(backup_pattern))
    
    if len(backup_files) <= retention_count:
        return  # No cleanup needed
    
    # Sort by modification time and remove old files
    backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    files_to_remove = backup_files[retention_count:]
    
    for backup_file in files_to_remove:
        backup_file.unlink()
        logger.info("Removed old backup: %s", backup_file)
```

#### Dry-Run Implementation
```python
def migrate(migrations_dir: str, dry_run: bool = False, backup: bool = False, 
           backup_retention: int = 7) -> int:
    """Enhanced migration function with backup and dry-run support.
    
    Dry-run logic:
    1. Generate migration plan without database changes
    2. Log each migration with description
    3. Return count of migrations that would be applied
    4. Guarantee no database modifications
    """
    pending = get_pending_migrations(migrations_dir)
    
    if dry_run:
        # Show plan without executing
        for migration_file in pending:
            description = _get_migration_description(migration_file)
            logger.info("Would apply: %s - %s", migration_file.stem, description)
        logger.info("DRY RUN: Would apply %d migrations", len(pending))
        return len(pending)
    
    # Normal execution with optional backup
    if backup and db_exists():
        backup_path = _create_backup(APP_DB_PATH, backup_retention)
    
    return _apply_sql_files(pending, dry_run=False)
```

#### CLI Enhancement
```python
def main() -> int:
    """Enhanced CLI with backup and dry-run support."""
    parser = argparse.ArgumentParser(description="SQLite forward-only migrator with backup support")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show migration plan without applying changes")
    parser.add_argument("--backup", action="store_true",
                       help="Create database backup before applying migrations")
    parser.add_argument("--backup-retention", type=int, default=7,
                       help="Number of backup files to retain (default: 7)")
    
    args = parser.parse_args()
    
    # Execute migration with specified options
    applied = migrate(args.dir, args.dry_run, args.backup, args.backup_retention)
    
    if args.dry_run:
        logger.info("Dry-run completed: would apply %d migration(s)", applied)
    else:
        logger.info("Migration completed: applied %d migration(s)", applied)
```

### Error Handling and Recovery

#### Backup Failure Scenarios
```python
# Backup creation failure
try:
    backup_path = _create_backup(APP_DB_PATH, backup_retention)
except Exception as e:
    logger.error("Failed to create backup: %s", e)
    raise RuntimeError(f"Backup creation failed: {e}") from e

# Migration continues only if backup succeeds
# This ensures data safety before any schema changes
```

#### Migration Failure Recovery
```python
# If migration fails after backup creation:
# 1. Backup file remains available for manual recovery
# 2. Database state is partially migrated (tracked in schema_version)
# 3. Subsequent runs will attempt only remaining migrations
# 4. Manual restoration: cp backup.sqlite app.db
```

#### Filesystem Error Handling
```python
# Cleanup failures don't stop the migration
try:
    _cleanup_old_backups(backup_dir, db_name, retention_count)
except Exception as e:
    logger.warning("Backup cleanup failed (migration continues): %s", e)
    # Migration proceeds - cleanup failure is non-critical
```

### Integration Points

#### Configuration Integration
```python
# app/config.py
class Settings(BaseSettings):
    BACKUP_RETENTION: int = 7  # Keep last N backup files
    
# Usage in migration
settings = get_settings()
retention = getattr(settings, 'BACKUP_RETENTION', 7)
```

#### Makefile Integration
```makefile
# Development commands
migrate:
	python -m app.utils.migrate --backup

migrate-dry:
	python -m app.utils.migrate --dry-run

backup-migrate:
	python -m app.utils.migrate --backup --backup-retention 10
```

#### CI/CD Integration
```yaml
# GitHub Actions example
- name: Run database migrations
  run: |
    python -m app.utils.migrate --backup --backup-retention 5
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## Validation Matrix

| Test Scenario | Input | Expected Behavior | Verification Method |
|---------------|-------|-------------------|-------------------|
| **Basic Backup** | `--backup` flag | Timestamped backup created | File exists with correct format |
| **Dry-Run Preview** | `--dry-run` flag | Migration plan displayed, no DB changes | Database unchanged after run |
| **Backup Retention** | Multiple backups, retention=3 | Only 3 most recent backups kept | File count verification |
| **Combined Flags** | `--backup --dry-run` | Backup shown in plan, no actual backup | No backup file created |
| **No Pending Migrations** | Current migrations applied | "No migrations" message | Zero return code |
| **Backup Failure** | Insufficient disk space | Migration fails with error | Error message and non-zero exit |
| **Missing Database** | No database file | Warning logged, backup skipped | Migration proceeds normally |
| **Description Parsing** | Migration with comment | Description extracted and shown | Correct description in output |
| **CLI Module Entry** | `python -m app.utils.migrate` | Same as direct script execution | Consistent behavior |
| **Makefile Integration** | `make migrate` | Backup-enabled migration | Backup file created |

## Error Scenarios and Responses

### Backup Creation Errors
```bash
# Insufficient disk space
ERROR: Backup creation failed: No space left on device
SOLUTION: Free disk space or disable backup for emergency migration

# Permission denied
ERROR: Backup creation failed: Permission denied
SOLUTION: Check file permissions on database directory

# Database locked
ERROR: Backup creation failed: Database is locked
SOLUTION: Ensure no other processes are using the database
```

### Migration Errors
```bash
# SQL syntax error in migration
ERROR: Migration failed: near "CREAT": syntax error
INFO: Successfully applied before failure: 001_create_users
SOLUTION: Fix SQL syntax in failed migration file

# Foreign key constraint violation
ERROR: Migration failed: FOREIGN KEY constraint failed
SOLUTION: Check migration order and referential integrity
```

### Cleanup Errors
```bash
# Backup cleanup permission error
WARNING: Backup cleanup failed (migration continues): Permission denied
INFO: Migration completed: applied 3 migration(s)
NOTE: Manual cleanup may be required for old backup files
```

## Testing Strategy

### Unit Tests
- **Backup Creation**: File format, content verification, timestamp parsing
- **Retention Logic**: Correct file selection, cleanup behavior, edge cases
- **Dry-Run Functionality**: No database changes, correct plan display
- **Description Parsing**: Comment extraction, fallback behavior
- **CLI Integration**: Argument parsing, flag combinations

### Integration Tests
- **End-to-End Migration**: Complete migration with backup and cleanup
- **Error Recovery**: Failed migration recovery, partial application
- **Concurrent Access**: Multiple migration processes, database locking
- **Filesystem Stress**: Low disk space, permission errors

### Performance Tests
- **Large Databases**: Backup performance with 100MB+ databases
- **Many Migrations**: Dry-run performance with 100+ migration files
- **Backup Cleanup**: Retention performance with many backup files

### Regression Tests
- **Backward Compatibility**: Existing migration behavior unchanged
- **Configuration Changes**: Environment variable integration
- **CLI Changes**: New flags don't break existing usage

## Success Metrics

### Operational Metrics
- **Backup Success Rate**: > 99% successful backup creation
- **Migration Reliability**: > 99.5% successful migration completion
- **Recovery Time**: < 5 minutes to restore from backup
- **Cleanup Efficiency**: 100% retention policy compliance

### Performance Metrics
- **Backup Speed**: < 5 seconds for typical database sizes
- **Dry-Run Speed**: < 1 second for migration plan generation
- **Storage Efficiency**: < 10% additional storage for backups
- **CLI Responsiveness**: < 2 seconds command startup time

### Developer Experience
- **Error Clarity**: 100% of errors include actionable guidance
- **Documentation Completeness**: All CLI options documented with examples
- **Recovery Success**: 100% of backup restores successful
- **Integration Ease**: Zero-configuration Makefile integration

## Risk Assessment

### Data Safety Risks
- **Backup Corruption**: Risk of corrupted backup files - **Mitigation**: Verify backup integrity during creation
- **Backup Failure**: Risk of migration proceeding without backup - **Mitigation**: Fail migration if backup fails
- **Storage Exhaustion**: Risk of backup files filling disk - **Mitigation**: Configurable retention with monitoring

### Operational Risks
- **Performance Impact**: Risk of backup slowing migrations - **Mitigation**: Optimize backup creation and cleanup
- **Complexity Increase**: Risk of feature complexity affecting reliability - **Mitigation**: Comprehensive testing and simple interfaces
- **Recovery Confusion**: Risk of unclear recovery procedures - **Mitigation**: Clear documentation and logging

### Integration Risks
- **CLI Changes**: Risk of breaking existing automation - **Mitigation**: Backward compatibility and optional flags
- **Configuration Drift**: Risk of inconsistent backup settings - **Mitigation**: Centralized configuration with defaults
- **Tool Dependencies**: Risk of backup tools affecting migration - **Mitigation**: Use standard library functions only

## Future Enhancements

### V2 Considerations
- **Compressed Backups**: Reduce backup file sizes with compression
- **Remote Backup Storage**: Upload backups to cloud storage
- **Backup Verification**: Automatic integrity checking of backup files
- **Parallel Operations**: Concurrent backup creation and cleanup

### Advanced Features
- **Incremental Backups**: Only backup changes since last backup
- **Migration Rollback**: Automated rollback using backup files
- **Backup Encryption**: Encrypted backup files for sensitive data
- **Cross-Database Support**: Backup strategies for other database types

### Monitoring Integration
- **Backup Metrics**: Integration with monitoring systems
- **Alert Integration**: Automatic alerts for backup failures
- **Dashboard Support**: Visual backup status and retention tracking
- **Audit Logging**: Detailed logs for compliance and debugging

### Operational Improvements
- **Health Checks**: Backup system health validation
- **Capacity Planning**: Predictive backup storage requirements
- **Performance Optimization**: Advanced backup strategies for large databases
- **Recovery Testing**: Automated backup restoration validation


