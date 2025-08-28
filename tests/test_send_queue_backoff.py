"""Unit tests for SendQueue jittered exponential backoff.

Tests:
- 429 with retry_after=None -> uses base+jitter
- retry_after=3 -> wait around 3±30%
- Property-based: backoff never exceeds BACKOFF_MAX
- Metrics and logging validation
"""

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from telegram.error import NetworkError, RetryAfter, TimedOut

from app.config import Settings
from app.services.send_queue import SendQueue


@pytest.fixture
def mock_bot():
    """Mock Telegram bot for testing."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    return bot


@pytest.fixture
def mock_settings():
    """Mock settings with test configuration."""
    settings = Settings()
    settings.BACKOFF_BASE = 0.5
    settings.BACKOFF_MAX = 20.0
    settings.BACKOFF_JITTER = "full"
    return settings


@pytest.fixture
async def send_queue(mock_bot):
    """Create SendQueue instance for testing."""
    with patch("app.services.send_queue.get_settings") as mock_get_settings:
        mock_get_settings.return_value = Settings(
            BACKOFF_BASE=0.5, BACKOFF_MAX=20.0, BACKOFF_JITTER="full"
        )
        queue = SendQueue(mock_bot)
        await queue.start()
        yield queue
        await queue.stop()


class TestJitteredBackoff:
    """Test jittered exponential backoff calculations."""

    def test_calculate_jittered_backoff_retry_after_with_jitter(self, send_queue):
        """Test RetryAfter scenario with ±30% jitter."""
        retry_after = 3.0

        # Run multiple times to verify jitter range
        delays = []
        for _ in range(100):
            delay = send_queue._calculate_jittered_backoff(1, retry_after)
            delays.append(delay)

        # Should be within ±30% of retry_after
        expected_min = retry_after * 0.7
        expected_max = retry_after * 1.3

        assert all(
            expected_min <= d <= expected_max for d in delays
        ), f"Delays {delays[:5]}... not in range [{expected_min}, {expected_max}]"

        # Should have some variation (not all the same)
        assert len(set(delays)) > 10, "Insufficient jitter variation"

    def test_calculate_jittered_backoff_exponential_bounds(self, send_queue):
        """Test exponential backoff respects BACKOFF_MAX."""
        # Test high attempt numbers
        for attempt in [1, 2, 5, 10, 20]:
            delay = send_queue._calculate_jittered_backoff(attempt)
            assert (
                0 <= delay <= send_queue._settings.BACKOFF_MAX
            ), f"Attempt {attempt}: delay {delay} exceeds max {send_queue._settings.BACKOFF_MAX}"

    def test_calculate_jittered_backoff_no_jitter(self, mock_bot):
        """Test pure exponential backoff without jitter."""
        with patch("app.services.send_queue.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(
                BACKOFF_BASE=0.5, BACKOFF_MAX=20.0, BACKOFF_JITTER="none"
            )
            queue = SendQueue(mock_bot)

            # Should get pure exponential values
            delay1 = queue._calculate_jittered_backoff(1)
            delay2 = queue._calculate_jittered_backoff(2)
            delay3 = queue._calculate_jittered_backoff(3)

            assert delay1 == 0.5  # base
            assert delay2 == 1.0  # base * 2
            assert delay3 == 2.0  # base * 4

    def test_calculate_jittered_backoff_decorrelated(self, mock_bot):
        """Test decorrelated jitter behavior."""
        with patch("app.services.send_queue.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Settings(
                BACKOFF_BASE=0.5, BACKOFF_MAX=20.0, BACKOFF_JITTER="decorrelated"
            )
            queue = SendQueue(mock_bot)

            # First attempt should be in [0, base]
            delays_1 = [queue._calculate_jittered_backoff(1) for _ in range(50)]
            assert all(0 <= d <= 0.5 for d in delays_1)

            # Later attempts should have more variation
            delays_3 = [queue._calculate_jittered_backoff(3) for _ in range(50)]
            assert all(0.5 <= d <= 6.0 for d in delays_3)  # base to exp_backoff*3


class TestRetryBehavior:
    """Test retry behavior with different error types."""

    @pytest.mark.asyncio
    async def test_retry_after_handling(self, send_queue, mock_bot, caplog):
        """Test RetryAfter exception handling with metrics."""
        # Setup RetryAfter exception
        retry_error = RetryAfter(retry_after=2.0)
        mock_bot.send_message.side_effect = [retry_error, None]  # Fail once, then succeed

        with (
            patch("app.services.send_queue.retry_total") as mock_retry_metric,
            patch("app.services.send_queue.backoff_seconds") as mock_backoff_metric,
            patch("asyncio.sleep") as mock_sleep,
        ):
            caplog.set_level(logging.INFO)
            await send_queue.send_text(12345, "test message")

            # Wait for worker to process the queue
            await asyncio.sleep(0.1)

            # Verify metrics
            mock_retry_metric.labels.assert_called_with(reason="rate_limit")
            mock_retry_metric.labels().inc.assert_called_once()
            mock_backoff_metric.observe.assert_called_once()

            # Verify sleep was called with jittered delay around 2.0
            mock_sleep.assert_called()
            sleep_delay = mock_sleep.call_args[0][0]
            assert 1.4 <= sleep_delay <= 2.6, f"Sleep delay {sleep_delay} not in expected range"

            # Verify logging
            assert "Rate limit hit, backing off" in caplog.text
            assert "retry_after" in caplog.text
            assert "wait_ms" in caplog.text

    @pytest.mark.asyncio
    async def test_network_error_exponential_backoff(self, send_queue, mock_bot, caplog):
        """Test network error handling with exponential backoff."""
        # Setup network errors that eventually succeed
        network_error = TimedOut("Connection timeout")
        mock_bot.send_message.side_effect = [
            network_error,
            network_error,
            None,  # Fail twice, then succeed
        ]

        with (
            patch("app.services.send_queue.retry_total") as mock_retry_metric,
            patch("app.services.send_queue.backoff_seconds") as mock_backoff_metric,
            patch("asyncio.sleep") as mock_sleep,
        ):
            caplog.set_level(logging.WARNING)
            await send_queue.send_text(12345, "test message")

            # Should have 2 retry attempts
            assert mock_retry_metric.labels.call_count == 2
            mock_retry_metric.labels.assert_called_with(reason="network_error")
            assert mock_retry_metric.labels().inc.call_count == 2

            # Should have 2 backoff observations
            assert mock_backoff_metric.observe.call_count == 2

            # Should have 2 sleep calls with increasing delays
            assert mock_sleep.call_count == 2
            delays = [call[0][0] for call in mock_sleep.call_args_list]
            assert delays[0] < delays[1], "Backoff delays should increase"

            # Verify logging
            assert caplog.text.count("Network error, retrying with backoff") == 2

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self, send_queue, mock_bot, caplog):
        """Test behavior when max attempts are exceeded."""
        # Setup persistent network error
        network_error = NetworkError("Persistent failure")
        mock_bot.send_message.side_effect = network_error

        with (
            patch("app.services.send_queue.retry_total") as mock_retry_metric,
            patch("asyncio.sleep"),
        ):
            caplog.set_level(logging.ERROR)

            # Should raise after max attempts
            with pytest.raises(NetworkError):
                await send_queue.send_text(12345, "test message")

            # Should have max_attempts_exceeded metric
            mock_retry_metric.labels.assert_any_call(reason="max_attempts_exceeded")

            # Verify error logging
            assert "Send failed after max attempts" in caplog.text
            assert "max_attempts_exceeded" in caplog.text

    @pytest.mark.asyncio
    async def test_retry_after_none_uses_base_jitter(self, send_queue, mock_bot):
        """Test that RetryAfter with retry_after=None uses base+jitter."""
        # Setup RetryAfter without retry_after value
        retry_error = RetryAfter(retry_after=None)
        mock_bot.send_message.side_effect = [retry_error, None]

        with patch("asyncio.sleep") as mock_sleep:
            await send_queue.send_text(12345, "test message")

            # Should use calculated jitter delay, not a fixed value
            mock_sleep.assert_called_once()
            sleep_delay = mock_sleep.call_args[0][0]

            # With retry_after=None, should use jittered delay around 1.0 (default fallback)
            assert 0.7 <= sleep_delay <= 1.3, f"Sleep delay {sleep_delay} not in expected range"


class TestPropertyBasedBackoff:
    """Property-based tests for backoff behavior."""

    @pytest.mark.parametrize("attempt", [1, 2, 3, 5, 10, 20, 100])
    def test_backoff_never_exceeds_max(self, send_queue, attempt):
        """Property test: backoff delay never exceeds BACKOFF_MAX."""
        for _ in range(10):  # Multiple samples for jitter
            delay = send_queue._calculate_jittered_backoff(attempt)
            assert (
                0 <= delay <= send_queue._settings.BACKOFF_MAX
            ), f"Attempt {attempt}: delay {delay} exceeds max {send_queue._settings.BACKOFF_MAX}"

    @pytest.mark.parametrize("retry_after", [0.1, 1.0, 5.0, 30.0])
    def test_retry_after_jitter_bounds(self, send_queue, retry_after):
        """Property test: RetryAfter jitter stays within ±30%."""
        for _ in range(20):  # Multiple samples
            delay = send_queue._calculate_jittered_backoff(1, retry_after)
            expected_min = retry_after * 0.7
            expected_max = retry_after * 1.3
            assert (
                expected_min <= delay <= expected_max
            ), f"RetryAfter {retry_after}: delay {delay} not in range [{expected_min}, {expected_max}]"

    def test_jitter_provides_variation(self, send_queue):
        """Property test: jitter actually provides variation."""
        delays = [send_queue._calculate_jittered_backoff(3) for _ in range(100)]
        unique_delays = set(delays)

        # Should have significant variation with jitter
        assert (
            len(unique_delays) > 50
        ), f"Insufficient variation: {len(unique_delays)} unique values"

        # Should use full range with full jitter
        min_delay, max_delay = min(delays), max(delays)
        expected_max = min(0.5 * (2**2), 20.0)  # attempt 3 -> base * 4, capped at max
        assert min_delay < expected_max * 0.3, "Minimum delay too high for full jitter"
        assert max_delay > expected_max * 0.7, "Maximum delay too low for full jitter"


class TestSendQueueIntegration:
    """Integration tests for SendQueue with backoff."""

    @pytest.mark.asyncio
    async def test_send_text_success_no_backoff(self, send_queue, mock_bot):
        """Test successful send without any retries."""
        mock_bot.send_message.return_value = None

        with patch("app.services.send_queue.retry_total") as mock_retry_metric:
            await send_queue.send_text(12345, "Hello World")

            # Should not increment retry metrics on success
            mock_retry_metric.labels.assert_not_called()
            mock_bot.send_message.assert_called_once_with(12345, "Hello World")

    @pytest.mark.asyncio
    async def test_edit_text_with_retries(self, send_queue, mock_bot):
        """Test edit_message_text with retry behavior."""
        timeout_error = TimedOut("Edit timeout")
        mock_bot.edit_message_text.side_effect = [timeout_error, None]

        with patch("asyncio.sleep"):
            await send_queue.edit_text(12345, 67890, "Updated message")

            # Should be called twice (initial + retry)
            assert mock_bot.edit_message_text.call_count == 2
            calls = mock_bot.edit_message_text.call_args_list

            # Verify correct parameters in both calls
            for call in calls:
                assert call[1]["chat_id"] == 12345
                assert call[1]["message_id"] == 67890
                assert call[0] == ("Updated message",)
