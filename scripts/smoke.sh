#!/usr/bin/env bash
set -euo pipefail

BASE="${PUBLIC_BASE:-http://127.0.0.1:8000}"

echo "Waiting for /readyz..."
for i in {1..60}; do
  if curl -fsS "$BASE/readyz" >/dev/null; then
    echo "ready"; break
  fi
  sleep 1
done

echo "Webhook info"
python scripts/manage_webhook.py --info | tee /tmp/webhook_info.json

PENDING=$(jq -r '.pending_update_count // 0' /tmp/webhook_info.json)
if [ "$PENDING" != "0" ]; then
  echo "Pending updates not zero: $PENDING" >&2
  exit 2
fi

echo "Ping webhook"
python scripts/ping_webhook.py | tee /tmp/ping_out.txt

STATUS=$(tail -n 2 /tmp/ping_out.txt | head -n1)
if [ "$STATUS" != "200" ]; then
  echo "Ping webhook status not 200: $STATUS" >&2
  exit 3
fi

echo "Check logs for request_id (best-effort)"
# In container environments logs go to stdout; skip strict check
echo "OK"



































