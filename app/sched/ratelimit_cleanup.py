from __future__ import annotations

import logging

from app.metrics import sched_errors_total, sched_runs_total
from app.services.rate_limit import TokenBucket

logger = logging.getLogger(__name__)


def run_cleanup_job(bucket: TokenBucket, per: float) -> None:
    job = "ratelimit_cleanup"
    sched_runs_total.labels(job).inc()
    try:
        removed = bucket.cleanup(max_age=5 * per)
        logger.info("ratelimit cleanup removed=%s", removed)
    except Exception as exc:  # noqa: BLE001
        sched_errors_total.labels(job).inc()
        logger.error("ratelimit cleanup error: %s", exc)
