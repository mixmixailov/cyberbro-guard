"""Tests for adaptive rate limits functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.adaptive_rate_limit import (
    AdaptiveRateLimitMiddleware,
    get_rate_limit_middleware,
)
from app.services.rate_limits import (
    AdaptiveRateLimitService,
    RateLimitConfig,
    get_rate_limit_service,
)


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_config_creation(self):
        """Test creating rate limit configuration."""
        config = RateLimitConfig(
            scope="test_scope",
            rate_limit=10.0,
            burst=20.0,
            cooldown=30.0,
            updated_at="2024-12-01T12:00:00",
        )

        assert config.scope == "test_scope"
        assert config.rate_limit == 10.0
        assert config.burst == 20.0
        assert config.cooldown == 30.0
        assert config.updated_at == "2024-12-01T12:00:00"

    def test_config_to_dict(self):
        """Test converting configuration to dictionary."""
        config = RateLimitConfig(
            scope="test_scope",
            rate_limit=10.0,
            burst=20.0,
            cooldown=30.0,
            updated_at="2024-12-01T12:00:00",
        )

        expected = {
            "scope": "test_scope",
            "rate_limit": 10.0,
            "burst": 20.0,
            "cooldown": 30.0,
            "updated_at": "2024-12-01T12:00:00",
        }

        assert config.to_dict() == expected


class TestAdaptiveRateLimitService:
    """Test adaptive rate limit service."""

    def setup_method(self):
        """Setup test environment."""
        self.service = AdaptiveRateLimitService(cache_ttl_seconds=1)  # Short TTL for testing

    @pytest.mark.asyncio
    async def test_set_and_get_config(self):
        """Test setting and getting rate limit configuration."""
        with (
            patch("app.services.rate_limits.execute") as mock_execute,
            patch("app.services.rate_limits.fetchall") as mock_fetchall,
        ):
            # Mock database operations
            mock_execute.return_value = 1
            mock_fetchall.return_value = [
                {
                    "scope": "test_scope",
                    "rate_limit": 15.0,
                    "burst": 25.0,
                    "cooldown": 35.0,
                    "updated_at": "2024-12-01T12:00:00",
                }
            ]

            # Set configuration
            config = await self.service.set_rate_limit_config("test_scope", 15.0, 25.0, 35.0)

            assert config.scope == "test_scope"
            assert config.rate_limit == 15.0
            assert config.burst == 25.0
            assert config.cooldown == 35.0

            # Get configuration
            retrieved_config = await self.service.get_rate_limit_config("test_scope")
            assert retrieved_config is not None
            assert retrieved_config.scope == "test_scope"

    @pytest.mark.asyncio
    async def test_config_validation(self):
        """Test configuration parameter validation."""
        with patch("app.services.rate_limits.execute"):
            # Test invalid rate limit
            with pytest.raises(ValueError, match="Rate limit must be positive"):
                await self.service.set_rate_limit_config("test_scope", -1.0, 5.0, 10.0)

            # Test invalid burst
            with pytest.raises(ValueError, match="Burst must be positive"):
                await self.service.set_rate_limit_config("test_scope", 5.0, -1.0, 10.0)

            # Test invalid cooldown
            with pytest.raises(ValueError, match="Cooldown cannot be negative"):
                await self.service.set_rate_limit_config("test_scope", 5.0, 5.0, -1.0)

            # Test empty scope
            with pytest.raises(ValueError, match="Scope cannot be empty"):
                await self.service.set_rate_limit_config("", 5.0, 5.0, 10.0)

    @pytest.mark.asyncio
    async def test_cache_functionality(self):
        """Test cache TTL and refresh functionality."""
        with (
            patch("app.services.rate_limits.execute") as mock_execute,
            patch("app.services.rate_limits.fetchall") as mock_fetchall,
        ):
            mock_execute.return_value = 1
            mock_fetchall.return_value = [
                {
                    "scope": "test_scope",
                    "rate_limit": 10.0,
                    "burst": 20.0,
                    "cooldown": 30.0,
                    "updated_at": "2024-12-01T12:00:00",
                }
            ]

            # Set configuration (should be cached)
            await self.service.set_rate_limit_config("test_scope", 10.0, 20.0, 30.0)

            # Get configuration (should use cache)
            config1 = await self.service.get_rate_limit_config("test_scope")
            assert config1 is not None

            # Wait for cache to expire
            await asyncio.sleep(1.1)

            # Get configuration again (should refresh from database)
            config2 = await self.service.get_rate_limit_config("test_scope")
            assert config2 is not None

            # Verify database was called for refresh
            assert mock_fetchall.call_count >= 1

    @pytest.mark.asyncio
    async def test_token_bucket_creation(self):
        """Test token bucket creation from configuration."""
        with (
            patch("app.services.rate_limits.execute") as mock_execute,
            patch("app.services.rate_limits.fetchall") as mock_fetchall,
        ):
            mock_execute.return_value = 1
            mock_fetchall.return_value = [
                {
                    "scope": "test_scope",
                    "rate_limit": 10.0,
                    "burst": 20.0,
                    "cooldown": 30.0,
                    "updated_at": "2024-12-01T12:00:00",
                }
            ]

            # Set configuration
            await self.service.set_rate_limit_config("test_scope", 10.0, 20.0, 30.0)

            # Get token bucket
            bucket = await self.service.get_token_bucket("test_scope")

            assert bucket is not None
            assert bucket.rate == 10.0
            assert bucket.burst == 20.0
            assert bucket.cool_down == 30.0

    @pytest.mark.asyncio
    async def test_delete_config(self):
        """Test deleting rate limit configuration."""
        with patch("app.services.rate_limits.execute") as mock_execute:
            # Test successful deletion
            mock_execute.return_value = 1
            deleted = await self.service.delete_config("test_scope")
            assert deleted is True

            # Test deletion of non-existent config
            mock_execute.return_value = 0
            deleted = await self.service.delete_config("nonexistent_scope")
            assert deleted is False

    @pytest.mark.asyncio
    async def test_ensure_defaults(self):
        """Test ensuring default configurations exist."""
        with (
            patch("app.services.rate_limits.fetchall") as mock_fetchall,
            patch.object(self.service, "set_rate_limit_config") as mock_set,
        ):
            # Mock empty database
            mock_fetchall.return_value = []
            mock_set.return_value = AsyncMock()

            await self.service.ensure_defaults()

            # Verify default configurations were set
            assert mock_set.call_count == len(self.service.DEFAULT_CONFIGS)

            # Check that specific defaults were called
            called_scopes = {call[0][0] for call in mock_set.call_args_list}
            expected_scopes = set(self.service.DEFAULT_CONFIGS.keys())
            assert called_scopes == expected_scopes

    @pytest.mark.asyncio
    async def test_list_all_configs(self):
        """Test listing all rate limit configurations."""
        with patch("app.services.rate_limits.fetchall") as mock_fetchall:
            mock_fetchall.return_value = [
                {
                    "scope": "scope1",
                    "rate_limit": 10.0,
                    "burst": 20.0,
                    "cooldown": 30.0,
                    "updated_at": "2024-12-01T12:00:00",
                },
                {
                    "scope": "scope2",
                    "rate_limit": 15.0,
                    "burst": 25.0,
                    "cooldown": 35.0,
                    "updated_at": "2024-12-01T12:01:00",
                },
            ]

            configs = await self.service.list_all_configs()

            assert len(configs) == 2
            assert "scope1" in configs
            assert "scope2" in configs
            assert configs["scope1"].rate_limit == 10.0
            assert configs["scope2"].rate_limit == 15.0

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics reporting."""
        with patch("app.services.rate_limits.execute"):
            # Set some configurations to populate cache
            await self.service.set_rate_limit_config("scope1", 10.0, 20.0, 30.0)
            await self.service.set_rate_limit_config("scope2", 15.0, 25.0, 35.0)

            stats = await self.service.get_cache_stats()

            assert "total_configs" in stats
            assert "total_buckets" in stats
            assert "cache_ttl_seconds" in stats
            assert "configs" in stats

            assert stats["total_configs"] >= 2
            assert stats["cache_ttl_seconds"] == 1


class TestAdaptiveRateLimitMiddleware:
    """Test adaptive rate limiting middleware."""

    def setup_method(self):
        """Setup test environment."""
        self.middleware = AdaptiveRateLimitMiddleware()

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self):
        """Test rate limit check when request is allowed."""
        mock_bucket = MagicMock()
        mock_bucket.consume.return_value = True

        with patch.object(
            self.middleware.rate_limit_service, "get_token_bucket", return_value=mock_bucket
        ):
            result = await self.middleware.check_rate_limit("test_scope", user_id=123)

            assert result is True
            mock_bucket.consume.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_check_rate_limit_denied(self):
        """Test rate limit check when request is denied."""
        mock_bucket = MagicMock()
        mock_bucket.consume.return_value = False

        with patch.object(
            self.middleware.rate_limit_service, "get_token_bucket", return_value=mock_bucket
        ):
            result = await self.middleware.check_rate_limit("test_scope", user_id=123)

            assert result is False
            mock_bucket.consume.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_check_rate_limit_no_config(self):
        """Test rate limit check when no configuration exists."""
        with patch.object(
            self.middleware.rate_limit_service, "get_token_bucket", return_value=None
        ):
            result = await self.middleware.check_rate_limit("nonexistent_scope", user_id=123)

            assert result is True  # Should allow when no config exists

    @pytest.mark.asyncio
    async def test_check_rate_limit_error_handling(self):
        """Test rate limit check error handling."""
        with patch.object(
            self.middleware.rate_limit_service,
            "get_token_bucket",
            side_effect=Exception("Database error"),
        ):
            result = await self.middleware.check_rate_limit("test_scope", user_id=123)

            assert result is True  # Should fail-open on error


class TestRuntimeRateLimitChanges:
    """Test runtime rate limit changes without restart."""

    def setup_method(self):
        """Setup test environment."""
        self.service = AdaptiveRateLimitService(cache_ttl_seconds=0.1)  # Very short TTL
        self.middleware = AdaptiveRateLimitMiddleware()

    @pytest.mark.asyncio
    async def test_runtime_config_change(self):
        """Test that configuration changes are applied without restart."""
        with (
            patch("app.services.rate_limits.execute") as mock_execute,
            patch("app.services.rate_limits.fetchall") as mock_fetchall,
        ):
            # Initial configuration
            mock_execute.return_value = 1
            mock_fetchall.return_value = [
                {
                    "scope": "test_scope",
                    "rate_limit": 5.0,
                    "burst": 10.0,
                    "cooldown": 20.0,
                    "updated_at": "2024-12-01T12:00:00",
                }
            ]

            # Set initial configuration
            await self.service.set_rate_limit_config("test_scope", 5.0, 10.0, 20.0)

            # Get initial token bucket
            bucket1 = await self.service.get_token_bucket("test_scope")
            assert bucket1 is not None
            assert bucket1.rate == 5.0

            # Update configuration
            mock_fetchall.return_value = [
                {
                    "scope": "test_scope",
                    "rate_limit": 15.0,
                    "burst": 30.0,
                    "cooldown": 40.0,
                    "updated_at": "2024-12-01T12:01:00",
                }
            ]

            await self.service.set_rate_limit_config("test_scope", 15.0, 30.0, 40.0)

            # Get new token bucket (should have new configuration)
            bucket2 = await self.service.get_token_bucket("test_scope")
            assert bucket2 is not None
            assert bucket2.rate == 15.0
            assert bucket2.burst == 30.0
            assert bucket2.cool_down == 40.0

            # Verify buckets are different (old one was invalidated)
            assert bucket1 is not bucket2

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(self):
        """Test that cache is properly invalidated when configuration is updated."""
        with (
            patch("app.services.rate_limits.execute") as mock_execute,
            patch("app.services.rate_limits.fetchall") as mock_fetchall,
        ):
            mock_execute.return_value = 1

            # Initial fetch
            mock_fetchall.return_value = [
                {
                    "scope": "test_scope",
                    "rate_limit": 10.0,
                    "burst": 20.0,
                    "cooldown": 30.0,
                    "updated_at": "2024-12-01T12:00:00",
                }
            ]

            # Set and get configuration (should be cached)
            await self.service.set_rate_limit_config("test_scope", 10.0, 20.0, 30.0)
            config1 = await self.service.get_rate_limit_config("test_scope")
            assert config1.rate_limit == 10.0

            # Update configuration (should invalidate cache)
            await self.service.set_rate_limit_config("test_scope", 25.0, 35.0, 45.0)

            # Get configuration again (should use updated cached value)
            config2 = await self.service.get_rate_limit_config("test_scope")
            assert config2.rate_limit == 25.0

    @pytest.mark.asyncio
    async def test_middleware_uses_updated_config(self):
        """Test that middleware uses updated configuration without restart."""
        # Mock token buckets with different behaviors
        bucket1 = MagicMock()
        bucket1.consume.return_value = True
        bucket1.rate = 5.0

        bucket2 = MagicMock()
        bucket2.consume.return_value = False  # Different behavior
        bucket2.rate = 15.0

        # First, return bucket1
        with patch.object(
            self.middleware.rate_limit_service, "get_token_bucket", return_value=bucket1
        ):
            result1 = await self.middleware.check_rate_limit("test_scope")
            assert result1 is True

        # Then, return bucket2 (simulating config update)
        with patch.object(
            self.middleware.rate_limit_service, "get_token_bucket", return_value=bucket2
        ):
            result2 = await self.middleware.check_rate_limit("test_scope")
            assert result2 is False

        # Verify both buckets were used
        bucket1.consume.assert_called_once()
        bucket2.consume.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_config_updates(self):
        """Test handling of concurrent configuration updates."""
        with patch("app.services.rate_limits.execute") as mock_execute:
            mock_execute.return_value = 1

            # Simulate concurrent updates
            tasks = []
            for i in range(5):
                task = asyncio.create_task(
                    self.service.set_rate_limit_config(
                        f"scope{i}", float(i + 1), float(i + 10), float(i + 20)
                    )
                )
                tasks.append(task)

            # Wait for all updates to complete
            configs = await asyncio.gather(*tasks)

            # Verify all configurations were set
            assert len(configs) == 5
            for i, config in enumerate(configs):
                assert config.scope == f"scope{i}"
                assert config.rate_limit == float(i + 1)


class TestGlobalServiceInstance:
    """Test global service instance management."""

    def test_get_rate_limit_service_singleton(self):
        """Test that get_rate_limit_service returns singleton instance."""
        service1 = get_rate_limit_service()
        service2 = get_rate_limit_service()

        assert service1 is service2

    def test_get_rate_limit_middleware_singleton(self):
        """Test that get_rate_limit_middleware returns singleton instance."""
        middleware1 = get_rate_limit_middleware()
        middleware2 = get_rate_limit_middleware()

        assert middleware1 is middleware2
