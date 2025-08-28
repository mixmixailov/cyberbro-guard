from __future__ import annotations

import json
import logging
from typing import Any

from .session import execute, execute_immediate, fetchone

logger = logging.getLogger(__name__)


def record_payment(
    tg_id: int,
    amount_cents: int,
    currency: str,
    provider: str,
    status: str,
    raw: dict[str, Any] | None,
    charge_id: str | None = None,
) -> int:
    """Record payment with optional charge_id for idempotency.
    
    Args:
        charge_id: Telegram charge ID for deduplication
        
    Returns:
        Payment ID if inserted, 0 if duplicate (idempotent)
    """
    # Use immediate transaction for critical payment operations
    return execute_immediate(
        """
        INSERT INTO payments (tg_id, amount_cents, currency, provider, status, created_at, raw_json, charge_id)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?)
        """,
        (tg_id, amount_cents, currency, provider, status, json.dumps(raw or {}), charge_id),
    )


def record_payment_idempotent(
    tg_id: int,
    amount_cents: int,
    currency: str,
    provider: str,
    status: str,
    raw: dict[str, Any] | None,
    charge_id: str,
) -> tuple[int, bool]:
    """Record payment with idempotency via INSERT OR IGNORE.
    
    Args:
        charge_id: Required Telegram charge ID for deduplication
        
    Returns:
        Tuple of (payment_id, was_inserted)
        - payment_id: ID of payment record (new or existing)
        - was_inserted: True if new payment, False if duplicate
    """
    # Use immediate transaction for critical payment operations
    result = execute_immediate(
        """
        INSERT OR IGNORE INTO payments (tg_id, amount_cents, currency, provider, status, created_at, raw_json, charge_id)
        VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?)
        """,
        (tg_id, amount_cents, currency, provider, status, json.dumps(raw or {}), charge_id),
    )
    
    if result > 0:
        # New payment inserted
        return result, True
    else:
        # Duplicate - fetch existing payment ID
        existing = fetchone("SELECT id FROM payments WHERE charge_id = ?", (charge_id,))
        return existing["id"] if existing else 0, False


def seen_charge_id(charge_id: str) -> bool:
    """Check if charge_id has been processed before.
    
    Uses efficient indexed lookup instead of JSON LIKE search.
    """
    if not charge_id:
        return False
    
    row = fetchone("SELECT id FROM payments WHERE charge_id = ? LIMIT 1", (charge_id,))
    return bool(row)


def get_payment_by_charge_id(charge_id: str) -> dict[str, Any] | None:
    """Get payment record by charge_id."""
    if not charge_id:
        return None
        
    return fetchone(
        """
        SELECT id, tg_id, amount_cents, currency, provider, status, created_at, raw_json, charge_id
        FROM payments 
        WHERE charge_id = ?
        """,
        (charge_id,)
    )


def record_star_transaction(
    tg_id: int,
    transaction_data: dict[str, Any],
) -> int:
    """Record StarTransaction from Telegram.
    
    Args:
        tg_id: User Telegram ID
        transaction_data: StarTransaction.to_dict() data
        
    Returns:
        Payment ID
    """
    # Extract key fields from StarTransaction
    transaction_id = transaction_data.get("id", "")
    amount = transaction_data.get("amount", 0)
    source = transaction_data.get("source", {})
    
    # Use transaction ID as charge_id for idempotency
    charge_id = f"star_tx_{transaction_id}" if transaction_id else None
    
    payment_id, was_inserted = record_payment_idempotent(
        tg_id=tg_id,
        amount_cents=amount,
        currency="XTR",
        provider="stars",
        status="star_transaction",
        raw=transaction_data,
        charge_id=charge_id or f"star_fallback_{tg_id}_{amount}",
    )
    
    if was_inserted:
        logger.info("Recorded new StarTransaction: payment_id=%d, tx_id=%s, amount=%d", 
                   payment_id, transaction_id, amount)
    else:
        logger.debug("Duplicate StarTransaction ignored: tx_id=%s", transaction_id)
    
    return payment_id


def record_refunded_payment(
    tg_id: int,
    refund_data: dict[str, Any],
) -> int:
    """Record RefundedPayment from Telegram.
    
    Args:
        tg_id: User Telegram ID  
        refund_data: RefundedPayment.to_dict() data
        
    Returns:
        Payment ID
    """
    # Extract key fields from RefundedPayment
    charge_id = refund_data.get("telegram_payment_charge_id", "")
    total_amount = refund_data.get("total_amount", 0)
    currency = refund_data.get("currency", "XTR")
    
    # Use refund charge_id for idempotency
    refund_charge_id = f"refund_{charge_id}" if charge_id else None
    
    payment_id, was_inserted = record_payment_idempotent(
        tg_id=tg_id,
        amount_cents=total_amount,
        currency=currency,
        provider="stars",
        status="refunded",
        raw=refund_data,
        charge_id=refund_charge_id or f"refund_fallback_{tg_id}_{total_amount}",
    )
    
    if was_inserted:
        logger.info("Recorded new RefundedPayment: payment_id=%d, charge_id=%s, amount=%d", 
                   payment_id, charge_id, total_amount)
    else:
        logger.debug("Duplicate RefundedPayment ignored: charge_id=%s", charge_id)
    
    return payment_id


































