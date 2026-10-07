# Run from any directory. Stop at the first failed release gate.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & backend/.venv/Scripts/python.exe backend/manage.py check --database default
    if ($LASTEXITCODE -ne 0) { throw 'Django check failed.' }
    & backend/.venv/Scripts/python.exe -m ruff check backend/apps/organization backend/apps/tenancy backend/apps/academic_calendar --select E9,F63,F7,F82
    if ($LASTEXITCODE -ne 0) { throw "Backend lint failed." }
    & backend/.venv/Scripts/python.exe -m pytest backend/apps --cov=apps.organization --cov=apps.tenancy --cov=apps.academic_calendar --cov-report=term --cov-fail-under=80
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

