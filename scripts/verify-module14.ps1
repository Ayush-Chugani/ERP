$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $python = Join-Path $root 'backend/.venv/Scripts/python.exe'
    & $python -m ruff check backend/apps/communication backend/apps/documents_exit/sharing.py
    if ($LASTEXITCODE) { throw 'M14 lint failed.' }
    & $python -m ruff format --check backend/apps/communication backend/apps/documents_exit/sharing.py
    if ($LASTEXITCODE) { throw 'M14 formatting failed.' }
    & $python backend/manage.py check --database default
    if ($LASTEXITCODE) { throw 'Django check failed.' }
    & $python backend/manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE) { throw 'Migration drift detected.' }
    & $python backend/manage.py shell --settings=config.settings.test -c "from django.conf import settings; db=settings.DATABASES['default']; name=db.get('TEST', {}).get('NAME'); assert name and name.startswith('test_') and name != db['NAME'], 'Refusing unsafe test database'"
    if ($LASTEXITCODE) { throw 'Test isolation check failed.' }
    & $python -m pytest backend/apps/communication/tests backend/apps/documents_exit/tests backend/apps/people_master/tests backend/apps/admission_enrolment/tests backend/apps/core -q --import-mode=importlib --reuse-db --create-db
    if ($LASTEXITCODE) { throw 'MySQL tests failed.' }
    & $python backend/manage.py spectacular --file backend/openapi.yaml --validate --fail-on-warn
    if ($LASTEXITCODE) { throw 'OpenAPI validation failed.' }
    & npm --prefix frontend run test:ui
    if ($LASTEXITCODE) { throw 'Frontend tests failed.' }
    & npm --prefix frontend run build
    if ($LASTEXITCODE) { throw 'Frontend build failed.' }
    Write-Output 'Automated M14 checks passed. Browser acceptance, pilot authorization and populated recovery/load tests remain separate gates.'
} finally { Pop-Location }
