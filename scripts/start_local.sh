#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

ENV_FILE=".env"

if [[ ! -f "$ENV_FILE" ]];
then
  cat > "$ENV_FILE" <<'EOF'
# Example .env (fill BOT_TOKEN before setting webhook)
BOT_TOKEN=
DEBUG=false
PORT=8080
# Optional: PUBLIC_BASE=https://your.domain
# Optional: WEBHOOK_SECRET=your-secret
EOF
  echo ".env template created. Edit it and set BOT_TOKEN if you plan to set webhook."
fi

PROFILE=${PROFILE:-}
echo "[+] Starting bot container..."
docker compose up -d bot

if [[ "$PROFILE" == "tunnel" ]]; then
  echo "[+] Starting cloudflared quick tunnel..."
  docker compose --profile tunnel up -d cloudflared
elif [[ "$PROFILE" == "tunnel_ngrok" ]]; then
  echo "[+] Starting ngrok tunnel..."
  docker compose --profile tunnel_ngrok up -d ngrok
fi

if [[ -n "${WEBHOOK_URL:-}" ]]; then
  echo "[+] Setting webhook to $WEBHOOK_URL"
  BOT_TOKEN=${BOT_TOKEN:-$(grep -E '^BOT_TOKEN=' .env | cut -d= -f2-)}
  if [[ -z "$BOT_TOKEN" ]]; then
    echo "[-] BOT_TOKEN is not set. Skipping webhook setup." >&2
    exit 1
  fi
  python scripts/manage_webhook.py --set --url "$WEBHOOK_URL" --drop-pending || {
    echo "[-] Failed to set webhook" >&2; exit 1; }
fi

echo "[+] Done. Check: http://localhost:8080/healthz"





