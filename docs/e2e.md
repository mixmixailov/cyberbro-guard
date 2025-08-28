# End-to-End Testing Documentation

## Overview

Данная документация описывает E2E тестирование CyberBro Guard через Playwright MCP для автоматизации полного payment flow: от первого контакта с ботом до подтверждения успешной подписки.

## MCP Integration

### Playwright MCP Server
```json
{
  "playwright": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-playwright@latest"],
    "env": {
      "PLAYWRIGHT_BROWSER": "chromium"
    },
    "alwaysAllow": [
      "browser_navigate",
      "browser_snapshot", 
      "browser_click",
      "browser_type",
      "browser_evaluate",
      "browser_take_screenshot"
    ]
  }
}
```

### Context7 MCP Server
```json
{
  "context7": {
    "command": "npx", 
    "args": ["@context7/mcp-server@latest"],
    "env": {
      "CONTEXT7_API_KEY": ""
    },
    "alwaysAllow": [
      "resolve-library-id",
      "get-library-docs"
    ]
  }
}
```

## Core E2E Scenario: Complete Payment Flow

### Scenario Overview
**Цель**: Протестировать полный цикл пользователя от знакомства с ботом до получения PRO подписки.

**Участники**:
- **New User**: Пользователь, впервые взаимодействующий с ботом
- **CyberBro Guard Bot**: Telegram bot instance
- **Payment System**: Telegram Stars payment processing
- **Database**: SQLite с payment records

**Предусловия**:
- Bot запущен и доступен via webhook
- Telegram Stars payments enabled (`PAYMENTS_STARS_ENABLED=true`)
- Test mode enabled (`PAYMENTS_STARS_TEST=true`)
- Database инициализирована с планами

### Step-by-Step E2E Flow

#### **Step 1: Initial Contact - `/start` Command**

**Action**: User sends `/start` command to bot
```
User -> Bot: /start
```

**Expected Bot Response**:
```
Добро пожаловать в CyberBro Guard! 🤖

Я помогу защитить ваш чат от спама и нежелательного контента.

Основные команды:
• /plan - проверить текущий план
• /buy_pro - купить PRO подписку  
• /help - помощь

Для начала работы добавьте меня в группу как администратора.
```

**E2E Test Assertions**:
- ✅ Bot responds within 2 seconds
- ✅ Response contains welcome message
- ✅ Response includes /plan and /buy_pro commands
- ✅ User record created in database (tg_id, plan='free')
- ✅ No errors in application logs

**Playwright Implementation**:
```python
async def test_start_command():
    # Simulate webhook call with /start command
    webhook_payload = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": 12345, "first_name": "TestUser", "is_bot": False},
            "chat": {"id": 12345, "type": "private"},
            "text": "/start",
            "date": int(time.time())
        }
    }
    
    response = await send_webhook(webhook_payload)
    assert response.status_code == 200
    
    # Verify database state
    user = get_user_by_tg_id(12345)
    assert user["plan"] == "free"
```

#### **Step 2: Plan Status Check - `/plan` Command**

**Action**: User checks current subscription status
```
User -> Bot: /plan
```

**Expected Bot Response**:
```
📊 Ваш план: FREE

Ограничения FREE плана:
• Базовая защита от спама
• AI модерация: 100 запросов/месяц
• Поддержка: community форум

⭐ Обновитесь до PRO для расширенных возможностей!
/buy_pro - купить PRO подписку
```

**E2E Test Assertions**:
- ✅ Bot responds with current plan status
- ✅ Shows FREE plan limitations
- ✅ Includes upgrade call-to-action
- ✅ Response time < 1 second

#### **Step 3: Purchase Initiation - `/buy_pro` Command**

**Action**: User initiates PRO subscription purchase
```
User -> Bot: /buy_pro
```

**Expected Bot Response**:
```
Bot -> User: Telegram Invoice
{
  "title": "CyberBro Guard PRO",
  "description": "Подписка на 30 дней", 
  "payload": "buy_pro_30d",
  "currency": "XTR",
  "prices": [{"label": "PRO", "amount": 4900}],
  "provider_data": {"test": true}
}
```

**E2E Test Assertions**:
- ✅ Invoice sent successfully
- ✅ Correct price (4900 XTR) and currency
- ✅ Proper payload for tracking
- ✅ Test mode enabled in provider_data
- ✅ Invoice appears in Telegram client

**Playwright Implementation**:
```python
async def test_buy_pro_command():
    webhook_payload = create_message_update(12345, "/buy_pro")
    
    # Mock Telegram API call
    with patch('telegram.Bot.send_invoice') as mock_invoice:
        response = await send_webhook(webhook_payload)
        
        assert response.status_code == 200
        mock_invoice.assert_called_once()
        
        # Verify invoice parameters
        call_args = mock_invoice.call_args
        assert call_args.kwargs['title'] == "CyberBro Guard PRO"
        assert call_args.kwargs['currency'] == "XTR"
        assert call_args.kwargs['prices'][0].amount == 4900
```

#### **Step 4: Payment Processing - `PreCheckoutQuery`**

**Action**: User confirms payment in Telegram client
```
Telegram -> Bot: PreCheckoutQuery
{
  "id": "query_123",
  "from": {"id": 12345},
  "currency": "XTR", 
  "total_amount": 4900,
  "invoice_payload": "buy_pro_30d"
}
```

**Expected Bot Response**:
```
Bot -> Telegram: answerPreCheckoutQuery
{
  "pre_checkout_query_id": "query_123",
  "ok": true
}
```

**E2E Test Assertions**:
- ✅ PreCheckoutQuery answered with ok=true
- ✅ Response time < 500ms
- ✅ No validation errors

#### **Step 5: Payment Completion - `SuccessfulPayment`**

**Action**: Telegram sends SuccessfulPayment after user completes payment
```
Telegram -> Bot: SuccessfulPayment
{
  "currency": "XTR",
  "total_amount": 4900,
  "invoice_payload": "buy_pro_30d",
  "telegram_payment_charge_id": "charge_12345_abc",
  "provider_payment_charge_id": "provider_abc123"
}
```

**Expected Bot Processing**:
1. **Idempotency Check**: Verify charge_id not seen before
2. **Payment Recording**: Save to payments table with charge_id
3. **Subscription Update**: Upgrade user to PRO for 30 days
4. **User Notification**: Send confirmation message
5. **Audit Logging**: Log payment action
6. **Metrics Update**: Increment payment counter

**Expected Bot Response**:
```
Квитанция: план PRO, сумма 4900 XTR, срок 30 дней.

🎉 Добро пожаловать в PRO!

Ваши новые возможности:
• Расширенная защита от спама
• AI модерация: без лимитов
• Приоритетная поддержка
• Дополнительные настройки

Подписка действительна до: 2025-02-15
```

**E2E Test Assertions**:
- ✅ Payment recorded in database
- ✅ User upgraded to PRO plan
- ✅ Subscription expiry date set correctly
- ✅ User receives confirmation message
- ✅ Idempotency: duplicate SuccessfulPayment ignored
- ✅ Audit trail logged
- ✅ Metrics updated

**Playwright Implementation**:
```python
async def test_successful_payment():
    # Send SuccessfulPayment update
    webhook_payload = {
        "update_id": 4,
        "message": {
            "message_id": 4,
            "from": {"id": 12345, "first_name": "TestUser"},
            "chat": {"id": 12345, "type": "private"},
            "date": int(time.time()),
            "successful_payment": {
                "currency": "XTR",
                "total_amount": 4900,
                "invoice_payload": "buy_pro_30d",
                "telegram_payment_charge_id": "test_charge_123",
                "provider_payment_charge_id": "provider_123"
            }
        }
    }
    
    with patch('telegram.Bot.send_message') as mock_send:
        response = await send_webhook(webhook_payload)
        
        assert response.status_code == 200
        
        # Verify database updates
        user = get_user_by_tg_id(12345)
        assert user["plan"] == "pro"
        assert user["until"] is not None
        
        # Verify payment recorded
        payment = get_payment_by_charge_id("test_charge_123")
        assert payment is not None
        assert payment["status"] == "ok"
        assert payment["amount_cents"] == 4900
        
        # Verify user notification
        mock_send.assert_called_once()
        message_text = mock_send.call_args.kwargs['text']
        assert "🎉 Добро пожаловать в PRO!" in message_text
```

#### **Step 6: Status Verification - `/plan` Command (Post-Purchase)**

**Action**: User checks subscription status after purchase
```
User -> Bot: /plan
```

**Expected Bot Response**:
```
📊 Ваш план: PRO ⭐

Активна до: 15 февраля 2025
Осталось: 29 дней

PRO возможности:
• Расширенная защита от спама ✅
• AI модерация: без лимитов ✅  
• Приоритетная поддержка ✅
• Дополнительные настройки ✅

AI квота: 0/безлимит
```

**E2E Test Assertions**:
- ✅ Shows PRO plan status
- ✅ Displays correct expiry date
- ✅ Shows days remaining
- ✅ Lists PRO features
- ✅ Shows unlimited AI quota

## Complete E2E Test Implementation

### Test Suite Structure
```python
class TestCompletePaymentFlow:
    """Complete E2E test for payment flow."""
    
    @pytest.fixture
    async def clean_test_environment(self):
        """Reset database and prepare test environment."""
        # Clear test user data
        execute("DELETE FROM users WHERE tg_id = ?", (TEST_USER_ID,))
        execute("DELETE FROM payments WHERE tg_id = ?", (TEST_USER_ID,))
        
    async def test_complete_payment_flow(self, clean_test_environment):
        """Test complete flow: /start -> /buy -> payment -> /plan."""
        
        # Step 1: /start command
        await self.send_command("/start")
        user = get_user_by_tg_id(TEST_USER_ID)
        assert user["plan"] == "free"
        
        # Step 2: /plan command (before purchase)
        response = await self.send_command("/plan")
        assert "FREE" in response
        
        # Step 3: /buy_pro command
        with patch('telegram.Bot.send_invoice') as mock_invoice:
            await self.send_command("/buy_pro")
            assert mock_invoice.called
        
        # Step 4: PreCheckoutQuery
        await self.send_pre_checkout_query()
        
        # Step 5: SuccessfulPayment
        charge_id = f"test_charge_{int(time.time())}"
        await self.send_successful_payment(charge_id)
        
        # Verify payment processing
        user = get_user_by_tg_id(TEST_USER_ID)
        assert user["plan"] == "pro"
        
        payment = get_payment_by_charge_id(charge_id)
        assert payment["status"] == "ok"
        
        # Step 6: /plan command (after purchase)
        response = await self.send_command("/plan")
        assert "PRO" in response
        assert "⭐" in response
```

### Idempotency Testing
```python
async def test_payment_idempotency(self):
    """Test that duplicate payments are properly handled."""
    charge_id = "idempotency_test_charge"
    
    # First payment
    await self.send_successful_payment(charge_id)
    
    # Verify payment recorded
    payment1 = get_payment_by_charge_id(charge_id)
    assert payment1 is not None
    
    # Second payment with same charge_id
    await self.send_successful_payment(charge_id)
    
    # Verify no duplicate payment
    payments = fetchall("SELECT * FROM payments WHERE charge_id = ?", (charge_id,))
    assert len(payments) == 1  # Only one payment
    
    # User should still have PRO
    user = get_user_by_tg_id(TEST_USER_ID)
    assert user["plan"] == "pro"
```

## Performance Benchmarks

### Response Time Targets
- **Command processing**: < 2 seconds
- **Payment processing**: < 5 seconds  
- **Database operations**: < 100ms
- **Webhook response**: < 500ms

### Load Testing Scenarios
```python
async def test_concurrent_payments():
    """Test multiple users purchasing simultaneously."""
    
    async def user_payment_flow(user_id: int):
        await send_command(user_id, "/start")
        await send_command(user_id, "/buy_pro")
        charge_id = f"concurrent_charge_{user_id}"
        await send_successful_payment(user_id, charge_id)
        
        # Verify user upgraded
        user = get_user_by_tg_id(user_id)
        assert user["plan"] == "pro"
    
    # Run 10 concurrent payment flows
    tasks = [user_payment_flow(12340 + i) for i in range(10)]
    await asyncio.gather(*tasks)
    
    # Verify all payments processed correctly
    pro_users = fetchall("SELECT * FROM users WHERE plan = 'pro'")
    assert len(pro_users) >= 10
```

## Error Scenario Testing

### Network Failures
```python
async def test_payment_with_network_errors():
    """Test payment processing with network issues."""
    
    # Simulate Telegram API timeout
    with patch('telegram.Bot.send_message', side_effect=asyncio.TimeoutError):
        await send_successful_payment("network_error_charge")
        
        # Payment should still be recorded
        payment = get_payment_by_charge_id("network_error_charge")
        assert payment is not None
        
        # User should be upgraded despite notification failure
        user = get_user_by_tg_id(TEST_USER_ID)
        assert user["plan"] == "pro"
```

### Database Constraints
```python
async def test_duplicate_charge_id_handling():
    """Test handling of duplicate charge_id constraints."""
    
    charge_id = "duplicate_constraint_test"
    
    # First payment succeeds
    await send_successful_payment(charge_id)
    
    # Second payment should be handled gracefully
    await send_successful_payment(charge_id)
    
    # No errors should occur, duplicate should be ignored
    payments = fetchall("SELECT * FROM payments WHERE charge_id = ?", (charge_id,))
    assert len(payments) == 1
```

## Monitoring & Alerting

### Key Metrics to Monitor
```python
# Payment flow completion rate
payment_flow_completion_rate = Histogram(
    "cyberbro_e2e_payment_flow_duration_seconds",
    "Time to complete full payment flow",
    buckets=(1, 5, 10, 30, 60)
)

# Step-specific metrics
command_response_time = Histogram(
    "cyberbro_e2e_command_response_time_seconds", 
    "Bot command response time",
    labelnames=("command",)
)

# Error rates
e2e_test_failures = Counter(
    "cyberbro_e2e_test_failures_total",
    "E2E test failures",
    labelnames=("test_step", "error_type")
)
```

### Health Checks
```python
async def e2e_health_check():
    """Quick E2E health check for monitoring."""
    
    try:
        # Test basic bot responsiveness
        start_time = time.time()
        await send_command(HEALTH_CHECK_USER_ID, "/start")
        response_time = time.time() - start_time
        
        if response_time > 5.0:
            return {"status": "degraded", "response_time": response_time}
        
        # Test database connectivity
        user = get_user_by_tg_id(HEALTH_CHECK_USER_ID)
        if not user:
            return {"status": "unhealthy", "error": "database_error"}
        
        return {"status": "healthy", "response_time": response_time}
        
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Continuous Integration

### GitHub Actions Integration
```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
          npx playwright install chromium
          
      - name: Setup test environment
        run: |
          export PAYMENTS_STARS_TEST=true
          export PAYMENTS_STARS_ENABLED=true
          python -c "from app.db.session import init_db; init_db()"
          
      - name: Run E2E tests
        run: |
          python -m pytest tests/e2e/ -v --tb=short
          
      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-test-artifacts
          path: |
            screenshots/
            test-results/
```

## Development Workflow

### Local E2E Testing
```bash
# Setup test environment
export PAYMENTS_STARS_TEST=true
export PAYMENTS_STARS_ENABLED=true
export DEBUG=true

# Initialize test database
python -c "from app.db.session import init_db; init_db()"

# Run specific E2E scenario
python -m pytest tests/e2e/test_payment_flow.py::test_complete_payment_flow -v -s

# Run all E2E tests
python -m pytest tests/e2e/ -v

# Run with Playwright debugging
PWDEBUG=1 python -m pytest tests/e2e/test_payment_flow.py -v -s
```

### Manual Testing Checklist
- [ ] Bot responds to /start command
- [ ] /plan shows FREE status initially  
- [ ] /buy_pro sends invoice correctly
- [ ] Payment processing works end-to-end
- [ ] /plan shows PRO status after payment
- [ ] Duplicate payments handled correctly
- [ ] Database state consistent
- [ ] All metrics collected properly

## Troubleshooting Guide

### Common Issues

#### Bot Not Responding
```python
# Check webhook configuration
curl -X POST "https://your-webhook-url.com/webhook" \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {"message_id": 1, "from": {"id": 12345}, "chat": {"id": 12345}, "text": "/start", "date": 1640995200}}'
```

#### Payment Not Processed
```python
# Check database state
python -c "
from app.db.payments import get_payment_by_charge_id
payment = get_payment_by_charge_id('your_charge_id')
print(payment)
"

# Check user subscription
python -c "
from app.db.queries import get_user_by_tg_id  
user = get_user_by_tg_id(12345)
print(user)
"
```

#### Idempotency Issues
```python
# Check for duplicate payments
python -c "
from app.db.session import fetchall
duplicates = fetchall('SELECT charge_id, COUNT(*) as count FROM payments GROUP BY charge_id HAVING count > 1')
print(duplicates)
"
```

## Best Practices

### Test Data Management
- Use deterministic test user IDs (12345, 67890, etc.)
- Clean up test data between runs
- Use test-specific charge_id patterns
- Mock external API calls for reliability

### Test Environment Isolation
- Use separate test database
- Enable test mode for payments
- Mock Telegram API responses
- Isolate tests from external dependencies

### Performance Optimization
- Run E2E tests in parallel where possible
- Use database transactions for faster cleanup
- Cache static test data
- Minimize external API calls

### Reliability Improvements
- Implement retry logic for flaky operations
- Add detailed logging for debugging
- Use deterministic test data
- Validate test environment before running


