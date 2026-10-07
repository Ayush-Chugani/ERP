# M3 Academic Calendar: implementation and usage

## Approved contract

The user approved shared academic years, terms and semesters with platform-superuser-only maintenance; one active shared year; terms and nonnull registration endpoints within the parent year; no overlapping active non-break slots in a campus; and reasoned reopening of closed periods. This resolves the proposals in [Prompts 0–1](M3_CONTRACT_AND_GAPS.md). No institution columns or scoped uniqueness were added to shared masters. Time slots retain campus ownership. Calendar activation was added to the existing InstitutionModule table, default false.

## Sequential prompt ledger

| Prompt | Deliverable |
| --- | --- |
| 0 Contract | M3_CONTRACT_AND_GAPS.md: boundary, custom auth, dependencies and decisions |
| 1 Domain review | Field-by-field and invariant matrices, risks and ADR proposals; no application changes in that stage |
| 2 App scaffold | apps/academic_calendar/apps.py and public.py; import/system-check test passed |
| 3 Models | Four baseline tables plus separate platform audit table; initial migration applied on MySQL; M3_initial_migration.sql inspected |
| 4 Lifecycle | services.py: typed WriteCommand, transactions, transitions, constraints and audit |
| 5 Slots | services.py overlap/activation rules, scheduling.py explicit timezone and DST handling |
| 6 Authorization | policies.py and CalendarPermission; existing membership/grants plus Django permissions |
| 7 API | api.py, urls.py, generated backend/openapi.yaml and validated request bodies |
| 8 Integration | selectors.py and immutable public DTOs; M3_QUERY_PLANS.md |
| 9 Admin/audit | admin.py service-backed saves and atomic bulk transitions, platform-only audit viewer |
| 10 React/PWA | CalendarApp.tsx, api.ts, navigation, parent search, forms, details and lifecycle confirmations |
| 11 Verification | tests/ and frontend/tests/calendar.test.tsx; scripts/verify-module3.ps1; MySQL CI workflow |
| 12 Rollout | M3_ROLLOUT.md; legacy reconciliation design and recovery plan |
| 13 Review | M3_RELEASE_AUDIT.md: evidence and release decision, distinct from implementation |

## Start locally

With the configured MySQL running, from the project root:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000
```

In a second terminal:

```powershell
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173/#/calendar and sign in. A platform superuser can create a year, activate it, create a term within its dates, open registration, activate and close the term. A reason is required for close and reopen. Close every term before closing its year. Semesters are reusable shared references. No baseline calendar dates or semester count were invented or seeded.

The frontend sends JSON with `Content-Type: application/json` for create, update and lifecycle operations. The user-reported unsupported text/plain request was corrected, with a regression test covering all three request types. Rebuild the frontend if serving a production preview; development uses Vite reload.

## Access provisioning and matrix

At `/admin/`, a platform superuser enables **academic_calendar** on the institution's existing InstitutionModule record. Create active Membership and ScopeGrant records using existing tenancy administration. Then assign the required Django permissions to the ordinary user or group. The organization_structure flag alone does not enable calendar access. `SIMS_ACADEMIC_CALENDAR_ENABLED=0` disables calendar policy access globally, including the superuser, while retaining installed models and migrations.

| Principal | Shared master reads | Shared master writes/lifecycle | Time-slot reads | Time-slot writes/lifecycle | Audit |
| --- | --- | --- | --- | --- | --- |
| Active platform superuser | All | All through services | All | All through services | Read only |
| Institution admin | With view permission and enabled active membership/grant | Denied | Own institution | Own institution plus operation permission | Denied |
| Campus admin | Same shared read rule | Denied | Assigned campus | Assigned campus plus operation permission | Denied |
| Department admin | Same shared read rule | Denied | Assigned campus | Denied | Denied |
| Teacher/student | Same shared read rule | Denied | Assigned institution/campus with active campus | Denied | Denied |
| Inactive or disabled membership/module | None | None | None | None | None |

All ordinary users require active institution and university ancestors. Manager reads retain inactive campus selections; new slots and reactivation require active campus ancestors. Grant `record_limits` can restrict `campuses` and `time-slots`; multiple grants union their permitted scope. IDs or institutions submitted in a payload never grant authority. Scope is applied before lists/counts/detail/parent choices and again under the write transaction. Django staff status allows access to the admin site but does not confer domain write authority.

Django permission prefixes are `academic_calendar`. Resources use model codenames `academicyear`, `academicterm`, `semester`, `timeslot`. Standard permissions are `view_<model>`, `add_<model>`, `change_<model>`; delete is always denied even if its Django permission exists. Additional codenames: `activate_academicyear`, `close_academicyear`, `reopen_academicyear`; `activate_academicterm`, `close_academicterm`, `reopen_academicterm`, `open_registration_academicterm`; `activate_timeslot`, `deactivate_timeslot`. Shared write/lifecycle permissions alone never override the platform-only rule. There is no parallel workflow permission store.

## Endpoints and permissions

Base `/api/v1/calendar/`. Resource paths: `academic-years`, `academic-terms`, `semesters`, `time-slots`.

| Endpoint | Method | Authority |
| --- | --- | --- |
| /metadata/ | GET | Authenticated active user and globally enabled module; returns resource structure and permitted create controls |
| /campus-choices/ | GET | Permitted campus manager with add/change timeslot permission; scoped active parents only |
| /{resource}/ | GET | Django view permission + scope above; superuser bypass explicit |
| /{resource}/{id}/ | GET | Same read scope; inaccessible object is 404 |
| /{resource}/ | POST | Add permission + scope; shared masters require superuser |
| /{resource}/{id}/ | PUT/PATCH | Change permission + scope; closed periods cannot be edited |
| /academic-years/{id}/activate,close,reopen/ | POST | Matching lifecycle permission and platform superuser |
| /academic-terms/{id}/activate,close,reopen,open-registration/ | POST | Matching lifecycle permission and platform superuser |
| /time-slots/{id}/activate,deactivate/ | POST | Matching lifecycle permission and campus management scope |
| Any resource DELETE | None | No public hard-delete endpoint |
| Audit records | Admin GET only | Active platform superuser; no ordinary API |

The notation containing comma-separated action names represents separate URLs, not a literal combined route. Semesters have no lifecycle routes. Calendar writes and admin actions use the same services and policies. Ordinary payloads cannot set status/is_active, actor, audit values, timestamps or ownership after creation. Unknown writable fields are rejected.

Lists use bounded pagination (default 25, maximum 100), `search` up to 100 characters and allowlisted `ordering` over resource fields. Filters: years `status`; terms `academic_year_id,status,term_type`; semesters `semester_number`; slots `campus_id,is_active,is_break`. Boolean filters require `true` or `false`. Positive integer filters reject decimals, negative values and repeated parameters. Sorting adds a primary-key tie-breaker. Unknown filters/order fields are errors. All API response bodies use existing project conventions; calendar data responses are no-store.

### Request/response examples

```http
POST /api/v1/calendar/academic-years/
Content-Type: application/json

{"year_code":"2026-27","start_date":"2026-09-01","end_date":"2027-03-31"}
```

Example response (ID is illustrative):

```json
{"academic_year_id":12,"year_code":"2026-27","start_date":"2026-09-01","end_date":"2027-03-31","status":"PLANNED","actions":["change","activate","close"],"parent_label":null,"timezone":null}
```

```http
POST /api/v1/calendar/academic-years/12/activate/
Content-Type: application/json

{}
```

```http
POST /api/v1/calendar/academic-terms/
Content-Type: application/json

{"academic_year_id":12,"term_code":"ODD","term_name":"Odd term","term_type":"ODD","start_date":"2026-09-01","end_date":"2026-12-31","registration_start_date":null,"registration_end_date":null}
```

```http
GET /api/v1/calendar/time-slots/?campus_id=4&is_active=true&ordering=start_time
POST /api/v1/calendar/academic-terms/9/close/
Content-Type: application/json

{"reason":"Teaching and registration checks completed"}
```

Errors use `{ "error": { "code": "...", "message": "...", "details": {} } }`. Validation is 400; a forbidden operation is 403 or an inaccessible record 404; illegal transitions and duplicates/overlaps are 409 (`invalid_transition` or `calendar_conflict`). Expected database failures are translated outside the failed atomic block. No SQL appears in expected errors. Overlap details include the conflicting slot only if it is in the actor's read scope. Successful write response `X-Request-ID` matches the recorded audit correlation.

## Lifecycle and concurrency

| Resource | Transition |
| --- | --- |
| Year | PLANNED -> ACTIVE; PLANNED/ACTIVE -> CLOSED; CLOSED -> PLANNED via reopen |
| Term | PLANNED -> REGISTRATION_OPEN; PLANNED/REGISTRATION_OPEN -> ACTIVE; any nonclosed state -> CLOSED; CLOSED -> PLANNED via reopen |
| Slot | Active -> inactive; inactive -> active with overlap and parent checks |

Term activation/registration requires an active year. Closed years prevent term modifications or reopening. Repeated target-state requests are idempotent and do not create another audit entry (close/reopen still require a reason). Create is not a blind idempotent upsert: stable code uniqueness yields a conflict on duplicate retry. After an uncertain network result, read before retrying. Writes serialize on the existing organization ContentType row, then lock records/parents. This deliberately conservative lock also coordinates campus lifecycle writes but limits cross-campus write throughput; measure contention before replacing it with finer-grained locks.

Break slots are exempt from overlap checks; inactive teaching slots do not conflict until reactivated. Adjacent intervals are allowed (`start < other.end AND end > other.start`). Overnight intervals are rejected. Order is by start/end/ID; there is no invented position column. Future reverse-FK dependents conservatively prevent edits/transitions until downstream lifecycle contracts are reviewed. Raw SQL/ORM bypasses service-only cross-row rules: use public services for every writer.

## Timezones and public integration

Configure actual campus IDs in the backend environment, for example:

```dotenv
SIMS_CALENDAR_CAMPUS_TIMEZONES={"4":"Asia/Kolkata"}
```

Restart Django after changing the setting. This does not alter campus schema or silently infer a timezone. Slot TIME values are campus wall-clock values; date-only calendar boundaries are not UTC timestamps. `scheduling.slot_datetimes` validates the configured IANA zone, rejects ambiguous/nonexistent DST times and returns aware start/end datetimes. Missing zone blocks conversion; the UI labels it unconfigured.

Downstream modules import `apps.academic_calendar.public`: `current_year`, `active_terms`, `registration_terms`, `term_by_code`, `semesters`, `campus_slots`. Every call takes actor and institution_id and validates that context. Returns are immutable DTOs/tuples rather than unrestricted model managers. Multiple matching registration terms are returned explicitly, avoiding a guessed singular term. Nullable registration endpoints mean an open bound within the year. No downstream module copies calendar state. Explicit context does not turn global year/term ownership into per-institution ownership.

## Audit, PWA and verification

CalendarAudit is a separate platform support table with actor, trusted institution for slots (null for global masters), action, resource, record ID, timestamp, correlation ID and bounded allowlisted before/after/reason. Audit insertion failure rolls back the data change. Admin bulk transitions are all-or-nothing; ordinary bulk update/delete is disabled. Audit model/queryset mutation is blocked, but application append-only is not DBA-proof tamper protection.

Calendar PWA policy caches static assets only. API bodies are not stored in service-worker caches; no calendar offline snapshot or mutation queue is provided. While mounted, stale in-memory records are labelled offline and write controls are disabled. Reconnect and refresh to revalidate. Offline reload does not restore calendar data. Keyboard focus/mobile/screen-reader/install/update acceptance still requires browser testing.

Run `scripts/verify-module3.ps1` for the full regression suite, or pytest on `backend/apps/academic_calendar/tests` for focused checks. `.github/workflows/calendar.yml` supplies MySQL 8.4 CI configuration; its existence is not evidence of a hosted CI run. See M3_RELEASE_AUDIT.md for final measured results and release limits.
