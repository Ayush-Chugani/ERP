# Runs backend (pytest-cov) and frontend (vitest v8) test suites with enforced coverage thresholds.
# Backend thresholds live in .coveragerc (fail_under); frontend thresholds in frontend/vitest.config.ts.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:SIMS_IDENTITY_ACCESS_ENABLED = '0'          # default flags; the dev .env enables staged modules
$env:SIMS_IDENTITY_ACCESS_SECURITY_ENABLED = '0'
Push-Location $root
try {
  & backend/.venv/Scripts/python.exe -m pytest -q --cov=backend/apps --cov-config=.coveragerc --cov-report=term:skip-covered --cov-report=html:backend/htmlcov backend
  if ($LASTEXITCODE -ne 0) { throw 'Backend tests or coverage threshold failed.' }
  Set-Location frontend
  npm test
  if ($LASTEXITCODE -ne 0) { throw 'Frontend contract tests failed.' }
  npm run test:coverage
  if ($LASTEXITCODE -ne 0) { throw 'Frontend tests or coverage threshold failed.' }
} finally { Pop-Location }
