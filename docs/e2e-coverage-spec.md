# E2E Coverage v1 — Stubbed Bot API - Technical Specification

## Overview

**Feature**: End-to-End Testing Coverage with Stubbed Telegram Bot API  
**Version**: v1.0  
**Status**: Implementation  
**Target**: Comprehensive E2E testing for core user flows without real Telegram integration

## Problem Statement

### Current Issues
1. **Limited E2E Coverage**: No comprehensive end-to-end testing for core user flows
2. **Telegram Dependency**: Testing requires real Telegram Bot API integration
3. **Manual Testing**: Core flows (onboarding, purchases) require manual verification
4. **CI/CD Gaps**: No automated validation of complete user journeys
5. **Regression Risk**: Changes can break core flows without early detection

### Goals
- **Comprehensive Coverage**: Automated testing for critical user journeys
- **Isolated Testing**: Test bot logic without external Telegram dependencies
- **CI Integration**: Automated E2E validation in continuous integration pipeline
- **Fast Feedback**: Quick detection of flow regressions during development
- **Production Confidence**: Validate core functionality before deployment

## Technical Requirements

### Functional Requirements

#### FR1: Core Flow Coverage
- **Onboarding Flow**: `/start` → language selection → help system
- **Purchase Flow**: `/buy` → plan selection → payment → status confirmation
- **User Interactions**: Callback queries, text messages, payment events
- **Multi-user Support**: Independent user sessions and state management

#### FR2: Mock Telegram Bot API
- **Lightweight Server**: Express.js-based mock API server on port 8001
- **Bot API Endpoints**: `getMe`, `setWebhook`, `sendMessage`, `editMessageText`
- **Payment Support**: `createInvoiceLink`, `answerPreCheckoutQuery`
- **Update Simulation**: Ability to send updates to webhook endpoint
- **State Management**: Track sent messages and webhook configuration

#### FR3: Test Infrastructure
- **Playwright Configuration**: Multi-browser testing (Chromium, Firefox, WebKit)
- **Test Fixtures**: Reusable components for mock API interaction
- **Global Setup/Teardown**: Mock server lifecycle management
- **Artifacts Collection**: Videos, screenshots, and HTML reports

#### FR4: CI/CD Integration
- **Automated Execution**: E2E tests run on every PR and main branch push
- **Artifact Upload**: Test results, videos, and screenshots uploaded to CI
- **Test Isolation**: Independent test database and configuration
- **Parallel Execution**: Efficient test execution with proper resource management

### Technical Specifications

#### Mock Telegram Bot API Endpoints
```typescript
// Bot information
GET /bot{token}/getMe
POST /bot{token}/setWebhook
GET /bot{token}/getWebhookInfo

// Messaging
POST /bot{token}/sendMessage
POST /bot{token}/editMessageText
POST /bot{token}/answerCallbackQuery

// Payments
POST /bot{token}/createInvoiceLink
POST /bot{token}/answerPreCheckoutQuery

// Debug endpoints
GET /health
GET /debug/messages
POST /debug/clear
```

#### Test Configuration
```typescript
// Environment variables for E2E testing
DEBUG: true
BOT_TOKEN: test:1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
WEBHOOK_SECRET: test_secret_for_e2e
USE_WEBHOOK: false
USE_POLLING: false
TELEGRAM_API_BASE: http://localhost:8001
SCHED_ENABLED: false
AUTO_MIGRATE: true
DATABASE_URL: sqlite:///./data/test_e2e.db
```

#### Update Message Format
```typescript
interface MockUpdate {
  update_id: number;
  message?: {
    message_id: number;
    from: UserInfo;
    chat: ChatInfo;
    date: number;
    text?: string;
    successful_payment?: PaymentInfo;
    refunded_payment?: PaymentInfo;
  };
  callback_query?: CallbackQueryInfo;
  pre_checkout_query?: PreCheckoutQueryInfo;
}
```

### Performance Requirements

#### PR1: Test Execution Performance
- **Test Suite Duration**: < 5 minutes for complete E2E test suite
- **Individual Test Time**: < 30 seconds per test scenario
- **Mock API Response**: < 10ms response time for Bot API calls
- **Application Startup**: < 30 seconds for FastAPI application in test mode

#### PR2: Resource Utilization
- **Memory Usage**: < 512MB total for test execution environment
- **CPU Usage**: < 80% during parallel test execution
- **Network Overhead**: Minimal external network dependencies
- **Storage**: < 100MB for test artifacts per run

#### PR3: Reliability Targets
- **Test Stability**: > 95% consistent pass rate for stable features
- **Flaky Test Rate**: < 5% intermittent failures due to timing issues
- **Mock API Uptime**: 100% availability during test execution
- **Test Isolation**: 0% cross-test interference or state leakage

## Implementation Details

### Core Components

#### Mock Telegram API Server (`tests/e2e/fixtures/mock-telegram-api.ts`)
```typescript
export class MockTelegramAPI {
  // Server lifecycle management
  async start(): Promise<void>
  async stop(): Promise<void>
  
  // Update simulation
  async sendUpdate(update: MockUpdate): Promise<boolean>
  
  // Helper methods
  createTextMessage(text: string, userId?: number): MockUpdate
  createCallbackQuery(data: string, userId?: number): MockUpdate
  createPreCheckoutQuery(payload: string, amount?: number): MockUpdate
  
  // State management
  getSentMessages(): any[]
  clearMessages(): void
}
```

#### Playwright Configuration (`tests/e2e/playwright.config.ts`)
```typescript
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  
  use: {
    baseURL: 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  
  webServer: {
    command: 'python -m uvicorn app.main:app --host 0.0.0.0 --port 8000',
    url: 'http://localhost:8000/status',
    reuseExistingServer: !process.env.CI,
  },
});
```

#### Test Fixtures (`tests/e2e/fixtures/index.ts`)
```typescript
export const test = base.extend<{
  mockTelegramAPI: MockTelegramAPI;
  apiClient: {
    sendUpdate: (update: MockUpdate) => Promise<boolean>;
    getSentMessages: () => any[];
    clearMessages: () => void;
    createTextMessage: (text: string) => MockUpdate;
    createCallbackQuery: (data: string) => MockUpdate;
    createPreCheckoutQuery: (payload: string, amount?: number) => MockUpdate;
  };
}>({
  // Fixture implementations
});
```

### Test Scenarios

#### Onboarding Flow Test (`test_onboarding.spec.ts`)
```typescript
test('should complete onboarding: /start -> i18n buttons -> help', async ({ apiClient }) => {
  // Step 1: Send /start command
  const startUpdate = apiClient.createTextMessage('/start', 12345, 12345);
  await apiClient.sendUpdate(startUpdate);
  
  // Step 2: Language selection via callback query
  const langUpdate = apiClient.createCallbackQuery('lang:en', 12345);
  await apiClient.sendUpdate(langUpdate);
  
  // Step 3: Request help
  const helpUpdate = apiClient.createTextMessage('/help', 12345, 12345);
  await apiClient.sendUpdate(helpUpdate);
  
  // Verify complete flow
  const messages = apiClient.getSentMessages();
  expect(messages.length).toBeGreaterThanOrEqual(3);
});
```

#### Purchase Flow Test (`test_purchase.spec.ts`)
```typescript
test('should complete purchase: /buy -> SuccessfulPayment -> /status active', async ({ apiClient }) => {
  // Step 1: Initiate purchase
  const buyUpdate = apiClient.createTextMessage('/buy', 54321, 54321);
  await apiClient.sendUpdate(buyUpdate);
  
  // Step 2: Plan selection
  const planUpdate = apiClient.createCallbackQuery('buy:premium', 54321);
  await apiClient.sendUpdate(planUpdate);
  
  // Step 3: Pre-checkout query
  const preCheckoutUpdate = apiClient.createPreCheckoutQuery('premium_plan_payload', 100, 54321);
  await apiClient.sendUpdate(preCheckoutUpdate);
  
  // Step 4: Successful payment
  const paymentUpdate = {
    update_id: Date.now(),
    message: {
      // ... payment message structure
      successful_payment: {
        currency: 'XTR',
        total_amount: 100,
        invoice_payload: 'premium_plan_payload',
        telegram_payment_charge_id: `charge_${Date.now()}`,
      }
    }
  };
  await apiClient.sendUpdate(paymentUpdate);
  
  // Step 5: Verify status shows active
  const statusUpdate = apiClient.createTextMessage('/status', 54321, 54321);
  await apiClient.sendUpdate(statusUpdate);
  
  const messages = apiClient.getSentMessages();
  const statusMessage = messages.find(msg => msg.text?.includes('active'));
  expect(statusMessage).toBeTruthy();
});
```

### Error Handling and Edge Cases

#### Network and Timing Issues
- **Retry Logic**: Automatic retry for flaky network operations
- **Timeout Handling**: Configurable timeouts for API calls and page operations
- **Race Condition Prevention**: Proper wait strategies for asynchronous operations
- **Resource Cleanup**: Guaranteed cleanup in case of test failures

#### Payment Edge Cases
- **Duplicate Payments**: Verify idempotency for same charge_id
- **Payment Cancellation**: Handle pre-checkout without successful payment
- **Refunded Payments**: Process refund events correctly
- **Invalid Amounts**: Handle edge cases in payment validation

#### Multi-user Scenarios
- **Session Isolation**: Independent user states and conversations
- **Concurrent Users**: Multiple users interacting simultaneously
- **User State Persistence**: Proper state management across interactions
- **Cross-user Privacy**: No data leakage between user sessions

## Validation Matrix

| Test Scenario | Input Flow | Expected Behavior | Verification Method |
|---------------|------------|-------------------|-------------------|
| **Basic Onboarding** | /start → lang:en → /help | Welcome → Language confirmation → Help text | Message content validation |
| **Language Switching** | /start → lang:ru → lang:en | Multiple language confirmations | Message count and content |
| **Unknown Commands** | /unknown_command | Error or help message | Response validation |
| **Multi-user Onboarding** | User1 /start, User2 /start | Independent responses | User-specific message filtering |
| **Purchase Initiation** | /buy | Plan selection options | Message content with plan options |
| **Plan Selection** | buy:premium callback | Invoice or payment link | Payment-related message |
| **Payment Flow** | Pre-checkout → SuccessfulPayment | Payment confirmation | Success message validation |
| **Status After Payment** | /status after payment | Active subscription status | Status message content |
| **Payment Cancellation** | Pre-checkout without payment | No status change | Status remains unchanged |
| **Duplicate Payment** | Same charge_id twice | Only one payment processed | Idempotency verification |
| **Refunded Payment** | RefundedPayment event | Refund acknowledgment | Refund message validation |
| **Multiple Plans** | Different plan selections | Plan-specific responses | Response variation validation |

## CI/CD Integration

### GitHub Actions Workflow
```yaml
e2e:
  runs-on: ubuntu-latest
  needs: lint_test
  
  steps:
  - name: Setup Node.js
    uses: actions/setup-node@v4
    with:
      node-version: '18'
      cache: 'npm'
  
  - name: Install dependencies
    run: |
      pip install -r requirements.txt
      npm ci
      npx playwright install --with-deps
  
  - name: Run E2E tests
    run: npx playwright test
    env:
      DEBUG: true
      TELEGRAM_API_BASE: http://localhost:8001
      # ... other test environment variables
  
  - name: Upload artifacts
    uses: actions/upload-artifact@v3
    if: always()
    with:
      name: playwright-artifacts
      path: |
        playwright-report/
        test-results/
        screenshots/
```

### Artifact Management
- **HTML Reports**: Detailed test execution reports with screenshots
- **Video Recordings**: Full session recordings for failed tests
- **Screenshots**: Point-in-time captures for debugging
- **Test Results**: JUnit XML format for CI integration
- **Retention Policy**: 30-day retention for all artifacts

## Testing Strategy

### Unit Test Coverage
- **Mock API Server**: Endpoint functionality and response validation
- **Test Fixtures**: Helper method behavior and state management
- **Update Creation**: Message format validation and field completeness
- **API Client**: Request/response handling and error scenarios

### Integration Tests
- **FastAPI Configuration**: Custom Telegram API base URL handling
- **Database Integration**: Test database isolation and migration
- **Service Lifecycle**: Application startup/shutdown with mock API
- **Webhook Processing**: End-to-end update processing pipeline

### End-to-End Tests
- **Complete User Journeys**: Full onboarding and purchase flows
- **Multi-step Interactions**: Complex sequences with state transitions
- **Error Recovery**: Graceful handling of failures and retries
- **Performance Validation**: Response times and resource usage

### Load and Stress Tests
- **Concurrent Users**: Multiple simultaneous user sessions
- **High Message Volume**: Rapid successive message processing
- **Memory Pressure**: Extended test runs with resource monitoring
- **Network Simulation**: Simulated network delays and failures

## Success Metrics

### Development Metrics
- **Test Coverage**: > 90% coverage for critical user flows
- **Test Reliability**: < 5% flaky test failure rate
- **Execution Speed**: < 5 minutes for complete E2E suite
- **Maintenance Overhead**: < 10% additional development time for E2E tests

### Quality Metrics
- **Bug Detection**: Early detection of flow regressions before production
- **False Positive Rate**: < 2% tests failing due to test issues
- **Coverage Accuracy**: 100% of critical paths tested
- **Regression Prevention**: 0% critical flow regressions reaching production

### Operational Metrics
- **CI Success Rate**: > 95% successful E2E test execution in CI
- **Artifact Availability**: 100% artifact upload success rate
- **Test Environment Stability**: < 1% infrastructure-related failures
- **Developer Productivity**: Faster debugging with visual test artifacts

## Risk Assessment

### Implementation Risks
- **Mock API Fidelity**: Risk of behavior differences between mock and real Telegram API - **Mitigation**: Regular validation against Telegram API documentation
- **Test Flakiness**: Risk of unreliable tests due to timing issues - **Mitigation**: Robust wait strategies and retry logic
- **Maintenance Overhead**: Risk of test maintenance becoming burdensome - **Mitigation**: Well-structured fixtures and helper utilities

### Technical Risks
- **Resource Consumption**: Risk of tests consuming excessive CI resources - **Mitigation**: Optimized test execution and artifact management
- **Test Isolation**: Risk of tests interfering with each other - **Mitigation**: Independent test databases and state cleanup
- **Version Compatibility**: Risk of Playwright or dependency version conflicts - **Mitigation**: Locked dependency versions and regular updates

### Operational Risks
- **CI Pipeline Impact**: Risk of E2E tests slowing down development workflow - **Mitigation**: Parallel execution and selective test triggering
- **False Security**: Risk of passing tests not representing real-world behavior - **Mitigation**: Complement with manual testing and production monitoring
- **Debugging Complexity**: Risk of difficult debugging for complex test failures - **Mitigation**: Comprehensive artifacts and detailed logging

## Future Enhancements

### V2 Considerations
- **Visual Regression Testing**: Screenshot comparison for UI consistency
- **Performance Testing**: Response time validation and load testing
- **Mobile Testing**: Device-specific testing scenarios
- **API Contract Testing**: Validation against OpenAPI specifications

### Integration Opportunities
- **Staging Environment**: Extended testing against staging API
- **Monitoring Integration**: Real-time test metrics in observability platform
- **Slack Integration**: Test failure notifications in development channels
- **Dashboard**: Real-time test status and historical trends

### Advanced Features
- **Test Data Management**: Dynamic test data generation and cleanup
- **Parallel Execution**: Advanced parallelization strategies
- **Cross-browser Validation**: Extended browser and device coverage
- **Accessibility Testing**: Automated accessibility validation

### Operational Improvements
- **Test Analytics**: Detailed analysis of test performance and reliability
- **Smart Test Selection**: Run only tests affected by code changes
- **Auto-healing Tests**: Automatic test fixing for common failure patterns
- **Documentation Integration**: Live documentation generated from test scenarios


