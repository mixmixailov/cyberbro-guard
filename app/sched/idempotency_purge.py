from __future__ import annotations

import logging
import time

from prometheus_client import Histogram
from app.metrics import sched_runs_total, sched_errors_total

from app.services.idempotency import IdempotencyStore
from app.metrics import idmp_purged_total


logger = logging.getLogger(__name__)

purge_seconds = Histogram(
    "cyberbro_idmp_purge_seconds",
    "Idempotency purge duration seconds",
)


def run_purge_job() -> None:
    job = "idmp_purge"
    sched_runs_total.labels(job).inc()
    store = IdempotencyStore()
    start = time.perf_counter()
    try:
        purged = store.purge_expired(limit=1000)
        idmp_purged_total.inc(purged)
        logger.info("idmp purge purged=%s", purged)
    except Exception as exc:  # noqa: BLE001
        sched_errors_total.labels(job).inc()
        logger.error("idmp purge error: %s", exc)
    finally:
        purge_seconds.observe(time.perf_counter() - start)


