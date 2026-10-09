# SIMS — Student Information Management System

A campus ERP covering organisation, people, admissions, registration, timetable, attendance, assessments and results,
feedback, student support, documents, communication and staff research/professional records.

| Layer | Technology |
| --- | --- |
| API | **FastAPI** (Python 3.13) · SQLAlchemy 2 · Alembic · Pydantic 2 · managed with **uv** |
| Database | **PostgreSQL** — Supabase in production, Docker locally |
| Web UI | React 19 · MUI 9 · TanStack Query · Vite 8 · TypeScript — white + orange design system, light/dark/system theme, Ctrl/⌘+K search; talks to the API only |
| Auth | Argon2id passwords · short-lived JWT access token · rotating HttpOnly refresh cookie · optional TOTP MFA |
| Access control | Roles with institution / campus / department / programme / self scopes, enforced on every row |
| Queue | PostgreSQL job queue (`FOR UPDATE SKIP LOCKED`) with retries, back-off and a scheduler |
| Files | Private storage — local disk or any S3-compatible bucket (e.g. Supabase Storage) |

The browser only ever talks to `/api/v1/*`. There are no server-rendered pages and no admin site; the UI is a static
bundle that can be hosted anywhere.

## Repository layout

```
backend/    FastAPI app (app/), Alembic migrations, tests, tools, load tests, Dockerfile
frontend/   React + MUI single-page app (src/), tests, nginx.conf, Dockerfile
docs/       Architecture, database, roles, security, deployment, operations, testing, demo data, AI
scripts/    setup.ps1 (Windows) and setup.sh (Linux / macOS / Git Bash)
compose.yaml  local PostgreSQL, and the full stack under the `app` profile
Makefile    shortcuts for the commands below
```

## Setup

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Node.js 22.12+ (24 recommended), Docker (for the local database).

### One command

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -SeedDemo
```

```bash
# Linux / macOS / Git Bash
./scripts/setup.sh --seed-demo
```

The script checks prerequisites, starts PostgreSQL in Docker (`127.0.0.1:54329`), creates `backend/.env` with a
generated secret key (an existing `.env` is never overwritten), installs backend and frontend dependencies, then
runs the migrations and loads the permission catalogue and roles. It is safe to re-run.

| Option (PowerShell / bash) | Effect |
| --- | --- |
| `-SeedDemo` / `--seed-demo` | also load the demo campus and demo accounts (development only) |
| `-SkipDb` / `--skip-db` | do not start Docker; use the database already set in `backend/.env` (e.g. Supabase) |

### Run it

Open two terminals:

```powershell
cd backend
uv run uvicorn app.main:app --reload       # API  -> http://127.0.0.1:8000/api/docs
```

```powershell
cd frontend
npm run dev                                # UI   -> http://localhost:5173
```

Optional third terminal for background jobs (notifications, announcement delivery, expiry scans, clean-up):
`cd backend && uv run python -m app.cli worker`.

### Sign in

* **With demo data** (`--seed-demo`): usernames and roles are listed in [docs/DEMO_DATA.md](docs/DEMO_DATA.md). The demo
  password is published there on purpose — never load demo data into production.
* **Without demo data**, create your own super administrator and sign in through the *Administrator* entrance:

```powershell
cd backend
$env:SIMS_BOOTSTRAP_ADMIN_PASSWORD = "a-long-unique-password"     # bash: export SIMS_BOOTSTRAP_ADMIN_PASSWORD=...
uv run python -m app.cli create-admin --username admin --email you@example.org
```

### Manual setup

If you prefer not to use the script (or have `make`):

```powershell
docker compose up -d --wait                 # local PostgreSQL on 127.0.0.1:54329
cd backend
copy .env.example .env                      # set SIMS_SECRET_KEY; set SIMS_COOKIE_SECURE=false for plain-http local use
uv sync
uv run python -m app.cli migrate            # create the schema
uv run python -m app.cli bootstrap          # permission catalogue, roles, reference data (safe to repeat)
uv run python -m app.cli seed-demo          # optional
cd ..\frontend ; npm ci
```

`make setup | db | migrate | bootstrap | seed-demo | admin | api | web | worker | test | lint | build` wrap the same commands.

### Configuration

Every backend setting is an environment variable prefixed `SIMS_`; `backend/.env.example` documents all of them
(database, secrets, cookies, rate limits, file storage, optional AI features). In production
(`SIMS_ENV=production`) the API refuses to start with an unsafe secret key, insecure cookies or no field-encryption keys.
The frontend needs no configuration for local use (`VITE_API_BASE_URL` defaults to `/api/v1`, and Vite proxies `/api`
to the API; set `SIMS_API_ORIGIN` if the API is not on port 8000).

## Using Supabase

1. Create a Supabase project and open **Project settings → Database → Connection string**.
2. Use the **Session pooler** string (IPv4, port 5432). The direct `db.<ref>.supabase.co` host is IPv6-only.
3. Put it in `backend/.env` as
   `SIMS_DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require`
   (URL-encode special characters in the password: `@` → `%40`).
4. `uv run python -m app.cli migrate && uv run python -m app.cli bootstrap && uv run python -m app.cli create-admin`

Migrations enable **row level security on every table** and revoke access from Supabase's `anon` and `authenticated`
roles, so the auto-generated Supabase REST API can never read or write your data; only the API service (which connects
as the table owner) can. See [docs/SECURITY.md](docs/SECURITY.md).

## Full stack in Docker

```powershell
copy backend\.env.example backend\.env      # set production values; SIMS_ENV=production enforces safe settings
docker compose --profile app up -d --build  # migrate -> api + worker + web on http://localhost:8080
```

With Supabase, skip the local database: `docker compose --profile app up -d --build migrate api worker web`.
Production guidance (TLS, scaling, backups, secrets) is in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## How the API is organised

* `GET /api/v1/meta` tells the UI which areas, fields, filters and workflow actions the signed-in user may use.
* Every table is exposed as a resource: `GET/POST /api/v1/{module}/{resource}`, `GET/PATCH/DELETE …/{id}`,
  `POST …/{id}/actions/{action}` (workflow), `GET …/{id}/history`, `GET …/export` (CSV).
  Filtering (`?field=`, `?field__in=`, `?search=`), ordering and pagination are uniform.
* Dedicated endpoints cover the business processes: admissions (`clearance`, `admit`), attendance marking and
  summaries, marks entry, result and SGPA/CGPA calculation, transcripts, anonymous feedback, private file upload and
  download, staff identifiers (encrypted), users/roles/assignments, audit trail and background jobs.
* Errors always look like `{"error": {"code", "message", "details"}}`.
* Interactive documentation: `/api/docs` (disable with `SIMS_DOCS_ENABLED=false`).

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) · [Roles & permissions](docs/ROLES.md) ·
[Security](docs/SECURITY.md) · [Deployment](docs/DEPLOYMENT.md) · [Operations runbook](docs/OPERATIONS.md) ·
[Testing & load results](docs/TESTING.md) · [Demo data](docs/DEMO_DATA.md) · [AI features](docs/AI.md)

## Tests and checks

```powershell
cd backend ; uv run pytest -q ; uv run ruff check app tests tools     # on a throw-away PostgreSQL database
cd frontend ; npm test ; npm run typecheck ; npm run build
```

The backend suite creates and drops its own schema and **refuses to run against any database whose name does not end
in `_test`**, so it can never touch Supabase or a development database. It uses `SIMS_TEST_DATABASE_URL`
(defaults to the Docker database's `sims_test`). CI is in `.github/workflows/ci.yml`.

## Moving data from the old Django/MySQL version

```powershell
cd backend
uv run --with pymysql --with cryptography python -m tools.import_legacy_mysql --mysql "mysql+pymysql://user:pass@host:3306/db"
```

copies people, academics and accounts into an empty, migrated database. Existing passwords keep working (they are
verified and upgraded to Argon2id at the next sign-in). The earlier Django implementation remains in this repository's
git history.
