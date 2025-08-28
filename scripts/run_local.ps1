$ErrorActionPreference = "Stop"

# Move to repo root (this script lives in scripts/)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
Set-Location $root

Write-Host "[+] Working dir: $((Get-Location).Path)"

# Ensure .env exists (minimal template)
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
@"
# Example .env
BOT_TOKEN=
DEBUG=true
PORT=8000
# Optional: PUBLIC_BASE=https://your.domain
# Optional: WEBHOOK_SECRET=your-secret
"@ | Out-File -Encoding utf8 $envFile
  Write-Host "[+] .env template created. Edit it as needed."
}

# Prefer Python 3.11 (target), fallback to 3.13, then default 'python'
function Resolve-Python {
  try {
    $p = & py -3.11 -c "import sys;print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $p) { return "py -3.11" }
  } catch {}
  try {
    $p = & py -3.13 -c "import sys;print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $p) { return "py -3.13" }
  } catch {}
  return "python"
}

$PY = Resolve-Python
Write-Host "[+] Using Python launcher: $PY"

# Create venv if missing
if (-not (Test-Path ".venv/Scripts/python.exe")) {
  Write-Host "[+] Creating venv in .venv"
  iex "$PY -m venv .venv"
}

# Install deps
Write-Host "[+] Upgrading pip and installing requirements"
& .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt | Out-Null

# Run FastAPI (uvicorn) on port from .env or default 8000
$port = if ($env:PORT) { $env:PORT } else { "8000" }
Write-Host "[+] Starting uvicorn on http://127.0.0.1:$port"
& .\.venv\Scripts\uvicorn.exe app.main:app --reload --port $port






