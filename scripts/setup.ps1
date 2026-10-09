<#
.SYNOPSIS
  One-command local setup for SIMS (Windows / PowerShell).

.DESCRIPTION
  Checks prerequisites, starts the local PostgreSQL container, creates backend/.env with a generated secret key,
  installs backend (uv) and frontend (npm) dependencies, then migrates and bootstraps the database.
  Safe to re-run: an existing backend/.env is never overwritten.

.PARAMETER SeedDemo
  Also load the demo campus and demo accounts (development only).

.PARAMETER SkipDb
  Do not start Docker PostgreSQL (use this when SIMS_DATABASE_URL already points at Supabase or another database).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -SeedDemo
#>
param(
    [switch]$SeedDemo,
    [switch]$SkipDb
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Yellow }
function Need($cmd, $hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "'$cmd' was not found. $hint" }
}
function Run($exe) {
    & $exe @args
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $exe $($args -join ' ')" }
}

Step "Checking prerequisites"
Need uv "Install it from https://docs.astral.sh/uv/getting-started/installation/"
Need node "Install Node.js 22.12+ (24 recommended) from https://nodejs.org/"
Need npm "It ships with Node.js."
if (-not $SkipDb) { Need docker "Install Docker Desktop, or re-run with -SkipDb and point SIMS_DATABASE_URL at your own PostgreSQL / Supabase." }

Step "Creating backend/.env"
$envFile = Join-Path $root "backend\.env"
if (Test-Path $envFile) {
    Write-Host "backend/.env already exists - leaving it untouched."
} else {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $text = Get-Content (Join-Path $root "backend\.env.example") -Raw
    $text = $text -replace "(?m)^SIMS_SECRET_KEY=.*$", "SIMS_SECRET_KEY=$secret"
    $text = $text -replace "(?m)^SIMS_COOKIE_SECURE=\S*", "SIMS_COOKIE_SECURE=false"
    [System.IO.File]::WriteAllText($envFile, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Wrote backend/.env (random secret key, SIMS_COOKIE_SECURE=false for plain-http local use)."
}

if (-not $SkipDb) {
    Step "Starting PostgreSQL (Docker, 127.0.0.1:54329)"
    Run docker compose up -d --wait
}

Step "Installing backend dependencies (uv)"
Push-Location backend
try {
    Run uv sync
    Step "Applying database migrations"
    Run uv run python -m app.cli migrate
    Step "Loading permissions, roles and reference data"
    Run uv run python -m app.cli bootstrap
    if ($SeedDemo) {
        Step "Loading demo campus and accounts"
        Run uv run python -m app.cli seed-demo
    }
} finally { Pop-Location }

Step "Installing frontend dependencies (npm)"
Push-Location frontend
try { Run npm ci } finally { Pop-Location }

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host @"

Start the app (two terminals):
  API : cd backend ; uv run uvicorn app.main:app --reload     -> http://127.0.0.1:8000/api/docs
  Web : cd frontend ; npm run dev                              -> http://localhost:5173
  Jobs: cd backend ; uv run python -m app.cli worker           (optional background worker)

"@
if ($SeedDemo) {
    Write-Host "Demo sign-ins: see docs/DEMO_DATA.md (usernames: demoadmin, registrar, hod, teacher, student ...)."
} else {
    Write-Host "No users yet. Create an administrator:"
    Write-Host '  $env:SIMS_BOOTSTRAP_ADMIN_PASSWORD = "a-long-unique-password"'
    Write-Host "  cd backend ; uv run python -m app.cli create-admin --username admin --email you@example.org"
}
