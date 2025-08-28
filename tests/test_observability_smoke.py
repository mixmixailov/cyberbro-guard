from __future__ import annotations

import logging
import os
import time
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.utils.observability import (
    area_context,
    debug_context,
    enhanced_pii_redaction,
    exception_tracker,
    get_debug_trace_areas,
    job_context,
    should_debug_area,
    setup_area_logging,
)


def test_enhanced_pii_redaction():
    """Test enhanced PII redaction patterns."""
    # Basic redaction
    text = "Contact user@example.com with token Bot 123456:ABC-DEF"
    result = enhanced_pii_redaction(text, aggressive=False)
    assert "***@example.com" in result
    assert "Bot ***-DEF" in result
    
    # Aggressive redaction
    sensitive_text = "IP: 192.168.1.1, Card: 4532-1234-5678-9012"
    result = enhanced_pii_redaction(sensitive_text, aggressive=True)
    assert "192.***.***.***" in result
    assert "****-****-****-****" in result


def test_area_context(caplog):
    """Test area context setting."""
    caplog.set_level(logging.INFO)
    
    from app.utils.logging import get_area
    
    # Initially no area
    assert get_area() is None
    
    # Set area
    with area_context("payments"):
        assert get_area() == "payments"
        logging.getLogger("test").info("Test message")
    
    # Area cleared after context
    assert get_area() is None


def test_job_context():
    """Test job context setting.""" 
    from app.utils.logging import get_job_id
    
    # Initially no job_id
    assert get_job_id() is None
    
    # Set job_id
    with job_context("job-123"):
        assert get_job_id() == "job-123"
    
    # Job ID cleared after context
    assert get_job_id() is None


def test_nested_contexts():
    """Test nested area and job contexts."""
    from app.utils.logging import get_area, get_job_id
    
    with area_context("services"):
        assert get_area() == "services"
        
        with job_context("job-456"):
            assert get_area() == "services"
            assert get_job_id() == "job-456"
            
            # Nested area
            with area_context("payments"):
                assert get_area() == "payments"
                assert get_job_id() == "job-456"
            
            # Back to services
            assert get_area() == "services"
            assert get_job_id() == "job-456"
    
    # All cleared
    assert get_area() is None
    assert get_job_id() is None


@patch.dict(os.environ, {"DEBUG_TRACE": "handlers,payments"})
def test_debug_trace_areas():
    """Test DEBUG_TRACE parsing."""
    # Force settings refresh
    settings = get_settings()
    assert settings.DEBUG_TRACE == "handlers,payments"
    
    debug_areas = get_debug_trace_areas()
    assert debug_areas == {"handlers", "payments"}
    
    assert should_debug_area("handlers")
    assert should_debug_area("payments")
    assert not should_debug_area("services")


@patch.dict(os.environ, {"DEBUG_TRACE": ""})
def test_debug_trace_disabled():
    """Test behavior when DEBUG_TRACE is empty."""
    debug_areas = get_debug_trace_areas()
    assert debug_areas == set()
    
    assert not should_debug_area("handlers")


def test_exception_tracker_sync():
    """Test exception tracking for sync functions."""
    from app.metrics import exceptions_total
    
    @exception_tracker("test_area")
    def failing_function():
        raise ValueError("test error")
    
    # Get initial count
    initial_count = exceptions_total.labels(area="test_area", exception_type="ValueError")._value._value
    
    with pytest.raises(ValueError, match="test error"):
        failing_function()
    
    # Count should have increased
    final_count = exceptions_total.labels(area="test_area", exception_type="ValueError")._value._value
    assert final_count > initial_count


@pytest.mark.asyncio
async def test_exception_tracker_async():
    """Test exception tracking for async functions."""
    from app.metrics import exceptions_total
    
    @exception_tracker("async_area")
    async def failing_async_function():
        raise RuntimeError("async error")
    
    # Get initial count
    initial_count = exceptions_total.labels(area="async_area", exception_type="RuntimeError")._value._value
    
    with pytest.raises(RuntimeError, match="async error"):
        await failing_async_function()
    
    # Count should have increased
    final_count = exceptions_total.labels(area="async_area", exception_type="RuntimeError")._value._value
    assert final_count > initial_count


@patch.dict(os.environ, {"DEBUG_TRACE": "test_debug"})
def test_debug_context(caplog):
    """Test debug context with enhanced PII."""
    caplog.set_level(logging.DEBUG)
    
    # Setup area logging first
    setup_area_logging()
    
    with debug_context("test_debug", enhanced_pii=True):
        logger = logging.getLogger("app.test_debug")
        logger.debug("Debug message with email: user@example.com")
    
    # Should see debug message if DEBUG_TRACE includes the area
    debug_messages = [record for record in caplog.records if record.levelname == "DEBUG"]
    assert len(debug_messages) > 0


def test_setup_area_logging():
    """Test area logging setup."""
    with patch.dict(os.environ, {"DEBUG_TRACE": "test_setup"}):
        setup_area_logging()
        
        logger = logging.getLogger("app.test_setup")
        assert logger.level == logging.DEBUG


# Integration test
def test_full_observability_integration(caplog):
    """Test complete observability workflow."""
    caplog.set_level(logging.INFO)
    
    # Setup
    with patch.dict(os.environ, {"DEBUG_TRACE": "integration"}):
        setup_area_logging()
        
        from app.utils.diag import set_issue_id, set_trace_id
        from app.utils.logging import set_update_context
        
        # Set diagnostic context
        set_issue_id("test-issue-123")
        set_trace_id("trace-abc")
        set_update_context(update_id=789, chat_id=456, user_id=123)
        
        # Test complete workflow
        with area_context("integration"):
            with job_context("integration-job"):
                logger = logging.getLogger("test.integration")
                logger.info("Integration test message")
                
                # Test exception tracking
                @exception_tracker("integration")
                def test_exception():
                    raise ValueError("integration test error")
                
                with pytest.raises(ValueError):
                    test_exception()
        
        # Verify logging structure
        log_records = [record for record in caplog.records if "integration" in record.message]
        assert len(log_records) >= 1


if __name__ == "__main__":
    # Self-check instructions
    print("🔍 Running observability smoke tests...")
    print("Expected output:")
    print("- All tests should pass")
    print("- PII redaction should mask sensitive data")
    print("- Area/job contexts should be properly managed")
    print("- Exception tracking should increment metrics")
    print("- DEBUG_TRACE should enable area-specific debugging")
    
    # Quick smoke test
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("\n📊 Quick observability test:")
    
    # Test PII redaction
    test_text = "User email: test@example.com, token: Bot 123456:ABC-DEF"
    redacted = enhanced_pii_redaction(test_text)
    print(f"PII Redaction: {redacted}")
    
    # Test area context
    with area_context("smoke_test"):
        with job_context("smoke-job"):
            from app.utils.logging import get_area, get_job_id
            print(f"Area: {get_area()}, Job ID: {get_job_id()}")
    
    print("✅ Observability smoke test completed")
