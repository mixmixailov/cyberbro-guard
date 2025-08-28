# 🔧 GitHub Repository Setup Guide

Quick setup guide for enabling PR Gate and branch protection on your CyberBro Guard repository.

## 📋 Prerequisites

- Admin access to the GitHub repository
- PR Gate workflow deployed (`.github/workflows/pr_gate.yml`)
- Existing CI workflow (`ci.yml`) working

## 🛡️ Step 1: Configure Branch Protection

### Option A: GitHub Web UI

1. **Navigate to Repository Settings**
   ```
   Your Repository → Settings → Branches
   ```

2. **Add Protection Rule for `main` branch**
   - Click "Add rule"
   - Branch name pattern: `main`

3. **Configure Protection Settings**
   ```
   ✅ Require pull request reviews before merging
      - Required approving reviews: 1
      - ✅ Dismiss stale reviews when new commits are pushed
      - ✅ Require review from code owners (if CODEOWNERS exists)
   
   ✅ Require status checks before merging
      - ✅ Require branches to be up to date before merging
      - Required status checks:
        ✅ ci
        ✅ pr_gate
        ✅ guard (if applicable)
   
   ✅ Require conversation resolution before merging
   ✅ Restrict pushes that create files (apply to admins)
   ❌ Allow force pushes
   ❌ Allow deletions
   ```

4. **Save Protection Rule**

### Option B: GitHub CLI

```bash
# Install GitHub CLI: https://cli.github.com/
gh auth login

# Set branch protection with required status checks
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ci","pr_gate","guard"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field required_conversation_resolution=true

# Verify setup
gh api repos/:owner/:repo/branches/main/protection | jq '.required_status_checks.contexts'
```

## ✅ Step 2: Verify Setup

### Test Branch Protection
```bash
# Try to push directly to main (should fail)
git checkout main
echo "test" > test.txt
git add test.txt
git commit -m "test: direct push"
git push origin main
# Expected: Error - branch is protected
```

### Test PR Gate
```bash
# Create test branch with large changes
git checkout -b test-pr-gate
# Make changes that would trigger PR gate
python scripts/check_pr_gate_local.py
# Create PR and verify PR gate runs
```

## 🔍 Step 3: Monitor and Validate

### Check Required Status Checks
```bash
# List current protection settings
gh api repos/:owner/:repo/branches/main/protection \
  --jq '.required_status_checks.contexts[]'

# Should output:
# ci
# pr_gate
# guard (if configured)
```

### Verify Workflow Runs
```bash
# Check recent workflow runs
gh run list --limit 5

# Check specific PR gate runs
gh run list --workflow="PR Gate" --limit 3
```

## 🚨 Troubleshooting

### PR Gate Workflow Not Running

**Problem**: PR gate doesn't appear in status checks
```bash
# Check workflow file syntax
gh workflow list
gh workflow view "PR Gate"

# Verify triggers
cat .github/workflows/pr_gate.yml | grep -A 5 "on:"
```

**Solution**: Ensure workflow file is in `main` branch and has correct triggers

### Status Check Not Required

**Problem**: PRs can be merged without pr_gate
```bash
# Check current branch protection
gh api repos/:owner/:repo/branches/main/protection \
  --jq '.required_status_checks.contexts'
```

**Solution**: Add "pr_gate" to required status checks list

### Permission Denied

**Problem**: Cannot configure branch protection
```bash
# Check your repository role
gh api repos/:owner/:repo --jq '.permissions'
```

**Solution**: Ensure you have admin access to the repository

## 📊 Example Commands for Common Tasks

### Add New Required Status Check
```bash
# Get current status checks
CURRENT=$(gh api repos/:owner/:repo/branches/main/protection \
  --jq '.required_status_checks.contexts')

# Add new check (example: adding "security" check)
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks="{\"strict\":true,\"contexts\":[\"ci\",\"pr_gate\",\"guard\",\"security\"]}"
```

### Temporarily Disable PR Gate (Emergency)
```bash
# Remove pr_gate from required checks
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ci","guard"]}'

# Re-enable later
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ci","pr_gate","guard"]}'
```

### Check PR Status
```bash
# Check status of specific PR
gh pr checks 123

# View PR gate results
gh pr view 123 --json statusCheckRollupState,commits
```

## 🔄 Rollback Plan

If you need to disable PR Gate:

1. **Remove from Required Status Checks**
   ```bash
   gh api repos/:owner/:repo/branches/main/protection \
     --method PUT \
     --field required_status_checks='{"strict":true,"contexts":["ci","guard"]}'
   ```

2. **Disable Workflow (Optional)**
   ```bash
   # Rename workflow file to disable
   git mv .github/workflows/pr_gate.yml .github/workflows/pr_gate.yml.disabled
   git commit -m "disable: PR gate workflow"
   git push origin main
   ```

3. **Re-enable When Ready**
   ```bash
   # Restore workflow
   git mv .github/workflows/pr_gate.yml.disabled .github/workflows/pr_gate.yml
   git commit -m "enable: PR gate workflow"
   git push origin main
   
   # Re-add to required checks
   gh api repos/:owner/:repo/branches/main/protection \
     --method PUT \
     --field required_status_checks='{"strict":true,"contexts":["ci","pr_gate","guard"]}'
   ```

## 📈 Success Indicators

After setup, you should see:

✅ **PR Gate workflow runs on every PR**
✅ **PRs blocked if they exceed 400 lines of code**  
✅ **PRs blocked if app/ changes lack tests**
✅ **PRs blocked if critical changes lack docs**
✅ **Status checks visible in PR UI**
✅ **Helpful error messages guide developers**

## 📞 Support

If you encounter issues:

1. **Check workflow logs**: `gh run view <run-id>`
2. **Validate YAML syntax**: Use GitHub's workflow validator
3. **Test locally**: `python scripts/check_pr_gate_local.py`
4. **Review documentation**: [PR Guidelines](contributing/pr-guidelines.md)

## 📚 Related Resources

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches)
- [GitHub Actions Status Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/troubleshooting-required-status-checks)
- [GitHub CLI Reference](https://cli.github.com/manual/gh_api)
