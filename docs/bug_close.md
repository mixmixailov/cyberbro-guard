# 🐛 Bug Resolution Template

This template provides a structured approach to documenting bug fixes, ensuring comprehensive resolution and knowledge transfer.

## 📋 Bug Information

**Issue ID**: #[ISSUE_NUMBER]  
**Title**: [Bug Title]  
**Severity**: [Critical/High/Medium/Low]  
**Reporter**: [Username]  
**Assignee**: [Username]  
**Date Reported**: [YYYY-MM-DD]  
**Date Resolved**: [YYYY-MM-DD]  

## 🔍 Root Cause Analysis

### Problem Description
> Describe the exact problem that was occurring

**What was happening:**
- [Detailed description of the buggy behavior]
- [Impact on users/system]
- [Frequency of occurrence]

**Expected vs Actual Behavior:**
```
Expected: [What should have happened]
Actual:   [What actually happened]
```

### Technical Root Cause
> Identify the underlying technical reason for the bug

**Primary Cause:**
- [Code/configuration/logic issue that caused the bug]
- [File/function/line where the issue originated]
- [Why this issue wasn't caught earlier]

**Contributing Factors:**
- [Secondary issues that made the bug worse]
- [Process gaps that allowed the bug to slip through]
- [Environmental factors]

### Investigation Process
```bash
# Commands used to reproduce the issue
[reproduction steps]

# Debugging commands used
[debugging process]

# Log analysis performed
[log investigation]
```

**Key Evidence:**
- Error messages/stack traces
- Log entries showing the problem
- Database queries that revealed the issue
- Network traces (if applicable)

## 🔧 Fix Implementation

### Solution Overview
> Describe the approach taken to resolve the bug

**Fix Strategy:**
- [High-level approach to solving the problem]
- [Why this approach was chosen over alternatives]
- [Risk assessment and mitigation]

### Code Changes
**Files Modified:**
- `[file_path]` - [description of changes]
- `[file_path]` - [description of changes]

**Key Changes:**
```python
# Before (buggy code)
[original code snippet]

# After (fixed code)  
[fixed code snippet]
```

**Configuration Changes:**
```yaml
# Before
[original configuration]

# After
[fixed configuration]
```

### Database Changes
```sql
-- Migration/schema changes (if any)
[SQL statements]
```

### Validation Steps
- [ ] Code review completed
- [ ] Manual testing performed
- [ ] Integration tests pass
- [ ] Performance impact assessed
- [ ] Security review (if applicable)

## 🧪 Tests Added

### Regression Tests
> Tests added to prevent this specific bug from recurring

**Test Files:**
- `tests/regression/test_[bug_name].py` - [description]
- `tests/unit/test_[component].py` - [updated/new tests]

**Test Cases:**
1. **Test Case**: [Test name]
   - **Purpose**: Verify the specific bug is fixed
   - **Input**: [test input]
   - **Expected Output**: [expected result]
   - **Status**: ✅ Pass

2. **Test Case**: [Edge case test]
   - **Purpose**: Cover edge cases related to the bug
   - **Input**: [test input]
   - **Expected Output**: [expected result]
   - **Status**: ✅ Pass

### Test Coverage
```bash
# Coverage before fix
Coverage: [X]%

# Coverage after fix
Coverage: [Y]%

# New lines covered: [Y-X]%
```

**Critical Paths Tested:**
- [ ] Happy path scenarios
- [ ] Error conditions that caused the bug
- [ ] Edge cases and boundary conditions
- [ ] Integration points affected

### Manual Test Results
**Test Environment**: [staging/production-like]
**Test Data**: [description of test data used]

| Test Scenario | Input | Expected | Actual | Status |
|---------------|-------|----------|--------|--------|
| [scenario 1] | [input] | [expected] | [actual] | ✅ |
| [scenario 2] | [input] | [expected] | [actual] | ✅ |

## 📊 Metrics Before/After

### Performance Metrics

**Before Fix:**
```
Response Time: [X]ms P95
Error Rate: [Y]%
Throughput: [Z] requests/second
Memory Usage: [A]MB
CPU Usage: [B]%
```

**After Fix:**
```
Response Time: [X']ms P95 (improvement: [X-X']ms)
Error Rate: [Y']% (improvement: [Y-Y']%)
Throughput: [Z'] requests/second (improvement: [Z'-Z])
Memory Usage: [A']MB (change: [A'-A]MB)
CPU Usage: [B']% (change: [B'-B]%)
```

### Business Metrics

**User Impact Before:**
- Affected Users: [number/percentage]
- Failed Operations: [number] per [time period]
- Support Tickets: [number] related to this issue

**User Impact After:**
- Error Reports: [number] (reduction: [%])
- User Satisfaction: [metric] (improvement: [%])
- Support Load: [number] tickets (reduction: [%])

### System Health Metrics

**Before Fix:**
```
Uptime: [%]
Error Logs: [number] per hour
Alert Frequency: [number] per day
Database Lock Timeouts: [number]
```

**After Fix:**
```
Uptime: [%] (improvement: [%])
Error Logs: [number] per hour (reduction: [%])
Alert Frequency: [number] per day (reduction: [%])
Database Lock Timeouts: [number] (reduction: [%])
```

### Monitoring Dashboard
**Dashboard Links:**
- [Grafana/DataDog/CloudWatch link to relevant metrics]
- [Application performance monitoring dashboard]
- [Error tracking dashboard (Sentry/Rollbar)]

**Key Metrics to Monitor:**
- [ ] Error rate in affected components
- [ ] Response times for fixed endpoints
- [ ] Resource utilization trends
- [ ] User engagement metrics

## 📚 Lessons Learned

### What Went Well
- [Things that worked well in the debugging process]
- [Effective tools/techniques used]
- [Good practices that helped identify or fix the issue]

### What Could Be Improved
- [Gaps in our testing that allowed this bug]
- [Process improvements needed]
- [Tools or monitoring that could have caught this earlier]

### Prevention Strategies
> How to prevent similar bugs in the future

**Code Review Process:**
- [ ] Add specific review criteria for [affected component]
- [ ] Include performance review for [specific area]
- [ ] Require [specific expert] review for [type of changes]

**Testing Strategy:**
- [ ] Add automated testing for [specific scenario]
- [ ] Include [edge case] in standard test suite
- [ ] Add load testing for [affected component]

**Monitoring Improvements:**
- [ ] Add alerting for [specific metric]
- [ ] Enhance logging in [affected area]
- [ ] Set up dashboard for [specific use case]

**Documentation Updates:**
- [ ] Update [architecture docs] with [new information]
- [ ] Add troubleshooting guide for [common scenario]
- [ ] Update deployment checklist with [new check]

### Team Knowledge Transfer
**Key Learnings:**
1. [Technical insight learned]
2. [Process insight learned]
3. [Tool/technique discovered]

**Documentation Updated:**
- [ ] Architecture docs reflect the fix
- [ ] Troubleshooting guides updated
- [ ] Runbooks include new procedures
- [ ] Team wiki updated with lessons

### Follow-up Actions
**Immediate (1 week):**
- [ ] Monitor metrics for regression
- [ ] Complete additional testing
- [ ] Update documentation

**Short-term (1 month):**
- [ ] Implement prevention measures
- [ ] Review similar code for potential issues
- [ ] Training for team on lessons learned

**Long-term (3 months):**
- [ ] Evaluate effectiveness of prevention measures
- [ ] Consider architectural improvements
- [ ] Share learnings with broader engineering team

## ✅ Resolution Checklist

### Development Complete
- [ ] Root cause identified and documented
- [ ] Fix implemented and code reviewed
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Regression tests added
- [ ] Documentation updated

### Quality Assurance
- [ ] Manual testing completed
- [ ] Performance impact assessed
- [ ] Security review completed (if applicable)
- [ ] Cross-browser/platform testing (if applicable)
- [ ] Accessibility testing (if applicable)

### Deployment
- [ ] Changes deployed to staging
- [ ] Staging validation completed
- [ ] Production deployment completed
- [ ] Post-deployment monitoring active
- [ ] Rollback plan prepared and tested

### Communication
- [ ] Stakeholders notified of resolution
- [ ] User-facing communication sent (if needed)
- [ ] Support team informed of changes
- [ ] Documentation shared with team

### Follow-up
- [ ] Metrics showing improvement
- [ ] No regression detected after 48 hours
- [ ] User feedback positive
- [ ] Issue marked as resolved
- [ ] Post-mortem scheduled (for critical bugs)

---

## 📎 Related Resources

**Pull Request**: [Link to PR that fixed the bug]  
**Test Results**: [Link to CI/test results]  
**Monitoring**: [Link to relevant dashboards]  
**Related Issues**: [Links to related bugs/features]

**Team Members Involved:**
- Developer: [name]
- Reviewer: [name] 
- QA: [name]
- DevOps: [name] (if deployment changes)

---

*Template Version: 1.0*  
*Last Updated: [Date]*  
*Created by: [Team/Individual]*
