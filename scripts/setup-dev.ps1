# One-shot local setup for teammates (Windows + Docker Desktop, Python 3.11+, Node 22+).
#   powershell -ExecutionPolicy Bypass -File scripts/setup-dev.ps1
# It: creates backend/.env with fresh random secrets, builds the Python venv, installs the frontend,
# starts MySQL in Docker, imports the shared sample database and creates the demo logins.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function New-Secret([int]$bytes = 48) {
  $b = New-Object byte[] $bytes
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  return [Convert]::ToBase64String($b).Replace('+', '-').Replace('/', '_').TrimEnd('=')
}

if (-not (Test-Path backend/.env)) {
  $text = Get-Content backend/.env.dev.example -Raw
  while ($text -match '__GENERATE__') { $text = ([regex]'__GENERATE__').Replace($text, (New-Secret), 1) }
  Set-Content -Path backend/.env -Value $text -Encoding utf8
  Write-Host 'Created backend/.env with new random secrets (it is git-ignored; never commit it).'
} else { Write-Host 'backend/.env already exists - keeping it.' }

if (-not (Test-Path backend/.venv)) { python -m venv backend/.venv }
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
Push-Location frontend; npm ci; Pop-Location

& "$PSScriptRoot/import-database.ps1" -Force
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py seed_sample_users

Write-Host ''
Write-Host 'Choose a password for the "admin" account:'
backend/.venv/Scripts/python.exe backend/manage.py changepassword admin

Write-Host ''
Write-Host 'Done. Start the app in two terminals:'
Write-Host '  backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000'
Write-Host '  cd frontend; npm run dev        -> http://127.0.0.1:5173'
