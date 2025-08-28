"""Adaptive rate limits service with database configuration and in-memory caching.

Provides runtime-configurable rate limiting with:
- Database-backed configuration
- In-memory caching with TTL for performance
- Admin interface for configuration changes
- Automatic default initialization
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from ..db.session import execute, fetchall
from ..services.rate_limit import TokenBucket

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a specific scope."""

    scope: str
    rate_limit: float
    burst: float
    cooldown: float
    updated_at: str

    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scope": self.scope,
            "rate_limit": self.rate_limit,
            "burst": self.burst,
            "cooldown": self.cooldown,
            "updated_at": self.updated_at,
        }


class AdaptiveRateLimitService:
    """Service for managing runtime-configurable rate limits."""

    # Default rate limit configurations
    DEFAULT_CONFIGS = {
        "callback_query": RateLimitConfig("callback_query", 6.0, 6.0, 15.0, ""),
        "message": RateLimitConfig("message", 10.0, 20.0, 30.0, ""),
        "payment": RateLimitConfig("payment", 5.0, 10.0, 60.0, ""),
        "admin": RateLimitConfig("admin", 20.0, 50.0, 10.0, ""),
        "global": RateLimitConfig("global", 30.0, 100.0, 60.0, ""),
    }

    def __init__(self, cache_ttl_seconds: int = 30):
        """Initialize the rate limit service.

        Args:
            cache_ttl_seconds: Time-to-live for cached configurations
        """
        self.cache_ttl = cache_ttl_seconds
        self._config_cache: Dict[str, RateLimitConfig] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._token_buckets: Dict[str, TokenBucket] = {}
        self._last_full_refresh = 0.0
        self._refresh_lock = asyncio.Lock()

    async def get_rate_limit_config(self, scope: str) -> Optional[RateLimitConfig]:
        """Get rate limit configuration for a scope.

        Args:
            scope: Rate limit scope (e.g., 'callback_query', 'message')

        Returns:
            Rate limit configuration or None if not found
        """
        # Check cache first
        if self._is_cache_valid(scope):
            return self._config_cache.get(scope)

        # Refresh from database
        await self._refresh_config(scope)
        return self._config_cache.get(scope)

    async def set_rate_limit_config(
        self, scope: str, rate_limit: float, burst: float, cooldown: float
    ) -> RateLimitConfig:
        """Set rate limit configuration for a scope.

        Args:
            scope: Rate limit scope
            rate_limit: Requests per second
            burst: Burst capacity
            cooldown: Cooldown period in seconds

        Returns:
            Updated configuration

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate parameters
        if rate_limit <= 0:
            raise ValueError("Rate limit must be positive")
        if burst <= 0:
            raise ValueError("Burst must be positive")
        if cooldown < 0:
            raise ValueError("Cooldown cannot be negative")
        if len(scope.strip()) == 0:
            raise ValueError("Scope cannot be empty")

        # Update database
        now = datetime.now().isoformat()
        execute(
            """INSERT OR REPLACE INTO rate_limits (scope, rate_limit, burst, cooldown, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (scope.strip(), rate_limit, burst, cooldown, now),
        )

        # Update cache
        config = RateLimitConfig(scope.strip(), rate_limit, burst, cooldown, now)
        self._config_cache[scope] = config
        self._cache_timestamps[scope] = time.time()

        # Invalidate token bucket for this scope to force recreation
        if scope in self._token_buckets:
            del self._token_buckets[scope]

        logger.info(
            "Rate limit updated for scope %s: rate=%.1f, burst=%.1f, cooldown=%.1f",
            scope,
            rate_limit,
            burst,
            cooldown,
        )

        return config

    async def get_token_bucket(self, scope: str) -> Optional[TokenBucket]:
        """Get or create a token bucket for the specified scope.

        Args:
            scope: Rate limit scope

        Returns:
            Token bucket instance or None if scope not configured
        """
        # Check if we have a cached token bucket
        if scope in self._token_buckets:
            return self._token_buckets[scope]

        # Get configuration
        config = await self.get_rate_limit_config(scope)
        if not config:
            return None

        # Create and cache token bucket
        bucket = TokenBucket(
            rate=config.rate_limit,
            per=1.0,  # per second
            burst=config.burst,
            cool_down=config.cooldown,
        )
        self._token_buckets[scope] = bucket

        logger.debug(
            "Created token bucket for scope %s: rate=%.1f, burst=%.1f",
            scope,
            config.rate_limit,
            config.burst,
        )

        return bucket

    async def list_all_configs(self) -> Dict[str, RateLimitConfig]:
        """Get all rate limit configurations.

        Returns:
            Dictionary of scope -> configuration
        """
        # Refresh all configs from database
        await self._refresh_all_configs()
        return self._config_cache.copy()

    async def delete_config(self, scope: str) -> bool:
        """Delete rate limit configuration for a scope.

        Args:
            scope: Rate limit scope to delete

        Returns:
            True if configuration was deleted, False if not found
        """
        # Check if config exists
        rows_affected = execute("DELETE FROM rate_limits WHERE scope = ?", (scope,))

        if rows_affected > 0:
            # Remove from cache
            self._config_cache.pop(scope, None)
            self._cache_timestamps.pop(scope, None)
            self._token_buckets.pop(scope, None)

            logger.info("Deleted rate limit configuration for scope: %s", scope)
            return True

        return False

    async def ensure_defaults(self) -> None:
        """Ensure default rate limit configurations exist in database."""
        # Check if we have any configurations
        existing_configs = fetchall("SELECT scope FROM rate_limits")
        existing_scopes = {row["scope"] for row in existing_configs}

        # Insert missing default configurations
        for scope, default_config in self.DEFAULT_CONFIGS.items():
            if scope not in existing_scopes:
                await self.set_rate_limit_config(
                    scope, default_config.rate_limit, default_config.burst, default_config.cooldown
                )
                logger.info("Initialized default rate limit for scope: %s", scope)

    def _is_cache_valid(self, scope: str) -> bool:
        """Check if cached configuration is still valid.

        Args:
            scope: Rate limit scope

        Returns:
            True if cache is valid and not expired
        """
        if scope not in self._config_cache:
            return False

        timestamp = self._cache_timestamps.get(scope, 0)
        return (time.time() - timestamp) < self.cache_ttl

    async def _refresh_config(self, scope: str) -> None:
        """Refresh configuration for a specific scope from database.

        Args:
            scope: Rate limit scope to refresh
        """
        async with self._refresh_lock:
            # Double-check cache validity after acquiring lock
            if self._is_cache_valid(scope):
                return

            # Fetch from database
            row = fetchall(
                "SELECT scope, rate_limit, burst, cooldown, updated_at FROM rate_limits WHERE scope = ?",
                (scope,),
            )

            if row:
                data = row[0]
                config = RateLimitConfig(
                    scope=data["scope"],
                    rate_limit=float(data["rate_limit"]),
                    burst=float(data["burst"]),
                    cooldown=float(data["cooldown"]),
                    updated_at=data["updated_at"],
                )

                self._config_cache[scope] = config
                self._cache_timestamps[scope] = time.time()

                logger.debug("Refreshed rate limit config for scope: %s", scope)

    async def _refresh_all_configs(self) -> None:
        """Refresh all configurations from database."""
        current_time = time.time()

        # Only refresh if it's been a while since last full refresh
        if (current_time - self._last_full_refresh) < (self.cache_ttl / 2):
            return

        async with self._refresh_lock:
            # Double-check timing after acquiring lock
            if (current_time - self._last_full_refresh) < (self.cache_ttl / 2):
                return

            # Fetch all configurations from database
            rows = fetchall(
                "SELECT scope, rate_limit, burst, cooldown, updated_at FROM rate_limits ORDER BY scope"
            )

            # Update cache
            for row in rows:
                config = RateLimitConfig(
                    scope=row["scope"],
                    rate_limit=float(row["rate_limit"]),
                    burst=float(row["burst"]),
                    cooldown=float(row["cooldown"]),
                    updated_at=row["updated_at"],
                )

                self._config_cache[config.scope] = config
                self._cache_timestamps[config.scope] = current_time

            self._last_full_refresh = current_time
            logger.debug("Refreshed all rate limit configurations from database")

    async def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with cache statistics
        """
        current_time = time.time()

        cache_stats = {
            "total_configs": len(self._config_cache),
            "total_buckets": len(self._token_buckets),
            "cache_ttl_seconds": self.cache_ttl,
            "last_full_refresh_ago": current_time - self._last_full_refresh,
            "configs": {},
        }

        # Per-config cache status
        for scope, timestamp in self._cache_timestamps.items():
            age = current_time - timestamp
            cache_stats["configs"][scope] = {
                "age_seconds": round(age, 1),
                "is_valid": age < self.cache_ttl,
                "has_bucket": scope in self._token_buckets,
            }

        return cache_stats


# Global instance
_rate_limit_service: Optional[AdaptiveRateLimitService] = None


def get_rate_limit_service() -> AdaptiveRateLimitService:
    """Get the global rate limit service instance."""
    global _rate_limit_service
    if _rate_limit_service is None:
        _rate_limit_service = AdaptiveRateLimitService()
    return _rate_limit_service


async def init_rate_limit_service() -> None:
    """Initialize the rate limit service with default configurations."""
    service = get_rate_limit_service()
    await service.ensure_defaults()
    logger.info("Rate limit service initialized with default configurations")
