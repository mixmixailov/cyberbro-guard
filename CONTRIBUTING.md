# Contributing to CyberBro Guard

## Environments
- Target Python is 3.11 for development and production.
- Project is compatible up to Python 3.13, but do not use 3.13-only APIs.

## Dependencies (pip-tools)
- Edit `requirements.in` and compile:
```
pip-compile --upgrade --generate-hashes --output-file requirements.txt requirements.in -c constraints.txt
pip-sync requirements.txt requirements-dev.txt
```
- Place pins for problematic packages (e.g., `tiktoken`) into `constraints.txt` and enable only via feature flags.

## Alembic / Migrations (SQLite)
- Forward-only migrations: implement `upgrade()` only; `downgrade()` must raise `NotImplementedError`.
- In `env.py` set `render_as_batch=True` to support SQLite schema changes.
- Keep migrations atomic; avoid long-running locks.

## SQLite Best Practices
- Enable WAL mode and busy timeout:
  - `PRAGMA journal_mode=WAL;`
  - `PRAGMA busy_timeout=5000;`
- Avoid upgrading read transactions to write; on Windows this often results in `SQLITE_BUSY`.
- Keep transactions short and explicit.

## Webhook Security
- Always set Telegram webhook with `secret_token` and verify `X-Telegram-Bot-Api-Secret-Token` in `/webhook`.
- Respond within 10 seconds with 2xx; log errors but do not force Telegram retries by returning 5xx.

## CI/Test Matrix
- Tests must run on Python 3.11 and 3.13.
- Deployment is performed on Python 3.11.

## Coding Style
- PEP8, type hints, short docstrings.
- No prints; use `logging` with structured context.
- All user-visible strings must go through i18n resources (RU/EN).










