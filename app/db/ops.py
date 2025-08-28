"""Database operations and helpers for queue management and inspection.

Provides SQL helpers for CLI tools to inspect and manage queues,
DLQ items, and other operational data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .session import fetchall, fetchone

__all__ = [
    "get_queue_stats",
    "get_dlq_items_with_details", 
    "get_dlq_item_by_id",
    "get_dlq_stats_summary",
    "get_oldest_newest_dlq_items",
    "count_unreplayed_dlq_by_type",
    "get_recent_dlq_errors",
]


def get_queue_stats() -> Dict[str, Any]:
    """Get comprehensive queue statistics.
    
    Returns:
        Dict with queue statistics including DLQ counts, types, etc.
    """
    # DLQ statistics by type
    dlq_stats = fetchall("""
        SELECT 
            type,
            COUNT(*) as total,
            COUNT(CASE WHEN replayed_at IS NULL THEN 1 END) as unreplayed,
            COUNT(CASE WHEN replayed_at IS NOT NULL THEN 1 END) as replayed,
            MIN(created_at) as oldest,
            MAX(created_at) as newest
        FROM dlq 
        GROUP BY type
        ORDER BY total DESC
    """)
    
    # Overall DLQ stats
    overall_dlq = fetchone("""
        SELECT 
            COUNT(*) as total_dlq_items,
            COUNT(CASE WHEN replayed_at IS NULL THEN 1 END) as unreplayed_total,
            MIN(created_at) as oldest_item,
            MAX(created_at) as newest_item
        FROM dlq
    """)
    
    # Most common error patterns (last 100 items)
    common_errors = fetchall("""
        SELECT 
            CASE 
                WHEN error LIKE '%NetworkError%' THEN 'NetworkError'
                WHEN error LIKE '%RetryAfter%' THEN 'RetryAfter'
                WHEN error LIKE '%TimedOut%' THEN 'TimedOut'
                WHEN error LIKE '%BadRequest%' THEN 'BadRequest'
                WHEN error LIKE '%Forbidden%' THEN 'Forbidden'
                WHEN error LIKE '%ValueError%' THEN 'ValueError'
                WHEN error LIKE '%KeyError%' THEN 'KeyError'
                ELSE 'Other'
            END as error_category,
            COUNT(*) as count
        FROM (
            SELECT error FROM dlq 
            ORDER BY created_at DESC 
            LIMIT 100
        )
        GROUP BY error_category
        ORDER BY count DESC
    """)
    
    return {
        "dlq_by_type": [dict(row) for row in dlq_stats],
        "overall": dict(overall_dlq) if overall_dlq else {},
        "common_errors": [dict(row) for row in common_errors],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_dlq_items_with_details(
    limit: int = 50,
    type_filter: Optional[str] = None,
    only_unreplayed: bool = True,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get DLQ items with detailed information for CLI display.
    
    Args:
        limit: Maximum number of items to return
        type_filter: Filter by job type (e.g., 'update', 'scheduled_job')
        only_unreplayed: Only return items not yet replayed
        offset: Number of items to skip for pagination
        
    Returns:
        List of DLQ items with parsed payload and metadata
    """
    conditions = []
    params = []
    
    if type_filter:
        conditions.append("type = ?")
        params.append(type_filter)
    
    if only_unreplayed:
        conditions.append("replayed_at IS NULL")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    items = fetchall(f"""
        SELECT 
            id,
            job_id,
            type,
            payload,
            error,
            attempts,
            created_at,
            last_attempt_at,
            replayed_at,
            metadata
        FROM dlq 
        WHERE {where_clause}
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    """, params + [limit, offset])
    
    result = []
    for item in items:
        item_dict = dict(item)
        
        # Parse JSON fields safely
        try:
            item_dict["payload"] = json.loads(item["payload"])
        except (json.JSONDecodeError, TypeError):
            item_dict["payload"] = item["payload"]
            
        try:
            item_dict["metadata"] = json.loads(item["metadata"]) if item["metadata"] else None
        except (json.JSONDecodeError, TypeError):
            item_dict["metadata"] = item["metadata"]
        
        # Extract error summary (first line only)
        error_lines = item["error"].split('\n')
        item_dict["error_summary"] = error_lines[0] if error_lines else item["error"]
        
        # Add helpful extracted fields based on type
        if item["type"] == "update" and isinstance(item_dict["payload"], dict):
            payload = item_dict["payload"]
            item_dict["update_id"] = payload.get("update_id")
            
            # Extract chat and user info from update
            message = payload.get("message", {})
            callback_query = payload.get("callback_query", {})
            
            if message:
                item_dict["chat_id"] = message.get("chat", {}).get("id")
                item_dict["user_id"] = message.get("from", {}).get("id")
            elif callback_query:
                item_dict["chat_id"] = callback_query.get("message", {}).get("chat", {}).get("id")
                item_dict["user_id"] = callback_query.get("from", {}).get("id")
        
        result.append(item_dict)
    
    return result


def get_dlq_item_by_id(dlq_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific DLQ item by ID with full details.
    
    Args:
        dlq_id: DLQ record ID
        
    Returns:
        DLQ item dict with parsed JSON fields, or None if not found
    """
    item = fetchone("""
        SELECT 
            id,
            job_id,
            type,
            payload,
            error,
            attempts,
            created_at,
            last_attempt_at,
            replayed_at,
            metadata
        FROM dlq 
        WHERE id = ?
    """, (dlq_id,))
    
    if not item:
        return None
    
    item_dict = dict(item)
    
    # Parse JSON fields
    try:
        item_dict["payload"] = json.loads(item["payload"])
    except (json.JSONDecodeError, TypeError):
        item_dict["payload"] = item["payload"]
        
    try:
        item_dict["metadata"] = json.loads(item["metadata"]) if item["metadata"] else None
    except (json.JSONDecodeError, TypeError):
        item_dict["metadata"] = item["metadata"]
    
    return item_dict


def get_dlq_stats_summary() -> Dict[str, Any]:
    """Get a concise summary of DLQ statistics for quick status check.
    
    Returns:
        Dict with high-level DLQ statistics
    """
    stats = fetchone("""
        SELECT 
            COUNT(*) as total_items,
            COUNT(CASE WHEN replayed_at IS NULL THEN 1 END) as unreplayed,
            COUNT(CASE WHEN replayed_at IS NOT NULL THEN 1 END) as replayed,
            COUNT(DISTINCT type) as unique_types,
            MIN(created_at) as oldest_item,
            MAX(created_at) as newest_item
        FROM dlq
    """)
    
    if not stats or stats["total_items"] == 0:
        return {
            "total_items": 0,
            "unreplayed": 0,
            "replayed": 0,
            "unique_types": 0,
            "oldest_item": None,
            "newest_item": None,
        }
    
    return dict(stats)


def get_oldest_newest_dlq_items(type_filter: Optional[str] = None) -> Tuple[Optional[Dict], Optional[Dict]]:
    """Get the oldest and newest DLQ items, optionally filtered by type.
    
    Args:
        type_filter: Optional job type filter
        
    Returns:
        Tuple of (oldest_item, newest_item) or (None, None) if no items
    """
    conditions = []
    params = []
    
    if type_filter:
        conditions.append("type = ?")
        params.append(type_filter)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    oldest = fetchone(f"""
        SELECT id, job_id, type, created_at, error
        FROM dlq 
        WHERE {where_clause}
        ORDER BY created_at ASC 
        LIMIT 1
    """, params)
    
    newest = fetchone(f"""
        SELECT id, job_id, type, created_at, error
        FROM dlq 
        WHERE {where_clause}
        ORDER BY created_at DESC 
        LIMIT 1
    """, params)
    
    return (
        dict(oldest) if oldest else None,
        dict(newest) if newest else None,
    )


def count_unreplayed_dlq_by_type() -> List[Dict[str, Any]]:
    """Get count of unreplayed DLQ items grouped by type.
    
    Returns:
        List of dicts with type and count
    """
    counts = fetchall("""
        SELECT 
            type,
            COUNT(*) as unreplayed_count
        FROM dlq 
        WHERE replayed_at IS NULL
        GROUP BY type
        ORDER BY unreplayed_count DESC
    """)
    
    return [dict(row) for row in counts]


def get_recent_dlq_errors(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent DLQ errors for quick error analysis.
    
    Args:
        limit: Number of recent errors to return
        
    Returns:
        List of recent DLQ items with error details
    """
    errors = fetchall("""
        SELECT 
            id,
            job_id,
            type,
            error,
            attempts,
            created_at
        FROM dlq 
        WHERE replayed_at IS NULL
        ORDER BY created_at DESC 
        LIMIT ?
    """, (limit,))
    
    result = []
    for error in errors:
        error_dict = dict(error)
        # Extract first line of error for summary
        error_lines = error["error"].split('\n')
        error_dict["error_summary"] = error_lines[0] if error_lines else error["error"]
        result.append(error_dict)
    
    return result


# Helper functions for SendQueue stats (in-memory queue)
def get_send_queue_info() -> Dict[str, Any]:
    """Get information about the send queue.
    
    Note: SendQueue is in-memory, so this returns general info.
    For real-time stats, the queue instance needs to be queried directly.
    
    Returns:
        Dict with send queue configuration and general info
    """
    from ..config import get_settings
    
    settings = get_settings()
    
    return {
        "type": "in_memory_asyncio_queue",
        "max_size": 2000,  # From SendQueue.__init__
        "rate_limits": {
            "global_rate": "30 messages/second",
            "per_chat_rate": "1 message/second",
        },
        "backoff_config": {
            "base_delay": settings.BACKOFF_BASE,
            "max_delay": settings.BACKOFF_MAX,
            "jitter_type": settings.BACKOFF_JITTER,
        },
        "retry_config": {
            "max_attempts": 5,  # From SendQueue._send method
        },
        "note": "Queue is in-memory. Use metrics endpoint for real-time stats.",
    }


def get_operational_summary() -> Dict[str, Any]:
    """Get a comprehensive operational summary for CLI dashboard.
    
    Returns:
        Dict with overall operational status
    """
    dlq_summary = get_dlq_stats_summary()
    unreplayed_by_type = count_unreplayed_dlq_by_type()
    recent_errors = get_recent_dlq_errors(5)
    send_queue_info = get_send_queue_info()
    
    return {
        "dlq": dlq_summary,
        "unreplayed_by_type": unreplayed_by_type,
        "recent_errors": recent_errors,
        "send_queue": send_queue_info,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
