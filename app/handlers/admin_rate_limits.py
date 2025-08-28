"""Admin commands for managing adaptive rate limits.

Provides Telegram bot commands for administrators to:
- View current rate limit configurations
- Update rate limits at runtime
- Monitor rate limiting statistics
"""
import logging
from typing import List
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from ..services.rate_limits import get_rate_limit_service
from ..utils.admin import is_admin
from ..middleware.adaptive_rate_limit import rate_limit


logger = logging.getLogger(__name__)


@rate_limit('admin')
async def ratelimit_set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set rate limit configuration for a scope.
    
    Usage: /ratelimit set <scope> <limit> <burst> <cooldown>
    
    Args:
        scope: Rate limit scope (e.g., 'callback_query', 'message')
        limit: Requests per second (float)
        burst: Burst capacity (float)  
        cooldown: Cooldown period in seconds (float)
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    if not context.args or len(context.args) != 4:
        await update.message.reply_text(
            "Usage: `/ratelimit set <scope> <limit> <burst> <cooldown>`\n\n"
            "Examples:\n"
            "• `/ratelimit set callback_query 6.0 6.0 15.0`\n"
            "• `/ratelimit set message 10.0 20.0 30.0`\n"
            "• `/ratelimit set payment 5.0 10.0 60.0`",
            parse_mode='Markdown'
        )
        return
    
    try:
        scope = context.args[0].strip()
        rate_limit_value = float(context.args[1])
        burst = float(context.args[2])
        cooldown = float(context.args[3])
        
        # Validate parameters
        if rate_limit_value <= 0:
            await update.message.reply_text("❌ Rate limit must be positive.")
            return
        if burst <= 0:
            await update.message.reply_text("❌ Burst must be positive.")
            return
        if cooldown < 0:
            await update.message.reply_text("❌ Cooldown cannot be negative.")
            return
        if len(scope) == 0:
            await update.message.reply_text("❌ Scope cannot be empty.")
            return
        
        # Update rate limit configuration
        service = get_rate_limit_service()
        config = await service.set_rate_limit_config(scope, rate_limit_value, burst, cooldown)
        
        await update.message.reply_text(
            f"✅ *Rate limit updated*\n\n"
            f"**Scope:** `{config.scope}`\n"
            f"**Rate:** {config.rate_limit:.1f} req/sec\n"
            f"**Burst:** {config.burst:.1f}\n"
            f"**Cooldown:** {config.cooldown:.1f}s\n"
            f"**Updated:** {config.updated_at[:19]}",
            parse_mode='Markdown'
        )
        
        logger.info(
            "Rate limit updated by admin user_id=%s: scope=%s, rate=%.1f, burst=%.1f, cooldown=%.1f",
            user_id, scope, rate_limit_value, burst, cooldown
        )
        
    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid parameter: {e}")
    except Exception as e:
        logger.error("Error setting rate limit: %s", e, exc_info=True)
        await update.message.reply_text("❌ Failed to update rate limit. Please try again.")


@rate_limit('admin')
async def ratelimit_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all current rate limit configurations.
    
    Usage: /ratelimit list
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    try:
        service = get_rate_limit_service()
        configs = await service.list_all_configs()
        
        if not configs:
            await update.message.reply_text("No rate limit configurations found.")
            return
        
        # Format configurations
        lines = ["🚦 *Rate Limit Configurations*\n"]
        
        for scope, config in sorted(configs.items()):
            lines.append(
                f"**{config.scope}**\n"
                f"├ Rate: {config.rate_limit:.1f} req/sec\n"
                f"├ Burst: {config.burst:.1f}\n"
                f"├ Cooldown: {config.cooldown:.1f}s\n"
                f"└ Updated: {config.updated_at[:19]}\n"
            )
        
        message = "\n".join(lines)
        
        # Split message if too long
        if len(message) > 4000:
            chunks = []
            current_chunk = "🚦 *Rate Limit Configurations*\n\n"
            
            for scope, config in sorted(configs.items()):
                config_text = (
                    f"**{config.scope}**\n"
                    f"├ Rate: {config.rate_limit:.1f} req/sec\n"
                    f"├ Burst: {config.burst:.1f}\n"
                    f"├ Cooldown: {config.cooldown:.1f}s\n"
                    f"└ Updated: {config.updated_at[:19]}\n\n"
                )
                
                if len(current_chunk + config_text) > 4000:
                    chunks.append(current_chunk)
                    current_chunk = config_text
                else:
                    current_chunk += config_text
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Send chunks
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await update.message.reply_text(chunk, parse_mode='Markdown')
                else:
                    await update.message.reply_text(f"*Continued...*\n\n{chunk}", parse_mode='Markdown')
        else:
            await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error("Error listing rate limits: %s", e, exc_info=True)
        await update.message.reply_text("❌ Failed to retrieve rate limit configurations.")


@rate_limit('admin')
async def ratelimit_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show rate limiting service status and cache statistics.
    
    Usage: /ratelimit status
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    try:
        service = get_rate_limit_service()
        stats = await service.get_cache_stats()
        
        lines = [
            "📊 *Rate Limiting Service Status*\n",
            f"**Total Configurations:** {stats['total_configs']}",
            f"**Active Token Buckets:** {stats['total_buckets']}",
            f"**Cache TTL:** {stats['cache_ttl_seconds']}s",
            f"**Last Full Refresh:** {stats['last_full_refresh_ago']:.1f}s ago\n",
            "**Per-Scope Status:**"
        ]
        
        for scope, config_stats in sorted(stats['configs'].items()):
            status_icon = "✅" if config_stats['is_valid'] else "⚠️"
            bucket_icon = "🪣" if config_stats['has_bucket'] else "⭕"
            
            lines.append(
                f"{status_icon} **{scope}**\n"
                f"├ Cache age: {config_stats['age_seconds']:.1f}s\n"
                f"├ Valid: {'Yes' if config_stats['is_valid'] else 'No'}\n"
                f"└ Bucket: {bucket_icon} {'Active' if config_stats['has_bucket'] else 'None'}"
            )
        
        message = "\n".join(lines)
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error("Error getting rate limit status: %s", e, exc_info=True)
        await update.message.reply_text("❌ Failed to retrieve rate limiting status.")


@rate_limit('admin')
async def ratelimit_delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete rate limit configuration for a scope.
    
    Usage: /ratelimit delete <scope>
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "Usage: `/ratelimit delete <scope>`\n\n"
            "Example: `/ratelimit delete custom_scope`",
            parse_mode='Markdown'
        )
        return
    
    try:
        scope = context.args[0].strip()
        
        service = get_rate_limit_service()
        deleted = await service.delete_config(scope)
        
        if deleted:
            await update.message.reply_text(
                f"✅ Rate limit configuration for `{scope}` has been deleted.",
                parse_mode='Markdown'
            )
            logger.info("Rate limit configuration deleted by admin user_id=%s: scope=%s", user_id, scope)
        else:
            await update.message.reply_text(
                f"❌ No rate limit configuration found for scope `{scope}`.",
                parse_mode='Markdown'
            )
        
    except Exception as e:
        logger.error("Error deleting rate limit: %s", e, exc_info=True)
        await update.message.reply_text("❌ Failed to delete rate limit configuration.")


def register_admin_rate_limit_handlers(application):
    """Register admin rate limit handlers with the application.
    
    Args:
        application: PTB Application instance
    """
    # Main rate limit command with subcommands
    application.add_handler(CommandHandler("ratelimit", ratelimit_cmd))
    
    # Legacy specific subcommands for backward compatibility
    application.add_handler(CommandHandler(["ratelimit_set", "rl_set"], ratelimit_set_cmd))
    application.add_handler(CommandHandler(["ratelimit_list", "rl_list"], ratelimit_list_cmd))
    application.add_handler(CommandHandler(["ratelimit_status", "rl_status"], ratelimit_status_cmd))
    application.add_handler(CommandHandler(["ratelimit_delete", "rl_delete"], ratelimit_delete_cmd))


async def ratelimit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main rate limit command with subcommands.
    
    Usage: /ratelimit [set|list|status|delete] [args...]
    """
    user_id = update.effective_user.id if update.effective_user else None
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    if not context.args:
        # Show help
        help_text = """🚦 *Rate Limit Management Commands*

**Set Rate Limit:**
`/ratelimit set <scope> <limit> <burst> <cooldown>`
Example: `/ratelimit set callback_query 6.0 6.0 15.0`

**List Configurations:**
`/ratelimit list` - Show all rate limit configs

**Service Status:**
`/ratelimit status` - Show cache and service status

**Delete Configuration:**
`/ratelimit delete <scope>` - Remove rate limit config

**Common Scopes:**
• `callback_query` - Telegram callback handling
• `message` - Regular message processing
• `payment` - Payment operations
• `admin` - Administrative commands
• `global` - Global application limits

**Parameters:**
• **limit**: Requests per second (e.g., 6.0)
• **burst**: Max burst capacity (e.g., 6.0)
• **cooldown**: Cooldown period in seconds (e.g., 15.0)"""

        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    subcommand = context.args[0].lower()
    
    if subcommand == "set":
        # Handle set subcommand
        if len(context.args) != 5:
            await update.message.reply_text(
                "Usage: `/ratelimit set <scope> <limit> <burst> <cooldown>`\n\n"
                "Examples:\n"
                "• `/ratelimit set callback_query 6.0 6.0 15.0`\n"
                "• `/ratelimit set message 10.0 20.0 30.0`\n"
                "• `/ratelimit set payment 5.0 10.0 60.0`",
                parse_mode='Markdown'
            )
            return
        
        # Create new context with correct args for ratelimit_set_cmd
        context.args = context.args[1:]  # Remove 'set' from args
        await ratelimit_set_cmd(update, context)
        
    elif subcommand == "list":
        await ratelimit_list_cmd(update, context)
        
    elif subcommand == "status":
        await ratelimit_status_cmd(update, context)
        
    elif subcommand == "delete":
        if len(context.args) != 2:
            await update.message.reply_text(
                "Usage: `/ratelimit delete <scope>`\n\n"
                "Example: `/ratelimit delete custom_scope`",
                parse_mode='Markdown'
            )
            return
        
        # Create new context with correct args for ratelimit_delete_cmd
        context.args = context.args[1:]  # Remove 'delete' from args
        await ratelimit_delete_cmd(update, context)
        
    else:
        await update.message.reply_text(
            f"❌ Unknown subcommand: `{subcommand}`\n\n"
            "Available subcommands: `set`, `list`, `status`, `delete`\n"
            "Use `/ratelimit` without arguments to see help.",
            parse_mode='Markdown'
        )


