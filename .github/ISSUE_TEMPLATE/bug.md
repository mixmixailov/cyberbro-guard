---
name: 🐛 Bug Report
about: Report a bug to help us improve CyberBro Guard
title: '[BUG] '
labels: ['bug', 'needs:repro']
assignees: ''
---

## 🐛 Bug Description
**Brief summary of the issue**

## 📋 Steps to Reproduce
1. 
2. 
3. 

## ✅ Expected Behavior
**What should have happened**

## ❌ Actual Behavior  
**What actually happened**

## 📊 Logs
**Include relevant logs, error messages, or stack traces**
```
Paste logs here
```

## 🌍 Environment
- **OS**: (e.g., Ubuntu 20.04, Windows 11, macOS 13)
- **Python Version**: (e.g., 3.11.5)
- **Bot Framework**: (e.g., python-telegram-bot 21.11.1)
- **Deployment**: (e.g., Railway, Docker, local)
- **Database**: (e.g., SQLite)

## 🔍 Commit SHA
**Latest commit where issue occurs**
```
git log -1 --oneline
```

## 🤔 Hypotheses (1-3)
**Your theories about what might be causing this issue**

### Hypothesis 1
**Description**: 
**Confidence**: High/Medium/Low
**Test**: How to verify this hypothesis

### Hypothesis 2 (optional)
**Description**: 
**Confidence**: High/Medium/Low  
**Test**: How to verify this hypothesis

### Hypothesis 3 (optional)
**Description**: 
**Confidence**: High/Medium/Low
**Test**: How to verify this hypothesis

## 📎 Additional Context
**Screenshots, related issues, or other relevant information**

---
**Priority Assessment** (will be labeled by maintainers):
- P1: Critical - Blocks core functionality, affects all users
- P2: High - Affects significant functionality or subset of users  
- P3: Medium - Minor functionality impact or workarounds available

**Area Assessment** (will be labeled by maintainers):
- `area:handlers` - Telegram message/callback handlers
- `area:services` - Business logic services (payments, moderation, etc.)
- `area:db` - Database queries, migrations, schema  
- `area:payments` - Payment processing, subscriptions
- `area:queue` - Background jobs, DLQ, scheduling
- `area:i18n` - Internationalization, localization
- `area:ci` - CI/CD, testing, deployment
