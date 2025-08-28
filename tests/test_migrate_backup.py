"""Unit tests for migration backup functionality."""
import pytest
import tempfile
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.utils.migrate import _create_backup, _cleanup_old_backups, migrate


class TestBackupCreation:
    """Test backup creation functionality."""

    def test_create_backup_success(self):
        """Test successful backup creation with correct filename format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test database
            db_path = temp_path / "test.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE test (id INTEGER, data TEXT)")
                conn.execute("INSERT INTO test VALUES (1, 'test data')")
                conn.commit()
            
            # Create backup
            backup_path = _create_backup(db_path, backup_retention=5)
            
            # Verify backup exists and has correct format
            assert backup_path.exists()
            assert backup_path.name.startswith("test.backup.")
            assert backup_path.name.endswith(".sqlite")
            assert len(backup_path.name.split('.')) == 4  # test.backup.timestamp.sqlite
            
            # Verify backup content
            with sqlite3.connect(backup_path) as conn:
                result = conn.execute("SELECT * FROM test").fetchone()
                assert result == (1, 'test data')

    def test_create_backup_with_timestamp_format(self):
        """Test that backup filename contains valid timestamp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test database
            db_path = temp_path / "app.db"
            db_path.touch()
            
            # Create backup
            backup_path = _create_backup(db_path)
            
            # Extract timestamp from filename
            parts = backup_path.name.split('.')
            assert len(parts) == 4
            assert parts[0] == "app"
            assert parts[1] == "backup"
            assert parts[3] == "sqlite"
            
            # Verify timestamp format (YYYYMMDD_HHMMSS)
            timestamp = parts[2]
            assert len(timestamp) == 15  # YYYYMMDD_HHMMSS
            assert timestamp[8] == '_'
            
            # Should be parseable as datetime format
            from datetime import datetime
            parsed = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
            assert parsed is not None

    def test_create_backup_nonexistent_directory(self):
        """Test backup creation when backup directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test database
            db_path = temp_path / "test.db"
            db_path.touch()
            
            # Try to create backup (should create directory automatically)
            backup_path = _create_backup(db_path)
            
            assert backup_path.exists()
            assert backup_path.parent == temp_path  # Should be in same directory


class TestBackupRetention:
    """Test backup retention/cleanup functionality."""

    def test_cleanup_old_backups_keeps_recent(self):
        """Test that cleanup keeps the most recent backups."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            
            # Create multiple backup files with different timestamps
            backup_files = []
            for i in range(10):
                backup_file = backup_dir / f"app.backup.2024010{i:01d}_120000.sqlite"
                backup_file.touch()
                # Set different modification times
                timestamp = time.time() - (10 - i) * 3600  # Newer files have higher i
                backup_file.touch(times=(timestamp, timestamp))
                backup_files.append(backup_file)
            
            # Keep only 5 most recent
            _cleanup_old_backups(backup_dir, "app", 5)
            
            # Check that only 5 files remain
            remaining_files = list(backup_dir.glob("app.backup.*.sqlite"))
            assert len(remaining_files) == 5
            
            # Check that the most recent files are kept
            remaining_names = {f.name for f in remaining_files}
            expected_names = {f"app.backup.2024010{i}_120000.sqlite" for i in range(5, 10)}
            assert remaining_names == expected_names

    def test_cleanup_old_backups_no_cleanup_needed(self):
        """Test cleanup when number of backups is within retention limit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            
            # Create fewer files than retention limit
            for i in range(3):
                backup_file = backup_dir / f"app.backup.2024010{i}_120000.sqlite"
                backup_file.touch()
            
            # Set retention to 5 (more than existing files)
            _cleanup_old_backups(backup_dir, "app", 5)
            
            # All files should remain
            remaining_files = list(backup_dir.glob("app.backup.*.sqlite"))
            assert len(remaining_files) == 3

    def test_cleanup_old_backups_different_databases(self):
        """Test that cleanup only affects backups for the specified database."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            
            # Create backups for different databases
            for db_name in ["app", "test", "other"]:
                for i in range(5):
                    backup_file = backup_dir / f"{db_name}.backup.2024010{i}_120000.sqlite"
                    backup_file.touch()
            
            # Cleanup only "app" backups
            _cleanup_old_backups(backup_dir, "app", 2)
            
            # Check "app" backups were reduced to 2
            app_backups = list(backup_dir.glob("app.backup.*.sqlite"))
            assert len(app_backups) == 2
            
            # Check other database backups are untouched
            test_backups = list(backup_dir.glob("test.backup.*.sqlite"))
            other_backups = list(backup_dir.glob("other.backup.*.sqlite"))
            assert len(test_backups) == 5
            assert len(other_backups) == 5

    def test_cleanup_old_backups_zero_retention(self):
        """Test cleanup with zero retention (remove all backups)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            
            # Create multiple backup files
            for i in range(5):
                backup_file = backup_dir / f"app.backup.2024010{i}_120000.sqlite"
                backup_file.touch()
            
            # Set retention to 0
            _cleanup_old_backups(backup_dir, "app", 0)
            
            # All files should be removed
            remaining_files = list(backup_dir.glob("app.backup.*.sqlite"))
            assert len(remaining_files) == 0


class TestMigrateWithBackup:
    """Test migration function with backup integration."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.migrations_dir = Path(self.temp_dir) / "migrations"
        self.migrations_dir.mkdir()
        
        # Create test migration files
        migration1 = self.migrations_dir / "001_create_users.sql"
        migration1.write_text("-- Create users table\nCREATE TABLE users (id INTEGER PRIMARY KEY);")
        
        migration2 = self.migrations_dir / "002_add_email.sql"
        migration2.write_text("-- Add email column\nALTER TABLE users ADD COLUMN email TEXT;")

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch('app.utils.migrate.APP_DB_PATH')
    def test_migrate_with_backup_enabled(self, mock_db_path):
        """Test migration with backup creation enabled."""
        # Setup mock database path
        db_path = Path(self.temp_dir) / "app.db"
        mock_db_path.__str__ = lambda: str(db_path)
        mock_db_path.exists.return_value = True
        mock_db_path.parent = db_path.parent
        mock_db_path.stem = db_path.stem
        
        # Create actual database file
        db_path.touch()
        
        with patch('app.utils.migrate._get_conn') as mock_conn, \
             patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'):
            
            # Mock database connection
            mock_conn.return_value.__enter__ = lambda x: MagicMock()
            mock_conn.return_value.__exit__ = lambda x, *args: None
            
            # Run migration with backup
            result = migrate(str(self.migrations_dir), backup=True, backup_retention=3)
            
            # Verify backup was created
            backup_files = list(db_path.parent.glob("app.backup.*.sqlite"))
            assert len(backup_files) == 1
            
            backup_file = backup_files[0]
            assert backup_file.name.startswith("app.backup.")
            assert backup_file.name.endswith(".sqlite")

    @patch('app.utils.migrate.APP_DB_PATH')
    def test_migrate_without_backup(self, mock_db_path):
        """Test migration without backup creation."""
        # Setup mock database path
        db_path = Path(self.temp_dir) / "app.db"
        mock_db_path.__str__ = lambda: str(db_path)
        mock_db_path.exists.return_value = True
        mock_db_path.parent = db_path.parent
        
        # Create actual database file
        db_path.touch()
        
        with patch('app.utils.migrate._get_conn') as mock_conn, \
             patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'):
            
            # Mock database connection
            mock_conn.return_value.__enter__ = lambda x: MagicMock()
            mock_conn.return_value.__exit__ = lambda x, *args: None
            
            # Run migration without backup
            result = migrate(str(self.migrations_dir), backup=False)
            
            # Verify no backup was created
            backup_files = list(db_path.parent.glob("app.backup.*.sqlite"))
            assert len(backup_files) == 0

    @patch('app.utils.migrate.APP_DB_PATH')
    def test_migrate_backup_retention(self, mock_db_path):
        """Test that migration respects backup retention settings."""
        # Setup mock database path
        db_path = Path(self.temp_dir) / "app.db"
        mock_db_path.__str__ = lambda: str(db_path)
        mock_db_path.exists.return_value = True
        mock_db_path.parent = db_path.parent
        mock_db_path.stem = db_path.stem
        
        # Create actual database file
        db_path.touch()
        
        # Create some existing backup files
        for i in range(5):
            existing_backup = db_path.parent / f"app.backup.2024010{i}_120000.sqlite"
            existing_backup.touch()
            # Set different modification times
            timestamp = time.time() - (5 - i) * 3600
            existing_backup.touch(times=(timestamp, timestamp))
        
        with patch('app.utils.migrate._get_conn') as mock_conn, \
             patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'):
            
            # Mock database connection
            mock_conn.return_value.__enter__ = lambda x: MagicMock()
            mock_conn.return_value.__exit__ = lambda x, *args: None
            
            # Run migration with backup retention of 3
            result = migrate(str(self.migrations_dir), backup=True, backup_retention=3)
            
            # Verify only 3 backup files remain (2 old + 1 new)
            backup_files = list(db_path.parent.glob("app.backup.*.sqlite"))
            assert len(backup_files) == 3

    @patch('app.utils.migrate.APP_DB_PATH')
    def test_migrate_backup_failure_stops_migration(self, mock_db_path):
        """Test that backup failure prevents migration from proceeding."""
        # Setup mock database path
        db_path = Path(self.temp_dir) / "app.db"
        mock_db_path.__str__ = lambda: str(db_path)
        mock_db_path.exists.return_value = True
        mock_db_path.parent = db_path.parent
        mock_db_path.stem = db_path.stem
        
        # Create actual database file
        db_path.touch()
        
        with patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'), \
             patch('app.utils.migrate._create_backup', side_effect=Exception("Backup failed")):
            
            # Migration should fail due to backup error
            with pytest.raises(RuntimeError, match="Backup creation failed"):
                migrate(str(self.migrations_dir), backup=True)

    def test_migrate_no_database_file_skips_backup(self):
        """Test that missing database file skips backup creation."""
        with patch('app.utils.migrate.APP_DB_PATH') as mock_db_path, \
             patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'), \
             patch('app.utils.migrate._get_conn') as mock_conn:
            
            # Setup mock to simulate no database file
            mock_db_path.exists.return_value = False
            
            # Mock database connection
            mock_conn.return_value.__enter__ = lambda x: MagicMock()
            mock_conn.return_value.__exit__ = lambda x, *args: None
            
            # Migration should proceed without backup
            result = migrate(str(self.migrations_dir), backup=True)
            
            # Should not raise any errors


