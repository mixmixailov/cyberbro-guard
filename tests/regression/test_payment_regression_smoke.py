"""Simplified smoke tests for payment regression scenarios.

These tests focus on the core regression logic without complex mocking.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.db.payments import record_payment_idempotent, seen_charge_id


@pytest.fixture
def simple_db():
    """Create a minimal test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    
    with patch("app.db.session.APP_DB_PATH", db_path):
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                amount_cents INTEGER NOT NULL,
                currency TEXT NOT NULL,
                provider TEXT,
                status TEXT,
                created_at TEXT NOT NULL,
                raw_json TEXT,
                charge_id TEXT UNIQUE
            );
        """)
        conn.commit()
        conn.close()
        
        yield db_path
    
    # Cleanup
    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.mark.regression
class TestPaymentIdempotencySmoke:
    """Simplified regression tests for payment idempotency.
    
    Issue ID: #PAY-001
    Description: Verify charge_id based idempotency works correctly.
    """
    
    def test_charge_id_idempotency_basic(self, simple_db):
        """Test basic charge_id idempotency functionality.
        
        Regression test for issue #PAY-001: Duplicate charge_ids
        should return the same payment_id without creating new records.
        """
        charge_id = "ch_regression_test_001"
        
        # First payment
        payment_id_1, was_inserted_1 = record_payment_idempotent(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"test": "data"},
            charge_id=charge_id
        )
        
        assert payment_id_1 > 0
        assert was_inserted_1 is True
        assert seen_charge_id(charge_id) is True
        
        # Duplicate payment with same charge_id
        payment_id_2, was_inserted_2 = record_payment_idempotent(
            tg_id=67890,  # Different user
            amount_cents=9800,  # Different amount
            currency="USD",  # Different currency
            provider="stars",
            status="ok",
            raw={"different": "data"},
            charge_id=charge_id  # Same charge_id
        )
        
        # Should return original payment_id
        assert payment_id_2 == payment_id_1
        assert was_inserted_2 is False
        assert seen_charge_id(charge_id) is True
    
    def test_different_charge_ids_create_separate_payments(self, simple_db):
        """Test that different charge_ids create separate payment records.
        
        Regression test for issue #PAY-001: Different charge_ids
        should create separate payment records.
        """
        charge_id_1 = "ch_regression_test_002"
        charge_id_2 = "ch_regression_test_003"
        
        # First payment
        payment_id_1, was_inserted_1 = record_payment_idempotent(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"test": "data_1"},
            charge_id=charge_id_1
        )
        
        # Second payment with different charge_id
        payment_id_2, was_inserted_2 = record_payment_idempotent(
            tg_id=12345,  # Same user
            amount_cents=4900,  # Same amount
            currency="XTR",  # Same currency
            provider="stars",
            status="ok",
            raw={"test": "data_2"},
            charge_id=charge_id_2  # Different charge_id
        )
        
        # Should create separate payments
        assert payment_id_1 > 0
        assert payment_id_2 > 0
        assert payment_id_1 != payment_id_2
        assert was_inserted_1 is True
        assert was_inserted_2 is True
        
        # Both charge_ids should be tracked
        assert seen_charge_id(charge_id_1) is True
        assert seen_charge_id(charge_id_2) is True
    
    def test_null_charge_id_handling(self, simple_db):
        """Test handling of payments without charge_id.
        
        Regression test for issue #PAY-001: Payments without charge_id
        should still be recorded but not tracked for idempotency.
        """
        # Payment without charge_id
        payment_id_1, was_inserted_1 = record_payment_idempotent(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"test": "no_charge_id"},
            charge_id=None
        )
        
        # Another payment without charge_id
        payment_id_2, was_inserted_2 = record_payment_idempotent(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"test": "no_charge_id_2"},
            charge_id=None
        )
        
        # Both should be recorded as separate payments
        assert payment_id_1 > 0
        assert payment_id_2 > 0
        assert payment_id_1 != payment_id_2
        assert was_inserted_1 is True
        assert was_inserted_2 is True


@pytest.mark.regression  
class TestRefundLogicSmoke:
    """Simplified regression tests for refund handling.
    
    Issue ID: #PAY-002
    Description: Verify refund processing works correctly.
    """
    
    def test_refund_charge_id_generation(self, simple_db):
        """Test that refund charge_ids are properly generated.
        
        Regression test for issue #PAY-002: Refunds should use
        prefixed charge_ids to avoid conflicts with original payments.
        """
        original_charge_id = "ch_original_123"
        
        # Record original payment
        original_payment_id, _ = record_payment_idempotent(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"original": True},
            charge_id=original_charge_id
        )
        
        # Record refund with prefixed charge_id
        refund_charge_id = f"refund_{original_charge_id}"
        refund_payment_id, was_inserted = record_payment_idempotent(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="refunded",
            raw={"refund": True, "original_charge_id": original_charge_id},
            charge_id=refund_charge_id
        )
        
        # Refund should be recorded as separate payment
        assert refund_payment_id > 0
        assert refund_payment_id != original_payment_id
        assert was_inserted is True
        
        # Both charge_ids should be tracked
        assert seen_charge_id(original_charge_id) is True
        assert seen_charge_id(refund_charge_id) is True


@pytest.mark.regression
class TestStarTransactionSmoke:
    """Simplified regression tests for StarTransaction handling.
    
    Issue ID: #PAY-003
    Description: Verify StarTransaction processing works correctly.
    """
    
    def test_star_transaction_idempotency(self, simple_db):
        """Test StarTransaction idempotency based on transaction_id.
        
        Regression test for issue #PAY-003: Duplicate StarTransaction
        updates should not create multiple payment records.
        """
        tx_id = "str_regression_test_123"
        
        # First StarTransaction
        payment_id_1, was_inserted_1 = record_payment_idempotent(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="star_transaction",
            raw={"transaction_id": tx_id, "amount": 4900},
            charge_id=f"star_tx_{tx_id}"
        )
        
        # Duplicate StarTransaction
        payment_id_2, was_inserted_2 = record_payment_idempotent(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars", 
            status="star_transaction",
            raw={"transaction_id": tx_id, "amount": 4900},
            charge_id=f"star_tx_{tx_id}"  # Same charge_id
        )
        
        # Should return original payment_id
        assert payment_id_2 == payment_id_1
        assert was_inserted_1 is True
        assert was_inserted_2 is False
        
        # Transaction should be tracked
        assert seen_charge_id(f"star_tx_{tx_id}") is True


if __name__ == "__main__":
    # Self-check instructions
    print("🧪 Running simplified payment regression tests...")
    print("Expected behavior:")
    print("- charge_id idempotency should prevent duplicate payments")
    print("- Different charge_ids should create separate payments")
    print("- Refunds should use prefixed charge_ids")
    print("- StarTransaction duplicates should be ignored")
    
    print("\n💡 To run these tests:")
    print("python -m pytest tests/regression/test_payment_regression_smoke.py -m regression -v")
    print("python -m pytest tests/regression/ -m regression -k smoke")
