# Extended Payment Handling Specification

## Overview

Данная спецификация описывает расширенную обработку платежей для CyberBro Guard с поддержкой StarTransaction, RefundedPayment и улучшенной идемпотентности через charge_id.

## Problem Statement

### Текущие проблемы
1. **Неэффективная идемпотентность**: Существующий `seen_charge_id()` использует LIKE поиск по JSON
2. **Ограниченные типы платежей**: Поддерживается только SuccessfulPayment
3. **Отсутствие обработки возвратов**: RefundedPayment не обрабатывается автоматически
4. **Нет аудита Star операций**: StarTransaction события не записываются
5. **Риск дублирования платежей**: При concurrent processing возможны дубли

### Бизнес-импакт
- **Financial accuracy**: Дублирование платежей влияет на billing consistency
- **User experience**: Неправильная обработка возвратов создает confusion
- **Audit compliance**: Отсутствие полного аудит-трейла Star операций
- **Support burden**: Manual resolution duplicate payment issues
- **Revenue loss**: Неточный учет платежей и возвратов

## Goals

### Основные цели
1. **Enhanced idempotency через charge_id UNIQUE constraint**
   - Eliminate LIKE-based charge_id lookups
   - Guarantee single payment per charge_id
   - Efficient indexed access для payment retrieval

2. **Comprehensive payment type support**
   - SuccessfulPayment (existing, enhanced)
   - StarTransaction processing и audit
   - RefundedPayment automatic handling
   - Unified payment recording interface

3. **Robust concurrent processing**
   - INSERT OR IGNORE для safe duplicate handling
   - BEGIN IMMEDIATE для critical payment operations
   - Atomic payment state transitions

4. **Complete audit trail**
   - All Star-related events logged
   - Payment status transitions tracked
   - Refund correlation with original payments
   - Comprehensive metrics collection

## Requirements

### Functional Requirements

#### FR-1: Enhanced Database Schema
- **Описание**: Add charge_id field with UNIQUE constraint to payments table
- **Критерии приёмки**:
  - `payments.charge_id` field with UNIQUE constraint
  - Efficient index on charge_id for fast lookups
  - Backward compatibility with existing payments (charge_id NULL allowed)
  - Database migration preserves existing data

#### FR-2: Idempotent Payment Recording
- **Описание**: Implement INSERT OR IGNORE pattern для charge_id deduplication
- **Критерии приёмки**:
  - `record_payment_idempotent()` returns (payment_id, was_inserted)
  - Duplicate charge_id returns existing payment_id с was_inserted=False
  - New charge_id creates payment и returns was_inserted=True
  - Handles concurrent access safely без race conditions

#### FR-3: StarTransaction Processing
- **Описание**: Handle StarTransaction updates from Telegram
- **Критерии приёмки**:
  - Automatic StarTransaction recording на webhook receipt
  - Extract transaction_id для charge_id generation
  - Idempotent processing для duplicate events
  - Proper audit logging и metrics collection

#### FR-4: RefundedPayment Handling
- **Описание**: Process RefundedPayment events automatically
- **Критерии приёмки**:
  - Automatic refund recording на webhook receipt
  - Correlation с original payment через charge_id
  - User notification о refund processing
  - Audit trail for refund operations

#### FR-5: Enhanced Payment Retrieval
- **Описание**: Efficient payment lookup и management functions
- **Критерии приёмки**:
  - `get_payment_by_charge_id()` fast indexed lookup
  - `seen_charge_id()` О(1) performance
  - Support для different charge_id patterns (payments, stars, refunds)
  - Backward compatibility с existing payment queries

### Non-Functional Requirements

#### NFR-1: Performance
- **Database query time**: charge_id lookup < 1ms
- **Concurrent processing**: support ≥20 simultaneous payment operations
- **Idempotency overhead**: < 5ms additional latency per operation
- **Index efficiency**: charge_id index size < 10% of table size

#### NFR-2: Reliability
- **Duplicate prevention**: 100% accuracy для charge_id deduplication
- **Data consistency**: ACID compliance для all payment operations
- **Concurrent safety**: no race conditions под high load
- **Error recovery**: graceful handling database constraint violations

#### NFR-3: Auditability
- **Complete audit trail**: 100% payment operations logged
- **Metrics coverage**: all payment types tracked в metrics
- **Error tracking**: detailed logging для failed operations
- **Compliance**: maintain financial audit requirements

## Technical Specifications

### Database Schema Enhancement

#### Enhanced Payments Table
```sql
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    provider TEXT,
    status TEXT,
    created_at TEXT NOT NULL,
    raw_json TEXT,
    charge_id TEXT UNIQUE              -- NEW: Unique constraint for idempotency
);

-- Indexes for performance
CREATE INDEX idx_payments_charge_id ON payments(charge_id);
CREATE INDEX idx_payments_tg_id ON payments(tg_id);
CREATE INDEX idx_payments_status ON payments(status);
```

#### Charge ID Patterns
```python
# Different patterns for different payment types
SUCCESSFUL_PAYMENT = "{telegram_payment_charge_id}"
STAR_TRANSACTION = "star_tx_{transaction_id}"
REFUNDED_PAYMENT = "refund_{original_charge_id}"
FALLBACK_PATTERN = "{type}_fallback_{user_id}_{amount}"
```

### API Design

#### Payment Recording Functions
```python
def record_payment(
    tg_id: int,
    amount_cents: int,
    currency: str,
    provider: str,
    status: str,
    raw: dict[str, Any] | None,
    charge_id: str | None = None,
) -> int:
    """Record payment with optional charge_id."""

def record_payment_idempotent(
    tg_id: int,
    amount_cents: int,
    currency: str,
    provider: str,
    status: str,
    raw: dict[str, Any] | None,
    charge_id: str,
) -> tuple[int, bool]:
    """Record payment with guaranteed idempotency."""

def seen_charge_id(charge_id: str) -> bool:
    """Efficient charge_id existence check."""

def get_payment_by_charge_id(charge_id: str) -> dict[str, Any] | None:
    """Retrieve payment by charge_id."""
```

#### Specialized Recording Functions
```python
def record_star_transaction(
    tg_id: int,
    transaction_data: dict[str, Any],
) -> int:
    """Record StarTransaction with auto-generated charge_id."""

def record_refunded_payment(
    tg_id: int,
    refund_data: dict[str, Any],
) -> int:
    """Record RefundedPayment with correlation to original."""
```

### Handler Integration

#### Extended Message Handlers
```python
# Star transaction handler
app.add_handler(MessageHandler(
    filters.MessageFilter(lambda msg: hasattr(msg, 'star_transaction')),
    handle_star_transaction
))

# Refunded payment handler  
app.add_handler(MessageHandler(
    filters.MessageFilter(lambda msg: hasattr(msg, 'refunded_payment')),
    handle_refunded_payment
))
```

#### Handler Implementation
```python
async def handle_star_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process StarTransaction events with idempotency."""
    star_tx = update.message.star_transaction
    uid = int(update.effective_user.id)
    
    payment_id = record_star_transaction(uid, star_tx.to_dict())
    if payment_id:
        log_action(payment_id, "star_transaction_recorded")
        payments_total.labels("star_transaction").inc()

async def handle_refunded_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process RefundedPayment events with user notification."""
    refunded = update.message.refunded_payment
    uid = int(update.effective_user.id)
    
    payment_id = record_refunded_payment(uid, refunded.to_dict())
    if payment_id:
        log_action(payment_id, "refund_processed")
        payments_total.labels("refunded").inc()
        await notify_user_about_refund(update.message, refunded)
```

## Payment Processing Flows

### SuccessfulPayment Flow (Enhanced)
```
1. Telegram sends SuccessfulPayment
2. Extract telegram_payment_charge_id
3. Check seen_charge_id() - O(1) lookup
4. If not seen:
   a. record_payment() with charge_id
   b. Process subscription upgrade
   c. Log audit event
   d. Update metrics
5. If seen: log duplicate and ignore
```

### StarTransaction Flow (New)
```  
1. Telegram sends StarTransaction
2. Extract transaction.id
3. Generate charge_id = "star_tx_{id}"
4. record_star_transaction() with idempotency
5. Log star operation audit
6. Update star metrics
7. Return payment_id (new or existing)
```

### RefundedPayment Flow (New)
```
1. Telegram sends RefundedPayment  
2. Extract telegram_payment_charge_id
3. Generate refund_charge_id = "refund_{original_id}"
4. record_refunded_payment() with idempotency
5. Notify user about refund processing
6. Log refund audit event
7. Update refund metrics
```

### Concurrent Processing Flow
```
1. Multiple threads receive same charge_id
2. All threads call record_payment_idempotent()
3. First thread: INSERT succeeds, returns (new_id, True)
4. Other threads: INSERT OR IGNORE ignored, returns (existing_id, False)
5. All threads get same payment_id
6. Only first thread processes business logic
7. Database consistency maintained
```

## Error Handling Strategy

### Database Constraint Violations
```python
try:
    payment_id = record_payment(charge_id=charge_id, ...)
except sqlite3.IntegrityError as e:
    if "UNIQUE constraint failed: payments.charge_id" in str(e):
        # Expected for concurrent requests
        existing_payment = get_payment_by_charge_id(charge_id)
        return existing_payment["id"] if existing_payment else 0
    else:
        # Unexpected constraint violation
        logger.error("Payment constraint violation: %s", e)
        raise
```

### Charge ID Generation Failures
```python
def generate_safe_charge_id(payment_type: str, primary_id: str, fallback_data: dict) -> str:
    """Generate charge_id with fallback strategies."""
    if primary_id:
        return f"{payment_type}_{primary_id}"
    
    # Fallback: deterministic ID from payment data
    fallback_id = f"{fallback_data['user_id']}_{fallback_data['amount']}_{int(time.time())}"
    return f"{payment_type}_fallback_{fallback_id}"
```

### Telegram API Failures
```python
async def handle_star_transaction(update, context):
    """Handle StarTransaction with error recovery."""
    try:
        payment_id = record_star_transaction(...)
        log_action(payment_id, "star_transaction_recorded")
    except Exception as e:
        logger.error("StarTransaction processing failed: %s", e)
        payments_total.labels("star_transaction_error").inc()
        
        # Best-effort admin notification
        await notify_admin_payment_error(update, e)
```

## Performance Optimization

### Database Query Optimization

#### Index Strategy
```sql
-- Primary index for charge_id lookups
CREATE UNIQUE INDEX idx_payments_charge_id ON payments(charge_id);

-- Composite index for user payment queries
CREATE INDEX idx_payments_user_status ON payments(tg_id, status);

-- Index for time-based queries
CREATE INDEX idx_payments_created_at ON payments(created_at);
```

#### Query Patterns
```python
# Efficient existence check
def seen_charge_id(charge_id: str) -> bool:
    """O(1) indexed lookup instead of JSON LIKE search."""
    return bool(fetchone("SELECT 1 FROM payments WHERE charge_id = ?", (charge_id,)))

# Batch payment retrieval
def get_payments_by_user(tg_id: int, limit: int = 10) -> list[dict]:
    """Efficient user payment history."""
    return fetchall(
        "SELECT * FROM payments WHERE tg_id = ? ORDER BY created_at DESC LIMIT ?",
        (tg_id, limit)
    )
```

### Concurrent Access Optimization

#### Connection Management
```python
# Use immediate transactions for payments
def record_payment_safe(charge_id: str, **kwargs) -> int:
    """Use BEGIN IMMEDIATE for critical payment operations."""
    return execute_immediate(
        "INSERT INTO payments (...) VALUES (...)",
        payment_params,
    )
```

#### Lock Minimization
```python
# Minimize transaction scope
def process_successful_payment(payment_data: dict) -> int:
    """Separate recording from business logic to minimize lock time."""
    # Quick payment recording with immediate transaction
    payment_id = record_payment_idempotent(charge_id=payment_data["charge_id"], ...)
    
    # Business logic outside transaction
    if payment_id and was_inserted:
        process_subscription_upgrade(payment_data)
        send_confirmation_message(payment_data)
    
    return payment_id
```

## Testing Strategy

### Unit Testing

#### Database Layer Tests
```python
def test_charge_id_uniqueness():
    """Test UNIQUE constraint enforcement."""
    charge_id = "test_unique_charge"
    
    # First payment succeeds
    payment_id_1 = record_payment(charge_id=charge_id, ...)
    assert payment_id_1 > 0
    
    # Second payment with same charge_id fails
    with pytest.raises(sqlite3.IntegrityError):
        record_payment(charge_id=charge_id, ...)

def test_idempotent_recording():
    """Test INSERT OR IGNORE idempotency."""
    charge_id = "test_idempotent_charge"
    
    # First call inserts
    payment_id_1, was_inserted_1 = record_payment_idempotent(charge_id=charge_id, ...)
    assert was_inserted_1 is True
    
    # Second call returns existing
    payment_id_2, was_inserted_2 = record_payment_idempotent(charge_id=charge_id, ...)
    assert payment_id_2 == payment_id_1
    assert was_inserted_2 is False
```

#### Concurrent Processing Tests
```python
def test_concurrent_payment_processing():
    """Test thread-safe payment processing."""
    charge_id = "concurrent_test_charge"
    results = []
    
    def process_payment(thread_id):
        payment_id, was_inserted = record_payment_idempotent(charge_id=charge_id, ...)
        results.append((thread_id, payment_id, was_inserted))
    
    # Run 10 concurrent threads
    threads = [threading.Thread(target=process_payment, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Verify exactly one insertion
    insertions = [r for r in results if r[2]]  # was_inserted=True
    assert len(insertions) == 1
    
    # All have same payment_id
    payment_ids = [r[1] for r in results]
    assert len(set(payment_ids)) == 1
```

### Integration Testing

#### Handler Testing
```python
async def test_star_transaction_handler():
    """Test complete StarTransaction flow."""
    # Mock StarTransaction update
    star_tx = Mock()
    star_tx.id = "test_star_tx"
    star_tx.to_dict.return_value = {"id": "test_star_tx", "amount": 1000}
    
    update = create_mock_update(star_transaction=star_tx)
    
    await handle_star_transaction(update, mock_context)
    
    # Verify payment recorded
    payment = get_payment_by_charge_id("star_tx_test_star_tx")
    assert payment is not None
    assert payment["status"] == "star_transaction"

async def test_refunded_payment_handler():
    """Test complete RefundedPayment flow."""
    refunded = Mock()
    refunded.telegram_payment_charge_id = "original_charge"
    refunded.total_amount = 5000
    refunded.to_dict.return_value = {...}
    
    update = create_mock_update(refunded_payment=refunded)
    
    await handle_refunded_payment(update, mock_context)
    
    # Verify refund recorded
    payment = get_payment_by_charge_id("refund_original_charge")
    assert payment is not None
    assert payment["status"] == "refunded"
```

### Performance Testing

#### Load Testing
```python
def test_payment_processing_under_load():
    """Test payment system under concurrent load."""
    import time
    
    start_time = time.time()
    successful_payments = 0
    
    def payment_worker():
        for i in range(100):
            try:
                charge_id = f"load_test_{threading.current_thread().ident}_{i}"
                payment_id = record_payment(charge_id=charge_id, ...)
                if payment_id > 0:
                    successful_payments += 1
            except Exception:
                pass
    
    # Run 20 threads, 100 payments each = 2000 total
    threads = [threading.Thread(target=payment_worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    duration = time.time() - start_time
    throughput = successful_payments / duration
    
    # Should handle >100 payments/second
    assert throughput > 100
    assert successful_payments >= 1950  # Allow some failures
```

## Security Considerations

### Input Validation

#### Charge ID Sanitization
```python
def validate_charge_id(charge_id: str) -> str:
    """Validate and sanitize charge_id input."""
    if not charge_id or not isinstance(charge_id, str):
        raise ValueError("charge_id must be non-empty string")
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[^\w\-_]', '', charge_id)
    
    if len(sanitized) > 255:  # Database column limit
        raise ValueError("charge_id too long")
    
    return sanitized
```

#### Amount Validation
```python
def validate_payment_amount(amount_cents: int, currency: str) -> None:
    """Validate payment amount ranges."""
    if currency == "XTR":
        if not (1 <= amount_cents <= 2500000):  # Telegram Stars limits
            raise ValueError(f"Invalid XTR amount: {amount_cents}")
    elif currency == "USD":
        if not (50 <= amount_cents <= 100000000):  # $0.50 to $1M
            raise ValueError(f"Invalid USD amount: {amount_cents}")
```

### Data Protection

#### PII Handling
```python
def sanitize_payment_data(raw_data: dict) -> dict:
    """Remove PII from payment data before storage."""
    # Remove sensitive user data
    sensitive_fields = ["user_name", "first_name", "last_name", "phone_number"]
    sanitized = {k: v for k, v in raw_data.items() if k not in sensitive_fields}
    
    # Hash user identifiers
    if "user_id" in sanitized:
        sanitized["user_id_hash"] = hashlib.sha256(str(sanitized["user_id"]).encode()).hexdigest()[:16]
    
    return sanitized
```

#### Audit Trail Protection
```python
def log_payment_action(payment_id: int, action: str, user_id: int) -> None:
    """Log payment action with privacy protection."""
    # Log without PII
    logger.info(
        "Payment action: payment_id=%d, action=%s, user_hash=%s",
        payment_id,
        action,
        hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
    )
```

## Monitoring & Alerting

### Key Metrics

#### Payment Processing Metrics
```python
# Prometheus metrics
payments_total = Counter(
    "cyberbro_payments_total",
    "Total payments processed",
    labelnames=("status", "payment_type", "currency")
)

payment_processing_duration = Histogram(
    "cyberbro_payment_processing_duration_seconds", 
    "Payment processing time",
    labelnames=("payment_type",)
)

duplicate_payments_total = Counter(
    "cyberbro_duplicate_payments_total",
    "Duplicate payments detected",
    labelnames=("payment_type",)
)
```

#### Database Performance Metrics
```python
charge_id_lookup_duration = Histogram(
    "cyberbro_charge_id_lookup_duration_seconds",
    "Charge ID lookup time"
)

payment_insert_errors_total = Counter(
    "cyberbro_payment_insert_errors_total",
    "Payment insertion errors",
    labelnames=("error_type",)
)
```

### Health Checks

#### Payment System Health
```python
async def check_payment_system_health() -> dict:
    """Comprehensive payment system health check."""
    health = {"status": "healthy", "checks": {}}
    
    try:
        # Test charge_id lookup performance
        start = time.time()
        seen_charge_id("health_check_test")
        lookup_time = time.time() - start
        
        health["checks"]["charge_id_lookup"] = {
            "status": "healthy" if lookup_time < 0.01 else "degraded",
            "duration_ms": lookup_time * 1000
        }
        
        # Test payment insertion
        test_payment_id = record_payment(
            tg_id=0,
            amount_cents=1,
            currency="TEST",
            provider="health_check",
            status="test",
            raw={},
            charge_id=f"health_{int(time.time())}"
        )
        
        health["checks"]["payment_insertion"] = {
            "status": "healthy" if test_payment_id > 0 else "unhealthy",
            "test_payment_id": test_payment_id
        }
        
    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)
    
    return health
```

#### Alerting Rules
```yaml
# Prometheus alerting rules
groups:
  - name: cyberbro_payments
    rules:
      - alert: HighPaymentDuplicateRate
        expr: rate(cyberbro_duplicate_payments_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High payment duplicate detection rate"
          
      - alert: PaymentProcessingErrors
        expr: rate(cyberbro_payment_insert_errors_total[5m]) > 0.01
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Payment processing errors detected"
          
      - alert: SlowChargeIdLookups
        expr: histogram_quantile(0.95, cyberbro_charge_id_lookup_duration_seconds) > 0.01
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow charge_id lookups detected"
```

## Migration Plan

### Phase 1: Database Schema Migration
1. **Add charge_id column** to payments table (nullable for backward compatibility)
2. **Create indexes** for performance optimization
3. **Test schema changes** в staging environment
4. **Deploy schema changes** to production (zero-downtime)

### Phase 2: Enhanced Recording Functions
1. **Deploy new payment recording functions** (backward compatible)
2. **Update existing SuccessfulPayment handling** to use charge_id
3. **Monitor performance impact** и error rates
4. **Gradual rollout** с feature flags

### Phase 3: Extended Payment Types
1. **Deploy StarTransaction handlers** и recording
2. **Deploy RefundedPayment handlers** и recording  
3. **Add comprehensive testing** для new flows
4. **Monitor new payment types** и metrics

### Phase 4: Performance Optimization
1. **Optimize seen_charge_id()** to use index instead of LIKE
2. **Remove legacy JSON-based lookups** after validation
3. **Tune database performance** based на production data
4. **Add advanced monitoring** и alerting

## Success Criteria

### Key Performance Indicators
- **Idempotency accuracy**: 100% duplicate detection via charge_id
- **Query performance**: charge_id lookup <1ms (vs >10ms LIKE search)
- **Concurrent processing**: Support 50+ simultaneous payments
- **Payment type coverage**: 100% SuccessfulPayment, StarTransaction, RefundedPayment

### Quality Gates
- **Test coverage**: ≥95% для payment processing code
- **Performance**: No regression в single-threaded processing
- **Reliability**: Zero payment duplicates в production
- **Audit compliance**: 100% payment operations logged

### Business Metrics
- **Financial accuracy**: Zero billing discrepancies from payment issues
- **User satisfaction**: Instant refund processing и notification
- **Support reduction**: 50% fewer payment-related support tickets
- **System reliability**: 99.99% payment processing uptime


