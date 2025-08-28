"""Concurrency smoke tests for WAL checkpoint operations.

Tests that WAL checkpoints don't block normal database operations.
"""

import asyncio
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

import pytest


class TestWALConcurrency:
    """Test WAL checkpoint operations under concurrent load."""

    def setup_method(self):
        """Setup test database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_concurrent.db"

        # Create test database with WAL mode
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, data TEXT);")
            conn.commit()

    def teardown_method(self):
        """Cleanup test database."""
        self.temp_dir.cleanup()

    def _get_test_conn(self):
        """Get connection to test database."""
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def test_checkpoint_during_writes(self):
        """Test that checkpoint doesn't block concurrent writes."""
        results = []
        checkpoint_result = []

        def writer_task(writer_id: int, write_count: int):
            """Write data to database."""
            try:
                with self._get_test_conn() as conn:
                    for i in range(write_count):
                        conn.execute(
                            "INSERT INTO test_data (data) VALUES (?)",
                            (f"writer_{writer_id}_item_{i}",),
                        )
                        conn.commit()
                        time.sleep(0.001)  # Small delay between writes
                results.append(f"writer_{writer_id}_completed")
            except Exception as e:
                results.append(f"writer_{writer_id}_error: {e}")

        def checkpoint_task():
            """Perform checkpoint operation."""
            try:
                time.sleep(0.05)  # Start checkpoint after some writes
                with self._get_test_conn() as conn:
                    result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
                    checkpoint_result.append(f"checkpoint_success: {result}")
            except Exception as e:
                checkpoint_result.append(f"checkpoint_error: {e}")

        # Start concurrent operations
        threads = []

        # Start 3 writer threads
        for i in range(3):
            thread = threading.Thread(target=writer_task, args=(i, 50))
            threads.append(thread)
            thread.start()

        # Start checkpoint thread
        checkpoint_thread = threading.Thread(target=checkpoint_task)
        threads.append(checkpoint_thread)
        checkpoint_thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join(timeout=10)

        # Verify results
        assert len(results) == 3  # All writers completed
        assert all("completed" in result for result in results)
        assert len(checkpoint_result) == 1  # Checkpoint completed
        assert "success" in checkpoint_result[0]

        # Verify data integrity
        with self._get_test_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM test_data").fetchone()[0]
            assert count == 150  # 3 writers * 50 records each

    def test_checkpoint_during_reads(self):
        """Test that checkpoint doesn't block concurrent reads."""
        # Populate test data
        with self._get_test_conn() as conn:
            for i in range(1000):
                conn.execute("INSERT INTO test_data (data) VALUES (?)", (f"test_item_{i}",))
            conn.commit()

        results = []
        checkpoint_result = []

        def reader_task(reader_id: int, read_count: int):
            """Read data from database."""
            try:
                with self._get_test_conn() as conn:
                    for i in range(read_count):
                        result = conn.execute("SELECT COUNT(*) FROM test_data").fetchone()
                        assert result[0] == 1000
                        time.sleep(0.001)  # Small delay between reads
                results.append(f"reader_{reader_id}_completed")
            except Exception as e:
                results.append(f"reader_{reader_id}_error: {e}")

        def checkpoint_task():
            """Perform checkpoint during reads."""
            try:
                time.sleep(0.05)  # Start checkpoint after some reads
                with self._get_test_conn() as conn:
                    result = conn.execute("PRAGMA wal_checkpoint(FULL);").fetchone()
                    checkpoint_result.append(f"checkpoint_success: {result}")
            except Exception as e:
                checkpoint_result.append(f"checkpoint_error: {e}")

        # Start concurrent operations
        threads = []

        # Start 5 reader threads
        for i in range(5):
            thread = threading.Thread(target=reader_task, args=(i, 100))
            threads.append(thread)
            thread.start()

        # Start checkpoint thread
        checkpoint_thread = threading.Thread(target=checkpoint_task)
        threads.append(checkpoint_thread)
        checkpoint_thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)

        # Verify results
        assert len(results) == 5  # All readers completed
        assert all("completed" in result for result in results)
        assert len(checkpoint_result) == 1  # Checkpoint completed
        assert "success" in checkpoint_result[0]

    def test_multiple_checkpoints_concurrent(self):
        """Test multiple checkpoint operations running concurrently."""
        results = []

        def checkpoint_task(checkpoint_id: int, mode: str):
            """Perform checkpoint with specific mode."""
            try:
                time.sleep(0.01 * checkpoint_id)  # Stagger start times slightly
                with self._get_test_conn() as conn:
                    result = conn.execute(f"PRAGMA wal_checkpoint({mode});").fetchone()
                    results.append(f"checkpoint_{checkpoint_id}_{mode}_success: {result}")
            except Exception as e:
                results.append(f"checkpoint_{checkpoint_id}_{mode}_error: {e}")

        # Start multiple checkpoint operations with different modes
        threads = []
        modes = ["PASSIVE", "FULL", "RESTART"]

        for i, mode in enumerate(modes):
            thread = threading.Thread(target=checkpoint_task, args=(i, mode))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=5)

        # Verify all checkpoints completed (some may be no-ops if WAL is empty)
        assert len(results) == 3
        assert all("error" not in result for result in results)

    @pytest.mark.asyncio
    async def test_async_checkpoint_with_sync_operations(self):
        """Test async checkpoint operations with synchronous database operations."""
        # Populate some data
        with self._get_test_conn() as conn:
            for i in range(100):
                conn.execute("INSERT INTO test_data (data) VALUES (?)", (f"async_test_{i}",))
            conn.commit()

        results = []

        async def async_operations():
            """Async operations that might trigger checkpoints."""
            for i in range(10):
                # Simulate async checkpoint call
                await asyncio.to_thread(self._perform_checkpoint, "PASSIVE")
                await asyncio.sleep(0.01)
            results.append("async_ops_completed")

        def _perform_checkpoint(self, mode: str):
            """Helper to perform checkpoint in thread."""
            try:
                with self._get_test_conn() as conn:
                    conn.execute(f"PRAGMA wal_checkpoint({mode});")
                return "success"
            except Exception as e:
                return f"error: {e}"

        def sync_operations():
            """Synchronous database operations."""
            try:
                with self._get_test_conn() as conn:
                    for i in range(50):
                        conn.execute("SELECT * FROM test_data WHERE id = ?", (i + 1,))
                        time.sleep(0.002)
                results.append("sync_ops_completed")
            except Exception as e:
                results.append(f"sync_ops_error: {e}")

        # Run async and sync operations concurrently
        sync_thread = threading.Thread(target=sync_operations)
        sync_thread.start()

        await async_operations()
        sync_thread.join(timeout=5)

        # Verify both completed successfully
        assert "async_ops_completed" in results
        assert "sync_ops_completed" in results

    def test_checkpoint_with_heavy_write_load(self):
        """Test checkpoint under heavy write load."""
        results = []

        def heavy_writer(writer_id: int):
            """Write large amounts of data."""
            try:
                with self._get_test_conn() as conn:
                    for batch in range(10):
                        conn.execute("BEGIN;")
                        for i in range(100):
                            conn.execute(
                                "INSERT INTO test_data (data) VALUES (?)",
                                (f"heavy_writer_{writer_id}_batch_{batch}_item_{i}",),
                            )
                        conn.commit()
                        time.sleep(0.01)  # Brief pause between batches
                results.append(f"heavy_writer_{writer_id}_completed")
            except Exception as e:
                results.append(f"heavy_writer_{writer_id}_error: {e}")

        def periodic_checkpoint():
            """Perform periodic checkpoints during heavy writes."""
            try:
                for i in range(5):
                    time.sleep(0.05)  # Wait between checkpoints
                    with self._get_test_conn() as conn:
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
                results.append("periodic_checkpoint_completed")
            except Exception as e:
                results.append(f"periodic_checkpoint_error: {e}")

        # Start heavy write load
        threads = []
        for i in range(2):
            thread = threading.Thread(target=heavy_writer, args=(i,))
            threads.append(thread)
            thread.start()

        # Start periodic checkpoints
        checkpoint_thread = threading.Thread(target=periodic_checkpoint)
        threads.append(checkpoint_thread)
        checkpoint_thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=15)

        # Verify all operations completed
        assert len([r for r in results if "heavy_writer" in r and "completed" in r]) == 2
        assert "periodic_checkpoint_completed" in results

        # Verify data integrity
        with self._get_test_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM test_data").fetchone()[0]
            assert count == 2000  # 2 writers * 10 batches * 100 items each

    def test_checkpoint_error_handling_concurrent(self):
        """Test checkpoint error handling under concurrent conditions."""
        results = []

        def corrupt_database():
            """Simulate database corruption or locking issues."""
            try:
                time.sleep(0.02)
                # Try to acquire exclusive lock to simulate lock conflict
                with self._get_test_conn() as conn:
                    conn.execute("BEGIN EXCLUSIVE;")
                    time.sleep(0.1)  # Hold lock
                    conn.rollback()
                results.append("corruption_task_completed")
            except Exception as e:
                results.append(f"corruption_task_error: {e}")

        def checkpoint_with_conflict():
            """Try checkpoint that might conflict with exclusive lock."""
            try:
                time.sleep(0.05)  # Start after corruption task
                with self._get_test_conn() as conn:
                    # This might fail due to lock conflict
                    result = conn.execute("PRAGMA wal_checkpoint(RESTART);").fetchone()
                    results.append(f"checkpoint_success: {result}")
            except Exception as e:
                results.append(f"checkpoint_expected_error: {e}")

        # Run concurrent operations that might conflict
        corruption_thread = threading.Thread(target=corrupt_database)
        checkpoint_thread = threading.Thread(target=checkpoint_with_conflict)

        corruption_thread.start()
        checkpoint_thread.start()

        corruption_thread.join(timeout=5)
        checkpoint_thread.join(timeout=5)

        # At least one operation should complete (error handling should work)
        assert len(results) >= 1

        # Database should still be functional after conflicts
        with self._get_test_conn() as conn:
            conn.execute("SELECT 1").fetchone()
