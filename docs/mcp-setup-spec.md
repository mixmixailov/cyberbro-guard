# MCP Server Setup Specification

## Overview

Данная спецификация описывает настройку Model Context Protocol (MCP) серверов для проекта CyberBro Guard для улучшения developer experience через автоматизированный доступ к документации и E2E тестирование.

## Problem Statement

### Текущие проблемы
1. **Manual documentation lookup**: Разработчики тратят время на поиск документации API
2. **Inconsistent E2E testing**: Отсутствие автоматизированного browser-based тестирования
3. **Limited AI assistance**: AI помощник не имеет доступа к актуальной документации библиотек
4. **Development inefficiency**: Медленный feedback loop при разработке и тестировании
5. **Knowledge fragmentation**: Документация разбросана по разным источникам

### Бизнес-импакт
- **Development velocity**: Slow documentation lookup снижает продуктивность
- **Code quality**: Недостаток E2E testing приводит к bugs в production
- **Developer experience**: Фрагментированный workflow затрудняет development
- **Time to market**: Длительные development cycles из-за manual processes
- **Technical debt**: Неполное тестирование accumulates technical debt

## Goals

### Основные цели
1. **Automated documentation access через Context7 MCP**
   - Real-time access к актуальной документации Telegram Bot API
   - Automatic library documentation retrieval
   - AI-powered documentation search и contextual help
   - Consistent documentation workflow в development

2. **Browser automation через Playwright MCP**
   - Automated E2E testing capabilities
   - Visual regression testing для UI components
   - Performance testing automation
   - Cross-browser compatibility validation

3. **Enhanced developer productivity**
   - Seamless integration с Cursor IDE
   - One-click access к library documentation
   - Automated test execution и reporting
   - Reduced context switching between tools

4. **Improved code quality**
   - Comprehensive E2E test coverage
   - Automated payment flow validation
   - Visual testing capabilities
   - Performance regression detection

## Requirements

### Functional Requirements

#### FR-1: Context7 MCP Server Configuration
- **Описание**: Setup Context7 MCP server для automated documentation access
- **Критерии приёмки**:
  - Context7 server configured в .cursor/mcp.json
  - resolve-library-id function available для library lookup
  - get-library-docs function accessible для documentation retrieval
  - API key configuration support (optional для basic usage)
  - Error handling для API failures и rate limits

#### FR-2: Playwright MCP Server Configuration  
- **Описание**: Setup Playwright MCP server для browser automation
- **Критерии приёмки**:
  - Playwright server configured в .cursor/mcp.json
  - Browser navigation capabilities enabled
  - Page snapshot и screenshot functionality
  - Element interaction (click, type, evaluate) available
  - Cross-browser support (Chromium default, Firefox/WebKit optional)

#### FR-3: MCP Server Integration
- **Описание**: Seamless integration между MCP servers и development workflow
- **Критерии приёмки**:
  - Always-allow permissions для frequently used functions
  - Proper error handling при server unavailability
  - Graceful degradation когда servers offline
  - Clear documentation для MCP usage patterns

#### FR-4: E2E Testing Framework
- **Описание**: Comprehensive E2E testing framework using Playwright MCP
- **Критерии приёмки**:
  - Complete payment flow testing (/start → /buy → payment → /status)
  - Webhook simulation и validation
  - Database state verification
  - Performance benchmarking capabilities
  - Visual regression testing support

#### FR-5: Documentation Workflow Enhancement
- **Описание**: Streamlined documentation access через Context7 MCP
- **Критерии приёмки**:
  - Telegram Bot API documentation readily available
  - Python library documentation accessible
  - FastAPI documentation integration
  - SQLite и database-related documentation
  - Payment processing documentation (Telegram Stars)

### Non-Functional Requirements

#### NFR-1: Performance
- **MCP server startup time**: < 3 seconds для each server
- **Documentation lookup time**: < 2 seconds для common libraries
- **Browser automation latency**: < 1 second для basic operations
- **Memory usage**: < 500MB total для both MCP servers

#### NFR-2: Reliability
- **Server availability**: 99% uptime during development hours
- **Graceful degradation**: Development workflow continues при MCP server failures
- **Error recovery**: Automatic retry для transient failures
- **Data consistency**: E2E tests provide reliable validation

#### NFR-3: Developer Experience
- **Setup complexity**: Single command MCP server installation
- **Learning curve**: < 30 minutes для basic MCP usage
- **IDE integration**: Seamless experience в Cursor
- **Documentation quality**: Complete setup и usage documentation

## Technical Specifications

### MCP Server Configuration

#### .cursor/mcp.json Structure
```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["@context7/mcp-server@latest"],
      "env": {
        "CONTEXT7_API_KEY": ""
      },
      "disabled": false,
      "alwaysAllow": [
        "resolve-library-id",
        "get-library-docs"
      ]
    },
    "playwright": {
      "command": "npx", 
      "args": ["@modelcontextprotocol/server-playwright@latest"],
      "env": {
        "PLAYWRIGHT_BROWSER": "chromium"
      },
      "disabled": false,
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
}
```

#### Context7 Server Functions
```typescript
// Library ID resolution
interface ResolveLibraryId {
  libraryName: string;
  returns: string; // Context7-compatible library ID
}

// Documentation retrieval
interface GetLibraryDocs {
  context7CompatibleLibraryID: string;
  tokens?: number; // Max tokens (default: 10000)
  topic?: string; // Focus topic (e.g., 'payments', 'webhooks')
  returns: string; // Formatted documentation
}
```

#### Playwright Server Functions
```typescript
// Browser navigation
interface BrowserNavigate {
  url: string;
  returns: void;
}

// Page snapshot for element identification
interface BrowserSnapshot {
  returns: string; // Accessibility tree representation
}

// Element interaction
interface BrowserClick {
  element: string; // Human-readable description  
  ref: string; // Element reference from snapshot
  returns: void;
}

interface BrowserType {
  element: string;
  ref: string;
  text: string;
  slowly?: boolean; // Character-by-character typing
  submit?: boolean; // Press Enter after typing
  returns: void;
}

// JavaScript evaluation
interface BrowserEvaluate {
  function: string; // JavaScript function to execute
  element?: string; // Target element description
  ref?: string; // Element reference
  returns: any; // Function return value
}

// Screenshot capture
interface BrowserTakeScreenshot {
  element?: string; // Target element
  ref?: string; // Element reference  
  filename?: string; // Output filename
  fullPage?: boolean; // Full page screenshot
  returns: string; // Screenshot path
}
```

### Integration Patterns

#### Documentation Lookup Workflow
```python
# 1. Resolve library ID
library_id = resolve_library_id("python-telegram-bot")
# Returns: "/python-telegram-bot/python-telegram-bot"

# 2. Get focused documentation
docs = get_library_docs(
    context7CompatibleLibraryID=library_id,
    topic="payments",
    tokens=5000
)
# Returns: Detailed payment-related documentation
```

#### E2E Testing Workflow
```python
# 1. Navigate to test environment
browser_navigate("http://localhost:8000")

# 2. Get page snapshot for element identification
snapshot = browser_snapshot()

# 3. Interact with elements
browser_click(
    element="Start bot button", 
    ref="button[data-action='start-bot']"
)

# 4. Verify results
result = browser_evaluate(
    function="() => document.querySelector('.status').textContent"
)

# 5. Capture evidence
browser_take_screenshot(
    filename="e2e-test-result.png",
    fullPage=True
)
```

### Error Handling Strategy

#### MCP Server Failures
```python
def with_mcp_fallback(mcp_function, fallback_action):
    """Execute MCP function with graceful fallback."""
    try:
        return mcp_function()
    except MCPServerUnavailable:
        logger.warning("MCP server unavailable, using fallback")
        return fallback_action()
    except MCPTimeout:
        logger.error("MCP server timeout")
        raise
```

#### Documentation Lookup Errors
```python
# Fallback documentation sources
FALLBACK_DOCS = {
    "python-telegram-bot": "https://docs.python-telegram-bot.org/",
    "fastapi": "https://fastapi.tiangolo.com/",
    "sqlite": "https://docs.python.org/3/library/sqlite3.html"
}

def get_documentation(library_name: str) -> str:
    try:
        # Try Context7 first
        library_id = resolve_library_id(library_name)
        return get_library_docs(library_id)
    except Exception:
        # Fallback to static URLs
        fallback_url = FALLBACK_DOCS.get(library_name)
        return f"Documentation available at: {fallback_url}"
```

#### Browser Automation Errors
```python
def safe_browser_action(action_func, max_retries=3):
    """Execute browser action with retry logic."""
    for attempt in range(max_retries):
        try:
            return action_func()
        except BrowserNotResponding:
            if attempt < max_retries - 1:
                time.sleep(1 * (2 ** attempt))  # Exponential backoff
                continue
            raise
        except ElementNotFound as e:
            # Take screenshot for debugging
            browser_take_screenshot(
                filename=f"element-not-found-{int(time.time())}.png"
            )
            raise
```

## E2E Testing Implementation

### Core Test Scenarios

#### Payment Flow Test
```python
async def test_complete_payment_flow():
    """Test /start -> /buy -> payment -> /status flow."""
    
    # Navigate to webhook endpoint
    browser_navigate("http://localhost:8000/webhook")
    
    # Simulate /start command
    webhook_payload = create_start_command_payload(TEST_USER_ID)
    response = await send_webhook_request(webhook_payload)
    
    # Verify bot response
    assert response.status_code == 200
    
    # Check database state
    user = get_user_by_tg_id(TEST_USER_ID)
    assert user["plan"] == "free"
    
    # Test /buy_pro command
    buy_payload = create_buy_command_payload(TEST_USER_ID)
    with patch('telegram.Bot.send_invoice') as mock_invoice:
        response = await send_webhook_request(buy_payload)
        assert mock_invoice.called
    
    # Simulate successful payment
    payment_payload = create_successful_payment_payload(
        TEST_USER_ID, 
        charge_id="test_charge_123"
    )
    response = await send_webhook_request(payment_payload)
    
    # Verify payment processing
    user = get_user_by_tg_id(TEST_USER_ID)
    assert user["plan"] == "pro"
    
    payment = get_payment_by_charge_id("test_charge_123")
    assert payment["status"] == "ok"
    
    # Test /plan status command
    plan_payload = create_plan_command_payload(TEST_USER_ID)
    response = await send_webhook_request(plan_payload)
    
    # Verify PRO status displayed
    # (Response verification would depend on bot implementation)
    
    # Take screenshot for visual verification
    browser_take_screenshot(
        filename="payment-flow-complete.png",
        fullPage=True
    )
```

#### Idempotency Validation Test
```python
async def test_payment_idempotency():
    """Test duplicate payment handling."""
    
    charge_id = "idempotency_test_charge"
    
    # First payment
    payment_payload = create_successful_payment_payload(
        TEST_USER_ID,
        charge_id=charge_id
    )
    response1 = await send_webhook_request(payment_payload)
    assert response1.status_code == 200
    
    # Verify payment recorded
    payment1 = get_payment_by_charge_id(charge_id)
    assert payment1 is not None
    
    # Duplicate payment
    response2 = await send_webhook_request(payment_payload)
    assert response2.status_code == 200
    
    # Verify no duplicate in database
    payments = fetchall(
        "SELECT * FROM payments WHERE charge_id = ?", 
        (charge_id,)
    )
    assert len(payments) == 1
    
    # Take screenshot of final state
    browser_take_screenshot(filename="idempotency-test-result.png")
```

### Performance Testing
```python
async def test_payment_processing_performance():
    """Test payment processing under load."""
    
    import time
    import asyncio
    
    async def single_payment_flow(user_id: int) -> float:
        """Execute single payment flow and return duration."""
        start_time = time.time()
        
        # Start command
        await send_webhook_request(create_start_command_payload(user_id))
        
        # Buy command  
        await send_webhook_request(create_buy_command_payload(user_id))
        
        # Successful payment
        charge_id = f"perf_test_{user_id}"
        await send_webhook_request(
            create_successful_payment_payload(user_id, charge_id)
        )
        
        return time.time() - start_time
    
    # Run 10 concurrent payment flows
    user_ids = [20000 + i for i in range(10)]
    durations = await asyncio.gather(*[
        single_payment_flow(uid) for uid in user_ids
    ])
    
    # Verify performance targets
    avg_duration = sum(durations) / len(durations)
    max_duration = max(durations)
    
    assert avg_duration < 5.0, f"Average flow duration {avg_duration}s exceeds 5s"
    assert max_duration < 10.0, f"Max flow duration {max_duration}s exceeds 10s"
    
    # Verify all payments processed
    for uid in user_ids:
        user = get_user_by_tg_id(uid)
        assert user["plan"] == "pro"
    
    # Document performance results
    browser_evaluate(f"""
        () => {{
            document.body.innerHTML = `
                <h1>Performance Test Results</h1>
                <p>Average Duration: {avg_duration:.2f}s</p>
                <p>Max Duration: {max_duration:.2f}s</p>
                <p>Total Flows: {len(durations)}</p>
                <p>All tests passed ✅</p>
            `;
        }}
    """)
    
    browser_take_screenshot(filename="performance-test-results.png")
```

## Development Workflow Integration

### IDE Integration Patterns

#### Context7 Usage in Development
```python
# Common documentation lookup patterns

# 1. Telegram Bot API reference
"""
@ai: Use Context7 to get Telegram Bot API documentation for SuccessfulPayment
"""
# AI will use: resolve-library-id("telegram-bot-api") -> get-library-docs(...)

# 2. Python library documentation  
"""
@ai: Get FastAPI documentation for webhook handling best practices
"""
# AI will resolve FastAPI docs and provide relevant sections

# 3. Payment-specific documentation
"""
@ai: Show Telegram Stars payment documentation with code examples
"""
# AI will focus on payment-related documentation from Telegram API
```

#### Playwright Usage for Testing
```python
# E2E test development workflow

# 1. Interactive test development
"""
@ai: Use Playwright to navigate to localhost:8000 and take a screenshot
"""
# AI will: browser_navigate() -> browser_take_screenshot()

# 2. Element identification
"""
@ai: Get page snapshot and identify the payment button
"""
# AI will: browser_snapshot() -> analyze elements -> provide ref

# 3. Automated test execution
"""
@ai: Click the payment button and verify the response
"""
# AI will: browser_click() -> browser_evaluate() -> validate results
```

### Code Generation Assistance

#### Template Generation
```python
# AI can generate test templates using MCP
"""
@ai: Generate an E2E test for webhook validation using our payment flow
Include Context7 docs for Telegram webhooks and use Playwright for automation
"""

# AI will:
# 1. Use Context7 to get webhook documentation
# 2. Generate test structure with Playwright actions
# 3. Include proper assertions and error handling
```

#### Documentation-Driven Development
```python
# Reference implementation generation
"""
@ai: Based on Telegram Bot API docs, implement a handler for RefundedPayment
Use the existing pattern from SuccessfulPayment handler
"""

# AI will:
# 1. Get Telegram Bot API docs via Context7
# 2. Analyze existing SuccessfulPayment implementation
# 3. Generate RefundedPayment handler following same patterns
```

## Security Considerations

### MCP Server Security

#### API Key Management
```python
# Context7 API key (optional but recommended for rate limits)
CONTEXT7_API_KEY = os.getenv("CONTEXT7_API_KEY", "")

# No sensitive data stored in MCP config
# API keys loaded from environment variables only
```

#### Permission Management  
```json
{
  "alwaysAllow": [
    "resolve-library-id",
    "get-library-docs",
    "browser_navigate",
    "browser_snapshot"
  ]
  // Only safe, read-only operations pre-approved
  // Destructive operations require explicit permission
}
```

#### Browser Security
```python
# Playwright browser isolation
PLAYWRIGHT_BROWSER_OPTIONS = {
    "headless": True,  # No GUI for security
    "sandbox": True,   # Sandboxed browser process
    "disable_dev_shm_usage": True,  # Avoid shared memory issues
    "no_first_run": True  # Skip first-run setup
}

# Network isolation for tests
TEST_NETWORK_CONFIG = {
    "block_external_requests": True,
    "allowed_domains": ["localhost", "127.0.0.1"],
    "timeout": 30000  # 30 second timeout
}
```

### Data Protection

#### Test Data Sanitization
```python
def sanitize_test_data(test_payload: dict) -> dict:
    """Remove sensitive data from test payloads."""
    sensitive_fields = ["real_user_id", "actual_charge_id", "api_key"]
    
    sanitized = test_payload.copy()
    for field in sensitive_fields:
        if field in sanitized:
            sanitized[field] = f"test_{field}"
    
    return sanitized
```

#### Audit Trail
```python
def log_mcp_usage(server: str, function: str, args: dict) -> None:
    """Log MCP server usage for audit."""
    logger.info(
        "MCP usage: server=%s, function=%s, args_hash=%s",
        server,
        function,
        hashlib.sha256(str(args).encode()).hexdigest()[:16]
    )
```

## Monitoring & Metrics

### MCP Server Health
```python
# Prometheus metrics for MCP servers
mcp_server_requests_total = Counter(
    "cyberbro_mcp_requests_total",
    "Total MCP server requests",
    labelnames=("server", "function", "status")
)

mcp_server_response_time = Histogram(
    "cyberbro_mcp_response_time_seconds",
    "MCP server response time",
    labelnames=("server", "function")
)

mcp_server_errors_total = Counter(
    "cyberbro_mcp_errors_total", 
    "MCP server errors",
    labelnames=("server", "error_type")
)
```

### E2E Test Metrics
```python
e2e_test_duration = Histogram(
    "cyberbro_e2e_test_duration_seconds",
    "E2E test execution time",
    labelnames=("test_name", "status")
)

e2e_test_failures = Counter(
    "cyberbro_e2e_test_failures_total",
    "E2E test failures",
    labelnames=("test_name", "failure_reason")
)

payment_flow_success_rate = Gauge(
    "cyberbro_payment_flow_success_rate",
    "Payment flow success rate from E2E tests"
)
```

### Health Checks
```python
async def check_mcp_servers_health() -> dict:
    """Health check for MCP servers."""
    health = {"status": "healthy", "servers": {}}
    
    # Test Context7 server
    try:
        start = time.time()
        library_id = resolve_library_id("python")
        duration = time.time() - start
        
        health["servers"]["context7"] = {
            "status": "healthy" if duration < 2.0 else "degraded",
            "response_time": duration
        }
    except Exception as e:
        health["servers"]["context7"] = {
            "status": "unhealthy", 
            "error": str(e)
        }
    
    # Test Playwright server
    try:
        start = time.time()
        browser_navigate("about:blank")
        browser_snapshot()
        duration = time.time() - start
        
        health["servers"]["playwright"] = {
            "status": "healthy" if duration < 3.0 else "degraded",
            "response_time": duration  
        }
    except Exception as e:
        health["servers"]["playwright"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Overall health
    server_statuses = [s["status"] for s in health["servers"].values()]
    if any(status == "unhealthy" for status in server_statuses):
        health["status"] = "unhealthy"
    elif any(status == "degraded" for status in server_statuses):
        health["status"] = "degraded"
    
    return health
```

## Success Criteria

### Key Performance Indicators
- **Documentation lookup time**: <2 seconds для common libraries
- **E2E test execution time**: <30 seconds для complete payment flow
- **MCP server availability**: >99% during development hours
- **Developer adoption**: >80% of team uses MCP features regularly

### Quality Gates
- **Setup complexity**: Single command MCP installation
- **Test coverage**: 100% critical payment flows covered by E2E tests  
- **Documentation coverage**: All major libraries accessible via Context7
- **Error handling**: Graceful degradation при MCP server issues

### Business Metrics
- **Development velocity**: 25% reduction в documentation lookup time
- **Bug detection**: 50% improvement в pre-production bug detection
- **Developer satisfaction**: Improved development experience ratings
- **Code quality**: Reduced production issues related to integration


