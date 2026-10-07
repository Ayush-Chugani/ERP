# Loads database/sims_sample.sql into the Dockerised MySQL (service "mysql" in compose.yaml).
# WARNING: replaces everything in the target database (sims_reference_dev by default).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/import-database.ps1 [-Force]
param([switch]$Force)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path backend/.env)) { throw 'backend/.env is missing. Run scripts/setup-dev.ps1 first.' }
if (-not $Force) {
  $answer = Read-Host 'This REPLACES all data in the local SIMS database. Type YES to continue'
  if ($answer -ne 'YES') { Write-Host 'Cancelled.'; exit 1 }
}

docker compose --env-file backend/.env up -d --wait
$container = (docker compose --env-file backend/.env ps -q mysql).Trim()
$pw = (docker exec $container printenv MYSQL_ROOT_PASSWORD).Trim()
$db = (docker exec $container printenv MYSQL_DATABASE).Trim()

docker exec -e MYSQL_PWD=$pw $container mysql -uroot -e "DROP DATABASE IF EXISTS $db; CREATE DATABASE $db CHARACTER SET utf8mb4;"
# Stream the dump in through stdin (cmd keeps the bytes untouched).
cmd /c "docker exec -i -e MYSQL_PWD=$pw $container mysql -uroot --default-character-set=utf8mb4 $db < database\sims_sample.sql"
if ($LASTEXITCODE -ne 0) { throw 'Import failed.' }
Write-Host "Imported database/sims_sample.sql into $db."
Write-Host 'Next: backend/.venv/Scripts/python.exe backend/manage.py seed_sample_users   (demo logins)'
Write-Host '      backend/.venv/Scripts/python.exe backend/manage.py changepassword admin (your admin login)'
