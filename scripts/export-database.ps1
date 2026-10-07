# Refreshes database/sims_sample.sql from your local database so teammates can share data changes.
# Sessions, tokens and login-audit rows are excluded and password hashes are blanked.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/export-database.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$container = (docker compose --env-file backend/.env ps -q mysql).Trim()
if (-not $container) { throw 'The MySQL container is not running. Start it with: docker compose --env-file backend/.env up -d --wait' }
$pw = (docker exec $container printenv MYSQL_ROOT_PASSWORD).Trim()
$db = (docker exec $container printenv MYSQL_DATABASE).Trim()

$skipData = 'token_blacklist_blacklistedtoken','token_blacklist_outstandingtoken','django_session','login_audit','activity_audit','password_history'
$common = @('--single-transaction','--no-tablespaces','--triggers','--routines','--skip-comments','--skip-add-locks','--default-character-set=utf8mb4','--hex-blob')
$ignore = $skipData | ForEach-Object { "--ignore-table=$db.$_" }
$tmp = Join-Path $env:TEMP 'sims-dump'
New-Item -ItemType Directory -Force $tmp | Out-Null

cmd /c "docker exec -e MYSQL_PWD=$pw $container mysqldump -uroot $($common -join ' ') $($ignore -join ' ') $db > `"$tmp\main.sql`""
cmd /c "docker exec -e MYSQL_PWD=$pw $container mysqldump -uroot $($common -join ' ') --no-data $db $($skipData -join ' ') > `"$tmp\empty.sql`""
python scripts/sanitize_dump.py "$tmp\main.sql" "$tmp\empty.sql" database/sims_sample.sql
Remove-Item -Recurse -Force $tmp
Write-Host "Wrote database/sims_sample.sql ($([math]::Round((Get-Item database/sims_sample.sql).Length/1MB,1)) MB). Commit it with your change."
