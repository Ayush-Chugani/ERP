$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $projectRoot 'backend/.venv/Scripts/python.exe'
Push-Location $projectRoot
try {
    & $pythonExe backend/manage.py check
    if ($LASTEXITCODE) { throw 'Django checks failed.' }
    & $pythonExe backend/manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE) { throw 'Migration state drift detected.' }
    & $pythonExe -m pytest backend/apps/identity_access/tests backend/apps/accounts/tests.py -q --reuse-db --tb=short
    if ($LASTEXITCODE) { throw 'M15 security tests failed.' }
    & $pythonExe backend/manage.py spectacular --file backend/schema-m15.yaml --validate
    if ($LASTEXITCODE) { throw 'OpenAPI validation failed.' }
} finally { Pop-Location }
