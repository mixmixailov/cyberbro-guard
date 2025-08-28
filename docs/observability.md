# 🔍 Observability Guide

This document describes the observability infrastructure in CyberBro Guard, including structured logging, metrics, and debugging capabilities.

## 📊 Structured Logging

### JSON Log Format

All logs are structured JSON with the following fields:

```json
{
  "ts": "2024-01-15T10:30:45.123456Z",
  "level": "INFO", 
  "area": "handlers",
  "chat_id": 12345,
  "job_id": "job-abc-123",
  "issue_id": "bug-456",
  "trace_id": "tr-789def",
  "logger": "app.handlers.payments",
  "msg": "Payment processed successfully",
  "request_id": "req-xyz",
  "update_id": 789,
  "user_id": 67890,
  "hypothesis_id": "h1-timeout"
}
```

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `ts` | string | ISO timestamp in UTC |
| `level` | string | Log level (DEBUG, INFO, WARN, ERROR) |
| `area` | string | Processing area ("handlers", "services", "payments", etc.) |
| `chat_id` | int | Telegram chat ID if available |
| `job_id` | string | Background job/task identifier |
| `issue_id` | string | Bug tracking ID for investigations |
| `trace_id` | string | Request/operation trace ID |
| `logger` | string | Python logger name |
| `msg` | string | Log message (PII redacted) |

### PII Redaction

Automatic redaction of sensitive data:

- **Emails**: `user@example.com` → `***@example.com`
- **Tokens**: `Bot 123456:ABC-DEF` → `Bot ***ABC-DEF`
- **API Keys**: `"api_key": "secretkey123"` → `"api_key": "***123"`
- **Phone Numbers**: `+1-555-123-4567` → `***4567`

In DEBUG_TRACE mode, enhanced redaction includes:
- Credit card numbers → `****-****-****-****`
- IP addresses → `192.***.***.***`
- URL credentials → `https://***:***@api.example.com`

## 🎯 Area-Based Observability

### Setting Processing Areas

Use context managers to set the current processing area:

```python
from app.utils.observability import area_context, job_context

# Set area for all logs within context
with area_context("payments"):
    logger.info("Processing payment")  # area: "payments"
    
    # Nested job context
    with job_context("pay-123"):
        logger.info("Validating payment")  # area: "payments", job_id: "pay-123"
```

### Available Areas

- `handlers` - Telegram message/callback handlers
- `services` - Business logic services
- `payments` - Payment processing
- `moderation` - Content moderation
- `ai` - AI/ML operations
- `db` - Database operations
- `queue` - Background job processing
- `scheduler` - Scheduled tasks

## 🐛 DEBUG_TRACE Feature Flag

### Configuration

Set `DEBUG_TRACE` environment variable to comma-separated area names:

```bash
# Enable DEBUG logging for specific areas
DEBUG_TRACE=handlers,payments,ai

# In .env file
DEBUG_TRACE=services,moderation
```

### Effects

When `DEBUG_TRACE` is set for an area:

1. **Enhanced Logging**: Area loggers escalate to DEBUG level
2. **Enhanced PII Redaction**: More aggressive pattern matching
3. **Detailed Traces**: Entry/exit logging for area contexts
4. **Extended Context**: Additional debugging fields in logs

### Usage Example

```python
from app.utils.observability import debug_context

# Enhanced debugging when DEBUG_TRACE=payments
with debug_context("payments", enhanced_pii=True):
    logger.debug("Payment validation details")  # Only logged if DEBUG_TRACE includes "payments"
    process_payment(data)
```

## 📈 Prometheus Metrics

### Exception Tracking

Track exceptions by area and type:

```python
from app.utils.observability import exception_tracker

@exception_tracker("services")
async def process_user_action():
    # Exceptions automatically tracked as:
    # cyberbro_exceptions_total{area="services", exception_type="ValueError"}
    pass
```

### Handler Latency

Measure processing time for handlers:

```python 
from app.metrics import handler_latency_seconds

# Manual timing
with handler_latency_seconds.labels(area="handlers", handler="payment").time():
    await handle_payment()

# Or using decorator from existing code
from app.metrics import timeit, webhook_latency_seconds

@timeit(webhook_latency_seconds, "payment_handler")
async def handle_payment():
    pass
```

### Available Metrics

#### Core Application Metrics
- `cyberbro_exceptions_total{area, exception_type}` - Exception counts by area
- `cyberbro_handler_latency_seconds{area, handler}` - Handler processing latency
- `cyberbro_webhook_latency_seconds{handler}` - Webhook handling latency

#### Business Metrics
- `cyberbro_updates_total{type, chat_type}` - Telegram updates received
- `cyberbro_commands_total{command}` - Commands processed
- `cyberbro_payments_total{status}` - Payment transactions
- `cyberbro_moderation_actions_total{action}` - Moderation actions taken

#### Infrastructure Metrics
- `cyberbro_dlq_size{type}` - Dead letter queue size
- `cyberbro_wal_pages` - Database WAL file pages
- `cyberbro_sched_runs_total{job}` - Scheduler job executions

## 🔧 Integration Examples

### Handler Implementation

```python
from app.utils.observability import area_context, exception_tracker
from app.utils.logging import set_update_context
from app.metrics import handler_latency_seconds

@exception_tracker("handlers")
async def handle_payment_callback(update, context):
    # Set Telegram context
    set_update_context(
        update_id=update.update_id,
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id
    )
    
    # Set processing area
    with area_context("payments"):
        with handler_latency_seconds.labels(area="handlers", handler="payment").time():
            logger.info("Processing payment callback")
            await process_payment(update.callback_query.data)
```

### Service Implementation

```python
from app.utils.observability import area_context, job_context, exception_tracker
from app.utils.diag import trace_section, set_issue_id

@exception_tracker("services")
async def process_subscription_renewal(user_id: int, subscription_id: str):
    job_id = f"renew-{subscription_id}"
    
    with area_context("services"):
        with job_context(job_id):
            with trace_section("subscription_renewal") as trace_id:
                logger.info("Starting subscription renewal", extra={
                    "user_id": user_id,
                    "subscription_id": subscription_id
                })
                
                # Process renewal logic
                await charge_payment(user_id, subscription_id)
                await update_subscription_status(subscription_id)
```

### Bug Investigation

```python
from app.utils.diag import set_issue_id, set_hypothesis_id
from app.utils.observability import debug_context

# When investigating bug report
set_issue_id("bug-12345")

# Test hypothesis with enhanced logging
for hypothesis in ["h1-timeout", "h2-race-condition", "h3-validation"]:
    set_hypothesis_id(hypothesis)
    
    with debug_context("payments", enhanced_pii=True):
        logger.info(f"Testing hypothesis: {hypothesis}")
        # All logs will include issue_id and hypothesis_id
        await test_payment_scenario()
```

## 📊 Observability Dashboard

### Grafana Queries

**Exception Rate by Area:**
```promql
rate(cyberbro_exceptions_total[5m])
```

**Handler Latency P95:**
```promql
histogram_quantile(0.95, rate(cyberbro_handler_latency_seconds_bucket[5m]))
```

**Top Exception Types:**
```promql
topk(5, sum by (exception_type) (rate(cyberbro_exceptions_total[1h])))
```

### Alert Rules

**High Exception Rate:**
```yaml
- alert: HighExceptionRate
  expr: rate(cyberbro_exceptions_total[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "High exception rate in {{ $labels.area }}"
```

**Handler Latency Alert:**
```yaml
- alert: HighHandlerLatency
  expr: histogram_quantile(0.95, rate(cyberbro_handler_latency_seconds_bucket[5m])) > 5
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Handler latency P95 > 5s in {{ $labels.area }}"
```

## 🛠️ Development Setup

### Local Development

```bash
# Enable debug tracing for development
export DEBUG_TRACE=handlers,services,payments

# Start application with enhanced logging
python -m app.main
```

### Testing Observability

```python
# Test metrics collection
from app.metrics import exceptions_total, handler_latency_seconds

# Test exception tracking
try:
    raise ValueError("test error")
except ValueError:
    exceptions_total.labels(area="test", exception_type="ValueError").inc()

# Test latency measurement
import time
with handler_latency_seconds.labels(area="test", handler="example").time():
    time.sleep(0.1)
```

### Log Analysis

```bash
# Filter logs by area
docker logs cyberbro-guard | jq 'select(.area == "payments")'

# Find errors with trace_id
docker logs cyberbro-guard | jq 'select(.level == "ERROR" and .trace_id != null)'

# Debug specific hypothesis
docker logs cyberbro-guard | jq 'select(.hypothesis_id == "h1-timeout")'
```

## 🔍 Troubleshooting

### Common Issues

**1. Missing area in logs**
- Ensure `area_context()` is used in code path
- Check that observability setup is called in application startup

**2. DEBUG_TRACE not working**
- Verify environment variable is set correctly
- Check that `setup_area_logging()` is called during initialization
- Confirm area names match those used in `area_context()`

**3. Metrics not appearing**
- Ensure Prometheus middleware is attached to FastAPI app
- Check that `/metrics` endpoint is accessible
- Verify metric labels are low-cardinality

### Performance Considerations

- **Log Volume**: DEBUG_TRACE can significantly increase log volume
- **Metric Cardinality**: Keep label values bounded to prevent metric explosion
- **PII Redaction**: Enhanced redaction adds processing overhead in debug mode

### Best Practices

1. **Use area contexts consistently** across all major code paths
2. **Set job_id for background tasks** to track execution
3. **Include relevant extra fields** in log statements
4. **Monitor metric cardinality** to prevent memory issues
5. **Use DEBUG_TRACE sparingly** in production environments
