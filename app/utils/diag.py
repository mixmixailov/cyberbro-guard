from __future__ import annotations

import contextvars
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, NoReturn, TypeVar

__all__ = [
    "assert_never",
    "trace_section", 
    "timer",
    "set_trace_id",
    "set_issue_id",
    "set_hypothesis_id",
    "get_trace_id",
    "get_issue_id", 
    "get_hypothesis_id",
]

T = TypeVar("T")

# Diagnostic context variables
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)
issue_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "issue_id", default=None  
)
hypothesis_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "hypothesis_id", default=None
)

logger = logging.getLogger(__name__)


def assert_never(value: NoReturn) -> NoReturn:
    """Type-safe exhaustiveness check for union types.
    
    Use in switch statements to ensure all cases are handled:
    
    match status:
        case "pending":
            ...
        case "completed":
            ...
        case _:
            assert_never(status)  # Will error if new status added
    """
    raise AssertionError(f"Unreachable code: unexpected value {value!r}")


def set_trace_id(trace_id: str | None) -> None:
    """Set trace ID for diagnostic correlation across operations."""
    trace_id_var.set(trace_id)


def set_issue_id(issue_id: str | None) -> None:
    """Set issue ID for bug tracking correlation."""
    issue_id_var.set(issue_id)


def set_hypothesis_id(hypothesis_id: str | None) -> None:  
    """Set hypothesis ID for debugging/testing correlation."""
    hypothesis_id_var.set(hypothesis_id)


def get_trace_id() -> str | None:
    """Get current trace ID."""
    return trace_id_var.get()


def get_issue_id() -> str | None:
    """Get current issue ID."""
    return issue_id_var.get()


def get_hypothesis_id() -> str | None:
    """Get current hypothesis ID."""
    return hypothesis_id_var.get()


@contextmanager
def trace_section(name: str, *, auto_trace: bool = True) -> Iterator[str]:
    """Context manager for tracing code sections with structured logging.
    
    Args:
        name: Human-readable name for the section
        auto_trace: Whether to auto-generate trace_id if not set
        
    Returns:
        The trace_id being used for this section
        
    Example:
        with trace_section("payment_processing") as trace_id:
            # All logs in this section will include the trace_id
            logger.info("Processing payment", extra={"amount": 100})
            process_payment()
    """
    trace_id = get_trace_id()
    
    if trace_id is None and auto_trace:
        trace_id = str(uuid.uuid4())[:8]  # Short trace ID
        set_trace_id(trace_id)
        auto_generated = True
    else:
        auto_generated = False
    
    logger.info(f"Entering section: {name}", extra={
        "section": name,
        "trace_id": trace_id,
        "event": "section_enter"
    })
    
    start_time = time.perf_counter()
    
    try:
        yield trace_id or ""
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"Section failed: {name}", extra={
            "section": name,
            "trace_id": trace_id,
            "event": "section_error",
            "duration_ms": round(duration * 1000, 2),
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise
    else:
        duration = time.perf_counter() - start_time
        logger.info(f"Exiting section: {name}", extra={
            "section": name,
            "trace_id": trace_id,
            "event": "section_exit",
            "duration_ms": round(duration * 1000, 2)
        })
    finally:
        if auto_generated:
            set_trace_id(None)


@contextmanager  
def timer(label: str) -> Iterator[None]:
    """Context manager for timing operations with structured logging.
    
    Args:
        label: Human-readable label for the timed operation
        
    Example:
        with timer("database_query"):
            result = db.execute(query)
    """
    trace_id = get_trace_id()
    issue_id = get_issue_id()
    hypothesis_id = get_hypothesis_id()
    
    logger.info(f"Timer start: {label}", extra={
        "timer": label,
        "event": "timer_start",
        "trace_id": trace_id,
        "issue_id": issue_id,
        "hypothesis_id": hypothesis_id
    })
    
    start_time = time.perf_counter()
    
    try:
        yield
    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(f"Timer failed: {label}", extra={
            "timer": label,
            "event": "timer_error", 
            "duration_ms": round(duration * 1000, 2),
            "trace_id": trace_id,
            "issue_id": issue_id,
            "hypothesis_id": hypothesis_id,
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise
    else:
        duration = time.perf_counter() - start_time
        logger.info(f"Timer end: {label}", extra={
            "timer": label,
            "event": "timer_end",
            "duration_ms": round(duration * 1000, 2),
            "trace_id": trace_id,
            "issue_id": issue_id,
            "hypothesis_id": hypothesis_id
        })
