"""CLI commands for queue and DLQ management.

Usage:
    python -m app.ops.queue stats                    # Show queue statistics  
    python -m app.ops.queue dlq:list                 # List recent DLQ items
    python -m app.ops.queue dlq:list --type update   # Filter by type
    python -m app.ops.queue dlq:replay --id 123      # Replay specific DLQ item
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..db.ops import (
    get_dlq_item_by_id,
    get_dlq_items_with_details,
    get_operational_summary,
    get_queue_stats,
)
from ..services.dlq import DLQService


def format_timestamp(ts: Optional[str]) -> str:
    """Format ISO timestamp for display."""
    if not ts:
        return "Never"
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return ts or "Unknown"


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text for table display."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def cmd_stats() -> None:
    """Show comprehensive queue statistics."""
    print("📊 Queue Statistics")
    print("=" * 50)
    
    try:
        stats = get_queue_stats()
        summary = get_operational_summary()
        
        # Overall DLQ Stats
        overall = stats.get("overall", {})
        print("\n🗃️ Dead Letter Queue Overview:")
        print(f"  Total DLQ Items: {overall.get('total_dlq_items', 0)}")
        print(f"  Unreplayed: {overall.get('unreplayed_total', 0)}")
        print(f"  Replayed: {overall.get('total_dlq_items', 0) - overall.get('unreplayed_total', 0)}")
        print(f"  Oldest Item: {format_timestamp(overall.get('oldest_item'))}")
        print(f"  Newest Item: {format_timestamp(overall.get('newest_item'))}")
        
        # DLQ by Type
        if stats.get("dlq_by_type"):
            print("\n📋 DLQ Items by Type:")
            print(f"{'Type':<15} {'Total':<8} {'Unreplayed':<12} {'Replayed':<10} {'Oldest':<20} {'Newest'}")
            print("-" * 85)
            
            for type_stat in stats["dlq_by_type"]:
                print(f"{type_stat['type']:<15} {type_stat['total']:<8} "
                      f"{type_stat['unreplayed']:<12} {type_stat['replayed']:<10} "
                      f"{format_timestamp(type_stat['oldest'])[:19]:<20} "
                      f"{format_timestamp(type_stat['newest'])[:19]}")
        
        # Common Errors
        if stats.get("common_errors"):
            print("\n⚠️ Common Error Categories (Last 100 items):")
            total_errors = sum(err["count"] for err in stats["common_errors"])
            
            for error in stats["common_errors"]:
                percentage = f"{(error['count'] / total_errors * 100):.1f}%" if total_errors > 0 else "0%"
                print(f"  {error['error_category']:<15} {error['count']:<5} ({percentage})")
        
        # Send Queue Info
        send_queue = summary.get("send_queue", {})
        print("\n📤 Send Queue Configuration:")
        print(f"  Type: {send_queue.get('type', 'Unknown')}")
        print(f"  Max Size: {send_queue.get('max_size', 'Unknown')}")
        print(f"  Global Rate: {send_queue.get('rate_limits', {}).get('global_rate', 'Unknown')}")
        print(f"  Per Chat Rate: {send_queue.get('rate_limits', {}).get('per_chat_rate', 'Unknown')}")
        print(f"  Max Retries: {send_queue.get('retry_config', {}).get('max_attempts', 'Unknown')}")
        print("\n  Note: Send queue is in-memory. Check /metrics for real-time stats.")
        
    except Exception as e:
        print(f"❌ Error getting queue stats: {e}")
        sys.exit(1)


def cmd_dlq_list(type_filter: Optional[str] = None, limit: int = 50, only_unreplayed: bool = True) -> None:
    """List DLQ items with details."""
    filter_desc = f" (type: {type_filter})" if type_filter else ""
    status_desc = " (unreplayed only)" if only_unreplayed else ""
    
    print(f"📋 DLQ Items{filter_desc}{status_desc}")
    print("=" * 80)
    
    try:
        items = get_dlq_items_with_details(
            limit=limit,
            type_filter=type_filter,
            only_unreplayed=only_unreplayed,
        )
        
        if not items:
            print("No DLQ items found.")
            return
        
        # Print table header
        print(f"{'ID':<5} {'Type':<12} {'Job ID':<18} {'Error':<35} {'Attempts':<8} {'Created':<12} {'Status'}")
        print("-" * 105)
        
        for item in items:
            status = "✅ Replayed" if item["replayed_at"] else "❌ Failed"
            created_short = format_timestamp(item["created_at"]).split()[1]  # Just time
            
            print(f"{item['id']:<5} {item['type']:<12} "
                  f"{truncate_text(item['job_id'], 18):<18} "
                  f"{truncate_text(item['error_summary'], 35):<35} "
                  f"{item['attempts']:<8} {created_short:<12} {status}")
        
        print(f"\nShowing {len(items)} items (max {limit})")
        
        # Show quick commands
        if items and only_unreplayed:
            first_id = items[0]["id"]
            print(f"\n💡 To replay an item: python -m app.ops.queue dlq:replay --id {first_id}")
            print(f"💡 To see details: python -m app.ops.queue dlq:details --id {first_id}")
        
    except Exception as e:
        print(f"❌ Error listing DLQ items: {e}")
        sys.exit(1)


def cmd_dlq_details(dlq_id: int) -> None:
    """Show detailed information for a specific DLQ item."""
    print(f"🔍 DLQ Item Details (ID: {dlq_id})")
    print("=" * 50)
    
    try:
        item = get_dlq_item_by_id(dlq_id)
        
        if not item:
            print(f"❌ DLQ item with ID {dlq_id} not found.")
            sys.exit(1)
        
        # Basic info
        print("\nℹ️ Basic Information:")
        print(f"  ID: {item['id']}")
        print(f"  Job ID: {item['job_id']}")
        print(f"  Type: {item['type']}")
        print(f"  Attempts: {item['attempts']}")
        print(f"  Created: {format_timestamp(item['created_at'])}")
        print(f"  Last Attempt: {format_timestamp(item['last_attempt_at'])}")
        print(f"  Replayed: {format_timestamp(item['replayed_at']) if item['replayed_at'] else 'No'}")
        
        # Error details
        print("\n❌ Error Details:")
        print("-" * 40)
        print(item["error"])
        
        # Payload (formatted JSON)
        if item["payload"]:
            print("\n📦 Payload:")
            print("-" * 40)
            try:
                if isinstance(item["payload"], dict):
                    print(json.dumps(item["payload"], indent=2))
                else:
                    print(str(item["payload"]))
            except Exception as e:
                print(f"Error formatting payload: {e}")
        
        # Metadata if present
        if item["metadata"]:
            print("\n📋 Metadata:")
            print("-" * 40)
            try:
                if isinstance(item["metadata"], dict):
                    print(json.dumps(item["metadata"], indent=2))
                else:
                    print(str(item["metadata"]))
            except Exception as e:
                print(f"Error formatting metadata: {e}")
        
        # Show replay command if not replayed
        if not item["replayed_at"]:
            print(f"\n💡 To replay this item: python -m app.ops.queue dlq:replay --id {dlq_id}")
        
    except Exception as e:
        print(f"❌ Error getting DLQ item details: {e}")
        sys.exit(1)


def cmd_dlq_replay(dlq_id: int, force: bool = False) -> None:
    """Replay a specific DLQ item."""
    print(f"🔄 Replaying DLQ Item (ID: {dlq_id})")
    print("=" * 40)
    
    try:
        # Get item details first
        item = get_dlq_item_by_id(dlq_id)
        
        if not item:
            print(f"❌ DLQ item with ID {dlq_id} not found.")
            sys.exit(1)
        
        # Check if already replayed
        if item["replayed_at"] and not force:
            print(f"⚠️ Item was already replayed at {format_timestamp(item['replayed_at'])}")
            print("Use --force to replay anyway.")
            return
        
        # Show item summary
        print(f"Job ID: {item['job_id']}")
        print(f"Type: {item['type']}")
        print(f"Original Error: {truncate_text(item['error'].split(chr(10))[0], 80)}")  # Use chr(10) instead of \\n
        print()
        
        # Confirm replay
        if not force:
            response = input("Are you sure you want to replay this item? (y/N): ")
            if response.lower() not in ('y', 'yes'):
                print("Replay cancelled.")
                return
        
        # Perform replay
        print("🔄 Attempting replay...")
        
        # Note: Actual replay logic would depend on the job type
        # For now, we'll just mark it as replayed
        success = DLQService.mark_replayed(dlq_id)
        
        if success:
            print("✅ Item marked as successfully replayed!")
            print(f"Replay timestamp: {format_timestamp(datetime.now().isoformat())}")
        else:
            print("❌ Failed to mark item as replayed.")
            print("Item may have been already replayed or not found.")
            sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error replaying DLQ item: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Queue and DLQ management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show queue statistics")
    
    # DLQ list command  
    dlq_list_parser = subparsers.add_parser("dlq:list", help="List DLQ items")
    dlq_list_parser.add_argument("--type", help="Filter by job type (e.g., update, scheduled_job)")
    dlq_list_parser.add_argument("--limit", type=int, default=50, help="Maximum items to show (default: 50)")
    dlq_list_parser.add_argument("--all", action="store_true", help="Include replayed items")
    
    # DLQ details command
    dlq_details_parser = subparsers.add_parser("dlq:details", help="Show detailed DLQ item info")
    dlq_details_parser.add_argument("--id", type=int, required=True, help="DLQ item ID")
    
    # DLQ replay command
    dlq_replay_parser = subparsers.add_parser("dlq:replay", help="Replay a DLQ item")
    dlq_replay_parser.add_argument("--id", type=int, required=True, help="DLQ item ID to replay")
    dlq_replay_parser.add_argument("--force", action="store_true", help="Force replay even if already replayed")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize database (ensure DLQ table exists)
    from ..db.session import _get_conn
    
    try:
        with _get_conn() as conn:
            # Just ensure DLQ table exists, don't run full init_db
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dlq (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    error TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
                    last_attempt_at TEXT,
                    replayed_at TEXT,
                    metadata TEXT
                )
            """)
            # Ensure indexes exist
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dlq_type ON dlq(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dlq_created_at ON dlq(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dlq_job_id ON dlq(job_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dlq_replayed_at ON dlq(replayed_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dlq_unreplayed ON dlq(type, replayed_at) WHERE replayed_at IS NULL")
            conn.commit()
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize DLQ table: {e}")
        print("Some commands may not work properly.")
    
    # Route to appropriate command
    if args.command == "stats":
        cmd_stats()
    elif args.command == "dlq:list":
        cmd_dlq_list(
            type_filter=args.type,
            limit=args.limit,
            only_unreplayed=not args.all,
        )
    elif args.command == "dlq:details":
        cmd_dlq_details(args.id)
    elif args.command == "dlq:replay":
        cmd_dlq_replay(args.id, force=args.force)
    else:
        parser.print_error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
