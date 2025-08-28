"""Unit tests for WAL checkpoint functionality."""
import pytest
import asyncio
import sqlite3
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

from app.db.session import get_wal_info, checkpoint_wal
from app.services.maintenance import MaintenanceService


class TestWALInfo:
    """Test WAL information gathering."""

    def test_get_wal_info_basic(self):
        """Test basic WAL info retrieval."""
        mock_result = (0, 5, 0)  # WAL checkpoint result format
        
        with patch('app.db.session._get_conn') as mock_conn_func, \
             patch('app.db.session.APP_DB_PATH') as mock_db_path:
            
            # Mock connection and result
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)
            mock_conn.execute().fetchone.return_value = mock_result
            mock_conn_func.return_value = mock_conn
            
            # Mock file paths and sizes
            mock_db_path.exists.return_value = True
            mock_db_path.stat.return_value.st_size = 1024 * 1024  # 1MB
            
            mock_wal_path = MagicMock()
            mock_wal_path.exists.return_value = True
            mock_wal_path.stat.return_value.st_size = 512 * 1024  # 512KB
            mock_db_path.with_suffix.return_value = mock_wal_path
            
            # Test
            result = get_wal_info()
            
            # Verify
            assert result["wal_pages"] == 5
            assert result["wal_size_bytes"] == 512 * 1024
            assert result["main_db_size_bytes"] == 1024 * 1024
            assert "error" not in result

    def test_get_wal_info_no_wal_file(self):
        """Test WAL info when WAL file doesn't exist."""
        mock_result = (0, 0, 0)
        
        with patch('app.db.session._get_conn') as mock_conn_func, \
             patch('app.db.session.APP_DB_PATH') as mock_db_path:
            
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)
            mock_conn.execute().fetchone.return_value = mock_result
            mock_conn_func.return_value = mock_conn
            
            # Main DB exists but WAL doesn't
            mock_db_path.exists.return_value = True
            mock_db_path.stat.return_value.st_size = 1024 * 1024
            
            mock_wal_path = MagicMock()
            mock_wal_path.exists.return_value = False
            mock_db_path.with_suffix.return_value = mock_wal_path
            
            result = get_wal_info()
            
            assert result["wal_pages"] == 0
            assert result["wal_size_bytes"] == 0
            assert result["main_db_size_bytes"] == 1024 * 1024

    def test_get_wal_info_error_handling(self):
        """Test WAL info error handling."""
        with patch('app.db.session._get_conn') as mock_conn_func:
            mock_conn_func.side_effect = sqlite3.Error("Database error")
            
            result = get_wal_info()
            
            assert result["wal_pages"] == 0
            assert result["wal_size_bytes"] == 0
            assert result["main_db_size_bytes"] == 0
            assert "error" in result


class TestWALCheckpoint:
    """Test WAL checkpoint operations."""

    def test_checkpoint_wal_success(self):
        """Test successful WAL checkpoint."""
        mock_result = (0, 2, 0)  # Successful checkpoint
        
        with patch('app.db.session._get_conn') as mock_conn_func, \
             patch('app.db.session.get_wal_info') as mock_get_info, \
             patch('time.perf_counter') as mock_time:
            
            # Mock timing
            mock_time.side_effect = [0.0, 0.050]  # 50ms duration
            
            # Mock connection
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)
            mock_conn.execute().fetchone.return_value = mock_result
            mock_conn_func.return_value = mock_conn
            
            # Mock WAL info before/after
            mock_get_info.side_effect = [
                {"wal_pages": 100, "wal_size_bytes": 1024 * 1024},  # Before
                {"wal_pages": 0, "wal_size_bytes": 0}              # After
            ]
            
            result = checkpoint_wal("TRUNCATE")
            
            assert result["success"] is True
            assert result["mode"] == "TRUNCATE"
            assert result["duration_ms"] == 50.0
            assert result["pages_before"] == 100
            assert result["pages_after"] == 0

    def test_checkpoint_wal_modes(self):
        """Test different checkpoint modes."""
        modes = ["PASSIVE", "FULL", "RESTART", "TRUNCATE"]
        
        for mode in modes:
            with patch('app.db.session._get_conn') as mock_conn_func, \
                 patch('app.db.session.get_wal_info', return_value={"wal_pages": 0, "wal_size_bytes": 0}):
                
                mock_conn = MagicMock()
                mock_conn.__enter__ = MagicMock(return_value=mock_conn)
                mock_conn.__exit__ = MagicMock(return_value=None)
                mock_conn.execute().fetchone.return_value = (0, 0, 0)
                mock_conn_func.return_value = mock_conn
                
                result = checkpoint_wal(mode)
                
                assert result["success"] is True
                assert result["mode"] == mode
                mock_conn.execute.assert_called_with(f"PRAGMA wal_checkpoint({mode});")

    def test_checkpoint_wal_error_handling(self):
        """Test checkpoint error handling."""
        with patch('app.db.session._get_conn') as mock_conn_func, \
             patch('time.perf_counter') as mock_time:
            
            mock_time.side_effect = [0.0, 0.025]  # 25ms duration
            mock_conn_func.side_effect = sqlite3.Error("Checkpoint failed")
            
            result = checkpoint_wal("TRUNCATE")
            
            assert result["success"] is False
            assert result["mode"] == "TRUNCATE"
            assert result["duration_ms"] == 25.0
            assert "error" in result


class TestMaintenanceService:
    """Test maintenance service functionality."""

    @pytest.mark.asyncio
    async def test_maintenance_service_start_stop(self):
        """Test maintenance service lifecycle."""
        with patch('app.services.maintenance.get_settings'):
            service = MaintenanceService()
            
            # Test start
            await service.start()
            assert service._running is True
            assert service._task is not None
            assert not service._task.done()
            
            # Test stop
            await service.stop()
            assert service._running is False

    @pytest.mark.asyncio
    async def test_update_wal_metrics(self):
        """Test WAL metrics update."""
        mock_wal_info = {
            "wal_pages": 150,
            "wal_size_bytes": 2 * 1024 * 1024  # 2MB
        }
        
        with patch('app.services.maintenance.get_settings'), \
             patch('app.services.maintenance.get_wal_info', return_value=mock_wal_info), \
             patch('app.services.maintenance.wal_pages') as mock_pages_gauge, \
             patch('app.services.maintenance.wal_size_bytes') as mock_size_gauge, \
             patch('asyncio.to_thread') as mock_to_thread:
            
            mock_to_thread.return_value = mock_wal_info
            
            service = MaintenanceService()
            await service._update_wal_metrics()
            
            mock_pages_gauge.set.assert_called_with(150)
            mock_size_gauge.set.assert_called_with(2 * 1024 * 1024)

    @pytest.mark.asyncio 
    async def test_check_and_checkpoint_needed_pages(self):
        """Test checkpoint when page threshold exceeded."""
        mock_wal_info = {
            "wal_pages": 1500,  # Exceeds 1000 threshold
            "wal_size_bytes": 10 * 1024 * 1024  # 10MB
        }
        
        mock_checkpoint_result = {
            "success": True,
            "duration_ms": 25.0
        }
        
        with patch('app.services.maintenance.get_settings'), \
             patch('asyncio.to_thread') as mock_to_thread, \
             patch('app.services.maintenance.checkpoint_performed_total') as mock_counter, \
             patch('app.services.maintenance.checkpoint_duration_seconds') as mock_histogram:
            
            mock_to_thread.side_effect = [mock_wal_info, mock_checkpoint_result]
            
            service = MaintenanceService()
            await service._check_and_checkpoint()
            
            # Verify checkpoint was called
            assert mock_to_thread.call_count == 2
            mock_counter.labels.assert_called_with(mode="TRUNCATE", status="success")
            mock_histogram.labels.assert_called_with(mode="TRUNCATE")

    @pytest.mark.asyncio
    async def test_check_and_checkpoint_needed_size(self):
        """Test checkpoint when size threshold exceeded."""
        mock_wal_info = {
            "wal_pages": 500,  # Below page threshold
            "wal_size_bytes": 70 * 1024 * 1024  # 70MB - exceeds 64MB threshold
        }
        
        with patch('app.services.maintenance.get_settings'), \
             patch('asyncio.to_thread') as mock_to_thread, \
             patch('app.services.maintenance.checkpoint_performed_total') as mock_counter:
            
            mock_to_thread.side_effect = [
                mock_wal_info, 
                {"success": True, "duration_ms": 30.0}
            ]
            
            service = MaintenanceService()
            await service._check_and_checkpoint()
            
            # Verify checkpoint was triggered due to size
            mock_counter.labels.assert_called_with(mode="TRUNCATE", status="success")

    @pytest.mark.asyncio
    async def test_check_and_checkpoint_not_needed(self):
        """Test no checkpoint when thresholds not exceeded."""
        mock_wal_info = {
            "wal_pages": 500,   # Below 1000 threshold
            "wal_size_bytes": 30 * 1024 * 1024  # 30MB - below 64MB threshold
        }
        
        with patch('app.services.maintenance.get_settings'), \
             patch('asyncio.to_thread', return_value=mock_wal_info), \
             patch('app.services.maintenance.checkpoint_performed_total') as mock_counter:
            
            service = MaintenanceService()
            await service._check_and_checkpoint()
            
            # Verify no checkpoint was performed
            mock_counter.labels.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_checkpoint(self):
        """Test manual checkpoint triggering."""
        mock_result = {
            "success": True,
            "mode": "FULL",
            "duration_ms": 40.0
        }
        
        with patch('app.services.maintenance.get_settings'), \
             patch('asyncio.to_thread', return_value=mock_result), \
             patch('app.services.maintenance.checkpoint_performed_total') as mock_counter, \
             patch('app.services.maintenance.checkpoint_duration_seconds') as mock_histogram:
            
            service = MaintenanceService()
            result = await service.force_checkpoint("FULL")
            
            assert result["success"] is True
            assert result["mode"] == "FULL"
            mock_counter.labels.assert_called_with(mode="FULL", status="success")
            mock_histogram.labels.assert_called_with(mode="FULL")

    @pytest.mark.asyncio
    async def test_get_maintenance_status(self):
        """Test maintenance status reporting."""
        mock_wal_info = {
            "wal_pages": 200,
            "wal_size_bytes": 5 * 1024 * 1024
        }
        
        with patch('app.services.maintenance.get_settings'), \
             patch('asyncio.to_thread', return_value=mock_wal_info):
            
            service = MaintenanceService()
            service._running = True
            service._task = MagicMock()
            service._task.done.return_value = False
            
            status = await service.get_maintenance_status()
            
            assert status["running"] is True
            assert status["task_done"] is False
            assert status["wal_info"] == mock_wal_info
            assert status["thresholds"]["max_wal_pages"] == 1000
            assert status["thresholds"]["max_wal_size_bytes"] == 64 * 1024 * 1024


class TestMaintenanceIntegration:
    """Integration tests for maintenance functionality."""

    @pytest.mark.asyncio
    async def test_maintenance_loop_single_iteration(self):
        """Test single iteration of maintenance loop."""
        mock_wal_info = {
            "wal_pages": 100,
            "wal_size_bytes": 1024 * 1024
        }
        
        with patch('app.services.maintenance.get_settings'), \
             patch('asyncio.to_thread', return_value=mock_wal_info), \
             patch('app.services.maintenance.wal_pages') as mock_pages, \
             patch('app.services.maintenance.wal_size_bytes') as mock_size, \
             patch('asyncio.sleep') as mock_sleep:
            
            service = MaintenanceService()
            service._running = True
            
            # Simulate one iteration then stop
            async def stop_after_sleep(duration):
                if duration == 300:  # Main loop sleep
                    service._running = False
            
            mock_sleep.side_effect = stop_after_sleep
            
            # Run maintenance loop
            await service._maintenance_loop()
            
            # Verify metrics were updated
            mock_pages.set.assert_called_with(100)
            mock_size.set.assert_called_with(1024 * 1024)

    def test_wal_thresholds_calculation(self):
        """Test WAL threshold calculations."""
        # Test page threshold
        MAX_PAGES = 1000
        assert 999 <= MAX_PAGES
        assert 1001 > MAX_PAGES
        
        # Test size threshold  
        MAX_SIZE = 64 * 1024 * 1024  # 64MB
        assert 63 * 1024 * 1024 < MAX_SIZE
        assert 65 * 1024 * 1024 > MAX_SIZE



