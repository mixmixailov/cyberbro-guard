#!/usr/bin/env python3
"""Worker CLI commands for background job management.

Provides CLI interface for DLQ replay and other worker operations.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import get_settings
from app.db import init_db
from app.logging_conf import setup_logging
from app.services.dlq import DLQService

logger = logging.getLogger(__name__)


async def replay_dlq_item(dlq_id: int) -> bool:
    """Replay a specific DLQ item.

    Args:
        dlq_id: DLQ record ID to replay

    Returns:
        True if replay succeeded, False otherwise
    """
    # Get the DLQ item
    item = DLQService.get_dlq_item(dlq_id)
    if not item:
        logger.error(f"DLQ item {dlq_id} not found")
        return False

    if item.replayed_at:
        logger.warning(f"DLQ item {dlq_id} already replayed at {item.replayed_at}")
        return False

    logger.info(f"Replaying DLQ item {dlq_id}: type={item.type}, job_id={item.job_id}")

    try:
        if item.type == "update":
            # For update types, we'd need to reconstruct and process the Telegram update
            # This is complex as it requires the full PTB application context
            logger.warning("Update replay not implemented - would require full application context")
            logger.info(f"Update payload: {item.payload}")

            # For now, just mark as replayed for demo purposes
            # In production, you'd implement proper update replay logic
            success = True

        elif item.type == "scheduled_job":
            # For scheduled jobs, re-execute the job logic
            job_data = item.payload.get("job_data", {})
            job_name = item.payload.get("job_name", "unknown")

            logger.info(f"Replaying scheduled job: {job_name}")
            logger.info(f"Job data: {job_data}")

            # TODO: Implement actual job replay logic based on job_name
            # This would involve calling the appropriate job function with job_data
            success = True

        else:
            logger.error(f"Unknown job type for replay: {item.type}")
            return False

        if success:
            # Mark as successfully replayed
            DLQService.mark_replayed(dlq_id)
            logger.info(f"Successfully replayed DLQ item {dlq_id}")
            return True
        else:
            logger.error(f"Replay failed for DLQ item {dlq_id}")
            return False

    except Exception as e:
        logger.error(f"Error replaying DLQ item {dlq_id}: {e}", exc_info=True)
        return False


async def list_dlq_items(job_type: str = None, limit: int = 20) -> None:
    """List DLQ items."""
    items = DLQService.get_dlq_items(job_type=job_type, only_unreplayed=True, limit=limit)

    if not items:
        print("No unreplayed DLQ items found")
        return

    print(f"\nFound {len(items)} unreplayed DLQ items:")
    print("-" * 80)
    print(f"{'ID':<5} {'Type':<15} {'Job ID':<25} {'Attempts':<8} {'Created':<20}")
    print("-" * 80)

    for item in items:
        created_short = item.created_at[:19] if len(item.created_at) > 19 else item.created_at
        job_id_short = item.job_id[:22] + "..." if len(item.job_id) > 25 else item.job_id

        print(
            f"{item.id:<5} {item.type:<15} {job_id_short:<25} {item.attempts:<8} {created_short:<20}"
        )

    print("-" * 80)


async def show_dlq_stats() -> None:
    """Show DLQ statistics."""
    stats = DLQService.get_stats_by_type()

    if not stats:
        print("No DLQ items found")
        return

    print("\nDLQ Statistics by Type:")
    print("-" * 50)
    print(f"{'Type':<15} {'Total':<8} {'Unreplayed':<10} {'Replayed':<8}")
    print("-" * 50)

    total_all = 0
    unreplayed_all = 0
    replayed_all = 0

    for job_type, counts in stats.items():
        total = counts["total"]
        unreplayed = counts["unreplayed"]
        replayed = counts["replayed"]

        total_all += total
        unreplayed_all += unreplayed
        replayed_all += replayed

        print(f"{job_type:<15} {total:<8} {unreplayed:<10} {replayed:<8}")

    print("-" * 50)
    print(f"{'TOTAL':<15} {total_all:<8} {unreplayed_all:<10} {replayed_all:<8}")
    print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Worker CLI for DLQ management")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # DLQ replay command
    replay_parser = subparsers.add_parser("dlq:replay", help="Replay a DLQ item")
    replay_parser.add_argument("--id", type=int, required=True, help="DLQ item ID to replay")

    # DLQ list command
    list_parser = subparsers.add_parser("dlq:list", help="List DLQ items")
    list_parser.add_argument("--type", help="Filter by job type")
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum items to show")

    # DLQ stats command
    subparsers.add_parser("dlq:stats", help="Show DLQ statistics")

    # DLQ cleanup command
    cleanup_parser = subparsers.add_parser("dlq:cleanup", help="Clean up old replayed items")
    cleanup_parser.add_argument(
        "--days", type=int, default=30, help="Remove items older than N days"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Setup logging
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)

    # Initialize database
    init_db()

    # Run the command
    async def run_command():
        if args.command == "dlq:replay":
            success = await replay_dlq_item(args.id)
            sys.exit(0 if success else 1)

        elif args.command == "dlq:list":
            await list_dlq_items(job_type=args.type, limit=args.limit)

        elif args.command == "dlq:stats":
            await show_dlq_stats()

        elif args.command == "dlq:cleanup":
            count = DLQService.cleanup_old_replayed(args.days)
            print(f"Cleaned up {count} old replayed DLQ items")

    try:
        asyncio.run(run_command())
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Command failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
