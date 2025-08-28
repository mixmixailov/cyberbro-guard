"""Tests for queue operations CLI and SQL helpers."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.db.ops import (
    count_unreplayed_dlq_by_type,
    get_dlq_item_by_id,
    get_dlq_items_with_details,
    get_dlq_stats_summary,
    get_oldest_newest_dlq_items,
    get_operational_summary,
    get_queue_stats,
    get_recent_dlq_errors,
    get_send_queue_info,
)
from app.services.dlq import DLQService


@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    
    # Patch the database path
    with patch("app.db.session.APP_DB_PATH", db_path):
        # Initialize test database with DLQ table
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dlq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                error TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
                last_attempt_at TEXT,
                replayed_at TEXT,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        yield db_path
        
    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def sample_dlq_data(temp_db):
    """Insert sample DLQ data for testing."""
    conn = sqlite3.connect(temp_db)
    
    # Sample DLQ items
    sample_items = [
        {
            "job_id": "update_12345",
            "type": "update",
            "payload": json.dumps({"update_id": 12345, "message": {"text": "test"}}),
            "error": "NetworkError: Connection timeout",
            "attempts": 3,
            "created_at": "2024-01-15T10:00:00Z",
            "last_attempt_at": "2024-01-15T10:05:00Z",
            "replayed_at": None,
            "metadata": json.dumps({"chat_id": 123, "user_id": 456}),
        },
        {
            "job_id": "job_payment_456",
            "type": "scheduled_job",
            "payload": json.dumps({"job_name": "payment_check", "user_id": 789}),
            "error": "ValueError: Invalid payment status",
            "attempts": 2,
            "created_at": "2024-01-15T11:00:00Z",
            "last_attempt_at": "2024-01-15T11:02:00Z",
            "replayed_at": "2024-01-15T12:00:00Z",
            "metadata": json.dumps({"job_name": "payment_check"}),
        },
        {
            "job_id": "update_67890",
            "type": "update",
            "payload": json.dumps({"update_id": 67890, "callback_query": {"data": "test"}}),
            "error": "RetryAfter: Rate limited for 30 seconds",
            "attempts": 1,
            "created_at": "2024-01-15T12:00:00Z",
            "last_attempt_at": None,
            "replayed_at": None,
            "metadata": json.dumps({"chat_id": 789, "user_id": 123}),
        },
    ]
    
    for item in sample_items:
        conn.execute("""
            INSERT INTO dlq (job_id, type, payload, error, attempts, created_at, last_attempt_at, replayed_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["job_id"],
            item["type"],
            item["payload"],
            item["error"],
            item["attempts"],
            item["created_at"],
            item["last_attempt_at"],
            item["replayed_at"],
            item["metadata"],
        ))
    
    conn.commit()
    conn.close()
    
    return sample_items


def test_get_queue_stats(sample_dlq_data):
    """Test queue statistics gathering."""
    stats = get_queue_stats()
    
    assert "dlq_by_type" in stats
    assert "overall" in stats
    assert "common_errors" in stats
    assert "timestamp" in stats
    
    # Check DLQ by type stats
    dlq_by_type = {item["type"]: item for item in stats["dlq_by_type"]}
    
    assert "update" in dlq_by_type
    assert "scheduled_job" in dlq_by_type
    
    # Update type should have 2 items (1 unreplayed)
    update_stats = dlq_by_type["update"]
    assert update_stats["total"] == 2
    assert update_stats["unreplayed"] == 2  # Both updates not replayed
    assert update_stats["replayed"] == 0
    
    # Scheduled job type should have 1 item (0 unreplayed)
    job_stats = dlq_by_type["scheduled_job"]
    assert job_stats["total"] == 1
    assert job_stats["unreplayed"] == 0
    assert job_stats["replayed"] == 1
    
    # Check overall stats
    overall = stats["overall"]
    assert overall["total_dlq_items"] == 3
    assert overall["unreplayed_total"] == 2


def test_get_dlq_items_with_details(sample_dlq_data):
    """Test DLQ items retrieval with details."""
    # Get all items
    items = get_dlq_items_with_details(limit=10, only_unreplayed=False)
    assert len(items) == 3
    
    # Check first item details
    first_item = items[0]  # Should be newest (created_at DESC)
    assert first_item["type"] == "update"
    assert first_item["job_id"] == "update_67890"
    assert isinstance(first_item["payload"], dict)
    assert first_item["update_id"] == 67890
    assert "error_summary" in first_item
    
    # Get only unreplayed items
    unreplayed_items = get_dlq_items_with_details(limit=10, only_unreplayed=True)
    assert len(unreplayed_items) == 2
    
    # Filter by type
    update_items = get_dlq_items_with_details(type_filter="update", only_unreplayed=False)
    assert len(update_items) == 2
    assert all(item["type"] == "update" for item in update_items)


def test_get_dlq_item_by_id(sample_dlq_data):
    """Test retrieving specific DLQ item by ID."""
    # Get first item ID from the test data
    items = get_dlq_items_with_details(limit=1)
    item_id = items[0]["id"]
    
    # Retrieve specific item
    item = get_dlq_item_by_id(item_id)
    assert item is not None
    assert item["id"] == item_id
    assert isinstance(item["payload"], dict)
    assert isinstance(item["metadata"], dict)
    
    # Test non-existent item
    non_existent = get_dlq_item_by_id(99999)
    assert non_existent is None


def test_get_dlq_stats_summary(sample_dlq_data):
    """Test DLQ statistics summary."""
    summary = get_dlq_stats_summary()
    
    assert summary["total_items"] == 3
    assert summary["unreplayed"] == 2
    assert summary["replayed"] == 1
    assert summary["unique_types"] == 2
    assert summary["oldest_item"] is not None
    assert summary["newest_item"] is not None


def test_get_oldest_newest_dlq_items(sample_dlq_data):
    """Test getting oldest and newest DLQ items."""
    oldest, newest = get_oldest_newest_dlq_items()
    
    assert oldest is not None
    assert newest is not None
    assert oldest["job_id"] == "update_12345"  # From 10:00:00
    assert newest["job_id"] == "update_67890"  # From 12:00:00
    
    # Test with type filter
    oldest_update, newest_update = get_oldest_newest_dlq_items(type_filter="update")
    assert oldest_update["type"] == "update"
    assert newest_update["type"] == "update"


def test_count_unreplayed_dlq_by_type(sample_dlq_data):
    """Test counting unreplayed DLQ items by type."""
    counts = count_unreplayed_dlq_by_type()
    
    # Should have update type with 2 unreplayed items
    update_count = next((item for item in counts if item["type"] == "update"), None)
    assert update_count is not None
    assert update_count["unreplayed_count"] == 2
    
    # Scheduled job should not appear (all replayed)
    job_count = next((item for item in counts if item["type"] == "scheduled_job"), None)
    assert job_count is None


def test_get_recent_dlq_errors(sample_dlq_data):
    """Test getting recent DLQ errors."""
    errors = get_recent_dlq_errors(limit=5)
    
    assert len(errors) == 2  # Only unreplayed items
    
    # Check error summaries
    error_summaries = [error["error_summary"] for error in errors]
    assert "RetryAfter: Rate limited for 30 seconds" in error_summaries
    assert "NetworkError: Connection timeout" in error_summaries


def test_get_send_queue_info():
    """Test send queue information retrieval."""
    info = get_send_queue_info()
    
    assert info["type"] == "in_memory_asyncio_queue"
    assert info["max_size"] == 2000
    assert "rate_limits" in info
    assert "backoff_config" in info
    assert "retry_config" in info
    assert info["retry_config"]["max_attempts"] == 5


def test_get_operational_summary(sample_dlq_data):
    """Test comprehensive operational summary."""
    summary = get_operational_summary()
    
    assert "dlq" in summary
    assert "unreplayed_by_type" in summary
    assert "recent_errors" in summary
    assert "send_queue" in summary
    assert "timestamp" in summary
    
    # Check DLQ summary
    dlq_summary = summary["dlq"]
    assert dlq_summary["total_items"] == 3
    assert dlq_summary["unreplayed"] == 2
    
    # Check unreplayed by type
    assert len(summary["unreplayed_by_type"]) == 1  # Only update type has unreplayed
    
    # Check recent errors
    assert len(summary["recent_errors"]) == 2


def test_dlq_service_integration(sample_dlq_data):
    """Test integration with DLQService."""
    # Get an unreplayed item
    items = get_dlq_items_with_details(only_unreplayed=True, limit=1)
    assert len(items) > 0
    
    item = items[0]
    item_id = item["id"]
    
    # Test marking as replayed
    success = DLQService.mark_replayed(item_id)
    assert success
    
    # Verify it's marked as replayed
    updated_item = get_dlq_item_by_id(item_id)
    assert updated_item["replayed_at"] is not None
    
    # Test marking already replayed item
    success_again = DLQService.mark_replayed(item_id)
    assert not success_again  # Should return False for already replayed


def test_empty_dlq():
    """Test operations with empty DLQ."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    
    with patch("app.db.session.APP_DB_PATH", db_path):
        # Initialize empty database
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dlq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                error TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
                last_attempt_at TEXT,
                replayed_at TEXT,
                metadata TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        # Test with empty DLQ
        stats = get_queue_stats()
        assert stats["overall"]["total_dlq_items"] == 0
        
        items = get_dlq_items_with_details()
        assert len(items) == 0
        
        summary = get_dlq_stats_summary()
        assert summary["total_items"] == 0
        
        counts = count_unreplayed_dlq_by_type()
        assert len(counts) == 0
        
        errors = get_recent_dlq_errors()
        assert len(errors) == 0
        
        oldest, newest = get_oldest_newest_dlq_items()
        assert oldest is None
        assert newest is None
        
    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.mark.integration
def test_cli_module_import():
    """Test that CLI module can be imported successfully."""
    try:
        from app.ops.queue import main, cmd_stats, cmd_dlq_list, cmd_dlq_details, cmd_dlq_replay
        assert callable(main)
        assert callable(cmd_stats)
        assert callable(cmd_dlq_list)
        assert callable(cmd_dlq_details)
        assert callable(cmd_dlq_replay)
    except ImportError as e:
        pytest.fail(f"Failed to import CLI module: {e}")


if __name__ == "__main__":
    # Self-check instructions
    print("🧪 Running queue operations tests...")
    print("Expected behavior:")
    print("- All SQL helper functions should work with sample data")
    print("- DLQ items should be retrievable and filterable")
    print("- Statistics should be calculated correctly")
    print("- Empty database should be handled gracefully")
    print("- DLQService integration should work")
    
    # Quick smoke test
    import tempfile
    import sqlite3
    from pathlib import Path
    
    print("\n📊 Quick ops test:")
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    
    with patch("app.db.session.APP_DB_PATH", db_path):
        # Setup test data
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dlq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                error TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
                last_attempt_at TEXT,
                replayed_at TEXT,
                metadata TEXT
            )
        """)
        
        # Insert test item
        conn.execute("""
            INSERT INTO dlq (job_id, type, payload, error, attempts)
            VALUES ('test_job', 'update', '{"test": true}', 'Test error', 1)
        """)
        conn.commit()
        conn.close()
        
        # Test operations
        stats = get_queue_stats()
        print(f"Total DLQ items: {stats['overall']['total_dlq_items']}")
        
        items = get_dlq_items_with_details(limit=5)
        print(f"Retrieved {len(items)} DLQ items")
        
        summary = get_operational_summary()
        print(f"Operational summary keys: {list(summary.keys())}")
    
    # Cleanup
    db_path.unlink(missing_ok=True)
    
    print("✅ Queue ops smoke test completed")
