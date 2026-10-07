# Module 2 - implementation and operator guide

## Current status

The University and Institution Structure module is integrated at `/#/organization`. All eight entity types have scoped backend APIs and shared list, detail, create/edit and lifecycle screens. The original Common Reference module remains available. The user approved implementing the missing authorization foundation here.

The supplied DOCX was treated as the requested task sequence, not as evidence that its assumed authorization extension already existed. `Manuals/M2_PROMPT_01_architecture.md` records that mismatch and the adopted schema contract. Source-only checkpoints are kept under `.tmp/m2-checkpoints`; environment files and dependencies are excluded.

## Prompt execution ledger

| Prompt | Result and principal files |
| --- | --- |
| 1 Architecture | Reviewed Appendix A; preserved code uniqueness and unsigned IDs; approved new authorization foundation. M2_PROMPT_01_architecture.md |
| 2 Foundation | apps.organization/apps.tenancy registered; existing auth/settings reused; django-filter, React Router, TanStack Query, Axios, React Hook Form and Zod installed and locked |
| 3 Models | Eight models, TextChoices/check constraints, protected FKs, normalized validation; organization/models.py and fields.py |
| 4 Migrations | organization/0001 and /0002 plus tenancy/0001; fresh development tables inspected and migrated; legacy adoption is separate |
| 5 Services | Atomic writes/audits, active-parent validation, impact and guarded moves; services.py |
| 6 Serializers | Explicit writable fields and ID inputs, per-action serializer classes, server errors; serializers.py |
| 7 Authorization | Membership, scope grants and activation; tenancy/models.py and organization/selectors.py |
| 8 API | Eight viewsets, ancestor/enum filters, ordering/pagination, lifecycle actions; views.py, filters.py |
| 9 Bulk onboarding | Bounded CSV template/import/dry-run/error report/export; bulk.py |
| 10 OpenAPI | Regenerated backend/openapi.yaml with create examples, action responses and move bodies; schema validation passes |
| 11 Frontend foundation | api.ts and OrganizationApp.tsx; Axios adapter reuses existing refresh coordination |
| 12 Explorer | Scoped counts, lazy child drill-down, resource navigation and breadcrumbs |
| 13 Lists/details | Server filters, URL state, sortable/paginated tables, optional columns, contact/audit metadata |
| 14 Forms | Hook Form/Zod validation, paginated historical parent selection, guarded lifecycle/move dialogs and impact preview |
| 15 Offline | Explicit active-label snapshot; user-bound, five-minute, tab-memory copy; online API caching remains disabled |
| 16 Security | Permission regression tests, no-store responses, body limits, production headers, dependency scans and DRF fix |
| 17 Quality | MySQL tests, concurrency/query-count tests, pytest coverage, Vitest/RTL/MSW tests, lint/type/build gates |
| 18 Operations | Linux systemd/Nginx/environment templates and M2_DEPLOYMENT.md; no production host changed |
| 19 Audit | M2_RELEASE_AUDIT.md; browser and Linux staging acceptance remain pending, so this is not a release approval |

## Launch

With Docker Desktop running, from the workspace root:

```powershell
docker compose --env-file backend/.env up -d --wait
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000
```

In another terminal:

```powershell
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173/#/organization and sign in. A platform superuser can bootstrap University, Institution, then Campus/Department/Programme/Specialization and Building/Room. No organization classifications, users or demo institutions were seeded into the working database.

### Provision institutional access

Only a platform superuser can manage the Tenancy admin screens at `/admin/`:

1. Create a Membership linking an existing user and institution; mark it active.
2. Create the institution's InstitutionModule row and enable organization_structure (default is disabled).
3. Create an active ScopeGrant with the appropriate role and campus/department scope.
4. Use record_limits only when explicit per-resource allowlists are required, e.g. `{"campuses":[12,15]}`. IDs must belong to the underlying grant scope; limits never widen it. Multiple grants combine their allowed scopes.
5. Sign in as that user and verify both permitted and denied paths.

The existing global Admin/Teacher/Student groups do not grant organization authority. No membership self-service or role-grant API exists. Django model add/change grants alone do not bypass organization scoping. State choices additionally require the existing Common Reference view_state permission.

## Permission matrix

All non-platform access requires an active user, active membership, active grant and enabled institution module. Teachers/students see active records with active ancestors; managers can inspect historical inactive records in their permitted hierarchy. Ancestor labels do not grant access to sibling institutions/campuses/departments.

| Entity | Platform superuser | Institution admin | Campus admin | Department admin | Teacher/student |
| --- | --- | --- | --- | --- | --- |
| University | Create/read/change/lifecycle | Read ancestor | Read ancestor | Read ancestor | Permitted active ancestor |
| Institution | Create/read/change/lifecycle | Read/change/lifecycle own institution | Read ancestor | Read ancestor | Permitted active ancestor |
| Campus | Full | Create/read/change/lifecycle in institution | Read/change/lifecycle assigned campus | Read ancestor | Active assigned scope |
| Department | Full | Full inside institution | Create/read/change/lifecycle in campus | Read/change/lifecycle assigned department | Active assigned scope |
| Programme | Full | Full inside institution | Full inside campus | Create/read/change/lifecycle in department | Active assigned scope |
| Specialization | Full | Full inside institution | Full inside campus | Full inside department | Active assigned scope |
| Building | Full | Full inside institution | Create/read/change/lifecycle in campus | No building authority from department grant | Active scope unless limited to department |
| Room | Full | Full inside institution | Full inside campus | No room authority from department grant | Active scope unless limited to department |

Full never includes hard deletion. Structural moves require management access to both source and destination, an active destination, no dependent references and unchanged institution ownership. Generic PATCH/PUT cannot change the ownership parent. State/address corrections are ordinary validated updates. Deactivation is non-cascading; reactivation does not reactivate ancestors.

## API contract

Base: `/api/v1/organization/`. Resource paths: universities, institutions, campuses, departments, programmes, programme-specializations, buildings, rooms. IDs retain the supplied names, including specialization_id.

| Route | Behavior |
| --- | --- |
| GET /metadata/ | Scoped counts, field descriptions/defaults and management capabilities; no-store |
| GET /resource/ | Paginated scoped list, default available only |
| POST /resource/ | Validated, authorized create with atomic audit |
| GET /resource/{id}/ | Scoped detail, inaccessible IDs return 404 |
| PUT/PATCH /resource/{id}/ | Update allowlisted fields; ownership moves and is_active use dedicated actions |
| GET /resource/{id}/impact/ | Manager-only scoped domain counts and guarded move eligibility; no membership-count disclosure |
| POST /resource/{id}/deactivate/ or reactivate/ | Empty JSON body; explicit lifecycle change |
| POST /resource/{id}/move/ | Only the new ownership parent ID |
| GET /resource/import-template/ | CSV header with primary key plus writable fields; no audit/status fields |
| POST /resource/import/ | JSON csv string plus boolean dry_run (default true) |
| GET /resource/export/ | Scoped, filtered CSV with formula escaping |
| GET /resource/offline-snapshot/ | At most 100 scoped active identity-label records, five-minute expiry, no contacts/audit/permissions |

List/export/snapshot filters: search (150 characters), allowlisted ordering with optional minus prefix, page/page_size (default 25, maximum 100), is_active=true/false/all, applicable parent and ancestor IDs, and entity enum fields. Unknown/repeated parameters fail. Parent identifiers are positive integers in their unsigned storage range. Inactive/all requests require management scope. The frontend exposes the direct-parent filter and child drill-down; APIs additionally support ancestor filters.

Examples (IDs are illustrative, use IDs returned by your instance):

```http
POST /api/v1/organization/universities/
Authorization: Bearer <in-memory access token>
Content-Type: application/json

{"university_code":"EXAMPLE","university_name":"Example University","university_type":"OTHER"}
```

```http
POST /api/v1/organization/campuses/
Authorization: Bearer <in-memory access token>
Content-Type: application/json

{"institution_id":1,"campus_code":"MAIN","campus_name":"Main Campus"}
```

```http
GET /api/v1/organization/programmes/?institution_id=1&campus_id=2&ordering=programme_code&page_size=25
GET /api/v1/organization/departments/3/impact/
POST /api/v1/organization/departments/3/move/
Content-Type: application/json

{"campus_id":4}
```

Use the existing login/CSRF cookie workflow documented in PROMPT_4_authentication.md. Request/response examples and JWT security are also available in `/api/v1/docs/`. Do not put real credentials or tokens into checked-in examples.

## CSV onboarding

Maximum 200 rows and 256 KB per JSON-contained CSV input; the batch is atomic. A supplied primary-key column means update that authorized record; a blank key means create. There is no implicit upsert by globally unique code. Parent columns use actual authorized API IDs, not assumed numeric IDs. Dry-run executes validation and writes inside a rolled-back transaction, including audit rows; normal auto-increment gaps may result. No user records persist from a dry-run. Repeated conflicting rows fail; any error rolls back all rows. The response includes row errors and error_report_csv, which clients may save as a downloadable report. Export is bounded to 5000 rows and escapes spreadsheet formula prefixes; exported audit/status columns must be removed before import. The CSV operations are API-first in this increment; dedicated bulk-onboarding screens are not supplied.

## Audit and safety boundaries

OrganizationAudit is an explicit platform-support table, separate from Common Reference auditing. It records actor/resource/record ID/action/timestamp and a fixed allowlist of bounded scalar before/after values. Read it in Django admin with organization.view_organizationaudit; ordinary add/change/delete are disabled. Direct SQL/low-level ORM can bypass application append-only rules. Alternate writers must use services; application auditing is not DBA-proof tamper protection.

Offline copies hold only selected active identity labels in tab memory. They are never placed in shared service-worker caches or persistent browser storage. Copies are tied to the authenticated user ID, expire in five minutes and clear on reconnect, session expiration, sign-out or account change; a BroadcastChannel clears copies in other tabs. A reload while offline cannot restore a copy or authenticate a new session. Permission revocation cannot be checked offline during the short remaining lifetime; the UI labels copies stale. This deliberately narrows Prompt 15's persistent offline-cache option to avoid cross-user and long-lived authorization leakage.

Global uniqueness of institution/programme codes is retained. A generic duplicate conflict can reveal that a code is occupied, but does not reveal another tenant's record or details. The tenancy foundation is purpose-built for organization scope; it does not implement unrelated future workflows or a general confidential-record system from the legacy full SQL.

## Tests and commands

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.in
npm --prefix frontend ci
powershell -NoProfile -File scripts/verify-module2.ps1
```

Tests include all eight resource lifecycles, MySQL unsigned/check behavior, cross-tenant ID denial, scoped campus/department roles, teacher read-only behavior, record limits, activation, audit rollback, concurrent duplicates, bounded query growth, CSV dry-run/rollback/formulas, and offline snapshot filtering. UI tests use Vitest, React Testing Library and MSW for visible permissions, URL filters, empty/error states, preserved form values and offline-owner/expiry clearing. Statement coverage excludes tests and migrations and has a 75% floor; a high statement result is not complete branch or browser coverage.

Manual acceptance remains required for live login/forms, nested parent selection, keyboard focus, mobile layout, browser PWA installation/update and multi-tab behavior. No browser was connected during implementation. See M2_RELEASE_AUDIT.md for remaining release gates.
