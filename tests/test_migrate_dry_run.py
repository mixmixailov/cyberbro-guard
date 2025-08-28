"""Unit tests for migration dry-run functionality."""
import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.utils.migrate import migrate, _apply_sql_files, _get_migration_description


class TestDryRunFunctionality:
    """Test dry-run migration functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.migrations_dir = Path(self.temp_dir) / "migrations"
        self.migrations_dir.mkdir()
        
        # Create test migration files with descriptions
        migration1 = self.migrations_dir / "001_create_users.sql"
        migration1.write_text("""-- Create users table with basic fields
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE
);""")
        
        migration2 = self.migrations_dir / "002_add_timestamps.sql"
        migration2.write_text("""-- Add timestamp fields to users table
ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE users ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP;""")
        
        migration3 = self.migrations_dir / "003_create_posts.sql"
        migration3.write_text("""-- Create posts table with foreign key
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);""")

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_dry_run_no_database_changes(self):
        """Test that dry-run mode doesn't modify the database."""
        # Create test database
        db_path = Path(self.temp_dir) / "test.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE existing_table (id INTEGER)")
            conn.execute("INSERT INTO existing_table VALUES (1)")
            conn.commit()
        
        # Get initial database state
        with sqlite3.connect(db_path) as conn:
            initial_tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            initial_data = conn.execute("SELECT * FROM existing_table").fetchall()
        
        with patch('app.utils.migrate.APP_DB_PATH', db_path), \
             patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'):
            
            # Run migration in dry-run mode
            result = migrate(str(self.migrations_dir), dry_run=True)
            
            # Verify return value indicates migrations that would be applied
            assert result == 3  # 3 migration files would be applied
        
        # Verify database state is unchanged
        with sqlite3.connect(db_path) as conn:
            final_tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            final_data = conn.execute("SELECT * FROM existing_table").fetchall()
        
        assert initial_tables == final_tables
        assert initial_data == final_data

    def test_dry_run_shows_migration_plan(self, caplog):
        """Test that dry-run mode shows the migration plan with descriptions."""
        with patch('app.utils.migrate.APP_DB_PATH'), \
             patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'):
            
            # Run migration in dry-run mode
            result = migrate(str(self.migrations_dir), dry_run=True)
            
            # Check that migration plan was logged
            log_messages = [record.message for record in caplog.records]
            
            # Should show found migrations
            assert any("Found 3 pending migrations" in msg for msg in log_messages)
            
            # Should show each migration with description
            assert any("001_create_users - Create users table with basic fields" in msg for msg in log_messages)
            assert any("002_add_timestamps - Add timestamp fields to users table" in msg for msg in log_messages)
            assert any("003_create_posts - Create posts table with foreign key" in msg for msg in log_messages)
            
            # Should show dry-run completion
            assert any("DRY RUN: Would apply 3 migrations (no changes made)" in msg for msg in log_messages)

    def test_dry_run_with_no_pending_migrations(self, caplog):
        """Test dry-run when no migrations are pending."""
        with patch('app.utils.migrate.APP_DB_PATH'), \
             patch('app.utils.migrate._current_version', return_value=999), \
             patch('app.utils.migrate._ensure_version_table'):
            
            # Run migration in dry-run mode
            result = migrate(str(self.migrations_dir), dry_run=True)
            
            # Should return 0 for no migrations
            assert result == 0
            
            # Should log no migrations to apply
            log_messages = [record.message for record in caplog.records]
            assert any("No migrations to apply" in msg for msg in log_messages)

    def test_dry_run_with_partial_migrations_applied(self, caplog):
        """Test dry-run when some migrations are already applied."""
        with patch('app.utils.migrate.APP_DB_PATH'), \
             patch('app.utils.migrate._current_version', return_value=1), \
             patch('app.utils.migrate._ensure_version_table'):
            
            # Run migration in dry-run mode (only migrations > version 1 should be shown)
            result = migrate(str(self.migrations_dir), dry_run=True)
            
            # Should return 2 (migrations 002 and 003)
            assert result == 2
            
            # Check that only pending migrations are shown
            log_messages = [record.message for record in caplog.records]
            assert any("Found 2 pending migrations" in msg for msg in log_messages)
            assert any("002_add_timestamps" in msg for msg in log_messages)
            assert any("003_create_posts" in msg for msg in log_messages)
            assert not any("001_create_users" in msg for msg in log_messages)


class TestMigrationDescriptionExtraction:
    """Test migration description extraction functionality."""

    def test_get_migration_description_with_comment(self):
        """Test description extraction from files with comment."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("-- This is a test migration\nCREATE TABLE test (id INTEGER);")
            f.flush()
            
            description = _get_migration_description(Path(f.name))
            assert description == "This is a test migration"

    def test_get_migration_description_without_comment(self):
        """Test description extraction from files without comment."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("CREATE TABLE test (id INTEGER);")
            f.flush()
            
            description = _get_migration_description(Path(f.name))
            assert description == "No description"

    def test_get_migration_description_empty_comment(self):
        """Test description extraction from files with empty comment."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("--\nCREATE TABLE test (id INTEGER);")
            f.flush()
            
            description = _get_migration_description(Path(f.name))
            assert description == ""

    def test_get_migration_description_multiline_comment(self):
        """Test description extraction only gets first line."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write("""-- First line description
-- Second line comment
CREATE TABLE test (id INTEGER);""")
            f.flush()
            
            description = _get_migration_description(Path(f.name))
            assert description == "First line description"

    def test_get_migration_description_file_error(self):
        """Test description extraction handles file read errors."""
        # Test with non-existent file
        description = _get_migration_description(Path("/nonexistent/file.sql"))
        assert description == "No description"


class TestApplySqlFilesDryRun:
    """Test the _apply_sql_files function in dry-run mode."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_apply_sql_files_dry_run_no_execution(self, caplog):
        """Test that _apply_sql_files in dry-run mode doesn't execute SQL."""
        # Create test migration files
        migrations_dir = Path(self.temp_dir) / "migrations"
        migrations_dir.mkdir()
        
        migration1 = migrations_dir / "001_test.sql"
        migration1.write_text("-- Test migration\nCREATE TABLE test (id INTEGER);")
        
        migration2 = migrations_dir / "002_test.sql"
        migration2.write_text("-- Another test\nINSERT INTO test VALUES (1);")
        
        files = [migration1, migration2]
        
        # Mock database connection to track calls
        mock_conn = MagicMock()
        
        with patch('app.utils.migrate._get_conn') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            mock_get_conn.return_value.__exit__.return_value = None
            
            # Run in dry-run mode
            result = _apply_sql_files(files, dry_run=True)
            
            # Should return 0 (no files actually applied)
            assert result == 0
            
            # Database connection should not be used for execution
            mock_conn.execute.assert_not_called()
            mock_conn.executescript.assert_not_called()
            mock_conn.commit.assert_not_called()
            
            # Should log what would be applied
            log_messages = [record.message for record in caplog.records]
            assert any("Would apply migration: 001_test - Test migration" in msg for msg in log_messages)
            assert any("Would apply migration: 002_test - Another test" in msg for msg in log_messages)

    def test_apply_sql_files_normal_mode_executes(self):
        """Test that _apply_sql_files in normal mode executes SQL."""
        # Create test migration files
        migrations_dir = Path(self.temp_dir) / "migrations"
        migrations_dir.mkdir()
        
        migration1 = migrations_dir / "001_test.sql"
        migration1.write_text("-- Test migration\nCREATE TABLE test (id INTEGER);")
        
        files = [migration1]
        
        # Mock database connection
        mock_conn = MagicMock()
        
        with patch('app.utils.migrate._get_conn') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            mock_get_conn.return_value.__exit__.return_value = None
            
            # Run in normal mode
            result = _apply_sql_files(files, dry_run=False)
            
            # Should return 1 (one file applied)
            assert result == 1
            
            # Database operations should be called
            mock_conn.execute.assert_called()
            mock_conn.executescript.assert_called()
            mock_conn.commit.assert_called()

    def test_apply_sql_files_dry_run_with_empty_list(self):
        """Test dry-run with empty file list."""
        result = _apply_sql_files([], dry_run=True)
        assert result == 0


class TestDryRunCLI:
    """Test CLI integration for dry-run functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.migrations_dir = Path(self.temp_dir) / "migrations"
        self.migrations_dir.mkdir()
        
        # Create test migration
        migration = self.migrations_dir / "001_test.sql"
        migration.write_text("-- CLI test migration\nCREATE TABLE cli_test (id INTEGER);")

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_cli_dry_run_flag(self, caplog):
        """Test CLI with --dry-run flag."""
        from app.utils.migrate import main
        
        # Mock command line arguments
        test_args = [
            "migrate",
            "--dir", str(self.migrations_dir),
            "--dry-run"
        ]
        
        with patch('sys.argv', test_args), \
             patch('app.utils.migrate.APP_DB_PATH'), \
             patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'):
            
            result = main()
            
            # Should return 0 (success)
            assert result == 0
            
            # Should log dry-run messages
            log_messages = [record.message for record in caplog.records]
            assert any("Starting migration dry-run..." in msg for msg in log_messages)
            assert any("Dry-run completed: would apply 1 migration(s)" in msg for msg in log_messages)

    def test_cli_without_dry_run_flag(self, caplog):
        """Test CLI without --dry-run flag."""
        from app.utils.migrate import main
        
        # Mock command line arguments
        test_args = [
            "migrate",
            "--dir", str(self.migrations_dir)
        ]
        
        with patch('sys.argv', test_args), \
             patch('app.utils.migrate.APP_DB_PATH'), \
             patch('app.utils.migrate._current_version', return_value=0), \
             patch('app.utils.migrate._ensure_version_table'), \
             patch('app.utils.migrate._get_conn') as mock_conn:
            
            # Mock database connection
            mock_conn.return_value.__enter__ = lambda x: MagicMock()
            mock_conn.return_value.__exit__ = lambda x, *args: None
            
            result = main()
            
            # Should return 0 (success)
            assert result == 0
            
            # Should log normal migration messages
            log_messages = [record.message for record in caplog.records]
            assert any("Starting migration..." in msg for msg in log_messages)
            assert any("Migration completed: applied 1 migration(s)" in msg for msg in log_messages)


