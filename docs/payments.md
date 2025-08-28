# Payments: Telegram Stars (XTR)

## Overview
- Currency: XTR (Telegram Stars) via Bot API invoices.
- Plan: PRO only.
- Renewal: manual (no auto‑rebill). Reminders are sent at T‑3, T‑1, T0 days.
- Test mode: set `PAYMENTS_STARS_TEST=true`.

## How it works
1) User sends `/buy_pro` in private chat.
2) Bot sends `sendInvoice(currency="XTR")` with price `PRO_PRICE_XTR` and period `PRO_PERIOD_DAYS`.
3) Bot answers `pre_checkout_query` (always ok for MVP).
4) On `successful_payment`:
   - Payment is recorded to `payments` (JSON payload stored, logs without PII).
   - Subscription is upserted in `subscriptions` and user upgraded to PRO (users.plan='pro', users.until set).

## Subscriptions lifecycle
- Active window: from purchase timestamp until `users.until`.
- Reminders:
  - T‑3: “PRO expires in 3 days. Renew with /buy_pro”.
  - T‑1: “PRO expires tomorrow. Renew with /buy_pro”.
  - T0: “PRO expired. Access limited. Renew with /buy_pro”.
- Reminders are idempotent via `subscription_reminders` flags.
- Expiration:
  - A scheduled job sets users back to FREE when `until <= now()`.

## Refund flow
- Command: `/refund_last` (private chat only).
- The bot:
  - Locates the user's latest successful payment in `payments`.
  - Creates a `support_tickets` record.
  - Calls `refund_star_payment(telegram_payment_charge_id=...)`.
- Policy window: `REFUND_WINDOW_H` (business policy; practical validation depends on provider payload).
- User feedback: success/failure short messages; details go to logs without PII.

## Configuration (.env)
- `PAYMENTS_STARS_ENABLED=true|false`
- `PAYMENTS_STARS_TEST=true|false` (sandbox)
- `PRO_PRICE_XTR=4900`
- `PRO_PERIOD_DAYS=30`
- `REFUND_WINDOW_H=24`

## Operational notes
- Idempotency: `telegram_payment_charge_id` checked to prevent double‑processing.
- Logs: mask sensitive data; store only aggregate identifiers.
- Reliability: invoice sending uses 3 retries with short backoff; failures are counted in `cyberbro_payments_total{status="failed_api"}`; successes increment `{status="ok"}`.




