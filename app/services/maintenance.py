"""Maintenance service for periodic database operations.

Handles WAL checkpoint operations and other maintenance tasks.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from ..config import get_settings
from ..db.session import checkpoint_wal, get_wal_info
from ..metrics import (
    checkpoint_duration_seconds,
    checkpoint_performed_total,
    wal_pages,
    wal_size_bytes,
)

logger = logging.getLogger(__name__)


class MaintenanceService:
    """Service for periodic database maintenance operations."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._settings = get_settings()

    async def start(self) -> None:
        """Start the maintenance service."""
        if self._task and not self._task.done():
            logger.warning("Maintenance service already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._maintenance_loop())
        logger.info("Maintenance service started")

    async def stop(self) -> None:
        """Stop the maintenance service."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error("Error stopping maintenance service: %s", e)

        logger.info("Maintenance service stopped")

    async def _maintenance_loop(self) -> None:
        """Main maintenance loop."""
        while self._running:
            try:
                # Update WAL metrics
                await self._update_wal_metrics()

                # Check if WAL checkpoint is needed
                await self._check_and_checkpoint()

                # Wait for next iteration (5 minutes)
                await asyncio.sleep(300)  # 5 minutes = 300 seconds

            except asyncio.CancelledError:
                logger.info("Maintenance loop cancelled")
                break
            except Exception as e:
                logger.error("Error in maintenance loop: %s", e, exc_info=True)
                # Wait a bit before retrying to avoid tight error loops
                await asyncio.sleep(30)

    async def _update_wal_metrics(self) -> None:
        """Update WAL-related Prometheus metrics."""
        try:
            # Run in thread to avoid blocking event loop
            wal_info = await asyncio.to_thread(get_wal_info)

            # Update gauges
            wal_pages.set(wal_info.get("wal_pages", 0))
            wal_size_bytes.set(wal_info.get("wal_size_bytes", 0))

            logger.debug(
                "WAL metrics updated",
                extra={
                    "wal_pages": wal_info.get("wal_pages", 0),
                    "wal_size_bytes": wal_info.get("wal_size_bytes", 0),
                },
            )

        except Exception as e:
            logger.error("Failed to update WAL metrics: %s", e)

    async def _check_and_checkpoint(self) -> None:
        """Check if WAL checkpoint is needed and perform it."""
        try:
            # Get current WAL info
            wal_info = await asyncio.to_thread(get_wal_info)

            wal_pages_count = wal_info.get("wal_pages", 0)
            wal_size = wal_info.get("wal_size_bytes", 0)

            # Define thresholds
            MAX_WAL_PAGES = 1000
            MAX_WAL_SIZE_BYTES = 64 * 1024 * 1024  # 64MB

            should_checkpoint = wal_pages_count > MAX_WAL_PAGES or wal_size > MAX_WAL_SIZE_BYTES

            if should_checkpoint:
                logger.info(
                    "WAL checkpoint triggered",
                    extra={
                        "wal_pages": wal_pages_count,
                        "wal_size_bytes": wal_size,
                        "max_pages": MAX_WAL_PAGES,
                        "max_size_bytes": MAX_WAL_SIZE_BYTES,
                        "reason": "pages" if wal_pages_count > MAX_WAL_PAGES else "size",
                    },
                )

                # Perform checkpoint in thread
                result = await asyncio.to_thread(checkpoint_wal, "TRUNCATE")

                # Update metrics
                status = "success" if result.get("success") else "error"
                checkpoint_performed_total.labels(mode="TRUNCATE", status=status).inc()

                if result.get("success"):
                    duration_seconds = result.get("duration_ms", 0) / 1000.0
                    checkpoint_duration_seconds.labels(mode="TRUNCATE").observe(duration_seconds)

            else:
                logger.debug(
                    "WAL checkpoint not needed",
                    extra={
                        "wal_pages": wal_pages_count,
                        "wal_size_bytes": wal_size,
                        "max_pages": MAX_WAL_PAGES,
                        "max_size_bytes": MAX_WAL_SIZE_BYTES,
                    },
                )

        except Exception as e:
            logger.error("Failed to check/perform WAL checkpoint: %s", e, exc_info=True)

    async def force_checkpoint(self, mode: str = "TRUNCATE") -> Dict[str, Any]:
        """Force a WAL checkpoint operation.

        Args:
            mode: Checkpoint mode (PASSIVE, FULL, RESTART, TRUNCATE)

        Returns:
            Checkpoint operation result
        """
        logger.info("Force checkpoint requested", extra={"mode": mode})

        try:
            result = await asyncio.to_thread(checkpoint_wal, mode)

            # Update metrics
            status = "success" if result.get("success") else "error"
            checkpoint_performed_total.labels(mode=mode, status=status).inc()

            if result.get("success"):
                duration_seconds = result.get("duration_ms", 0) / 1000.0
                checkpoint_duration_seconds.labels(mode=mode).observe(duration_seconds)

            return result

        except Exception as e:
            logger.error("Force checkpoint failed: %s", e, exc_info=True)
            checkpoint_performed_total.labels(mode=mode, status="error").inc()
            return {"success": False, "mode": mode, "error": str(e)}

    async def get_maintenance_status(self) -> Dict[str, Any]:
        """Get current maintenance service status."""
        wal_info = await asyncio.to_thread(get_wal_info)

        return {
            "running": self._running,
            "task_done": self._task.done() if self._task else True,
            "wal_info": wal_info,
            "thresholds": {"max_wal_pages": 1000, "max_wal_size_bytes": 64 * 1024 * 1024},
        }
