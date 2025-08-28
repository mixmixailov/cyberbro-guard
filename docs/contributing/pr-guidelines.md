# 🔄 Pull Request Guidelines

This document outlines the requirements and best practices for submitting pull requests to CyberBro Guard.

## 📋 PR Gate Requirements

All pull requests must pass automated PR Gate checks before they can be merged. The PR Gate enforces the following rules:

### 1. 📏 Size Limits

**Maximum 400 lines of code changes** (excluding `docs/` and `tests/`)

- **Why**: Large PRs are harder to review and more likely to contain bugs
- **Counted**: Additions + deletions in all files except documentation and tests
- **Solution**: Split large changes into smaller, focused PRs

```bash
# Example: Check your PR size locally
git diff --numstat origin/main..HEAD | grep -v '^.*\(docs/\|tests/\)' | awk '{sum += $1 + $2} END {print "Lines changed:", sum}'
```

### 2. 🧪 Test Requirements

**Tests required when modifying `app/` directory**

- **Rule**: Any changes to application code must include test updates
- **Types**: Unit tests, integration tests, or regression tests
- **Location**: `tests/unit/`, `tests/regression/`, or root `tests/`

**Examples of required test updates:**
- New function → Add unit test
- Bug fix → Add regression test  
- Feature → Add integration test
- API change → Update existing tests

### 3. 📚 Documentation Requirements

**Documentation required for critical system changes**

**Triggers**: Changes to `payments/` or `queue/` directories
**Required**: Update `docs/spec.md` OR `docs/scope.md`

**When to update docs/spec.md:**
- API changes
- New payment flows
- Queue behavior changes
- Technical specifications

**When to update docs/scope.md:**
- Feature scope changes
- New requirements
- Behavioral changes
- User-facing features

## 🛡️ Branch Protection Settings

Repository requires the following status checks to pass:

### Required Checks
1. **`ci`** - Main CI pipeline (tests, linting, build)
2. **`guard`** - Security and quality checks
3. **`pr_gate`** - PR Gate validation (size, tests, docs)

### Branch Protection Rules
```yaml
# GitHub repository settings
protection_rules:
  main:
    required_status_checks:
      strict: true
      contexts:
        - ci
        - guard  
        - pr_gate
    enforce_admins: true
    required_pull_request_reviews:
      required_approving_review_count: 1
      dismiss_stale_reviews: true
      require_code_owner_reviews: true
    restrictions: null
```

## 📝 PR Best Practices

### Writing Good PR Descriptions

```markdown
## Summary
Brief description of what this PR does

## Changes
- List specific changes made
- Use bullet points for clarity
- Include any breaking changes

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Documentation
- [ ] API docs updated (if applicable)
- [ ] README updated (if applicable)
- [ ] Spec/scope docs updated (if applicable)

## Related Issues
Fixes #123
Relates to #456
```

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `test` - Test changes
- `refactor` - Code refactoring
- `perf` - Performance improvements
- `ci` - CI/CD changes

**Examples:**
```
feat(payments): add refund processing for StarTransaction
fix(queue): resolve duplicate message handling in DLQ
docs(api): update webhook signature validation examples
test(regression): add payment idempotency tests for issue #PAY-001
```

## 🔧 Local Development Workflow

### Before Creating PR

1. **Ensure tests pass:**
   ```bash
   python -m pytest tests/ -v
   python -m pytest tests/regression/ -m regression
   ```

2. **Run linting:**
   ```bash
   ruff check app/ tests/
   ruff format app/ tests/
   ```

3. **Check PR size:**
   ```bash
   git diff --numstat origin/main..HEAD | grep -v -E '^.*\s+(docs|tests)/' | awk '{sum += $1 + $2} END {print "Code lines changed:", sum}'
   ```

4. **Verify documentation (if needed):**
   - Check if `app/handlers/payments.py` or `app/services/payments.py` changed
   - Check if `app/services/dlq.py` or `app/services/send_queue.py` changed
   - Update `docs/spec.md` or `docs/scope.md` accordingly

### PR Size Management

**Strategies for keeping PRs small:**

1. **Preparatory PRs** - Extract setup/refactoring to separate PRs
2. **Feature toggles** - Add feature behind a flag, enable in follow-up
3. **Incremental delivery** - Break feature into logical chunks
4. **Documentation PRs** - Separate docs updates when not directly related

**Example PR sequence:**
```
PR #1: Refactor payment validation (prep work)
PR #2: Add payment idempotency infrastructure 
PR #3: Implement SuccessfulPayment idempotency
PR #4: Add RefundedPayment handling
PR #5: Update documentation and examples
```

## 🚨 Common PR Gate Failures

### "PR is too large"

**Problem**: More than 400 lines of code changed
**Solutions:**
- Split into multiple PRs
- Move documentation to separate PR
- Extract refactoring to prep PR
- Use feature flags for incremental delivery

### "Missing tests for app/ changes"

**Problem**: Code changes without test updates
**Solutions:**
- Add unit tests for new functions
- Update existing tests for changed behavior
- Add regression tests for bug fixes
- Include integration tests for features

### "Missing documentation updates"

**Problem**: Critical changes without docs updates
**Solutions:**
- Update `docs/spec.md` for technical changes
- Update `docs/scope.md` for feature changes
- Add examples for new APIs
- Document breaking changes

## 🔍 Reviewer Guidelines

### What Reviewers Should Check

**Code Quality:**
- [ ] Code follows project style
- [ ] Logic is clear and correct
- [ ] Error handling is appropriate
- [ ] Performance considerations

**Testing:**
- [ ] Adequate test coverage
- [ ] Tests are meaningful
- [ ] Edge cases covered
- [ ] Regression tests for bug fixes

**Documentation:**
- [ ] API changes documented
- [ ] Complex logic explained
- [ ] Examples provided
- [ ] Breaking changes noted

**Security:**
- [ ] Input validation
- [ ] Authentication/authorization
- [ ] No secrets in code
- [ ] SQL injection prevention

### Review Response Times

**Target response times:**
- **Critical fixes**: 4 hours
- **Features**: 24 hours  
- **Documentation**: 48 hours
- **Refactoring**: 72 hours

## 📊 PR Metrics

Track these metrics for continuous improvement:

- **PR size distribution** - Keep average under 200 lines
- **Review time** - Target under 24 hours
- **Defect rate** - PRs requiring hotfixes
- **Test coverage** - Maintain above 80%

## 🔗 Related Documentation

- [Contributing Guide](../CONTRIBUTING.md)
- [Development Setup](../README.md#development)
- [Testing Standards](../docs/testing-standards.md)
- [Security Guidelines](../docs/security.md)
