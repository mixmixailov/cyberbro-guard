from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator, TypeVar

from app.config import get_settings

__all__ = [
    "setup_area_logging",
    "area_context", 
    "job_context",
    "exception_tracker",
    "enhanced_pii_redaction",
]

F = TypeVar("F", bound=Callable[..., Any])

# Enhanced PII patterns for better redaction
ENHANCED_PII_PATTERNS = {
    "email": re.compile(r"([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"),
    "phone": re.compile(r"\b(?:\+?\d[\s\-]?)?(?:\(?\d{2,3}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{2,4}\b"),
    "token": re.compile(r"\b(?:Bearer|Bot)\s+([A-Za-z0-9:_\-]{16,})\b", re.IGNORECASE),
    "api_key": re.compile(r"\b(?:api_key|apikey|secret|password|token)['\"]\s*:\s*['\"]([\w\-]{8,})['\"]\b", re.IGNORECASE),
    "credit_card": re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "url_auth": re.compile(r"https?://[^:\s]+:[^@\s]+@[^\s]+", re.IGNORECASE),
}


def setup_area_logging() -> None:
    """Configure area-specific logging based on DEBUG_TRACE setting."""
    settings = get_settings()
    debug_areas = set()
    
    if settings.DEBUG_TRACE:
        debug_areas = {area.strip().lower() for area in settings.DEBUG_TRACE.split(",") if area.strip()}
    
    # Configure loggers for specific areas
    for area in debug_areas:
        logger_name = f"app.{area}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        
        # Add specific handler if needed for area debugging
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            logger.propagate = True  # Ensure it still goes to root logger


def enhanced_pii_redaction(text: str, aggressive: bool = False) -> str:
    """Enhanced PII redaction with configurable aggressiveness.
    
    Args:
        text: Text to redact
        aggressive: If True, redact more patterns (IPs, partial card numbers, etc.)
    """
    result = text
    
    # Always redact these
    for pattern_name, pattern in ENHANCED_PII_PATTERNS.items():
        if pattern_name in ("email", "token", "api_key"):
            if pattern_name == "email":
                result = pattern.sub(lambda m: f"***@{m.group(2)}", result)
            elif pattern_name == "token":
                result = pattern.sub(lambda m: f"{m.group(0).split()[0]} {m.group(1)[:3]}***{m.group(1)[-4:]}", result)
            elif pattern_name == "api_key":
                result = pattern.sub(lambda m: f"{m.group(0).split(':')[0]}: \"***{m.group(1)[-4:]}\"", result)
    
    # Aggressive redaction for DEBUG_TRACE mode
    if aggressive:
        for pattern_name, pattern in ENHANCED_PII_PATTERNS.items():
            if pattern_name in ("phone", "credit_card", "ssn", "ip_address", "url_auth"):
                if pattern_name == "phone":
                    result = pattern.sub(lambda m: f"***{m.group(0)[-4:]}", result)
                elif pattern_name == "credit_card":
                    result = pattern.sub("****-****-****-****", result)
                elif pattern_name == "ssn":
                    result = pattern.sub("***-**-****", result)
                elif pattern_name == "ip_address":
                    result = pattern.sub(lambda m: f"{m.group(0).split('.')[0]}.***.***.***", result)
                elif pattern_name == "url_auth":
                    result = pattern.sub(lambda m: m.group(0).split('@')[0].split('://')[0] + "://***:***@" + m.group(0).split('@')[1], result)
    
    return result


@contextmanager
def area_context(area: str) -> Iterator[None]:
    """Context manager to set current processing area for observability."""
    from app.utils.logging import set_area
    
    old_area = None
    try:
        # Save previous area if any
        from app.utils.logging import get_area
        old_area = get_area()
        
        set_area(area)
        
        # Check if this area should have DEBUG logging
        settings = get_settings()
        if settings.DEBUG_TRACE:
            debug_areas = {a.strip().lower() for a in settings.DEBUG_TRACE.split(",") if a.strip()}
            if area.lower() in debug_areas:
                logger = logging.getLogger(f"app.{area}")
                logger.debug(f"Entering area: {area}")
        
        yield
    finally:
        # Restore previous area
        set_area(old_area)


@contextmanager
def job_context(job_id: str) -> Iterator[None]:
    """Context manager to set current job ID for observability."""
    from app.utils.logging import set_job_id, get_job_id
    
    old_job_id = get_job_id()
    try:
        set_job_id(job_id)
        yield
    finally:
        set_job_id(old_job_id)


def exception_tracker(area: str) -> Callable[[F], F]:
    """Decorator to track exceptions by area for Prometheus metrics.
    
    Args:
        area: Processing area name (e.g., "handlers", "services", "payments")
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Import here to avoid circular imports
                from app.metrics import exceptions_total
                
                exception_type = type(e).__name__
                exceptions_total.labels(area=area, exception_type=exception_type).inc()
                
                # Log with enhanced context
                logger = logging.getLogger(func.__module__)
                logger.error(
                    f"Exception in {area}: {exception_type}",
                    extra={
                        "area": area,
                        "exception_type": exception_type,
                        "function": func.__name__,
                        "error": str(e),
                    },
                    exc_info=True
                )
                raise
        
        # Handle async functions
        import asyncio
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    from app.metrics import exceptions_total
                    
                    exception_type = type(e).__name__
                    exceptions_total.labels(area=area, exception_type=exception_type).inc()
                    
                    logger = logging.getLogger(func.__module__)
                    logger.error(
                        f"Exception in {area}: {exception_type}",
                        extra={
                            "area": area,
                            "exception_type": exception_type,
                            "function": func.__name__,
                            "error": str(e),
                        },
                        exc_info=True
                    )
                    raise
            
            return async_wrapper  # type: ignore
        
        return wrapper  # type: ignore
    
    return decorator


def get_debug_trace_areas() -> set[str]:
    """Get list of areas that have DEBUG_TRACE enabled."""
    settings = get_settings()
    if not settings.DEBUG_TRACE:
        return set()
    
    return {area.strip().lower() for area in settings.DEBUG_TRACE.split(",") if area.strip()}


def should_debug_area(area: str) -> bool:
    """Check if given area should have DEBUG logging enabled."""
    debug_areas = get_debug_trace_areas()
    return area.lower() in debug_areas


# Context manager for enhanced PII logging in debug mode
@contextmanager
def debug_context(area: str, enhanced_pii: bool = True) -> Iterator[None]:
    """Combined context for area + enhanced PII redaction when in debug mode."""
    with area_context(area):
        if should_debug_area(area) and enhanced_pii:
            # Temporarily patch the PII masking function
            from app.utils import logging as logging_module
            original_mask_pii = logging_module.mask_pii
            
            def enhanced_mask_pii(text: str) -> str:
                return enhanced_pii_redaction(text, aggressive=True)
            
            logging_module.mask_pii = enhanced_mask_pii
            try:
                yield
            finally:
                logging_module.mask_pii = original_mask_pii
        else:
            yield
