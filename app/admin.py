"""Admin endpoints for debugging and monitoring.

This module provides admin-only endpoints for system monitoring,
debugging, and maintenance operations.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from .db.session import get_wal_info
from .services.dlq import DLQService

logger = logging.getLogger(__name__)
router = APIRouter()


async def admin_required(admin_ids: str = None) -> None:
    """Dependency to check if request is from admin.

    For HTTP endpoints, we can't check Telegram user ID easily,
    so this is a placeholder for more sophisticated admin auth.
    In production, you might use API keys, JWT tokens, etc.
    """
    # For now, just log the access attempt
    # In production, implement proper admin authentication
    logger.info("Admin endpoint accessed")


@router.get("/dbz")
async def debug_database_stats(_: None = Depends(admin_required)) -> JSONResponse:
    """Debug endpoint for database and WAL statistics.

    Admin-only endpoint that provides detailed database health information.
    """
    try:
        # Get WAL information
        wal_info = get_wal_info()

        # Get DLQ statistics
        dlq_stats = DLQService.get_stats_by_type()

        # Calculate some additional stats
        total_dlq_items = sum(stats["total"] for stats in dlq_stats.values())
        total_unreplayed = sum(stats["unreplayed"] for stats in dlq_stats.values())

        # Build response
        response_data = {
            "database": {
                "main_db_path": wal_info.get("main_db_path"),
                "main_db_size_bytes": wal_info.get("main_db_size_bytes", 0),
                "main_db_size_mb": round(wal_info.get("main_db_size_bytes", 0) / (1024 * 1024), 2),
            },
            "wal": {
                "wal_path": wal_info.get("wal_path"),
                "wal_pages": wal_info.get("wal_pages", 0),
                "wal_size_bytes": wal_info.get("wal_size_bytes", 0),
                "wal_size_mb": round(wal_info.get("wal_size_bytes", 0) / (1024 * 1024), 2),
                "checkpoint_needed": (
                    wal_info.get("wal_pages", 0) > 1000
                    or wal_info.get("wal_size_bytes", 0) > 64 * 1024 * 1024
                ),
            },
            "dlq": {
                "total_items": total_dlq_items,
                "unreplayed_items": total_unreplayed,
                "by_type": dlq_stats,
            },
            "thresholds": {
                "wal_max_pages": 1000,
                "wal_max_size_bytes": 64 * 1024 * 1024,
                "wal_max_size_mb": 64,
            },
        }

        # Add error info if present
        if "error" in wal_info:
            response_data["wal"]["error"] = wal_info["error"]

        logger.info(
            "Database debug stats requested",
            extra={
                "wal_pages": wal_info.get("wal_pages", 0),
                "wal_size_bytes": wal_info.get("wal_size_bytes", 0),
                "dlq_total": total_dlq_items,
                "dlq_unreplayed": total_unreplayed,
            },
        )

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error("Failed to get database debug stats: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {e}")


@router.get("/dbz/wal")
async def debug_wal_only(_: None = Depends(admin_required)) -> JSONResponse:
    """Debug endpoint specifically for WAL statistics."""
    try:
        wal_info = get_wal_info()

        response_data = {
            "wal_pages": wal_info.get("wal_pages", 0),
            "wal_size_bytes": wal_info.get("wal_size_bytes", 0),
            "wal_size_mb": round(wal_info.get("wal_size_bytes", 0) / (1024 * 1024), 2),
            "wal_path": wal_info.get("wal_path"),
            "checkpoint_needed": (
                wal_info.get("wal_pages", 0) > 1000
                or wal_info.get("wal_size_bytes", 0) > 64 * 1024 * 1024
            ),
            "thresholds": {"max_pages": 1000, "max_size_bytes": 64 * 1024 * 1024},
        }

        if "error" in wal_info:
            response_data["error"] = wal_info["error"]

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error("Failed to get WAL debug stats: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get WAL stats: {e}")


@router.get("/dbz/dlq")
async def debug_dlq_only(_: None = Depends(admin_required)) -> JSONResponse:
    """Debug endpoint specifically for DLQ statistics."""
    try:
        dlq_stats = DLQService.get_stats_by_type()
        recent_items = DLQService.get_dlq_items(only_unreplayed=True, limit=10)

        response_data = {
            "stats_by_type": dlq_stats,
            "total_items": sum(stats["total"] for stats in dlq_stats.values()),
            "unreplayed_items": sum(stats["unreplayed"] for stats in dlq_stats.values()),
            "recent_unreplayed": [
                {
                    "id": item.id,
                    "job_id": item.job_id,
                    "type": item.type,
                    "attempts": item.attempts,
                    "created_at": item.created_at,
                    "error_preview": item.error[:100] + "..."
                    if len(item.error) > 100
                    else item.error,
                }
                for item in recent_items
            ],
        }

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error("Failed to get DLQ debug stats: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get DLQ stats: {e}")
