# Run from any directory. Stop at the first failed release gate.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & backend/.venv/Scripts/python.exe backend/manage.py check --database default
    if ($LASTEXITCODE -ne 0) { throw 'Django check failed.' }
    & backend/.venv/Scripts/python.exe backend/manage.py test apps.organization apps.tenancy apps.common_reference apps.accounts apps.core --settings=config.settings.test --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed. Verify local MySQL is running.' }
    & backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'Migration drift detected.' }
    & backend/.venv/Scripts/python.exe backend/manage.py spectacular --file backend/openapi.yaml --validate --fail-on-warn
    if ($LASTEXITCODE -ne 0) { throw 'OpenAPI validation failed.' }
    & npm --prefix frontend test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    & npm --prefix frontend run test:ui
    if ($LASTEXITCODE -ne 0) { throw 'Frontend component tests failed.' }
    & npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Production build failed.' }
    Write-Output 'Automated checks passed. Complete the browser checklist before release.'
} finally { Pop-Location }
