"""Dead Letter Queue service for failed jobs and updates.

Handles storage, retrieval, and replay of failed processing tasks.
"""
from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from ..db.session import execute_immediate, fetchall, fetchone
from ..metrics import dlq_size_gauge, dlq_in_total, dlq_replayed_total


logger = logging.getLogger(__name__)


@dataclass
class DLQItem:
    """Dead Letter Queue item representation."""
    id: int
    job_id: str
    type: str
    payload: Dict[str, Any]
    error: str
    attempts: int
    created_at: str
    last_attempt_at: Optional[str] = None
    replayed_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_row(cls, row: Any) -> "DLQItem":
        """Create DLQItem from database row."""
        return cls(
            id=row["id"],
            job_id=row["job_id"],
            type=row["type"],
            payload=json.loads(row["payload"]),
            error=row["error"],
            attempts=row["attempts"],
            created_at=row["created_at"],
            last_attempt_at=row["last_attempt_at"],
            replayed_at=row["replayed_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None
        )


class DLQService:
    """Service for managing Dead Letter Queue operations."""

    @staticmethod
    def add_to_dlq(
        job_id: str,
        job_type: str,
        payload: Dict[str, Any],
        error: Exception | str,
        attempts: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Add a failed job to the Dead Letter Queue.
        
        Args:
            job_id: Unique identifier for the job
            job_type: Type of job (update, webhook, scheduled_job, etc)
            payload: Original job data as dict
            error: Error that caused the failure
            attempts: Number of retry attempts made
            metadata: Optional additional metadata
            
        Returns:
            DLQ record ID
        """
        error_str = str(error)
        if isinstance(error, Exception):
            error_str = f"{error.__class__.__name__}: {error}\n{traceback.format_exc()}"

        dlq_id = execute_immediate(
            """
            INSERT INTO dlq (job_id, type, payload, error, attempts, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                job_type,
                json.dumps(payload),
                error_str,
                attempts,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(metadata) if metadata else None
            )
        )

        # Update metrics
        dlq_in_total.labels(type=job_type, reason="max_attempts_exceeded").inc()
        DLQService._update_size_gauge(job_type)

        logger.error(
            "Job moved to DLQ",
            extra={
                "dlq_id": dlq_id,
                "job_id": job_id,
                "job_type": job_type,
                "attempts": attempts,
                "error": str(error)[:200] + "..." if len(str(error)) > 200 else str(error)
            }
        )

        return dlq_id

    @staticmethod
    def get_dlq_item(dlq_id: int) -> Optional[DLQItem]:
        """Get a specific DLQ item by ID."""
        row = fetchone("SELECT * FROM dlq WHERE id = ?", (dlq_id,))
        return DLQItem.from_row(row) if row else None

    @staticmethod
    def get_dlq_items(
        job_type: Optional[str] = None,
        only_unreplayed: bool = True,
        limit: int = 100
    ) -> List[DLQItem]:
        """Get DLQ items with optional filtering.
        
        Args:
            job_type: Filter by job type
            only_unreplayed: Only return items not yet replayed
            limit: Maximum number of items to return
            
        Returns:
            List of DLQ items
        """
        conditions = []
        params = []

        if job_type:
            conditions.append("type = ?")
            params.append(job_type)

        if only_unreplayed:
            conditions.append("replayed_at IS NULL")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        rows = fetchall(
            f"""
            SELECT * FROM dlq 
            WHERE {where_clause}
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            params + [limit]
        )

        return [DLQItem.from_row(row) for row in rows]

    @staticmethod
    def mark_replayed(dlq_id: int) -> bool:
        """Mark a DLQ item as successfully replayed.
        
        Args:
            dlq_id: DLQ record ID
            
        Returns:
            True if item was found and marked, False otherwise
        """
        # Get item info for metrics before updating
        item = DLQService.get_dlq_item(dlq_id)
        if not item:
            return False

        rows_affected = execute_immediate(
            """
            UPDATE dlq 
            SET replayed_at = ?
            WHERE id = ? AND replayed_at IS NULL
            """,
            (datetime.now(timezone.utc).isoformat(), dlq_id)
        )

        if rows_affected > 0:
            # Update metrics
            dlq_replayed_total.labels(type=item.type).inc()
            DLQService._update_size_gauge(item.type)

            logger.info(
                "DLQ item replayed successfully",
                extra={
                    "dlq_id": dlq_id,
                    "job_id": item.job_id,
                    "job_type": item.type
                }
            )
            return True

        return False

    @staticmethod
    def get_stats_by_type() -> Dict[str, Dict[str, int]]:
        """Get DLQ statistics grouped by job type.
        
        Returns:
            Dict with type as key and stats dict as value
            Example: {"update": {"total": 10, "unreplayed": 3}, ...}
        """
        rows = fetchall(
            """
            SELECT 
                type,
                COUNT(*) as total,
                COUNT(CASE WHEN replayed_at IS NULL THEN 1 END) as unreplayed,
                COUNT(CASE WHEN replayed_at IS NOT NULL THEN 1 END) as replayed
            FROM dlq 
            GROUP BY type
            ORDER BY total DESC
            """
        )

        return {
            row["type"]: {
                "total": row["total"],
                "unreplayed": row["unreplayed"], 
                "replayed": row["replayed"]
            }
            for row in rows
        }

    @staticmethod
    def cleanup_old_replayed(days_old: int = 30) -> int:
        """Remove old replayed items from DLQ.
        
        Args:
            days_old: Remove replayed items older than this many days
            
        Returns:
            Number of items removed
        """
        rows_affected = execute_immediate(
            """
            DELETE FROM dlq 
            WHERE replayed_at IS NOT NULL 
            AND replayed_at < datetime('now', '-' || ? || ' days')
            """,
            (days_old,)
        )

        logger.info(f"Cleaned up {rows_affected} old replayed DLQ items")
        
        # Update gauges for all types
        stats = DLQService.get_stats_by_type()
        for job_type in stats:
            DLQService._update_size_gauge(job_type)
            
        return rows_affected

    @staticmethod
    def _update_size_gauge(job_type: str) -> None:
        """Update the DLQ size gauge for a specific job type."""
        count = fetchone(
            "SELECT COUNT(*) as count FROM dlq WHERE type = ? AND replayed_at IS NULL",
            (job_type,)
        )
        if count:
            dlq_size_gauge.labels(type=job_type).set(count["count"])


# Convenience functions for common operations
def add_failed_update_to_dlq(update_data: Dict[str, Any], error: Exception, attempts: int) -> int:
    """Add a failed Telegram update to DLQ."""
    update_id = update_data.get("update_id", "unknown")
    return DLQService.add_to_dlq(
        job_id=f"update_{update_id}",
        job_type="update",
        payload=update_data,
        error=error,
        attempts=attempts,
        metadata={
            "chat_id": update_data.get("message", {}).get("chat", {}).get("id"),
            "user_id": update_data.get("message", {}).get("from", {}).get("id")
        }
    )


def add_failed_job_to_dlq(job_name: str, job_data: Dict[str, Any], error: Exception, attempts: int) -> int:
    """Add a failed scheduled job to DLQ."""
    return DLQService.add_to_dlq(
        job_id=f"job_{job_name}_{datetime.now().timestamp()}",
        job_type="scheduled_job",
        payload={"job_name": job_name, "job_data": job_data},
        error=error,
        attempts=attempts,
        metadata={"job_name": job_name}
    )
