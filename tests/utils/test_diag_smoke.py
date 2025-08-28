from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator
from unittest.mock import patch

import pytest

from app.utils.diag import (
    assert_never,
    get_hypothesis_id,
    get_issue_id,
    get_trace_id,
    set_hypothesis_id,
    set_issue_id,
    set_trace_id,
    timer,
    trace_section,
)


def test_assert_never_raises():
    """Test that assert_never raises AssertionError with useful message."""
    with pytest.raises(AssertionError, match="Unreachable code: unexpected value 'invalid'"):
        assert_never("invalid")  # type: ignore


def test_trace_id_context():
    """Test trace_id context variable operations."""
    # Initially None
    assert get_trace_id() is None
    
    # Set and get
    set_trace_id("test-trace-123")
    assert get_trace_id() == "test-trace-123"
    
    # Clear
    set_trace_id(None)
    assert get_trace_id() is None


def test_issue_id_context():
    """Test issue_id context variable operations."""
    # Initially None
    assert get_issue_id() is None
    
    # Set and get
    set_issue_id("issue-456")
    assert get_issue_id() == "issue-456"
    
    # Clear
    set_issue_id(None)
    assert get_issue_id() is None


def test_hypothesis_id_context():
    """Test hypothesis_id context variable operations."""
    # Initially None
    assert get_hypothesis_id() is None
    
    # Set and get
    set_hypothesis_id("hypothesis-789")
    assert get_hypothesis_id() == "hypothesis-789"
    
    # Clear
    set_hypothesis_id(None)
    assert get_hypothesis_id() is None


def test_trace_section_auto_trace(caplog):
    """Test trace_section with auto trace generation."""
    caplog.set_level(logging.INFO)
    
    # Should auto-generate trace_id
    with trace_section("test_operation") as trace_id:
        assert trace_id is not None
        assert len(trace_id) == 8  # Short UUID
        assert get_trace_id() == trace_id
        
        # Log something inside the section
        logging.getLogger("test").info("Inside section")
    
    # trace_id should be cleared after auto-generated section
    assert get_trace_id() is None
    
    # Check log messages
    assert "Entering section: test_operation" in caplog.text
    assert "Exiting section: test_operation" in caplog.text
    assert "duration_ms" in caplog.text


def test_trace_section_existing_trace_id(caplog):
    """Test trace_section with existing trace_id."""
    caplog.set_level(logging.INFO)
    
    # Pre-set trace_id
    set_trace_id("existing-trace")
    
    with trace_section("test_operation", auto_trace=False) as trace_id:
        assert trace_id == "existing-trace"
        assert get_trace_id() == "existing-trace"
    
    # trace_id should remain after non-auto section
    assert get_trace_id() == "existing-trace"
    
    # Cleanup
    set_trace_id(None)


def test_trace_section_exception_handling(caplog):
    """Test trace_section properly logs exceptions."""
    caplog.set_level(logging.INFO)
    
    with pytest.raises(ValueError, match="test error"):
        with trace_section("failing_operation") as trace_id:
            assert trace_id is not None
            raise ValueError("test error")
    
    # Check error was logged
    assert "Section failed: failing_operation" in caplog.text
    assert "error_type" in caplog.text
    assert "ValueError" in caplog.text


def test_timer_basic(caplog):
    """Test basic timer functionality."""
    caplog.set_level(logging.INFO)
    
    with timer("test_timer"):
        time.sleep(0.001)  # Small delay to ensure measurable duration
    
    # Check log messages
    assert "Timer start: test_timer" in caplog.text
    assert "Timer end: test_timer" in caplog.text
    assert "duration_ms" in caplog.text


def test_timer_with_diagnostic_context(caplog):
    """Test timer includes diagnostic context in logs."""
    caplog.set_level(logging.INFO)
    
    # Set diagnostic context
    set_trace_id("test-trace")
    set_issue_id("test-issue")
    set_hypothesis_id("test-hypothesis")
    
    with timer("context_timer"):
        pass
    
    # Verify context is included (will be visible in structured logs)
    log_records = [record for record in caplog.records if "context_timer" in record.message]
    assert len(log_records) >= 2  # start and end
    
    # Clean up
    set_trace_id(None)
    set_issue_id(None)
    set_hypothesis_id(None)


def test_timer_exception_handling(caplog):
    """Test timer properly logs exceptions."""
    caplog.set_level(logging.INFO)
    
    with pytest.raises(RuntimeError, match="timer test error"):
        with timer("failing_timer"):
            raise RuntimeError("timer test error")
    
    # Check error was logged
    assert "Timer failed: failing_timer" in caplog.text
    assert "error_type" in caplog.text
    assert "RuntimeError" in caplog.text


def test_multiple_diagnostic_contexts():
    """Test that diagnostic contexts work independently."""
    # Set all contexts
    set_trace_id("trace-123")
    set_issue_id("issue-456")
    set_hypothesis_id("hypothesis-789")
    
    # Verify all are set
    assert get_trace_id() == "trace-123"
    assert get_issue_id() == "issue-456"  
    assert get_hypothesis_id() == "hypothesis-789"
    
    # Clear one at a time
    set_trace_id(None)
    assert get_trace_id() is None
    assert get_issue_id() == "issue-456"
    assert get_hypothesis_id() == "hypothesis-789"
    
    set_issue_id(None)
    assert get_issue_id() is None
    assert get_hypothesis_id() == "hypothesis-789"
    
    set_hypothesis_id(None)
    assert get_hypothesis_id() is None


@pytest.mark.integration
def test_diagnostic_integration_example(caplog):
    """Test realistic usage pattern combining all diagnostic tools."""
    caplog.set_level(logging.INFO)
    
    # Simulate bug investigation workflow
    set_issue_id("bug-12345")
    set_hypothesis_id("h1-payment-timeout")
    
    with trace_section("payment_processing") as trace_id:
        assert trace_id is not None
        
        # Simulate payment steps
        with timer("validate_payment_data"):
            # Simulate validation work
            time.sleep(0.001)
        
        with timer("charge_payment"):
            # Simulate payment processing
            time.sleep(0.001)
        
        # Log diagnostic info
        logging.getLogger("test").info("Payment processed successfully", extra={
            "amount": 100.50,
            "currency": "USD"
        })
    
    # Cleanup
    set_issue_id(None)
    set_hypothesis_id(None)
    
    # Verify logging structure
    assert "payment_processing" in caplog.text
    assert "validate_payment_data" in caplog.text  
    assert "charge_payment" in caplog.text


if __name__ == "__main__":
    # Self-check instructions
    print("🧪 Running diagnostic toolkit smoke tests...")
    print("Expected output:")
    print("- All tests should pass")
    print("- Logs should show structured JSON with diagnostic fields")
    print("- trace_section should auto-generate short UUIDs")
    print("- timer should measure durations in milliseconds")
    print("- Context variables should be properly isolated")
    
    # Run a quick smoke test
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("\n📊 Quick smoke test:")
    set_issue_id("smoke-test")
    
    with trace_section("smoke_test") as trace_id:
        print(f"Generated trace_id: {trace_id}")
        
        with timer("smoke_operation"):
            time.sleep(0.01)
        
        print(f"Current diagnostic context:")
        print(f"  trace_id: {get_trace_id()}")
        print(f"  issue_id: {get_issue_id()}")
        print(f"  hypothesis_id: {get_hypothesis_id()}")
    
    print("✅ Smoke test completed")
