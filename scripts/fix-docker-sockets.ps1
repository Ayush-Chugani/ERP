# Recovers Docker Desktop when it crashes at startup with:
#   "initializing Inference manager / Secrets Engine: listening on unix://...: remove ...:
#    The file cannot be accessed by the system."
# Cause: after an unclean shutdown, Docker leaves AF_UNIX socket files behind that Windows
# can neither open nor delete (error 1920), so the backend cannot recreate them.
# Fix: quit Docker, move the stale folders aside (renaming does not need to open the files),
# and relaunch. Container data (volumes) is not touched.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts/fix-docker-sockets.ps1
$ErrorActionPreference = 'Stop'
$local = $env:LOCALAPPDATA
$stamp = Get-Date -Format 'yyyyMMddHHmmss'

Get-Process | Where-Object { $_.ProcessName -match '^(Docker Desktop|com\.docker\.backend|docker)$' } |
  Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

foreach ($rel in 'Docker\run', 'docker-secrets-engine') {
  $path = Join-Path $local $rel
  if (Test-Path -LiteralPath $path) {
    $leaf = Split-Path $path -Leaf
    Rename-Item -LiteralPath $path -NewName "$leaf.stale-$stamp"
    Write-Host "moved aside: $rel"
  }
}

Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
Write-Host 'Docker Desktop relaunched. Waiting for the engine...'
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 6
  docker ps *> $null
  if ($LASTEXITCODE -eq 0) { Write-Host 'Engine is up.'; exit 0 }
}
Write-Warning 'Engine did not come up within ~4 minutes. Check the Docker Desktop window for a prompt.'
exit 1
