$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $python = Join-Path $root 'backend/.venv/Scripts/python.exe'
    & $python backend/manage.py check --database default
    if ($LASTEXITCODE) { throw 'Django check failed.' }
    & $python backend/manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE) { throw 'Migration drift detected.' }
    # Rebuild the isolated test DB: rolled-back fixtures still consume unsigned TINYINT sequences.
    & $python backend/manage.py shell --settings=config.settings.test -c "from django.conf import settings; db=settings.DATABASES['default']; name=db.get('TEST', {}).get('NAME'); assert name and name.startswith('test_') and name != db['NAME'], 'Refusing an unsafe test database name'"
    if ($LASTEXITCODE) { throw 'Test database isolation check failed.' }
    & $python -m pytest backend/apps/assessments_results/tests backend/apps/attendance_lesson_plan/tests backend/apps/teaching_timetable/tests backend/apps/term_registration/tests backend/apps/admission_enrolment/tests backend/apps/core -q --import-mode=importlib --reuse-db --create-db
    if ($LASTEXITCODE) { throw 'MySQL tests failed.' }
    & $python backend/manage.py spectacular --file backend/openapi.yaml --validate --fail-on-warn
    if ($LASTEXITCODE) { throw 'OpenAPI validation failed.' }
    & npm --prefix frontend run test:ui
    if ($LASTEXITCODE) { throw 'Frontend component tests failed.' }
    & npm --prefix frontend run build
    if ($LASTEXITCODE) { throw 'Frontend build failed.' }
    Write-Output 'Automated M10 checks passed. Browser acceptance, approved academic policies and staging recovery remain separate gates.'
} finally {
    Pop-Location
}
