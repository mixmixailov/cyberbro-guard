$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$envFile = ".env"
if (-not (Test-Path $envFile)) {
@"
# Example .env (fill BOT_TOKEN before setting webhook)
BOT_TOKEN=
DEBUG=false
PORT=8080
# Optional: PUBLIC_BASE=https://your.domain
# Optional: WEBHOOK_SECRET=your-secret
"@ | Out-File -Encoding utf8 $envFile
Write-Host ".env template created. Edit it and set BOT_TOKEN if you plan to set webhook."
}

$PROFILE = $env:PROFILE
Write-Host "[+] Starting bot container..."
docker compose up -d bot

if ($PROFILE -eq "tunnel") {
  Write-Host "[+] Starting cloudflared quick tunnel..."
  docker compose --profile tunnel up -d cloudflared
} elseif ($PROFILE -eq "tunnel_ngrok") {
  Write-Host "[+] Starting ngrok tunnel..."
  docker compose --profile tunnel_ngrok up -d ngrok
}

if ($env:WEBHOOK_URL) {
  Write-Host "[+] Setting webhook to $($env:WEBHOOK_URL)"
  if (-not $env:BOT_TOKEN) { Write-Error "BOT_TOKEN is not set in environment. Skipping webhook setup." }
  python scripts/manage_webhook.py --set --url $env:WEBHOOK_URL --drop-pending
}

Write-Host "[+] Done. Check: http://localhost:8080/healthz"





