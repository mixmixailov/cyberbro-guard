"""Tests for extended payment handling: StarTransaction, RefundedPayment, idempotency."""

import pytest
import json
import sqlite3
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User, Chat, SuccessfulPayment
from telegram.ext import ContextTypes

from app.db.payments import (
    record_payment,
    record_payment_idempotent,
    seen_charge_id,
    get_payment_by_charge_id,
    record_star_transaction,
    record_refunded_payment,
)
from app.handlers.payments import handle_star_transaction, handle_refunded_payment
from app.db.session import init_db, execute_immediate
import tempfile
from pathlib import Path


class TestPaymentIdempotency:
    """Test payment idempotency via charge_id and INSERT OR IGNORE."""

    @pytest.fixture(scope="function")
    def temp_db(self, monkeypatch):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = Path(f.name)
        
        monkeypatch.setattr("app.db.session.APP_DB_PATH", temp_path)
        init_db()
        yield temp_path
        
        # Cleanup
        try:
            temp_path.unlink()
        except Exception:
            pass

    def test_record_payment_with_charge_id(self, temp_db):
        """Test basic payment recording with charge_id."""
        charge_id = "test_charge_123"
        
        payment_id = record_payment(
            tg_id=12345,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"test": "data"},
            charge_id=charge_id,
        )
        
        assert payment_id > 0
        
        # Verify payment can be retrieved by charge_id
        payment = get_payment_by_charge_id(charge_id)
        assert payment is not None
        assert payment["charge_id"] == charge_id
        assert payment["tg_id"] == 12345
        assert payment["amount_cents"] == 4900

    def test_record_payment_idempotent_new_payment(self, temp_db):
        """Test record_payment_idempotent with new payment."""
        charge_id = "unique_charge_456"
        
        payment_id, was_inserted = record_payment_idempotent(
            tg_id=67890,
            amount_cents=2500,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"invoice": "data"},
            charge_id=charge_id,
        )
        
        assert payment_id > 0
        assert was_inserted is True
        
        # Verify payment exists
        payment = get_payment_by_charge_id(charge_id)
        assert payment["id"] == payment_id

    def test_record_payment_idempotent_duplicate_payment(self, temp_db):
        """Test record_payment_idempotent with duplicate charge_id."""
        charge_id = "duplicate_charge_789"
        
        # First insertion
        payment_id_1, was_inserted_1 = record_payment_idempotent(
            tg_id=11111,
            amount_cents=1000,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"first": "payment"},
            charge_id=charge_id,
        )
        
        assert payment_id_1 > 0
        assert was_inserted_1 is True
        
        # Second insertion with same charge_id (should be ignored)
        payment_id_2, was_inserted_2 = record_payment_idempotent(
            tg_id=22222,  # Different user
            amount_cents=2000,  # Different amount
            currency="USD",  # Different currency
            provider="test",
            status="duplicate",
            raw={"second": "payment"},
            charge_id=charge_id,  # Same charge_id
        )
        
        # Should return existing payment ID
        assert payment_id_2 == payment_id_1
        assert was_inserted_2 is False
        
        # Verify original payment unchanged
        payment = get_payment_by_charge_id(charge_id)
        assert payment["tg_id"] == 11111  # Original user
        assert payment["amount_cents"] == 1000  # Original amount

    def test_seen_charge_id_functionality(self, temp_db):
        """Test seen_charge_id efficient lookup."""
        charge_id = "seen_test_charge"
        
        # Initially not seen
        assert seen_charge_id(charge_id) is False
        assert seen_charge_id("") is False
        assert seen_charge_id(None) is False
        
        # Record payment
        record_payment(
            tg_id=33333,
            amount_cents=500,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={},
            charge_id=charge_id,
        )
        
        # Now should be seen
        assert seen_charge_id(charge_id) is True
        assert seen_charge_id("different_charge") is False

    def test_unique_constraint_enforcement(self, temp_db):
        """Test that database enforces UNIQUE constraint on charge_id."""
        charge_id = "constraint_test_charge"
        
        # First payment succeeds
        payment_id_1 = record_payment(
            tg_id=44444,
            amount_cents=3000,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={},
            charge_id=charge_id,
        )
        assert payment_id_1 > 0
        
        # Second payment with same charge_id should fail
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            record_payment(
                tg_id=55555,
                amount_cents=4000,
                currency="XTR",
                provider="stars",
                status="duplicate",
                raw={},
                charge_id=charge_id,
            )


class TestStarTransactionHandling:
    """Test StarTransaction recording and processing."""

    @pytest.fixture(scope="function")
    def temp_db(self, monkeypatch):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = Path(f.name)
        
        monkeypatch.setattr("app.db.session.APP_DB_PATH", temp_path)
        init_db()
        yield temp_path
        
        try:
            temp_path.unlink()
        except Exception:
            pass

    def test_record_star_transaction_new(self, temp_db):
        """Test recording new StarTransaction."""
        transaction_data = {
            "id": "star_tx_12345",
            "amount": 500,
            "source": {"type": "user", "user": {"id": 123456}},
            "date": 1640995200,
        }
        
        payment_id = record_star_transaction(
            tg_id=123456,
            transaction_data=transaction_data,
        )
        
        assert payment_id > 0
        
        # Verify payment recorded correctly
        payment = get_payment_by_charge_id("star_tx_star_tx_12345")
        assert payment is not None
        assert payment["tg_id"] == 123456
        assert payment["amount_cents"] == 500
        assert payment["currency"] == "XTR"
        assert payment["provider"] == "stars"
        assert payment["status"] == "star_transaction"

    def test_record_star_transaction_duplicate(self, temp_db):
        """Test StarTransaction idempotency."""
        transaction_data = {
            "id": "star_tx_duplicate",
            "amount": 750,
            "source": {"type": "user", "user": {"id": 789012}},
        }
        
        # First recording
        payment_id_1 = record_star_transaction(
            tg_id=789012,
            transaction_data=transaction_data,
        )
        assert payment_id_1 > 0
        
        # Second recording (duplicate)
        payment_id_2 = record_star_transaction(
            tg_id=789012,
            transaction_data=transaction_data,
        )
        assert payment_id_2 == payment_id_1

    def test_record_star_transaction_no_id(self, temp_db):
        """Test StarTransaction with missing ID (fallback charge_id)."""
        transaction_data = {
            "amount": 1000,
            "source": {"type": "system"},
        }
        
        payment_id = record_star_transaction(
            tg_id=345678,
            transaction_data=transaction_data,
        )
        
        assert payment_id > 0
        
        # Should use fallback charge_id
        payment = get_payment_by_charge_id("star_fallback_345678_1000")
        assert payment is not None

    @pytest.mark.asyncio
    async def test_handle_star_transaction_handler(self, temp_db):
        """Test StarTransaction handler function."""
        # Mock objects
        user = Mock(spec=User)
        user.id = 111111
        
        star_tx = Mock()
        star_tx.id = "handler_test_tx"
        star_tx.to_dict.return_value = {
            "id": "handler_test_tx",
            "amount": 1500,
        }
        
        message = Mock(spec=Message)
        message.star_transaction = star_tx
        
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Mock external dependencies
        with patch("app.handlers.payments.log_action") as mock_log, \
             patch("app.handlers.payments.payments_total") as mock_metrics:
            
            await handle_star_transaction(update, context)
            
            # Verify payment was recorded
            payment = get_payment_by_charge_id("star_tx_handler_test_tx")
            assert payment is not None
            assert payment["tg_id"] == 111111
            
            # Verify logging and metrics
            mock_log.assert_called_once()
            mock_metrics.labels.assert_called_with("star_transaction")


class TestRefundedPaymentHandling:
    """Test RefundedPayment recording and processing."""

    @pytest.fixture(scope="function")
    def temp_db(self, monkeypatch):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = Path(f.name)
        
        monkeypatch.setattr("app.db.session.APP_DB_PATH", temp_path)
        init_db()
        yield temp_path
        
        try:
            temp_path.unlink()
        except Exception:
            pass

    def test_record_refunded_payment_new(self, temp_db):
        """Test recording new RefundedPayment."""
        refund_data = {
            "telegram_payment_charge_id": "original_charge_123",
            "provider_payment_charge_id": "provider_123",
            "total_amount": 4900,
            "currency": "XTR",
        }
        
        payment_id = record_refunded_payment(
            tg_id=666777,
            refund_data=refund_data,
        )
        
        assert payment_id > 0
        
        # Verify refund recorded correctly
        payment = get_payment_by_charge_id("refund_original_charge_123")
        assert payment is not None
        assert payment["tg_id"] == 666777
        assert payment["amount_cents"] == 4900
        assert payment["currency"] == "XTR"
        assert payment["status"] == "refunded"

    def test_record_refunded_payment_duplicate(self, temp_db):
        """Test RefundedPayment idempotency."""
        refund_data = {
            "telegram_payment_charge_id": "duplicate_refund_456",
            "total_amount": 2500,
            "currency": "XTR",
        }
        
        # First recording
        payment_id_1 = record_refunded_payment(
            tg_id=888999,
            refund_data=refund_data,
        )
        assert payment_id_1 > 0
        
        # Second recording (duplicate)
        payment_id_2 = record_refunded_payment(
            tg_id=888999,
            refund_data=refund_data,
        )
        assert payment_id_2 == payment_id_1

    def test_record_refunded_payment_no_charge_id(self, temp_db):
        """Test RefundedPayment with missing charge_id."""
        refund_data = {
            "total_amount": 1500,
            "currency": "USD",
        }
        
        payment_id = record_refunded_payment(
            tg_id=111222,
            refund_data=refund_data,
        )
        
        assert payment_id > 0
        
        # Should use fallback charge_id
        payment = get_payment_by_charge_id("refund_fallback_111222_1500")
        assert payment is not None

    @pytest.mark.asyncio
    async def test_handle_refunded_payment_handler(self, temp_db):
        """Test RefundedPayment handler function."""
        # Mock objects
        user = Mock(spec=User)
        user.id = 333444
        
        refunded = Mock()
        refunded.telegram_payment_charge_id = "refund_handler_test"
        refunded.total_amount = 5000
        refunded.currency = "XTR"
        refunded.to_dict.return_value = {
            "telegram_payment_charge_id": "refund_handler_test",
            "total_amount": 5000,
            "currency": "XTR",
        }
        
        message = Mock(spec=Message)
        message.refunded_payment = refunded
        message.reply_text = AsyncMock()
        
        update = Mock(spec=Update)
        update.message = message
        update.effective_user = user
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Mock external dependencies
        with patch("app.handlers.payments.log_action") as mock_log, \
             patch("app.handlers.payments.payments_total") as mock_metrics:
            
            await handle_refunded_payment(update, context)
            
            # Verify refund was recorded
            payment = get_payment_by_charge_id("refund_refund_handler_test")
            assert payment is not None
            assert payment["tg_id"] == 333444
            
            # Verify user notification
            message.reply_text.assert_called_once()
            call_args = message.reply_text.call_args[0][0]
            assert "💫 Возврат обработан: 5000 XTR" in call_args
            
            # Verify logging and metrics
            mock_log.assert_called_once()
            mock_metrics.labels.assert_called_with("refunded")


class TestPaymentIntegration:
    """Integration tests for complete payment flow."""

    @pytest.fixture(scope="function")
    def temp_db(self, monkeypatch):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = Path(f.name)
        
        monkeypatch.setattr("app.db.session.APP_DB_PATH", temp_path)
        init_db()
        yield temp_path
        
        try:
            temp_path.unlink()
        except Exception:
            pass

    def test_complete_payment_refund_cycle(self, temp_db):
        """Test complete payment -> refund cycle with idempotency."""
        user_id = 555666
        original_charge = "cycle_test_charge"
        
        # 1. Record original successful payment
        payment_id_1 = record_payment(
            tg_id=user_id,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={"telegram_payment_charge_id": original_charge},
            charge_id=original_charge,
        )
        assert payment_id_1 > 0
        
        # 2. Record StarTransaction for same payment
        star_data = {
            "id": "star_for_payment",
            "amount": 4900,
            "source": {"type": "payment", "payment_charge_id": original_charge}
        }
        payment_id_2 = record_star_transaction(user_id, star_data)
        assert payment_id_2 > 0
        assert payment_id_2 != payment_id_1  # Different records
        
        # 3. Record refund
        refund_data = {
            "telegram_payment_charge_id": original_charge,
            "total_amount": 4900,
            "currency": "XTR",
        }
        payment_id_3 = record_refunded_payment(user_id, refund_data)
        assert payment_id_3 > 0
        assert payment_id_3 not in [payment_id_1, payment_id_2]
        
        # 4. Verify all records exist and are distinct
        original_payment = get_payment_by_charge_id(original_charge)
        star_payment = get_payment_by_charge_id("star_tx_star_for_payment")
        refund_payment = get_payment_by_charge_id(f"refund_{original_charge}")
        
        assert original_payment["status"] == "ok"
        assert star_payment["status"] == "star_transaction"
        assert refund_payment["status"] == "refunded"
        
        # 5. Test idempotency - duplicate operations should be ignored
        duplicate_payment_id, was_inserted = record_payment_idempotent(
            tg_id=user_id,
            amount_cents=4900,
            currency="XTR",
            provider="stars",
            status="ok",
            raw={},
            charge_id=original_charge,
        )
        assert duplicate_payment_id == payment_id_1
        assert was_inserted is False

    def test_concurrent_payment_processing(self, temp_db):
        """Test concurrent payment processing with charge_id idempotency."""
        import threading
        import time
        
        charge_id = "concurrent_test_charge"
        user_id = 777888
        results = []
        
        def process_payment(thread_id: int):
            """Worker function for concurrent payment processing."""
            try:
                payment_id, was_inserted = record_payment_idempotent(
                    tg_id=user_id,
                    amount_cents=1000,
                    currency="XTR",
                    provider="stars",
                    status="ok",
                    raw={"thread_id": thread_id},
                    charge_id=charge_id,
                )
                results.append((thread_id, payment_id, was_inserted))
                time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                results.append((thread_id, 0, False, str(e)))
        
        # Run 5 concurrent threads trying to process same payment
        threads = [threading.Thread(target=process_payment, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify results
        assert len(results) == 5
        
        # Exactly one should have been inserted
        inserted_count = sum(1 for result in results if len(result) == 3 and result[2])
        assert inserted_count == 1
        
        # All should have same payment_id
        payment_ids = [result[1] for result in results if len(result) >= 2 and result[1] > 0]
        assert len(set(payment_ids)) == 1  # All same payment ID
        
        # Verify only one record in database
        payment = get_payment_by_charge_id(charge_id)
        assert payment is not None
        assert payment["tg_id"] == user_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


