"""Smoke test for BEGIN IMMEDIATE functionality with concurrent writes."""

import sqlite3
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from app.db.session import _get_conn, execute, execute_immediate


class TestBeginImmediateSmoke:
    """Test BEGIN IMMEDIATE prevents database locked errors."""

    @pytest.fixture(scope="function")
    def temp_db_path(self, monkeypatch):
        """Create temporary database for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            # Monkeypatch the database path
            monkeypatch.setattr("app.db.session.APP_DB_PATH", db_path)
            yield db_path

    def test_regular_connection_properties(self, temp_db_path):
        """Test that regular connections have correct properties."""
        conn = _get_conn()

        # Check WAL mode is enabled
        result = conn.execute("PRAGMA journal_mode;").fetchone()
        assert result[0].upper() == "WAL"

        # Check foreign keys are enabled
        result = conn.execute("PRAGMA foreign_keys;").fetchone()
        assert result[0] == 1

        # Check busy timeout is set
        result = conn.execute("PRAGMA busy_timeout;").fetchone()
        assert result[0] == 5000

        conn.close()

    def test_immediate_connection_starts_transaction(self, temp_db_path):
        """Test that immediate=True starts a transaction."""
        # Create test table first
        with _get_conn() as conn:
            conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT);")
            conn.commit()

        # Test immediate connection
        conn = _get_conn(immediate=True)

        # Insert data (should be in transaction)
        conn.execute("INSERT INTO test_table (value) VALUES (?);", ("test",))

        # Check data is not visible from another connection (still in transaction)
        with _get_conn() as other_conn:
            result = other_conn.execute("SELECT COUNT(*) FROM test_table;").fetchone()
            assert result[0] == 0  # Should be 0 because transaction not committed

        # Commit and check data is now visible
        conn.commit()
        conn.close()

        with _get_conn() as other_conn:
            result = other_conn.execute("SELECT COUNT(*) FROM test_table;").fetchone()
            assert result[0] == 1  # Should be 1 after commit

    def test_concurrent_writes_without_immediate(self, temp_db_path):
        """Test concurrent writes without BEGIN IMMEDIATE may cause database locked errors."""
        # Create test table
        with _get_conn() as conn:
            conn.execute(
                "CREATE TABLE concurrent_test (id INTEGER PRIMARY KEY, thread_id INTEGER);"
            )
            conn.commit()

        errors = []
        successful_writes = []

        def write_worker(thread_id: int, num_writes: int):
            """Worker function that performs writes."""
            for i in range(num_writes):
                try:
                    # Use regular execute (no immediate transaction)
                    execute("INSERT INTO concurrent_test (thread_id) VALUES (?);", (thread_id,))
                    successful_writes.append((thread_id, i))
                    time.sleep(0.001)  # Small delay to increase contention
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        errors.append(f"Thread {thread_id}: {e}")
                    else:
                        raise

        # Run concurrent writers
        num_threads = 5
        writes_per_thread = 10

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(write_worker, thread_id, writes_per_thread)
                for thread_id in range(num_threads)
            ]

            for future in as_completed(futures):
                future.result()  # Wait for completion, will raise if worker failed

        print(f"Regular writes: {len(successful_writes)} successful, {len(errors)} errors")

        # Note: This test might not always generate errors due to SQLite's robustness
        # but documents the potential for database locked errors

    def test_concurrent_writes_with_immediate(self, temp_db_path):
        """Test concurrent writes with BEGIN IMMEDIATE should prevent database locked errors."""
        # Create test table
        with _get_conn() as conn:
            conn.execute("CREATE TABLE immediate_test (id INTEGER PRIMARY KEY, thread_id INTEGER);")
            conn.commit()

        errors = []
        successful_writes = []

        def immediate_write_worker(thread_id: int, num_writes: int):
            """Worker function that performs immediate writes."""
            for i in range(num_writes):
                try:
                    # Use execute_immediate for critical writes
                    execute_immediate(
                        "INSERT INTO immediate_test (thread_id) VALUES (?);", (thread_id,)
                    )
                    successful_writes.append((thread_id, i))
                    time.sleep(0.001)  # Small delay to increase contention
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        errors.append(f"Thread {thread_id}: {e}")
                    else:
                        raise

        # Run concurrent writers with immediate transactions
        num_threads = 5
        writes_per_thread = 10

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(immediate_write_worker, thread_id, writes_per_thread)
                for thread_id in range(num_threads)
            ]

            for future in as_completed(futures):
                future.result()  # Wait for completion

        print(f"Immediate writes: {len(successful_writes)} successful, {len(errors)} errors")

        # With BEGIN IMMEDIATE, we should have fewer (ideally zero) database locked errors
        assert len(errors) == 0, f"Expected no 'database is locked' errors, got: {errors}"
        assert len(successful_writes) == num_threads * writes_per_thread

        # Verify all data was written correctly
        with _get_conn() as conn:
            result = conn.execute("SELECT COUNT(*) FROM immediate_test;").fetchone()
            assert result[0] == num_threads * writes_per_thread

    def test_immediate_transaction_rollback_on_error(self, temp_db_path):
        """Test that immediate transactions rollback on errors."""
        # Create test table with constraint
        with _get_conn() as conn:
            conn.execute("""
                CREATE TABLE constraint_test (
                    id INTEGER PRIMARY KEY,
                    unique_value TEXT UNIQUE NOT NULL
                );
            """)
            conn.commit()

        # Insert initial data
        execute_immediate("INSERT INTO constraint_test (unique_value) VALUES (?);", ("initial",))

        # Try to insert duplicate (should fail and rollback)
        with pytest.raises(sqlite3.IntegrityError):
            execute_immediate(
                "INSERT INTO constraint_test (unique_value) VALUES (?);", ("initial",)
            )

        # Verify database is in consistent state
        with _get_conn() as conn:
            result = conn.execute("SELECT COUNT(*) FROM constraint_test;").fetchone()
            assert result[0] == 1  # Only the first insert should remain

    def test_mixed_read_write_concurrency(self, temp_db_path):
        """Test mixed read and write operations with immediate transactions."""
        # Create test table
        with _get_conn() as conn:
            conn.execute("CREATE TABLE mixed_test (id INTEGER PRIMARY KEY, value INTEGER);")
            # Insert initial data
            for i in range(10):
                conn.execute("INSERT INTO mixed_test (value) VALUES (?);", (i,))
            conn.commit()

        results = []
        errors = []

        def reader_worker(worker_id: int):
            """Worker that performs read operations."""
            try:
                for _ in range(20):
                    with _get_conn() as conn:
                        result = conn.execute("SELECT COUNT(*) FROM mixed_test;").fetchone()
                        results.append(f"Reader {worker_id}: count={result[0]}")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(f"Reader {worker_id}: {e}")

        def writer_worker(worker_id: int):
            """Worker that performs write operations."""
            try:
                for i in range(5):
                    execute_immediate(
                        "INSERT INTO mixed_test (value) VALUES (?);", (worker_id * 100 + i,)
                    )
                    time.sleep(0.002)
            except Exception as e:
                errors.append(f"Writer {worker_id}: {e}")

        # Run mixed workload
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []

            # Start 3 readers
            for i in range(3):
                futures.append(executor.submit(reader_worker, i))

            # Start 3 writers
            for i in range(3):
                futures.append(executor.submit(writer_worker, i))

            for future in as_completed(futures):
                future.result()

        print(f"Mixed workload: {len(results)} reads, {len(errors)} errors")
        assert len(errors) == 0, f"Expected no errors in mixed workload: {errors}"

        # Verify final state
        with _get_conn() as conn:
            result = conn.execute("SELECT COUNT(*) FROM mixed_test;").fetchone()
            assert result[0] == 25  # 10 initial + 15 from writers (3 writers × 5 inserts)


if __name__ == "__main__":
    # Run smoke test standalone
    pytest.main([__file__, "-v", "-s"])
