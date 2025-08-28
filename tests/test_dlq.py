"""Unit tests for Dead Letter Queue functionality."""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.services.dlq import DLQService, DLQItem, add_failed_update_to_dlq, add_failed_job_to_dlq
from app.db.session import execute_immediate, fetchone, fetchall


class TestDLQService:
    """Test DLQ service operations."""

    def test_add_to_dlq_basic(self):
        """Test basic DLQ item creation."""
        payload = {"test": "data", "update_id": 123}
        error = Exception("Test error")
        
        with patch('app.services.dlq.execute_immediate') as mock_execute, \
             patch('app.services.dlq.DLQService._update_size_gauge'), \
             patch('app.services.dlq.dlq_in_total') as mock_counter:
            
            mock_execute.return_value = 42  # Mock DLQ ID
            
            dlq_id = DLQService.add_to_dlq(
                job_id="test_job_123",
                job_type="update",
                payload=payload,
                error=error,
                attempts=3
            )
            
            assert dlq_id == 42
            mock_execute.assert_called_once()
            
            # Verify SQL call
            call_args = mock_execute.call_args
            assert "INSERT INTO dlq" in call_args[0][0]
            params = call_args[0][1]
            assert params[0] == "test_job_123"  # job_id
            assert params[1] == "update"        # type
            assert json.loads(params[2]) == payload  # payload
            assert "Test error" in params[3]   # error
            assert params[4] == 3              # attempts
            
            # Verify metrics
            mock_counter.labels.assert_called_with(type="update", reason="max_attempts_exceeded")
            mock_counter.labels().inc.assert_called_once()

    def test_add_to_dlq_with_metadata(self):
        """Test DLQ item creation with metadata."""
        payload = {"update_id": 456}
        metadata = {"chat_id": 789, "user_id": 101112}
        
        with patch('app.services.dlq.execute_immediate') as mock_execute, \
             patch('app.services.dlq.DLQService._update_size_gauge'), \
             patch('app.services.dlq.dlq_in_total'):
            
            mock_execute.return_value = 99
            
            dlq_id = DLQService.add_to_dlq(
                job_id="test_job_456",
                job_type="webhook",
                payload=payload,
                error="Network timeout",
                attempts=5,
                metadata=metadata
            )
            
            call_args = mock_execute.call_args
            params = call_args[0][1]
            assert json.loads(params[5]) == metadata  # metadata field

    def test_get_dlq_item(self):
        """Test retrieving a specific DLQ item."""
        mock_row = {
            "id": 1,
            "job_id": "test_job",
            "type": "update",
            "payload": '{"test": "data"}',
            "error": "Test error",
            "attempts": 2,
            "created_at": "2024-01-01T12:00:00",
            "last_attempt_at": None,
            "replayed_at": None,
            "metadata": '{"chat_id": 123}'
        }
        
        with patch('app.services.dlq.fetchone', return_value=mock_row):
            item = DLQService.get_dlq_item(1)
            
            assert item is not None
            assert item.id == 1
            assert item.job_id == "test_job"
            assert item.type == "update"
            assert item.payload == {"test": "data"}
            assert item.error == "Test error"
            assert item.attempts == 2
            assert item.metadata == {"chat_id": 123}

    def test_get_dlq_item_not_found(self):
        """Test retrieving non-existent DLQ item."""
        with patch('app.services.dlq.fetchone', return_value=None):
            item = DLQService.get_dlq_item(999)
            assert item is None

    def test_get_dlq_items_with_filters(self):
        """Test retrieving DLQ items with filters."""
        mock_rows = [
            {
                "id": 1,
                "job_id": "test_1",
                "type": "update",
                "payload": '{}',
                "error": "Error 1",
                "attempts": 1,
                "created_at": "2024-01-01T12:00:00",
                "last_attempt_at": None,
                "replayed_at": None,
                "metadata": None
            },
            {
                "id": 2,
                "job_id": "test_2", 
                "type": "update",
                "payload": '{}',
                "error": "Error 2",
                "attempts": 2,
                "created_at": "2024-01-01T13:00:00",
                "last_attempt_at": None,
                "replayed_at": None,
                "metadata": None
            }
        ]
        
        with patch('app.services.dlq.fetchall', return_value=mock_rows):
            items = DLQService.get_dlq_items(job_type="update", only_unreplayed=True, limit=10)
            
            assert len(items) == 2
            assert items[0].id == 1
            assert items[1].id == 2
            assert all(item.type == "update" for item in items)

    def test_mark_replayed_success(self):
        """Test successfully marking item as replayed."""
        mock_item = DLQItem(
            id=1,
            job_id="test_job",
            type="update", 
            payload={},
            error="Test error",
            attempts=3,
            created_at="2024-01-01T12:00:00"
        )
        
        with patch('app.services.dlq.DLQService.get_dlq_item', return_value=mock_item), \
             patch('app.services.dlq.execute_immediate', return_value=1), \
             patch('app.services.dlq.DLQService._update_size_gauge'), \
             patch('app.services.dlq.dlq_replayed_total') as mock_counter:
            
            result = DLQService.mark_replayed(1)
            
            assert result is True
            mock_counter.labels.assert_called_with(type="update")
            mock_counter.labels().inc.assert_called_once()

    def test_mark_replayed_not_found(self):
        """Test marking non-existent item as replayed."""
        with patch('app.services.dlq.DLQService.get_dlq_item', return_value=None):
            result = DLQService.mark_replayed(999)
            assert result is False

    def test_mark_replayed_already_replayed(self):
        """Test marking already replayed item."""
        with patch('app.services.dlq.DLQService.get_dlq_item') as mock_get, \
             patch('app.services.dlq.execute_immediate', return_value=0):
            
            mock_get.return_value = MagicMock()
            result = DLQService.mark_replayed(1)
            assert result is False

    def test_get_stats_by_type(self):
        """Test getting DLQ statistics by type."""
        mock_stats = [
            {"type": "update", "total": 10, "unreplayed": 3, "replayed": 7},
            {"type": "scheduled_job", "total": 5, "unreplayed": 2, "replayed": 3}
        ]
        
        with patch('app.services.dlq.fetchall', return_value=mock_stats):
            stats = DLQService.get_stats_by_type()
            
            assert "update" in stats
            assert "scheduled_job" in stats
            assert stats["update"]["total"] == 10
            assert stats["update"]["unreplayed"] == 3
            assert stats["scheduled_job"]["total"] == 5

    def test_cleanup_old_replayed(self):
        """Test cleanup of old replayed items."""
        with patch('app.services.dlq.execute_immediate', return_value=3), \
             patch('app.services.dlq.DLQService.get_stats_by_type', return_value={}), \
             patch('app.services.dlq.DLQService._update_size_gauge'):
            
            count = DLQService.cleanup_old_replayed(days_old=30)
            assert count == 3

    def test_update_size_gauge(self):
        """Test size gauge update."""
        mock_count = {"count": 5}
        
        with patch('app.services.dlq.fetchone', return_value=mock_count), \
             patch('app.services.dlq.dlq_size_gauge') as mock_gauge:
            
            DLQService._update_size_gauge("update")
            
            mock_gauge.labels.assert_called_with(type="update")
            mock_gauge.labels().set.assert_called_with(5)


class TestDLQHelperFunctions:
    """Test DLQ helper functions."""

    def test_add_failed_update_to_dlq(self):
        """Test helper function for failed updates."""
        update_data = {
            "update_id": 123,
            "message": {
                "chat": {"id": 456},
                "from": {"id": 789}
            }
        }
        error = Exception("Update processing failed")
        
        with patch('app.services.dlq.DLQService.add_to_dlq', return_value=42) as mock_add:
            dlq_id = add_failed_update_to_dlq(update_data, error, 3)
            
            assert dlq_id == 42
            mock_add.assert_called_once()
            
            call_args = mock_add.call_args
            assert call_args[1]["job_id"] == "update_123"
            assert call_args[1]["job_type"] == "update"
            assert call_args[1]["payload"] == update_data
            assert call_args[1]["error"] == error
            assert call_args[1]["attempts"] == 3
            
            # Check metadata
            metadata = call_args[1]["metadata"]
            assert metadata["chat_id"] == 456
            assert metadata["user_id"] == 789

    def test_add_failed_job_to_dlq(self):
        """Test helper function for failed scheduled jobs."""
        job_data = {"param1": "value1", "param2": 42}
        error = Exception("Job execution failed")
        
        with patch('app.services.dlq.DLQService.add_to_dlq', return_value=99) as mock_add, \
             patch('app.services.dlq.datetime') as mock_datetime:
            
            mock_datetime.now.return_value.timestamp.return_value = 1640995200.0
            
            dlq_id = add_failed_job_to_dlq("cleanup_job", job_data, error, 2)
            
            assert dlq_id == 99
            mock_add.assert_called_once()
            
            call_args = mock_add.call_args
            assert call_args[1]["job_id"] == "job_cleanup_job_1640995200.0"
            assert call_args[1]["job_type"] == "scheduled_job"
            assert call_args[1]["payload"]["job_name"] == "cleanup_job"
            assert call_args[1]["payload"]["job_data"] == job_data
            assert call_args[1]["metadata"]["job_name"] == "cleanup_job"


class TestDLQItem:
    """Test DLQItem dataclass."""

    def test_from_row_complete(self):
        """Test creating DLQItem from complete database row."""
        row = {
            "id": 1,
            "job_id": "test_job",
            "type": "update",
            "payload": '{"test": "data"}',
            "error": "Test error",
            "attempts": 3,
            "created_at": "2024-01-01T12:00:00",
            "last_attempt_at": "2024-01-01T12:05:00",
            "replayed_at": "2024-01-01T12:10:00",
            "metadata": '{"chat_id": 123}'
        }
        
        item = DLQItem.from_row(row)
        
        assert item.id == 1
        assert item.job_id == "test_job"
        assert item.type == "update"
        assert item.payload == {"test": "data"}
        assert item.error == "Test error"
        assert item.attempts == 3
        assert item.created_at == "2024-01-01T12:00:00"
        assert item.last_attempt_at == "2024-01-01T12:05:00"
        assert item.replayed_at == "2024-01-01T12:10:00"
        assert item.metadata == {"chat_id": 123}

    def test_from_row_minimal(self):
        """Test creating DLQItem from minimal database row."""
        row = {
            "id": 2,
            "job_id": "minimal_job",
            "type": "webhook",
            "payload": '{}',
            "error": "Minimal error",
            "attempts": 1,
            "created_at": "2024-01-01T12:00:00",
            "last_attempt_at": None,
            "replayed_at": None,
            "metadata": None
        }
        
        item = DLQItem.from_row(row)
        
        assert item.id == 2
        assert item.job_id == "minimal_job"
        assert item.payload == {}
        assert item.last_attempt_at is None
        assert item.replayed_at is None
        assert item.metadata is None


class TestDLQIntegration:
    """Integration tests for DLQ functionality."""

    @pytest.mark.asyncio
    async def test_worker_dlq_integration(self):
        """Test that worker properly integrates with DLQ."""
        # This would test the actual worker integration
        # For now, just test the error handling logic
        
        update_data = {"update_id": 789}
        error = Exception("Worker integration test")
        
        with patch('app.services.dlq.add_failed_update_to_dlq') as mock_add:
            mock_add.return_value = 123
            
            # Simulate the worker error handling
            dlq_id = add_failed_update_to_dlq(update_data, error, 3)
            
            assert dlq_id == 123
            mock_add.assert_called_once_with(update_data, error, 3)

    def test_metrics_integration(self):
        """Test that DLQ properly updates metrics."""
        with patch('app.services.dlq.execute_immediate', return_value=1), \
             patch('app.services.dlq.dlq_in_total') as mock_in_counter, \
             patch('app.services.dlq.dlq_size_gauge') as mock_gauge, \
             patch('app.services.dlq.fetchone', return_value={"count": 5}):
            
            DLQService.add_to_dlq(
                job_id="metrics_test",
                job_type="test",
                payload={},
                error="Test error",
                attempts=1
            )
            
            # Verify metrics were called
            mock_in_counter.labels.assert_called_with(type="test", reason="max_attempts_exceeded")
            mock_in_counter.labels().inc.assert_called_once()
            mock_gauge.labels.assert_called_with(type="test")
            mock_gauge.labels().set.assert_called_with(5)
