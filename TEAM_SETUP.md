# SIMS — team setup guide

SIMS is a campus ERP: a **Django REST API** (`backend/`), a **React + MUI** web app (`frontend/`) and a
**MySQL 8.4** database that runs in Docker. This guide gets a new teammate from clone to a running app with
sample data in a few minutes.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker Desktop | recent | runs MySQL (port **3307**, so it does not clash with XAMPP/local MySQL on 3306) |
| Python | 3.11+ | backend (a venv is created in `backend/.venv`) |
| Node.js | 22.12+ | frontend |
| Git | any | |

## Quick start (Windows / PowerShell)

```powershell
git clone https://github.com/Ayush-Chugani/ERP.git
cd ERP
powershell -ExecutionPolicy Bypass -File scripts/setup-dev.ps1
```

The script creates `backend/.env` with fresh random secrets, installs Python and npm dependencies, starts MySQL,
imports the shared sample database, creates the demo logins and asks you to choose an **admin** password.
Then run the app in two terminals:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000
cd frontend; npm run dev          # http://127.0.0.1:5173
```

macOS/Linux: the scripts are PowerShell, but every step is a plain command; see "Manual setup" below.

## Sign-in accounts

`admin` has **no password until you set one** (the setup script asks; or run
`backend/.venv/Scripts/python.exe backend/manage.py changepassword admin`).

The other demo accounts (`registrar`, `campusadm`, `hod`, `teacher`, `examcell`, `support`, `student`, `student2`)
share the development password defined as `DEMO_PASSWORD` at the top of
`backend/apps/core/management/commands/seed_sample_data.py`. Each represents a role with its own scope; the table of
roles, what each can see and how access is enforced is in [`Manuals/DEMO_DATA.md`](Manuals/DEMO_DATA.md).
These passwords are for local development only.

## The database

`database/sims_sample.sql` (~1 MB) holds the full schema (244 tables, 5 views, 26 triggers) plus **synthetic** sample data:
50 students, 15 staff, courses, admissions, timetable, attendance, marks, staff research activities, grievances,
certificate requests, announcements and role assignments. It contains **no real personal data**: password hashes are
blanked and session/token/login-audit rows are excluded.

| Task | Command |
|---|---|
| Load the shared database (replaces your local one) | `powershell -ExecutionPolicy Bypass -File scripts/import-database.ps1` |
| Share your data/schema changes | `powershell -ExecutionPolicy Bypass -File scripts/export-database.ps1`, then commit `database/sims_sample.sql` |
| Re-create demo logins after an import | `backend/.venv/Scripts/python.exe backend/manage.py seed_sample_users` |
| Rebuild sample data from scratch | `backend/.venv/Scripts/python.exe backend/manage.py seed_sample_all` (idempotent) |

Rules of thumb: schema changes go through Django migrations (`makemigrations`), never only through the dump; re-export the
dump when your change needs new sample rows; never put real student/staff data in the dump.

## Manual setup (any OS)

```bash
cp backend/.env.dev.example backend/.env      # then replace every __GENERATE__ with a long random value
python -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.lock        # Scripts\ instead of bin\ on Windows
docker compose --env-file backend/.env up -d --wait               # MySQL on 127.0.0.1:3307
# import the sample database into the container's sims_reference_dev, e.g.:
docker compose --env-file backend/.env exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" sims_reference_dev' < database/sims_sample.sql
backend/.venv/bin/python backend/manage.py migrate
backend/.venv/bin/python backend/manage.py seed_sample_users
backend/.venv/bin/python backend/manage.py changepassword admin
cd frontend && npm ci && npm run dev
```

## Tests and quality gates

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-coverage.ps1     # backend + frontend with enforced coverage floors
```

* **Backend**: `pytest` (730 tests). Run with `SIMS_IDENTITY_ACCESS_ENABLED=0 SIMS_IDENTITY_ACCESS_SECURITY_ENABLED=0`
  because the dev `.env` switches staged modules on. Coverage floor: **85%** (`.coveragerc`). Avoid `--reuse-db` for
  full runs: some tables use 8-bit keys that run out after many reuses.
* **Frontend**: `cd frontend && npm test` (contract tests) and `npm run test:coverage` (225 UI tests; floors in
  `frontend/vitest.config.ts`). Also `npx tsc --noEmit` and `npm run build`.
* Raise the coverage floors when you add tests; never lower them.

## Docker Desktop will not start

If Docker crashes at launch with *"listening on unix://… The file cannot be accessed by the system"*, stale socket files
from an unclean shutdown are blocking it. Run `powershell -ExecutionPolicy Bypass -File scripts/fix-docker-sockets.ps1`
(quits Docker, moves the stale folders aside, relaunches; your containers' data is untouched).

## Where things live

```
backend/apps/<module>/      one Django app per module (people_master, attendance_lesson_plan, ...)
backend/config/             settings (base/test), URLs, OpenAPI schema
frontend/src/app/           shell: layout, navigation, router, theme, dashboard, login
frontend/src/features/      one folder per module screen
frontend/tests/             vitest + msw UI tests, accessibility (axe) tests
database/                   shared sample database
scripts/                    setup, import/export, coverage, docker recovery, module verifiers
Manuals/                    module docs, release audits and DEMO_DATA.md (accounts and roles)
```

Access control has three layers (Django groups, IAM roles, scope grants) and the UI hides what a role cannot use; the API
always re-checks. Details are in `Manuals/DEMO_DATA.md`.

## Contributing

1. Branch from `main` (`feature/<short-name>`), keep changes focused.
2. Run the tests above before opening a pull request; CI runs the module verification workflow.
3. Never commit `backend/.env`, real data, uploaded documents or secrets. `.gitignore` already excludes them.
4. If your change needs data, update the seeders (`backend/apps/core/management/commands/seed_sample_*.py`) and/or re-export the dump.
