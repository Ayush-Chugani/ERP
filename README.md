> **New to the project? Start with [TEAM_SETUP.md](TEAM_SETUP.md)** — one-command local setup, shared sample database, demo accounts, tests and troubleshooting.

> Module 7: [Registration implementation](Manuals/M7_IMPLEMENTATION.md), [stage status](Manuals/M7_IMPLEMENTATION_STATUS.md), [rollout](Manuals/M7_ROLLOUT.md), and [verification](Manuals/M7_RELEASE_AUDIT.md). Run scripts/verify-module7.ps1. Activation and the real course eligibility provider remain deployment gates.

> Module 8: [Teaching allocation and timetable](Manuals/M8_IMPLEMENTATION.md), [stage status](Manuals/M8_IMPLEMENTATION_STATUS.md), [rollout](Manuals/M8_ROLLOUT.md), and [verified results](Manuals/M8_RELEASE_AUDIT.md). Run scripts/verify-module8.ps1. Local migrations are applied; runtime remains disabled pending upstream and manual release gates.

> Module 3: [Academic Calendar implementation and usage](Manuals/M3_IMPLEMENTATION.md), [rollout](Manuals/M3_ROLLOUT.md), and [release review](Manuals/M3_RELEASE_AUDIT.md). Run scripts/verify-module3.ps1.

> Module 2: [Organization implementation and usage](Manuals/M2_IMPLEMENTATION.md), [deployment](Manuals/M2_DEPLOYMENT.md), and [release audit](Manuals/M2_RELEASE_AUDIT.md). Run scripts/verify-module2.ps1 for automated checks.

> Prompt 9: [Release verification results and pending browser/database checks](Manuals/PROMPT_9_verification.md). Run scripts/verify-release.ps1 once MySQL is available.

> Prompt 7 update: [Login and Common Reference frontend](Manuals/PROMPT_7_reference_frontend.md). Includes usage and verification limits.

> Prompt 6 update: [Administration, seed data and audit history](Manuals/PROMPT_6_admin_seed_audit.md). Apply the new core migration before reference writes.

> Prompt 5 update: [Common Reference API endpoints, filters, examples and permissions](Manuals/PROMPT_5_reference_api.md).

> Prompt 4 update: [authentication endpoints, permissions, tests and operational commands](Manuals/PROMPT_4_authentication.md). Starter groups now receive reference view permissions.

> Prompt 3 update: see [models, MySQL verification and adoption](Manuals/PROMPT_3_models_and_adoption.md). MySQL is now running on port 3307; reference migrations require it. Earlier SQLite-only instructions below describe Prompt 2 and no longer apply to the full migration suite.

# SIMS foundation Ã¢â‚¬â€ Prompt 2

The new entry point is `backend/manage.py`. The older root-level settings/urls/wsgi files and the parent-directory manage.py belong to the earlier scaffold and are not used by this foundation. Existing XAMPP `sims_v6` is unchanged. This step does not implement reference models, CRUD, login UI, or service workers.

## Windows setup (PowerShell, from repository root)

Prerequisites: Python 3.11, Node 22.12+ (verified here with Node 24.15), Docker Desktop with Linux containers running. MySQL is bound only to localhost port 3307 to avoid XAMPP port 3306. Compose uses a separate named volume.

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
Copy-Item backend/.env.example backend/.env
backend/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
notepad backend/.env
```

Replace `DJANGO_SECRET_KEY` with the generated value and `SIMS_DB_PASSWORD` with your chosen local root password. Example files contain placeholders only; `.env` is ignored. Keep `SIMS_DB_NAME=sims_reference_dev`, host 127.0.0.1, port 3307 and user root. Never point these initial migrations at the previously imported `sims_v6`. Environment variables override `.env`; remove stale shell overrides when troubleshooting.

```powershell
docker compose --env-file backend/.env up -d --wait
backend/.venv/Scripts/python.exe backend/manage.py check --database default
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py seed_role_groups
backend/.venv/Scripts/python.exe backend/manage.py createsuperuser
backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000
```

The Docker root password is initialized only on a fresh volume; changing `.env` does not rotate an existing database password. `docker compose down` stops the service without deleting the volume. Do not use `down -v` unless deliberately deleting this development database.

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173/. Vite proxies `/api` to Django. Optional `frontend/.env` may be copied from its example; no frontend secrets. Production uses relative `/api/v1`, with no cross-origin access.

## Checks

Foundation tests can run without MySQL using the explicit SQLite switch:

```powershell
$env:SIMS_TEST_SQLITE='1'
backend/.venv/Scripts/python.exe backend/manage.py test apps.core --settings=config.settings.test
backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run --settings=config.settings.test
backend/.venv/Scripts/python.exe backend/manage.py spectacular --settings=config.settings.test --file backend/openapi.yaml --validate --fail-on-warn
Remove-Item Env:SIMS_TEST_SQLITE
backend/.venv/Scripts/python.exe -m pip check
npm --prefix frontend run build
```

Real MySQL verification after Docker starts:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py test apps.core --settings=config.settings.test
backend/.venv/Scripts/python.exe backend/manage.py check --database default
```

The test runner uses `test_sims_reference`; it must never be configured as a production database. SQLite verifies foundation behavior only, not unsigned types, generated columns, FK parity, collations or concurrent MySQL writes.

## Foundation behavior

`accounts.User` and `AUTH_USER_MODEL` exist before `accounts/0001_initial`. Physical user table is `user_account`, primary key `user_id`; the ID is signed BIGINT in this new platform model, not a claim of compatibility with the legacy full-schema accounts table. Ten reference-model key widths will be preserved separately in Prompt 3. No migration of Django's default User is performed.

Admin, Teacher and Student are global starter Group records, allow multiple membership, and initially grant no permissions. The seed command preserves existing memberships/permissions and is idempotent. These are not institution-scoped roles. No role column exists. Only superusers may use account admin until scoped account administration is implemented. Database root is distinct from a Django platform superuser.

DRF defaults to JWT authentication and authenticated permissions. `/api/v1/` is protected. No public token-issuance routes are enabled yet; auth flows arrive in Prompt 4. Simple JWT uses custom `user_id`, five-minute access tokens, refresh rotation and blacklist app configuration. Navigation/permission strings in the static registry are declarations; reference permissions are materialized with reference models in later steps. No runtime plugin installation or domain APIs are present.

Pagination defaults to 25 and caps requests at 100. Queryset order receives an explicit PK tie-breaker. Future list endpoints must use this pagination and allowlist user-selected ordering; random ordering is not supported.

API error shape: `{"error":{"code":"...","message":"...","details":{}}}`. Authentication/validation failures and unknown API routes use it. Unexpected API failures return generic text; exception details are logged server-side. Non-API Django admin errors are not this contract. Production 404/500 handlers also return safe JSON.

Public, unauthenticated `/api/v1/core/live/` returns process liveness without touching the database. `/api/v1/core/ready/` verifies a database query and pending migrations; failure is a generic 503, never credentials or exception text. `/api/v1/schema/` and `/api/v1/docs/` require staff JWT authentication. Generated `backend/openapi.yaml` can be viewed offline; the docs UI may require a token-capable client before login UI exists.

Explicit development origins: http://localhost:5173 and http://127.0.0.1:5173. Production CORS origins are empty. SQL strict mode and UTC are set on each database connection; Compose selects InnoDB's default server engine, utf8mb4 and utf8mb4_0900_ai_ci.

## Linux production setup outline

Set production environment secrets and `DJANGO_ALLOWED_HOSTS` to explicit hostnames. `backend/requirements.lock` is the resolved Windows development dependency snapshot, not a hash-verified cross-platform production lock. `requirements-production.in` adds Gunicorn for Linux; resolve/audit a Linux lock before release. The MySQL 8.4 tag deliberately tracks its maintained patch series for local development; pin a tested immutable image digest for production.

```bash
python3.11 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-production.in
backend/.venv/bin/pip freeze > backend/requirements-production.lock
export DJANGO_SETTINGS_MODULE=config.settings.production
# Supply DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS and SIMS_DB_* securely.
backend/.venv/bin/python backend/manage.py check --deploy
backend/.venv/bin/python backend/manage.py migrate
backend/.venv/bin/python backend/manage.py collectstatic --noinput
cd backend
.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000
```

`deploy/nginx.conf.example` is a TLS server fragment serving frontend at `/`, proxying `/api/` and `/admin/`, and serving collected `/static/`. Configure your TLS certificates/HTTP-to-HTTPS server and process supervision before deployment. Only the trusted proxy may reach Gunicorn and set forwarding headers. This step does not deploy a public service or configure certificates.

## Compatibility evidence

Django 5.2.17 LTS: https://www.djangoproject.com/download/
DRF 3.16 support: https://www.django-rest-framework.org/community/3.16-announcement/
MySQL and driver requirements: https://docs.djangoproject.com/en/5.2/ref/databases/
Simple JWT release metadata: https://pypi.org/project/djangorestframework-simplejwt/5.5.1/
Schema generator support: https://drf-spectacular.readthedocs.io/en/stable/readme.html
MUI peer requirements: https://mui.com/material-ui/getting-started/installation/
Vite Node requirements: https://vite.dev/guide/
TypeScript 5.9: https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-9.html
Vite PWA integration: https://vite-pwa-org.netlify.app/guide/

Simple JWT 5.5.1's installed release metadata explicitly lists Django 5.2, resolving the older documentation gap in ADR 001. The actual custom-user access-token and blacklist smoke tests pass with DRF 3.16.1. Full rotation/cookie/CSRF flows remain unimplemented and untested. Frontend exact transitive dependencies are captured in package-lock.json; service worker registration is intentionally deferred to Prompt 8.

## Verification performed in this workspace

- Six foundation tests passed using in-memory SQLite; custom-user migration applied in the test database.
- Django system checks and production `check --deploy` passed (temporary environment values, no production connection).
- Migration drift check: no changes detected.
- OpenAPI generation with validation and warnings-as-errors passed.
- pip dependency consistency check passed.
- TypeScript check and Vite production build passed; npm installation audit reported zero vulnerabilities.
- Docker executable exists, but daemon connection failed. MySQL container startup, MySQL migration execution and real readiness success are NOT verified.
- Browser visual verification and Linux Gunicorn/Nginx execution were not performed.

## Created files and continuation

Backend: config/settings/{base,development,test,production}.py, config/{urls,wsgi}.py, manage.py; apps/accounts user/admin/initial migration/seed command; apps/core registry/pagination/errors/health/tests; common_reference URL placeholder; dependency input/lock/production input, environment example and generated OpenAPI. Frontend: package manifest/lock, tsconfig, Vite config, index.html, main entry, app shell, API contract and feature/component boundaries. Root: .gitignore, compose.yaml, this README. Deployment: Nginx example. Package initializer files accompany Python directories. Existing SQL/ADR and legacy scaffold files are unchanged.

Prompt 3: implement the ten managed reference models and migration-safe unsigned fields, explicit columns/collations and generated caste uniqueness. First start Docker and verify the fresh MySQL foundation migrations. Do not adopt the old full schema or add future domain models implicitly.




## Curriculum and Course Catalog (M4)

Implemented module: [usage, API and permissions](Manuals/M4_IMPLEMENTATION.md), [rollout/recovery](Manuals/M4_ROLLOUT.md), [verification and release audit](Manuals/M4_RELEASE_AUDIT.md). Open `http://127.0.0.1:5173/#/curriculum` after starting backend and frontend. Run `./scripts/verify-module4.ps1` for automated checks. Earlier foundation verification notes above are historical; the M4 report records current MySQL results and remaining browser/staging checks.

## Student and Staff Masters (M5)

[Usage, permissions and API examples](Manuals/M5_IMPLEMENTATION.md) · [Verification and rollout runbook](Manuals/M5_RELEASE_AUDIT.md). Open `http://127.0.0.1:5173/#/people` after starting the backend/frontend. Run `./scripts/verify-module5.ps1` for automated checks. Student ownership and activation requirements follow the user's approved choices; browser and staging recovery acceptance remain release gates.
