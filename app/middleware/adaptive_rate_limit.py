"""Adaptive rate limiting middleware using database configuration.

Provides runtime-configurable rate limiting for different scopes:
- callback_query: Telegram callback query handling
- message: Regular message processing
- payment: Payment-related operations
- admin: Administrative commands
- global: Global application rate limiting
"""

import logging
from typing import Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..services.rate_limits import get_rate_limit_service

logger = logging.getLogger(__name__)


class AdaptiveRateLimitMiddleware:
    """Middleware for adaptive rate limiting based on database configuration."""

    def __init__(self):
        """Initialize the rate limiting middleware."""
        self.rate_limit_service = get_rate_limit_service()

    async def check_rate_limit(
        self, scope: str, user_id: Optional[int] = None, chat_id: Optional[int] = None
    ) -> bool:
        """Check if request is within rate limits for the given scope.

        Args:
            scope: Rate limit scope (e.g., 'callback_query', 'message')
            user_id: User ID for per-user rate limiting
            chat_id: Chat ID for additional context

        Returns:
            True if request is allowed, False if rate limited
        """
        try:
            # Get token bucket for this scope
            bucket = await self.rate_limit_service.get_token_bucket(scope)

            if bucket is None:
                # No rate limit configured for this scope - allow request
                logger.debug("No rate limit configured for scope: %s", scope)
                return True

            # Check if request is allowed
            is_allowed = bucket.consume(1)

            if not is_allowed:
                logger.warning(
                    "Rate limit exceeded for scope %s (user_id=%s, chat_id=%s)",
                    scope,
                    user_id,
                    chat_id,
                )
                # TODO: Add metrics for rate limit violations
                # rate_limit_violations_total.labels(scope=scope).inc()
            else:
                logger.debug("Rate limit check passed for scope %s (user_id=%s)", scope, user_id)

            return is_allowed

        except Exception as e:
            logger.error("Error checking rate limit for scope %s: %s", scope, e)
            # On error, allow the request to proceed (fail-open)
            return True

    def create_rate_limit_handler(self, scope: str) -> Callable:
        """Create a rate limit handler for a specific scope.

        Args:
            scope: Rate limit scope

        Returns:
            Handler function that can be used as middleware
        """

        async def rate_limit_handler(
            update: Update, context: ContextTypes.DEFAULT_TYPE
        ) -> Optional[bool]:
            """Rate limit handler for the specified scope."""
            user_id = None
            chat_id = None

            if update.effective_user:
                user_id = update.effective_user.id
            if update.effective_chat:
                chat_id = update.effective_chat.id

            # Check rate limit
            is_allowed = await self.check_rate_limit(scope, user_id, chat_id)

            if not is_allowed:
                # Rate limited - stop processing
                logger.info(
                    "Request rate limited for scope %s (user_id=%s, chat_id=%s)",
                    scope,
                    user_id,
                    chat_id,
                )
                return False  # Stop processing this update

            # Allow request to proceed
            return None  # Continue processing

        return rate_limit_handler


# Global middleware instance
_rate_limit_middleware: Optional[AdaptiveRateLimitMiddleware] = None


def get_rate_limit_middleware() -> AdaptiveRateLimitMiddleware:
    """Get the global rate limiting middleware instance."""
    global _rate_limit_middleware
    if _rate_limit_middleware is None:
        _rate_limit_middleware = AdaptiveRateLimitMiddleware()
    return _rate_limit_middleware


async def apply_rate_limit(scope: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Apply rate limiting for a specific scope.

    Args:
        scope: Rate limit scope
        update: Telegram update
        context: Bot context

    Returns:
        True if request is allowed, False if rate limited
    """
    middleware = get_rate_limit_middleware()

    user_id = None
    chat_id = None

    if update.effective_user:
        user_id = update.effective_user.id
    if update.effective_chat:
        chat_id = update.effective_chat.id

    return await middleware.check_rate_limit(scope, user_id, chat_id)


# Rate limiting decorators for handlers
def rate_limit(scope: str):
    """Decorator to add rate limiting to a handler function.

    Args:
        scope: Rate limit scope to apply

    Usage:
        @rate_limit('callback_query')
        async def my_callback_handler(update, context):
            # Handler logic here
            pass
    """

    def decorator(handler_func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Apply rate limiting
            is_allowed = await apply_rate_limit(scope, update, context)

            if not is_allowed:
                # Rate limited - don't execute handler
                logger.info("Handler rate limited for scope: %s", scope)
                return

            # Execute original handler
            return await handler_func(update, context)

        return wrapper

    return decorator
