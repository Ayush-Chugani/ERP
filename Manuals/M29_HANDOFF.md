# M29 Extra-Curricular Activities handoff

Implemented in prompt order using the existing M15 access evaluator, StaffActivity workflow, M13 private files, audit service, authenticated React client and PWA shell. The source DOCX and consolidated SQL are unchanged.

## Runtime and entry points

- Backend: `apps.extracurricular`; `/api/v1/extracurricular/activities/`, `lookups/`, `category-admin/`.
- Frontend: `#/extracurricular`, lazy-loaded from main navigation.
- Flag: `SIMS_EXTRACURRICULAR_ENABLED=0` by default; both IAM runtime/security flags are also required. No user/role grants are made by migrations or configuration seeding.
- `seed_extracurricular` installs compatible shared workflow defaults, the EXTRA_CURRICULAR activity type, seven ACTIVITY permissions and MASTER.UPDATE. It fails on incompatible existing configuration. Shared category rows are institution-defined; no invented category catalogue is seeded.
- `SIMS_EXTRACURRICULAR_RATE=120/min`; notification adapter `SIMS_EXTRACURRICULAR_EVENT_HANDLER` is empty by default.

## Contract and behavior

The twelve source columns remain native MySQL-compatible, including the unsigned StaffActivity one-to-one primary key, nullable geographic/organization/event fields and TEXT activity details. ExtraCurricularCategory belongs to staff_profile, not a duplicate M29 catalogue. A retained normalized status history is the only additional table.

Employee, institution, campus and department derive from an assignment valid on the immutable context date. Event date is optional; a supplied date must equal context date. Required category and event name, active references, organizer's active organization and country/state consistency are checked before parent and child commit. TEXT has a 65,535-byte UTF-8 ceiling. Repeated event names are legitimate; search/name/date/employee filters support duplicate review and actor-bound idempotency prevents retry duplicates.

Draft/returned metadata and evidence are editable. Shared submit/review/return/verify/approve/reject/withdraw transitions retain independent reviewers and mandatory reasons. Only draft/returned/withdrawn/rejected activities can be archived. Archive retains the record and history. Ownership, type and approval status cannot be mass assigned. Version tokens include audited revisions, preventing stale edits and change/revert races.

## Access and evidence

ACTIVITY actions: READ, CREATE, UPDATE, DELETE (soft archive), VERIFY, APPROVE, EXPORT. M15 global/institution/campus/department/SELF scopes and explicit DENY apply on every request. Categories require separate global MASTER.UPDATE for create/update/deactivation; no category delete endpoint. Other masters remain with their existing owners.

Evidence uses existing ActivityAttachment/FileObject storage and retained replacement links. Categories: CERTIFICATE, AWARD, EVENT_LETTER, APPROVED_EVIDENCE, ORGANIZER_PROOF, APPROVED_PHOTO. The shared upload policy currently accepts PDF, PNG and JPEG with content/size/scanner checks. All evidence is RESTRICTED and also requires M13 institutional/file permissions, including historical downloads. No public storage URLs are returned. Submitted records require return before changing evidence.

Notifications emit only after committed submission, return, approval or rejection, with history-based event ID, activity ID, status and actor ID. The configured adapter must deduplicate event_id, resolve authorized recipients and enqueue through the shared communication infrastructure. Delivery exceptions do not undo business data and logs exclude payload secrets. History supports reconciliation if an adapter fails or the process dies after commit. No adapter, recipients or outbound delivery were configured or invoked during implementation.

## Reports and performance

Lists and reports share scope and all category/event-date/organization/geography/context/status filters. Summary and CSV use the READ/EXPORT intersection. CSV is formula-safe, capped at 10,000 records, and iterates ORM rows in chunks of 500; narrower filters are required above the cap. Summary groups are capped at 100, with explicit truncation metadata. Sensitive responses are private/no-store; APIs are NetworkOnly in the existing service worker.

Eight local ORM EXPLAIN plans and the native schema inventory are recorded separately. Canonical FK indexes remain; no speculative indexes were added. Date sorting/search should be profiled using representative production distributions before adding a targeted index migration. Constant-list-query regression is tested; local empty/development plans are not a production latency benchmark.

## Deployment procedure

1. Back up the target database and private file store; rehearse restoration and migrations on an isolated copy. Compare all source/category columns and FKs with M29_SCHEMA_INVENTORY.json. Existing manually-created tables intentionally cause migration refusal: review exact schema alignment before an explicit adoption process; never drop them to bypass the check.
2. Run `manage.py migrate`, then `manage.py seed_extracurricular`. The category migration depends on staff_profile 0005; M29 depends on existing shared parents/masters. Run system checks, migration drift checks and OpenAPI validation.
3. Through authorized access administration, grant the minimum ACTIVITY scopes and optional global MASTER.UPDATE. Configure/maintain categories. Configure M13 institution access, scanner and private storage. Configure a deduplicating queued notification adapter if notifications are required.
4. Build frontend with `npm run build`, deploy matching static assets and API code, and restart the existing deployment services using the normal operations runbook. The generated service-worker asset manifest changes automatically; existing API NetworkOnly policy must remain.
5. Enable M29 and IAM flags only after staged acceptance. Smoke-test scoped list/create/draft edit/submit/independent review/return/approve, category-state choices, restricted upload/download/replacement, report/export and offline write protection using separate authorized/unauthorized accounts.
6. Monitor HTTP 403/409 rates, scanner/upload failures, audit writes, notification adapter failure event IDs and slow list/export queries. Reconcile retained status events against the notification queue when delivery fails.

Rollback: disable SIMS_EXTRACURRICULAR_ENABLED first, restore compatible application/static assets and restart. Populated migration reversal is deliberately refused to preserve staff records/history. Empty reversal and reinstallation are tested only on an isolated test database. Category rollback separately refuses populated data. Restore a verified backup only through the institution's approved recovery procedure. Soft archive and evidence replacement do not physically purge data; retention/purge remains the institution's existing policy.

## Accessibility and verification scope

The UI uses labelled MUI controls/dialogs, required markers, inline errors and alert/status regions, responsive table/cards, keyboard-operable controls, focus-managed dialogs, offline restrictions and an unsaved-change guard. Automated UI tests exercise safe text rendering, permission-driven creation, offline behavior, stable create/workflow retry keys and a complete mocked-API form journey with dependent country/state selection. These are component/API integration tests, not physical-device or live-server end-to-end tests. MUI responsive breakpoints are implemented, but physical-device installation, 200% zoom, screen-reader review and production notification delivery require staging acceptance; they are not claimed as automated browser evidence.

Detailed test counts and final check results are recorded in M29_VERIFICATION.json. Field-to-code and all sixteen prompt mappings and the consolidated master prompt are in M29_TRACEABILITY.json.


## M29-specific API and profile integration

Source columns are `staff_activity_id`, `extracurricular_category_id`, `event_name`, `organizer_id`, `institution_organization_id`, `event_date`, `venue_name`, `city`, `state_id`, `country_id`, `award_recognition`, `activity_details`. Category master is `staff_profile.ExtraCurricularCategory`, installed by 0006. Organizer identifies the organizer; institution_organization identifies a host or associated organization. They may differ. Event-name internal whitespace is collapsed; multiline activity details retain line breaks.

Activity endpoints support GET/POST/PATCH/PUT/DELETE. PATCH preserves omitted fields; PUT requires category/event name and resets omitted nullable fields. All updates require the current version; create and workflow commands require Idempotency-Key. DELETE soft-archives eligible states. Unknown fields and client ownership/type/status overrides are rejected.

List filters: `search`, `employee`, `institution`, `campus`, `department`, `academic_year`, `category`, `organizer`, `institution_organization`, `country`, `state`, `city`, `award`, `award_present=true|false`, `status`, `date_from`, `date_to`, `mine=1`. Search covers event, venue, city, award, details and organizer/host names. Ordering accepts staff_activity_id, event_name, event_date and extracurricular_category__category_name with optional minus prefix, always with PK tie-break. Lists use at most 100 rows/page. Summary includes counts with/without awards. Existing CSV export uses exactly the same filters and authorized READ/EXPORT intersection.

The Employees record-details dialog links to `#/extracurricular?employee=<id>`. M29 initializes the employee filter from that route and does not replace it with the default owner-only filter. The activity detail includes the retained timeline, parent verification/approval remarks and private evidence. This is navigation into the server-scoped module, never an authorization grant. An arbitrary employee ID in the URL cannot expose out-of-scope data.

Example create body (IDs illustrative; choose live authorized lookup values):

```json
{
  "context": {"employee_assignment_id": "12", "context_date": "2026-09-28", "academic_year_id": null},
  "activity": {
    "extracurricular_category_id": "3", "event_name": "Community arts festival",
    "event_date": "2026-09-28", "organizer_id": null,
    "institution_organization_id": null, "venue_name": "Main hall", "city": null,
    "state_id": null, "country_id": null, "award_recognition": "Participation recognition",
    "activity_details": "Coordinated the faculty programme."
  }
}
```

POST it to `/api/v1/extracurricular/activities/` with a new Idempotency-Key. Read response uses `staff_activity` as the string identifier, related string IDs and display names, parent status, version, permitted actions, evidence and history. Supply version on PATCH/PUT, workflow POST and archive DELETE. Representative invalid input: a state from another country returns a `state_id` error; event date differing from context date returns `event_date`; inactive category returns `extracurricular_category_id`; stale version returns 409. Correct values and refresh a stale record before retrying an edit.

## Verification commands and operational limits

- `backend/.venv/Scripts/python.exe -m pytest backend/apps/extracurricular/tests -q --reuse-db --tb=short`
- `backend/.venv/Scripts/python.exe backend/manage.py check`
- `backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run`
- `backend/.venv/Scripts/python.exe backend/manage.py spectacular --file .tmp/m29-openapi.yaml --validate`
- `backend/.venv/Scripts/python.exe backend/manage.py shell -c "exec(open('scripts/m29_verification.py').read())"`
- From frontend: `npm run test:ui -- --maxWorkers=1`, `npm test`, `npm run build`.

Performance budgets are bounded row/page/group counts and constant list query count as data grows. Eight local EXPLAIN plans justify retaining FK indexes without redundant speculative indexes. Leading-wildcard details/venue text search and event-date sorts require production slow-query monitoring and representative distribution testing before index changes. No production response-time/load claim is made.

Final acceptance evidence is recorded in M29_VERIFICATION.json. Physical-device installation, keyboard/zoom/screen-reader acceptance on target browsers and a live-server browser journey remain staging checks. Automated component tests use mocked API responses. Runtime and notification integration remain disabled until operations configure scoped grants, masters, scanner/storage and (if desired) the deduplicating queued adapter. No messages are sent by implementation or configuration seeding.


## Final local verification (2026-09-28)

Clean-database backend regression: **629 tests and 86 subtests passed**. Focused M29 backend: **23 tests and 10 subtests passed**. Final M29/staff UI: **11 tests passed**, including all seven M29 tests and the employee-profile link. Transport/PWA checks: **12 passed**. TypeScript/Vite build, native schema review, eight EXPLAIN plans, Django system/migration checks, Ruff and OpenAPI validation passed.

Two full UI runs each passed 96 of 97 tests but hit a timeout following a long execution delay: first an unchanged internship form test, then the M29 complete-form journey. The internship file passed unchanged in isolation, and the final M29/staff run passed all 11 tests. Other 20 UI files passed the second full run. This is **not a claim of an uninterrupted clean full UI run**. Repeat that acceptance check on a stable uninterrupted workstation; test timeouts were not relaxed or hidden. Backend elapsed time also includes execution delays and is not a load benchmark.

The final country-selector change avoids refetching unrelated masters when country changes; only dependent state choices refresh. Runtime/IAM flags and the notification adapter remain disabled. No user or role grants were added and no outbound messages were sent.
