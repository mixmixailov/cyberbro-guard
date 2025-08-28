# 🏷️ GitHub Labels Configuration

This file contains the labels that should be configured in the GitHub repository to support the bug intake discipline workflow.

## Setup Instructions

1. Go to repository Settings → Labels
2. Create the following labels with specified colors and descriptions
3. Existing default labels can be kept or removed as needed

## Label Definitions

### Bug Type
| Name | Color | Description |
|------|-------|-------------|
| `bug` | `#d73a4a` | Something isn't working |

### Severity Labels
| Name | Color | Description |
|------|-------|-------------|
| `sev:P1` | `#b60205` | Critical: Blocks core functionality, affects all users |
| `sev:P2` | `#d93f0b` | High: Affects significant functionality or subset of users |
| `sev:P3` | `#fbca04` | Medium: Minor functionality impact or workarounds available |

### Area Labels  
| Name | Color | Description |
|------|-------|-------------|
| `area:handlers` | `#0e8a16` | Telegram message/callback handlers |
| `area:services` | `#1d76db` | Business logic services (payments, moderation, etc.) |
| `area:db` | `#5319e7` | Database queries, migrations, schema |
| `area:payments` | `#f9d0c4` | Payment processing, subscriptions |
| `area:queue` | `#c2e0c6` | Background jobs, DLQ, scheduling |
| `area:i18n` | `#ffd700` | Internationalization, localization |
| `area:ci` | `#0052cc` | CI/CD, testing, deployment |

### Status Labels
| Name | Color | Description |
|------|-------|-------------|
| `needs:info` | `#7057ff` | Waiting for more information from reporter |
| `needs:repro` | `#008672` | Needs reproduction confirmation |
| `needs:fix` | `#d93f0b` | Confirmed bug, needs implementation |
| `needs:review` | `#0075ca` | Fix ready, needs code review |
| `needs:verify` | `#1d76db` | Fix merged, needs verification testing |
| `verified` | `#0e8a16` | Bug confirmed fixed |
| `cannot-reproduce` | `#6f42c1` | Unable to reproduce reported issue |

### Special Labels
| Name | Color | Description |
|------|-------|-------------|
| `stale` | `#ffffff` | Issue has been inactive for 30+ days |
| `good first issue` | `#7057ff` | Good for newcomers |
| `help wanted` | `#008672` | Extra attention is needed |

## Automation Setup

These labels work with:
- Issue templates (auto-applied on creation)
- CODEOWNERS (auto-assignment)
- Stale bot configuration
- GitHub Actions workflows

## Label Usage Guidelines

### Priority Assignment
- **P1**: Production down, security vulnerability, data loss
- **P2**: Feature broken for users, performance severely degraded  
- **P3**: Minor bugs, cosmetic issues, edge cases

### Area Assignment
- Use only one area label per issue
- Choose the area most relevant to the root cause
- If uncertain, use the area where the bug manifests

### Status Flow
```
needs:repro → needs:fix → needs:review → needs:verify → verified
```

Missing information branches:
```  
needs:repro → cannot-reproduce
any stage → needs:info
```
