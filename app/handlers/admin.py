"""Admin commands for DLQ management and system monitoring."""

import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from ..services.dlq import DLQService
from ..utils.admin import admin_only

logger = logging.getLogger(__name__)


@admin_only
async def dlq_stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Dead Letter Queue statistics. Admin only."""
    try:
        stats = DLQService.get_stats_by_type()

        if not stats:
            await update.message.reply_text("📊 DLQ пуста - нет failed jobs")
            return

        # Build stats message
        message = "📊 **Dead Letter Queue Statistics**\n\n"

        total_all = 0
        unreplayed_all = 0

        for job_type, counts in stats.items():
            total = counts["total"]
            unreplayed = counts["unreplayed"]
            replayed = counts["replayed"]

            total_all += total
            unreplayed_all += unreplayed

            message += f"**{job_type}**:\n"
            message += f"  • Total: {total}\n"
            message += f"  • Unreplayed: {unreplayed}\n"
            message += f"  • Replayed: {replayed}\n\n"

        message += f"**TOTAL**: {total_all} items ({unreplayed_all} unreplayed)\n\n"

        # Add recent items info
        recent_items = DLQService.get_dlq_items(only_unreplayed=True, limit=5)
        if recent_items:
            message += "🔴 **Recent Failed Items**:\n"
            for item in recent_items:
                created_short = item.created_at[:19]
                job_id_short = item.job_id[:20] + "..." if len(item.job_id) > 20 else item.job_id
                message += f"  • #{item.id} {item.type} `{job_id_short}` ({created_short})\n"

        message += "\n💡 Use `python -m app.worker dlq:list` to see all items"
        message += "\n🔄 Use `python -m app.worker dlq:replay --id N` to replay item"

        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in dlq_stats command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error getting DLQ stats: {e}")


def register_admin_handlers(app) -> None:
    """Register admin command handlers."""
    app.add_handler(CommandHandler("dlq_stats", dlq_stats_cmd))
    logger.info("Admin DLQ handlers registered")
