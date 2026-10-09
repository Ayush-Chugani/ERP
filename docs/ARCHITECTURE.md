# Architecture

```
backend/app
  main.py            application factory (middleware, error handlers, routers)
  config.py          typed settings from SIMS_* environment variables, with production guards
  db/                engine/session, naming conventions
  models/            SQLAlchemy models, one file per domain (192 tables) + platform tables (sessions, audit, jobs …)
  core/              security (Argon2, JWT), crypto (AES-GCM), rate limiting, TOTP, errors, middleware
  rbac/              permission engine (scopes), scope→SQL translation, catalogue + role matrix
  resources/         the generic resource engine (see below)
  api/routers/       auth, meta, security admin, workspace + the dedicated business endpoints
  services/          auth and audit domain logic
  worker/            PostgreSQL job queue, scheduler, handlers
  seed/              packaged base + demo fixtures and loaders
  storage.py         private object storage (local / S3)
backend/alembic      migrations (0001 schema, 0002 views, append-only triggers, row level security)
backend/tests        ~280 tests against a throw-away PostgreSQL database
frontend/src         API client, auth context, metadata-driven pages, a few bespoke screens
```

## The resource engine
`resources/spec.py` introspects each SQLAlchemy model into a `ResourceSpec` (columns, types, enums from CHECK
constraints, foreign keys, required/read-only flags) and builds Pydantic create/update/output models. One router
builder (`resources/router.py`) then mounts uniform REST endpoints for every spec, and `/meta` describes them to the UI.
This gives consistent validation, filtering, pagination, CSV export, audit and security across 150+ resources with no
per-table boilerplate. Behaviour that needs more than the schema is layered on explicitly:

| Concern | Where |
| --- | --- |
| Which module/permission a table belongs to, read-only tables, self-service rules | `resources/registry.py` |
| Status workflows (who may move a record from where to where, remarks, history) | `resources/workflows.py` |
| Numbering, defaults, cross-row integrity (credits, capacity, clashes) | `resources/rules.py`, `resources/domain_hooks.py` |
| Staff activities (awards, internships, projects…) sharing one parent record and review chain | `resources/activity.py` |
| Row scoping | `rbac/scope.py` (`scope_clause`) |

Business processes with multi-row logic have dedicated routers: admissions (`admit`), attendance, assessments/results,
feedback, files, HR identifiers.

## Request flow
`SecurityMiddleware` (host check, size limit, headers, request id) → router → `current_principal` (bearer token →
live session check → permissions and scopes, cached for 10 s) → handler → `crud`/service (scoped SQL, rules, audit) →
explicit `commit()` → JSON using the `{"error": …}` envelope on failure.

## Background work
Handlers enqueue jobs in the same transaction as the change (`worker.queue.enqueue`), so a rolled-back request never
leaves a stray job. `python -m app.cli worker` claims jobs with `FOR UPDATE SKIP LOCKED`, retries with exponential
back-off, marks exhausted jobs `dead`, recovers jobs abandoned by a crashed worker and triggers recurring schedules
(`maintenance.purge`, `memberships.expire`, `documents.expire`, `evidence.expiry_scan`).

## Data model notes
* Table and column names are the original SIMS schema (e.g. `student`, `employee_assignment`), cleaned of the
  Django/MySQL specifics: unsigned types, collations and generated columns became plain integers and partial/expression
  unique indexes.
* Per-module audit/outbox/receipt tables were replaced by four generic ones: `audit_log`, `status_history`, `job`,
  `idempotency_key`.
* `person_account_link` ties a login to a student or an employee; that link drives SELF-scoped access.
