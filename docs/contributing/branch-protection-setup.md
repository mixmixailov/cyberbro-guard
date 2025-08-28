# 🛡️ Branch Protection Setup

This guide explains how to configure GitHub branch protection rules to enforce PR Gate requirements and maintain code quality.

## 📋 Required Status Checks

The repository requires these status checks to pass before merging:

### 1. `ci` - Continuous Integration
- **Purpose**: Run tests, linting, and build verification
- **Workflow**: `.github/workflows/ci.yml`
- **Checks**: 
  - Unit tests pass
  - Integration tests pass
  - Linting passes (ruff, mypy)
  - Code formatting verified
  - Build succeeds

### 2. `guard` - Security and Quality Guard
- **Purpose**: Security scanning and quality gates
- **Workflow**: `.github/workflows/guard.yml` (if exists)
- **Checks**:
  - Dependency vulnerability scanning
  - SAST (Static Application Security Testing)
  - Code quality metrics
  - License compliance

### 3. `pr_gate` - PR Gate Validation
- **Purpose**: Enforce PR guidelines and requirements
- **Workflow**: `.github/workflows/pr_gate.yml`
- **Checks**:
  - PR size limit (≤400 lines of code)
  - Test requirements for app/ changes
  - Documentation requirements for critical changes

## ⚙️ GitHub Repository Configuration

### Step 1: Access Branch Protection Settings

1. Navigate to your GitHub repository
2. Go to **Settings** → **Branches**
3. Click **Add rule** or edit existing rule for `main` branch

### Step 2: Configure Protection Rules

```yaml
# Branch protection configuration
Branch name pattern: main

Protection settings:
✅ Restrict pushes that create files
✅ Require pull request reviews before merging
   - Required approving reviews: 1
   - ✅ Dismiss stale reviews when new commits are pushed
   - ✅ Require review from code owners
   - ❌ Restrict reviews to users with write access
   - ❌ Allow specified actors to bypass required pull requests

✅ Require status checks before merging
   - ✅ Require branches to be up to date before merging
   - Required status checks:
     ✅ ci
     ✅ guard
     ✅ pr_gate

✅ Require conversation resolution before merging
✅ Restrict pushes that create files
❌ Allow force pushes
❌ Allow deletions
```

### Step 3: Advanced Settings

```yaml
# Additional protection rules
Restrictions:
  - Apply restrictions to administrators: true
  - Restrict who can push to matching branches: false
  
Lock branch:
  - Make this branch read-only: false
  
Required deployments:
  - None (for main branch)
```

## 🔧 GitHub CLI Setup

You can also configure branch protection using GitHub CLI:

```bash
# Install GitHub CLI if not already installed
# https://cli.github.com/

# Login to GitHub
gh auth login

# Set branch protection rules
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ci","guard","pr_gate"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
  --field restrictions=null
```

## 📋 Terraform Configuration

For infrastructure-as-code approach:

```hcl
# terraform/github_repository.tf
resource "github_branch_protection" "main" {
  repository_id = github_repository.cyberbro_guard.node_id
  pattern       = "main"

  required_status_checks {
    strict   = true
    contexts = ["ci", "guard", "pr_gate"]
  }

  required_pull_request_reviews {
    required_approving_review_count = 1
    dismiss_stale_reviews          = true
    require_code_owner_reviews     = true
  }

  enforce_admins = true

  allows_deletions = false
  allows_force_pushes = false
}
```

## 🔍 Verification

### Testing Branch Protection

1. **Create test PR** without required checks:
   ```bash
   git checkout -b test-branch-protection
   echo "test" > test-file.txt
   git add test-file.txt
   git commit -m "test: branch protection verification"
   git push origin test-branch-protection
   ```

2. **Create PR on GitHub** - should show required checks as pending

3. **Verify blocking behavior**:
   - Try to merge without status checks → Should be blocked
   - Try to merge without reviews → Should be blocked
   - Try to push directly to main → Should be blocked

### Check Status in Repository

```bash
# View current branch protection status
gh api repos/:owner/:repo/branches/main/protection | jq .

# List required status checks
gh api repos/:owner/:repo/branches/main/protection/required_status_checks | jq .contexts
```

## 🚨 Troubleshooting

### Common Issues

**❌ Status checks not appearing**
- Verify workflow files exist and are valid
- Check that workflows run on `pull_request` events
- Ensure workflow job names match required check names

**❌ Can't merge despite passing checks**
- Verify branch is up to date with target branch
- Check if conversation resolution is required
- Verify reviewer requirements are met

**❌ Administrators bypassing rules**
- Enable "Restrict pushes that create files" for administrators
- Review admin bypass settings in branch protection

### Debug Commands

```bash
# Check workflow runs for a PR
gh run list --branch feature-branch

# View specific workflow run
gh run view <run-id>

# Check repository branch protection
gh api repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'

# View PR check status
gh pr checks <pr-number>
```

## 📊 Monitoring and Metrics

### Branch Protection Compliance

Track these metrics to ensure effective protection:

```bash
# PRs bypassing protection (should be 0)
gh api search/issues --jq '.items | length' \
  --field q='repo:owner/repo is:pr is:merged -status:success'

# Average time to pass status checks
gh api repos/:owner/:repo/pulls --jq '.[] | select(.merged_at != null) | .number' | \
  head -10 | xargs -I {} gh pr view {} --json statusCheckRollupState,createdAt,mergedAt

# Review requirement compliance
gh api search/issues --jq '.items | length' \
  --field q='repo:owner/repo is:pr is:merged review:none'
```

### Alerts and Notifications

Set up notifications for:
- Status checks failing repeatedly
- PRs bypassing branch protection
- Direct pushes to protected branches (should be 0)
- Emergency admin bypasses

```yaml
# .github/workflows/branch-protection-monitor.yml
name: Branch Protection Monitor
on:
  schedule:
    - cron: '0 9 * * MON'  # Weekly on Monday
  
jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - name: Check protection compliance
        run: |
          # Check for any bypassed protections
          BYPASSED=$(gh api search/issues --jq '.total_count' \
            --field q='repo:${{ github.repository }} is:pr is:merged -status:success created:>$(date -d "7 days ago" +%Y-%m-%d)')
          
          if [ "$BYPASSED" -gt 0 ]; then
            echo "⚠️ $BYPASSED PRs bypassed protection in the last week"
            # Send alert to team
          fi
```

## 🔄 Updates and Maintenance

### Regular Reviews

**Monthly:**
- Review branch protection effectiveness
- Check if new workflows need to be added to required checks
- Verify admin bypass usage (should be rare and documented)

**Quarterly:**
- Review and update required status checks
- Assess if protection rules need adjustment
- Update documentation with any changes

### Evolution Path

As the project grows, consider:
1. **Additional required checks** (security scans, performance tests)
2. **Environment-specific protections** (staging, production branches)
3. **Auto-merge for dependabot** (with appropriate safeguards)
4. **Path-based protections** (different rules for different directories)

## 📚 References

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches)
- [Required Status Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches#require-status-checks-before-merging)
- [GitHub CLI Reference](https://cli.github.com/manual/gh_api)
- [Terraform GitHub Provider](https://registry.terraform.io/providers/integrations/github/latest/docs/resources/branch_protection)
