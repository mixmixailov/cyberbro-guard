"""Property-based tests for SendQueue backoff behavior.

Uses hypothesis for property-based testing to ensure backoff behavior
is correct across a wide range of inputs and scenarios.
"""

from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.config import Settings
from app.services.send_queue import SendQueue


@pytest.fixture
def mock_bot():
    """Mock Telegram bot for property testing."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    return bot


class TestBackoffProperties:
    """Property-based tests for backoff calculations."""

    @given(
        attempt=st.integers(min_value=1, max_value=50),
        base=st.floats(min_value=0.1, max_value=2.0),
        max_delay=st.floats(min_value=5.0, max_value=60.0),
    )
    def test_backoff_bounds_invariant(self, mock_bot, attempt, base, max_delay):
        """Property: backoff delay is always between 0 and max_delay."""
        assume(base < max_delay)

        with patch("app.services.send_queue.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=base, BACKOFF_MAX=max_delay, BACKOFF_JITTER="full"
            )
            queue = SendQueue(mock_bot)

            delay = queue._calculate_jittered_backoff(attempt)
            assert (
                0 <= delay <= max_delay
            ), f"Delay {delay} not in bounds [0, {max_delay}] for attempt {attempt}"

    @given(
        retry_after=st.floats(min_value=0.1, max_value=60.0),
        jitter_ratio=st.floats(min_value=0.2, max_value=0.4),  # Test different jitter ranges
    )
    def test_retry_after_jitter_property(self, mock_bot, retry_after, jitter_ratio):
        """Property: RetryAfter jitter stays within specified bounds."""
        with patch("app.services.send_queue.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5, BACKOFF_MAX=20.0, BACKOFF_JITTER="full"
            )
            queue = SendQueue(mock_bot)

            # Test multiple samples for consistency
            for _ in range(10):
                delay = queue._calculate_jittered_backoff(1, retry_after)
                # Currently hardcoded to ±30%, but test with property
                expected_min = retry_after * 0.7
                expected_max = retry_after * 1.3
                assert (
                    expected_min <= delay <= expected_max
                ), f"Delay {delay} not in jitter range [{expected_min}, {expected_max}]"

    @given(
        attempt1=st.integers(min_value=1, max_value=10),
        attempt2=st.integers(min_value=1, max_value=10),
    )
    def test_exponential_growth_property(self, mock_bot, attempt1, attempt2):
        """Property: Later attempts generally have higher expected backoff (without jitter)."""
        assume(attempt1 < attempt2)

        with patch("app.services.send_queue.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5,
                BACKOFF_MAX=60.0,  # High max to avoid capping
                BACKOFF_JITTER="none",  # No jitter for deterministic comparison
            )
            queue = SendQueue(mock_bot)

            delay1 = queue._calculate_jittered_backoff(attempt1)
            delay2 = queue._calculate_jittered_backoff(attempt2)

            # Without jitter, later attempts should have higher delay
            assert (
                delay1 <= delay2
            ), f"Attempt {attempt1} delay {delay1} should be <= attempt {attempt2} delay {delay2}"

    @given(
        jitter_type=st.sampled_from(["full", "decorrelated", "none"]),
        attempt=st.integers(min_value=1, max_value=10),
        samples=st.integers(min_value=20, max_value=100),
    )
    def test_jitter_variation_property(self, mock_bot, jitter_type, attempt, samples):
        """Property: Jitter types provide appropriate variation levels."""
        with patch("app.services.send_queue.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5, BACKOFF_MAX=20.0, BACKOFF_JITTER=jitter_type
            )
            queue = SendQueue(mock_bot)

            delays = [queue._calculate_jittered_backoff(attempt) for _ in range(samples)]
            unique_delays = len(set(delays))

            if jitter_type == "none":
                # No jitter should produce identical results
                assert (
                    unique_delays == 1
                ), f"No jitter should produce 1 unique value, got {unique_delays}"
            else:
                # Jitter should produce variation
                expected_min_variation = samples * 0.3  # At least 30% unique values
                assert (
                    unique_delays >= expected_min_variation
                ), f"Jitter type '{jitter_type}' should produce at least {expected_min_variation} unique values, got {unique_delays}"

    @given(
        base=st.floats(min_value=0.1, max_value=5.0),
        multiplier=st.floats(min_value=1.5, max_value=3.0),
        max_delay=st.floats(min_value=10.0, max_value=100.0),
    )
    def test_exponential_scaling_property(self, mock_bot, base, multiplier, max_delay):
        """Property: Exponential backoff follows expected scaling pattern."""
        assume(base * (multiplier**10) > max_delay)  # Ensure we hit the cap

        with patch("app.services.send_queue.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=base, BACKOFF_MAX=max_delay, BACKOFF_JITTER="none"
            )
            queue = SendQueue(mock_bot)

            # Test first few attempts follow exponential pattern
            delays = []
            for attempt in range(1, 6):
                delay = queue._calculate_jittered_backoff(attempt)
                delays.append(delay)

                # Should not exceed max
                assert delay <= max_delay

                # Should follow exponential pattern (within rounding)
                expected = min(base * (2 ** (attempt - 1)), max_delay)
                assert (
                    abs(delay - expected) < 1e-10
                ), f"Attempt {attempt}: expected {expected}, got {delay}"

    @given(
        base=st.floats(min_value=0.1, max_value=2.0),
        max_delay=st.floats(min_value=0.05, max_value=1.0),  # Max < base
    )
    def test_max_smaller_than_base_property(self, mock_bot, base, max_delay):
        """Property: When max_delay < base, all delays should be capped at max_delay."""
        assume(max_delay < base)

        with patch("app.services.send_queue.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=base, BACKOFF_MAX=max_delay, BACKOFF_JITTER="full"
            )
            queue = SendQueue(mock_bot)

            # Test multiple attempts and samples
            for attempt in range(1, 10):
                for _ in range(10):
                    delay = queue._calculate_jittered_backoff(attempt)
                    assert (
                        delay <= max_delay
                    ), f"Delay {delay} exceeds max_delay {max_delay} for attempt {attempt}"


class TestConfigurationProperties:
    """Property-based tests for different configuration scenarios."""

    @given(
        config_base=st.floats(min_value=0.1, max_value=5.0),
        config_max=st.floats(min_value=1.0, max_value=60.0),
        config_jitter=st.sampled_from(["full", "decorrelated", "none"]),
    )
    def test_configuration_consistency(self, mock_bot, config_base, config_max, config_jitter):
        """Property: Any valid configuration should produce valid delays."""
        assume(config_base <= config_max)

        with patch("app.services.send_queue.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=config_base, BACKOFF_MAX=config_max, BACKOFF_JITTER=config_jitter
            )
            queue = SendQueue(mock_bot)

            # Test range of attempts
            for attempt in [1, 3, 5, 10]:
                delay = queue._calculate_jittered_backoff(attempt)

                # Basic invariants
                assert delay >= 0, f"Delay {delay} should be non-negative"
                assert delay <= config_max, f"Delay {delay} should not exceed max {config_max}"
                assert delay < float("inf"), f"Delay {delay} should be finite"

    @given(
        attempt=st.integers(min_value=1, max_value=20),
        retry_values=st.lists(st.floats(min_value=0.1, max_value=30.0), min_size=1, max_size=10),
    )
    def test_retry_after_consistency(self, mock_bot, attempt, retry_values):
        """Property: RetryAfter handling should be consistent across different values."""
        with patch("app.services.send_queue.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                BACKOFF_BASE=0.5, BACKOFF_MAX=20.0, BACKOFF_JITTER="full"
            )
            queue = SendQueue(mock_bot)

            for retry_after in retry_values:
                delay = queue._calculate_jittered_backoff(attempt, retry_after)

                # Should be roughly centered around retry_after with ±30% jitter
                expected_min = retry_after * 0.7
                expected_max = retry_after * 1.3
                assert (
                    expected_min <= delay <= expected_max
                ), f"RetryAfter {retry_after}: delay {delay} not in expected range"
