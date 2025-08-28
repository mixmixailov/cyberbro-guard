"""Simplified unit tests for SendQueue jittered backoff functionality.

Focus on testing the core backoff calculation logic directly
without complex async queue interactions.
"""
import random
import pytest
from unittest.mock import patch, MagicMock

from app.services.send_queue import SendQueue
from app.config import Settings


@pytest.fixture
def mock_bot():
    """Mock Telegram bot for testing."""
    return MagicMock()


class TestBackoffCalculation:
    """Test backoff calculation methods directly."""

    def test_retry_after_jitter(self):
        """Test RetryAfter with ±30% jitter."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=20.0,
                BACKOFF_JITTER="full"
            )
            queue = SendQueue(MagicMock())
            
            retry_after = 3.0
            delays = [queue._calculate_jittered_backoff(1, retry_after) for _ in range(50)]
            
            # All delays should be within ±30% of retry_after
            expected_min = retry_after * 0.7
            expected_max = retry_after * 1.3
            assert all(expected_min <= d <= expected_max for d in delays)
            
            # Should have variation
            assert len(set(delays)) > 10

    def test_exponential_backoff_bounds(self):
        """Test exponential backoff respects max bounds."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=5.0,
                BACKOFF_JITTER="full"
            )
            queue = SendQueue(MagicMock())
            
            # Test various attempt numbers
            for attempt in [1, 5, 10, 20]:
                delay = queue._calculate_jittered_backoff(attempt)
                assert 0 <= delay <= 5.0, f"Attempt {attempt}: delay {delay} exceeds max"

    def test_no_jitter_deterministic(self):
        """Test no jitter produces deterministic results."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=20.0,
                BACKOFF_JITTER="none"
            )
            queue = SendQueue(MagicMock())
            
            # Should get exact exponential values
            assert queue._calculate_jittered_backoff(1) == 0.5
            assert queue._calculate_jittered_backoff(2) == 1.0
            assert queue._calculate_jittered_backoff(3) == 2.0

    def test_decorrelated_jitter(self):
        """Test decorrelated jitter algorithm."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=20.0,
                BACKOFF_JITTER="decorrelated"
            )
            queue = SendQueue(MagicMock())
            
            # First attempt should be in [0, base]
            delays_1 = [queue._calculate_jittered_backoff(1) for _ in range(20)]
            assert all(0 <= d <= 0.5 for d in delays_1)
            
            # Later attempts should have wider range
            delays_3 = [queue._calculate_jittered_backoff(3) for _ in range(20)]
            assert all(0.5 <= d <= 6.0 for d in delays_3)  # base to exp*3

    @pytest.mark.parametrize("attempt", [1, 2, 5, 10, 20])
    def test_backoff_never_exceeds_max(self, attempt):
        """Property test: backoff never exceeds max."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=10.0,
                BACKOFF_JITTER="full"
            )
            queue = SendQueue(MagicMock())
            
            for _ in range(10):  # Multiple samples
                delay = queue._calculate_jittered_backoff(attempt)
                assert 0 <= delay <= 10.0

    def test_retry_after_none_fallback(self):
        """Test handling of RetryAfter with None value."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=20.0,
                BACKOFF_JITTER="full"
            )
            queue = SendQueue(MagicMock())
            
            # When retry_after is None, should use normal exponential backoff
            delay = queue._calculate_jittered_backoff(1, None)
            assert 0 <= delay <= 0.5  # Should be within first attempt range


class TestConfigurationIntegration:
    """Test different configuration scenarios."""

    def test_configuration_loading(self):
        """Test that SendQueue properly loads configuration."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            test_settings = Settings(
                BACKOFF_BASE=1.0,
                BACKOFF_MAX=30.0,
                BACKOFF_JITTER="decorrelated"
            )
            mock_settings.return_value = test_settings
            
            queue = SendQueue(MagicMock())
            
            # Verify settings are loaded
            assert queue._settings.BACKOFF_BASE == 1.0
            assert queue._settings.BACKOFF_MAX == 30.0
            assert queue._settings.BACKOFF_JITTER == "decorrelated"

    def test_edge_case_max_less_than_base(self):
        """Test configuration where max < base."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=5.0,
                BACKOFF_MAX=2.0,  # Max less than base
                BACKOFF_JITTER="full"
            )
            queue = SendQueue(MagicMock())
            
            # All delays should be capped at max
            for attempt in [1, 2, 5]:
                delay = queue._calculate_jittered_backoff(attempt)
                assert delay <= 2.0


class TestJitterVariation:
    """Test jitter provides appropriate variation."""

    def test_full_jitter_variation(self):
        """Test full jitter provides good variation."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=20.0,
                BACKOFF_JITTER="full"
            )
            queue = SendQueue(MagicMock())
            
            delays = [queue._calculate_jittered_backoff(3) for _ in range(100)]
            unique_delays = len(set(delays))
            
            # Should have significant variation
            assert unique_delays > 50, f"Only {unique_delays} unique values"
            
            # Should span expected range
            min_delay, max_delay = min(delays), max(delays)
            expected_max = min(0.5 * 4, 20.0)  # attempt 3 -> base * 4
            assert min_delay < expected_max * 0.3
            assert max_delay > expected_max * 0.7

    def test_zero_jitter_no_variation(self):
        """Test no jitter produces no variation."""
        with patch('app.services.send_queue.get_settings') as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=20.0,
                BACKOFF_JITTER="none"
            )
            queue = SendQueue(MagicMock())
            
            delays = [queue._calculate_jittered_backoff(3) for _ in range(20)]
            unique_delays = len(set(delays))
            
            # Should have no variation
            assert unique_delays == 1
            assert delays[0] == 2.0  # base * 4 = 0.5 * 4 = 2.0
