# 🧪 Bug Reproduction Tests

## Overview
This document describes how to create and maintain bug reproduction tests in CyberBro Guard. These tests are created for confirmed bugs to ensure reproducibility and prevent regressions.

## 🎯 Purpose

Bug reproduction tests serve several key purposes:

1. **Reproducibility**: Ensure bugs can be consistently reproduced
2. **Regression Prevention**: Verify fixes don't break in the future  
3. **Documentation**: Provide concrete examples of bug behavior
4. **Development Aid**: Help developers understand and fix issues
5. **Verification**: Confirm when bugs are actually resolved

## 📁 Test Structure

### Unit Tests
Bug reproduction unit tests are organized by application area:

```
tests/unit/
├── handlers/        # Telegram handler bugs
├── services/        # Business logic bugs  
├── db/             # Database layer bugs
├── payments/       # Payment system bugs
├── queue/          # Background job bugs
├── i18n/           # Internationalization bugs
└── ci/             # CI/CD pipeline bugs
```

### E2E Tests
User-facing bug reproduction tests:

```
tests/e2e/
└── bug-repro-*.spec.ts    # End-to-end reproduction tests
```

## 🏷️ Test Markers

All bug reproduction tests use specific pytest markers:

- `@pytest.mark.bug` - Identifies test as bug reproduction
- `@pytest.mark.issue_id("123")` - Links to GitHub issue
- `@pytest.mark.{area}` - Identifies application area

## 🛠️ Creating Reproduction Tests

### Automated Generation

Use the provided script to generate test scaffolding:

```bash
# Generate unit test only
python scripts/create_repro_test.py --issue 123 --area handlers --slug "callback-processing-error"

# Generate both unit and E2E tests
python scripts/create_repro_test.py --issue 456 --area services --slug "payment-calculation-bug" --e2e
```

### Manual Creation

#### Unit Test Template

```python
"""
Bug reproduction test for issue #123.
"""

import pytest

@pytest.mark.bug
@pytest.mark.issue_id("123")
@pytest.mark.handlers
def test_callback_processing_error_repro():
    """
    Reproduces callback processing bug from issue #123.
    
    Description: Callback data with special characters causes handler to crash
    
    Steps to reproduce:
    1. Create callback query with emoji in data
    2. Process through callback handler
    3. Handler fails to parse data correctly
    
    Expected: Handler processes callback successfully
    Actual: Handler raises UnicodeDecodeError
    """
    # Arrange: Setup callback data that triggers the bug
    callback_data = "action:test_😀_data"
    mock_query = create_mock_callback_query(callback_data)
    
    # Act: Process callback through handler
    with pytest.raises(UnicodeDecodeError):
        result = process_callback_query(mock_query)
    
    # This test should FAIL until the bug is fixed
    # When fixed, remove the pytest.raises and assert success
```

#### E2E Test Template

```typescript
/**
 * E2E bug reproduction for issue #123
 */
import { test, expect } from '@playwright/test';

test('reproduces UI button click bug #123 @bug @issue_id:123', async ({ page }) => {
  /**
   * Description: Save button doesn't work on settings page
   * 
   * User steps:
   * 1. Navigate to settings page
   * 2. Change a setting value
   * 3. Click save button
   * 
   * Expected: Settings are saved and success message shown
   * Actual: Button click has no effect, settings not saved
   */
  
  // Arrange: Navigate to settings page
  await page.goto('/settings');
  
  // Act: Change setting and click save
  await page.fill('[data-testid="max-users"]', '100');
  await page.click('[data-testid="save-button"]');
  
  // Assert: Verify bug occurs (test should fail until bug is fixed)
  await expect(page.locator('.success-message')).toBeVisible();
  // This assertion will fail until the bug is fixed
});
```

## 🔄 Test Lifecycle

### 1. Creation Phase
- Generate test using script or manual template
- Implement minimal reproduction case
- Ensure test **FAILS** before bug is fixed
- Add descriptive documentation

### 2. Development Phase  
- Test runs in CI and fails (expected)
- Developers use test to understand bug
- Test helps verify potential fixes
- Test may be updated as understanding improves

### 3. Fix Phase
- Developer implements bug fix
- Test should now **PASS** 
- Test verifies fix is complete
- Test becomes regression prevention

### 4. Maintenance Phase
- Test continues running in CI
- Prevents regression of the bug
- May need updates for code refactoring
- Can be archived if area is deprecated

## 🔧 Running Reproduction Tests

### Local Development

```bash
# Run all bug reproduction tests
pytest -m "bug"

# Run bug tests for specific area
pytest -m "bug and handlers"

# Run tests for specific issue
pytest -m "issue_id:123"

# Run E2E bug reproduction tests
npm test -- --grep "@bug"
```

### CI Integration

Bug reproduction tests run automatically in CI:

- **Unit tests**: Run with `continue-on-error: true` (expected to fail)
- **E2E tests**: Run separately with failure tolerance
- **Results**: Uploaded as artifacts for analysis
- **Reporting**: Test results show bug reproduction status

## 📊 Test Guidelines

### Do's ✅

- **Keep tests minimal** - Only reproduce the specific bug
- **Make them deterministic** - Should fail/pass consistently  
- **Document clearly** - Explain what bug is being reproduced
- **Use descriptive names** - Include issue ID and brief description
- **Link to GitHub issue** - Use `issue_id` marker
- **Update when fixed** - Change assertions when bug is resolved

### Don'ts ❌

- **Don't test fixes** - Only reproduce the bug behavior
- **Don't make complex** - Avoid unnecessary setup or logic
- **Don't ignore failures** - Failing bug tests indicate unfixed bugs
- **Don't remove markers** - Keep bug/issue_id markers for tracking
- **Don't combine bugs** - One test per bug/issue

## 🔍 Debugging Tips

### Unit Test Debugging

```python
# Add detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Use pytest fixtures for common setup
@pytest.fixture
def bug_reproduction_data():
    return create_test_data_that_triggers_bug()

# Add parametrized tests for edge cases
@pytest.mark.parametrize("input_data", [
    "edge_case_1",
    "edge_case_2", 
    "edge_case_3"
])
def test_bug_with_variations(input_data):
    # Test multiple variations of the bug
    pass
```

### E2E Test Debugging

```typescript
// Enable debug mode
test.use({ video: 'on', screenshot: 'only-on-failure' });

// Add detailed steps
test.step('Setup bug conditions', async () => {
  // Step-by-step setup
});

test.step('Trigger bug behavior', async () => {
  // Bug reproduction
});

// Capture network activity
page.on('requestfailed', request => {
  console.log('Failed request:', request.url());
});
```

## 📈 Metrics and Tracking

### Test Status Tracking

- **Failing bug tests**: Indicate open bugs needing fixes
- **Passing bug tests**: Show resolved bugs with regression protection
- **Test count by area**: Identify areas with most reproduction tests
- **Resolution time**: Track how long bugs take to fix

### CI Dashboard

Bug reproduction test results are available in:

- **GitHub Actions artifacts**: Detailed test reports
- **Test result summaries**: Pass/fail counts by area
- **Historical trends**: Bug fix rates over time
- **Coverage reports**: Areas with reproduction test coverage

## 🛡️ Best Practices

### For Bug Reporters
- Provide clear reproduction steps in GitHub issue
- Test on latest commit before reporting
- Include environment details and logs

### For Developers
- Create reproduction test as first step when fixing bug
- Use test to verify fix before submitting PR
- Keep test after fix to prevent regression
- Update test documentation when behavior changes

### For Reviewers
- Verify reproduction test actually reproduces the bug
- Check that test fails before fix and passes after
- Ensure test is minimal and focused
- Validate test documentation and markers

## 🔄 Maintenance

### Regular Reviews
- Monthly review of all failing bug reproduction tests
- Identify tests that may need updates or removal
- Check for duplicate tests covering same bugs
- Update documentation based on learnings

### Cleanup Process
- Archive tests for deprecated functionality
- Remove duplicate or obsolete reproduction tests  
- Migrate tests when code structure changes
- Update markers and documentation as needed

This process ensures comprehensive bug tracking and prevention of regressions while maintaining test suite quality and relevance.
