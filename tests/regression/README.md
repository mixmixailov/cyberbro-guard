# 🐛 Regression Tests

This directory contains regression tests that verify fixes for specific issues that have been identified and resolved. Each test is linked to a specific issue ID and marked with the `@pytest.mark.regression` marker.

## 📋 Overview

Regression tests help ensure that previously fixed bugs don't reoccur during development. They serve as:

- **Documentation** of historical bugs and their fixes
- **Safety net** preventing regression of resolved issues
- **Quality assurance** for critical functionality

## 🏷️ Test Structure

### Issue Linking

Each regression test class includes:

```python
@pytest.mark.regression
class TestFeatureRegression:
    """Regression tests for specific feature.
    
    Issue ID: #<ISSUE_NUMBER>
    Description: Brief description of the original issue
    
    Root cause: What caused the bug
    Fix: How it was resolved
    """
```

### Test Naming Convention

- **Class names**: `Test<Feature>Regression` or `Test<Component><Issue>Regression`
- **Method names**: `test_<specific_scenario>_<regression_behavior>`
- **Issue references**: Include issue ID in docstrings and comments

## 📁 Current Regression Tests

### Payment System Regressions

#### `test_payment_regressions.py`
- **Issue #PAY-001**: SuccessfulPayment idempotency
  - Duplicate payments with same charge_id were processed multiple times
  - Fixed with enhanced charge_id validation and idempotency store
  
- **Issue #PAY-002**: RefundedPayment subscription deactivation  
  - Refunded payments didn't deactivate user subscriptions
  - Fixed with subscription cancellation logic in refund handler
  
- **Issue #PAY-003**: StarTransaction reconciliation
  - StarTransaction updates weren't properly correlated with payment records
  - Fixed with comprehensive reconciliation and validation

#### `test_payment_regression_smoke.py`
- Simplified versions of payment regression tests
- Focus on core database-level functionality
- Faster execution, minimal mocking

## 🔄 Running Regression Tests

### Run All Regression Tests
```bash
# Run all regression tests
python -m pytest tests/regression/ -m regression -v

# Run with coverage
python -m pytest tests/regression/ -m regression --cov=app --cov-report=html

# Run only smoke tests (faster)
python -m pytest tests/regression/ -m regression -k smoke
```

### Run Specific Issue Tests
```bash
# Run tests for specific payment issue
python -m pytest tests/regression/test_payment_regressions.py::TestSuccessfulPaymentIdempotency -v

# Run smoke tests for payment idempotency
python -m pytest tests/regression/test_payment_regression_smoke.py::TestPaymentIdempotencySmoke -v
```

### Integration with CI/CD
```bash
# In CI pipeline - fail fast on regressions
python -m pytest tests/regression/ -m regression --tb=short --maxfail=1

# Generate regression test report
python -m pytest tests/regression/ -m regression --html=reports/regression.html --self-contained-html
```

## 📊 Test Categories

### Database Regression Tests
- **Focus**: Data integrity, schema changes, query correctness
- **Examples**: Payment idempotency, subscription state management
- **Speed**: Fast (minimal setup)

### Handler Regression Tests  
- **Focus**: Telegram update processing, webhook handling
- **Examples**: Duplicate update filtering, callback validation
- **Speed**: Medium (requires mocking)

### Integration Regression Tests
- **Focus**: End-to-end scenarios, service interactions
- **Examples**: Payment flow completion, refund processing
- **Speed**: Slow (full setup required)

## 🛡️ Best Practices

### Writing Regression Tests

1. **Link to Issues**: Always include issue ID and description
2. **Isolate Root Cause**: Test the specific failure scenario
3. **Verify Fix**: Ensure the test fails without the fix
4. **Minimal Scope**: Focus on the regression, not general functionality
5. **Clear Documentation**: Explain what was broken and how it's fixed

### Test Data
```python
# Good: Specific to the regression scenario
charge_id = "ch_regression_duplicate_payment_001"

# Bad: Generic test data
charge_id = "test_charge_123"
```

### Assertions
```python
# Good: Specific regression check
assert seen_charge_id(charge_id) is True  # Idempotency fix
assert payment_id_2 == payment_id_1  # Same payment returned

# Bad: General functionality check  
assert payment_id > 0  # Just checking it works
```

## 🔍 Debugging Failed Regression Tests

### When a Regression Test Fails

1. **Identify the Issue**: Which specific issue has regressed?
2. **Check Recent Changes**: What code changes might have caused it?
3. **Reproduce Manually**: Can you reproduce the original bug?
4. **Review the Fix**: Is the original fix still in place?
5. **Update if Needed**: Has the fix approach changed?

### Common Failure Patterns

**Database Schema Changes**
```bash
# Error: table X has no column Y
# Solution: Update test database schema or migration
```

**API Changes**
```bash  
# Error: mock object has no attribute Z
# Solution: Update mocks to match current API
```

**Business Logic Changes**
```bash
# Error: assertion failed - behavior changed
# Solution: Review if change is intentional, update test accordingly
```

## 📈 Metrics and Reporting

### Regression Test Health

Track these metrics:
- **Pass Rate**: % of regression tests passing
- **Coverage**: How many known issues are covered
- **Execution Time**: Time to run all regression tests
- **Age**: How long since each test was added

### Monthly Review

1. **Audit Coverage**: Are new bugs getting regression tests?
2. **Clean Up**: Remove tests for issues that are no longer relevant
3. **Performance**: Keep execution time reasonable
4. **Documentation**: Update issue links and descriptions

## 🔗 Integration Points

### With Issue Tracking
```python
# Link tests to GitHub issues
"""
Regression test for issue #PAY-001
GitHub: https://github.com/org/repo/issues/PAY-001
"""
```

### With Monitoring
```bash
# Alert on regression test failures
if [ "$REGRESSION_FAILURES" -gt 0 ]; then
    echo "🚨 ALERT: $REGRESSION_FAILURES regression tests failed"
    # Send notification to team
fi
```

### With Documentation
- Link regression tests in issue resolution comments
- Reference tests in release notes for bug fixes
- Include test results in deployment approvals

## 🏃‍♂️ Quick Start

### Adding a New Regression Test

1. **Create Test File** (if needed):
   ```bash
   touch tests/regression/test_<feature>_regressions.py
   ```

2. **Add Test Class**:
   ```python
   @pytest.mark.regression
   class TestFeatureRegression:
       """Issue ID: #<ISSUE_ID>"""
   ```

3. **Write Test Method**:
   ```python
   def test_specific_regression_scenario(self):
       """Test description with issue context."""
   ```

4. **Run and Verify**:
   ```bash
   python -m pytest tests/regression/test_<feature>_regressions.py -v
   ```

### Testing Your Regression Test

1. **Temporarily Break the Fix**: Comment out the bug fix
2. **Run the Test**: Should fail with the original bug
3. **Restore the Fix**: Uncomment the fix
4. **Run Again**: Should pass

This ensures your regression test actually catches the regression!

## 📚 References

- [Pytest Regression Testing Guide](https://docs.pytest.org/en/stable/how.html#regression-testing)
- [Test-Driven Bug Fixing](https://blog.cleancoder.com/uncle-bob/2014/12/17/TheCyclesOfTDD.html)
- [Issue-Driven Development](https://guides.github.com/introduction/flow/)
