from __future__ import annotations

import inspect
import time

from fastapi import APIRouter
from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest
from starlette_exporter import PrometheusMiddleware, handle_metrics

router = APIRouter()

updates_total = Counter(
    "cyberbro_updates_total",
    "Total updates",
    labelnames=("type", "chat_type"),
    registry=REGISTRY,
)

commands_total = Counter(
    "cyberbro_commands_total",
    "Total commands",
    labelnames=("command",),
    registry=REGISTRY,
)

moderation_actions_total = Counter(
    "cyberbro_moderation_actions_total",
    "Total moderation actions",
    labelnames=("action",),
    registry=REGISTRY,
)

payments_total = Counter(
    "cyberbro_payments_total",
    "Total payments",
    labelnames=("status",),
    registry=REGISTRY,
)

idmp_purged_total = Counter(
    "cyberbro_idmp_purged_total",
    "Idempotency rows purged",
    registry=REGISTRY,
)

# Webhook latency (handlers)
webhook_latency_seconds = Histogram(
    "cyberbro_webhook_latency_seconds",
    "Webhook handling latency seconds",
    labelnames=("handler",),
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

# AI latency histogram (reused by guard)
ai_latency_seconds = Histogram(
    "cyberbro_ai_latency_seconds",
    "AI moderation call latency seconds (including retries)",
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

# Scheduler counters
sched_runs_total = Counter(
    "cyberbro_sched_runs_total",
    "Scheduler job runs",
    labelnames=("job",),
    registry=REGISTRY,
)

sched_errors_total = Counter(
    "cyberbro_sched_errors_total",
    "Scheduler job errors",
    labelnames=("job",),
    registry=REGISTRY,
)

ai_skipped_total = Counter(
    "cyberbro_ai_skipped_total",
    "AI moderation skipped",
    labelnames=("reason",),
    registry=REGISTRY,
)

# Send queue retry metrics
retry_total = Counter(
    "cyberbro_retry_total",
    "Total send queue retries",
    labelnames=("reason",),
    registry=REGISTRY,
)

backoff_seconds = Histogram(
    "cyberbro_backoff_seconds",
    "Send queue backoff delay in seconds",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, float("inf")),
    registry=REGISTRY,
)

# Dead Letter Queue metrics
dlq_size_gauge = Gauge(
    "cyberbro_dlq_size",
    "Current number of items in Dead Letter Queue",
    labelnames=("type",),
    registry=REGISTRY,
)

dlq_in_total = Counter(
    "cyberbro_dlq_in_total",
    "Total items moved to Dead Letter Queue",
    labelnames=("type", "reason"),
    registry=REGISTRY,
)

dlq_replayed_total = Counter(
    "cyberbro_dlq_replayed_total",
    "Total items successfully replayed from Dead Letter Queue",
    labelnames=("type",),
    registry=REGISTRY,
)

# WAL checkpoint metrics
wal_pages = Gauge(
    "cyberbro_wal_pages",
    "Current number of pages in WAL file",
    registry=REGISTRY,
)

wal_size_bytes = Gauge(
    "cyberbro_wal_size_bytes",
    "Current WAL file size in bytes",
    registry=REGISTRY,
)

checkpoint_performed_total = Counter(
    "cyberbro_checkpoint_performed_total",
    "Total WAL checkpoints performed",
    labelnames=("mode", "status"),
    registry=REGISTRY,
)

checkpoint_duration_seconds = Histogram(
    "cyberbro_checkpoint_duration_seconds",
    "WAL checkpoint operation duration in seconds",
    labelnames=("mode",),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float("inf")),
    registry=REGISTRY,
)


def timeit(hist: Histogram, label_value: str):  # type: ignore[name-defined]
    def decorator(fn):  # type: ignore[no-untyped-def]
        if inspect.iscoroutinefunction(fn):

            async def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
                start = time.perf_counter()
                try:
                    return await fn(*args, **kwargs)
                finally:
                    try:
                        hist.labels(label_value).observe(time.perf_counter() - start)
                    except Exception:
                        pass

            return wrapped
        else:

            def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
                start = time.perf_counter()
                try:
                    return fn(*args, **kwargs)
                finally:
                    try:
                        hist.labels(label_value).observe(time.perf_counter() - start)
                    except Exception:
                        pass

            return wrapped

    return decorator


webhook_dropped_total = Counter(
    "cyberbro_webhook_dropped_total",
    "Webhook updates dropped (duplicates/filtered/too_large)",
    labelnames=("reason",),
    registry=REGISTRY,
)

webhook_errors_total = Counter(
    "cyberbro_webhook_errors_total",
    "Webhook processing errors",
    labelnames=("stage",),
    registry=REGISTRY,
)

# Exception tracking by area
exceptions_total = Counter(
    "cyberbro_exceptions_total",
    "Total exceptions by area and type",
    labelnames=("area", "exception_type"),
    registry=REGISTRY,
)

# Handler latency (enhanced from existing webhook_latency_seconds)
handler_latency_seconds = Histogram(
    "cyberbro_handler_latency_seconds",
    "Handler processing latency in seconds",
    labelnames=("area", "handler"),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)


def attach_exporter(app) -> None:  # type: ignore[no-untyped-def]
    # Starlette exporter middleware collects default http_* metrics.
    # Ensure path label is low-cardinality; library sanitizes automatically.
    app.add_middleware(PrometheusMiddleware, group_paths=True)
    app.add_route("/metrics", handle_metrics)


# Expose registry and generate_latest for tests/utilities
registry = REGISTRY
