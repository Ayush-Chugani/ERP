# M28 Co-Curricular Activities handoff

Implemented in prompt order using the existing M15 access evaluator, StaffActivity workflow, M13 private files, audit service, authenticated React client and PWA shell. The source DOCX and consolidated SQL are unchanged. M29 is not included, per the user decision.

## Runtime and entry points

- Backend: `apps.cocurricular`; `/api/v1/cocurricular/activities/`, `lookups/`, `category-admin/`.
- Frontend: `#/cocurricular`, lazy-loaded from main navigation.
- Flag: `SIMS_COCURRICULAR_ENABLED=0` by default; both IAM runtime/security flags are also required. No user/role grants are made by migrations or configuration seeding.
- `seed_cocurricular` installs compatible shared workflow defaults, the CO_CURRICULAR activity type, seven ACTIVITY permissions and MASTER.UPDATE. It fails on incompatible existing configuration. Shared category rows are institution-defined; no invented category catalogue is seeded.
- `SIMS_COCURRICULAR_RATE=120/min`; notification adapter `SIMS_COCURRICULAR_EVENT_HANDLER` is empty by default.

## Contract and behavior

The twelve source columns remain native MySQL-compatible, including the unsigned StaffActivity one-to-one primary key, nullable geographic/organization/event fields and TEXT contribution. CoCurricularCategory belongs to staff_profile, not a duplicate M28 catalogue. A retained normalized status history is the only additional table.

Employee, institution, campus and department derive from an assignment valid on the immutable context date. Event date is optional; a supplied date must equal context date. Required category and event name, active references, organizer's active organization and country/state consistency are checked before parent and child commit. TEXT has a 65,535-byte UTF-8 ceiling. Repeated event names are legitimate; search/name/date/employee filters support duplicate review and actor-bound idempotency prevents retry duplicates.

Draft/returned metadata and evidence are editable. Shared submit/review/return/verify/approve/reject/withdraw transitions retain independent reviewers and mandatory reasons. Only draft/returned/withdrawn/rejected activities can be archived. Archive retains the record and history. Ownership, type and approval status cannot be mass assigned. Version tokens include audited revisions, preventing stale edits and change/revert races.

## Access and evidence

ACTIVITY actions: READ, CREATE, UPDATE, DELETE (soft archive), VERIFY, APPROVE, EXPORT. M15 global/institution/campus/department/SELF scopes and explicit DENY apply on every request. Categories require separate global MASTER.UPDATE for create/update/deactivation; no category delete endpoint. Other masters remain with their existing owners.

Evidence uses existing ActivityAttachment/FileObject storage and retained replacement links. Categories: CERTIFICATE, AWARD, INVITATION_NOMINATION, BROCHURE, ORGANIZER_PROOF, APPROVED_PHOTO. The shared upload policy currently accepts PDF, PNG and JPEG with content/size/scanner checks. All evidence is RESTRICTED and also requires M13 institutional/file permissions, including historical downloads. No public storage URLs are returned. Submitted records require return before changing evidence.

Notifications emit only after committed submission, return, approval or rejection, with history-based event ID, activity ID, status and actor ID. The configured adapter must deduplicate event_id, resolve authorized recipients and enqueue through the shared communication infrastructure. Delivery exceptions do not undo business data and logs exclude payload secrets. History supports reconciliation if an adapter fails or the process dies after commit. No adapter, recipients or outbound delivery were configured or invoked during implementation.

## Reports and performance

Lists and reports share scope and all category/event-date/organization/geography/context/status filters. Summary and CSV use the READ/EXPORT intersection. CSV is formula-safe, capped at 10,000 records, and iterates ORM rows in chunks of 500; narrower filters are required above the cap. Summary groups are capped at 100, with explicit truncation metadata. Sensitive responses are private/no-store; APIs are NetworkOnly in the existing service worker.

Six local ORM EXPLAIN plans and the native schema inventory are recorded separately. Canonical FK indexes remain; no speculative indexes were added. Date sorting/search should be profiled using representative production distributions before adding a targeted index migration. Constant-list-query regression is tested; local empty/development plans are not a production latency benchmark.

## Deployment procedure

1. Back up the target database and private file store; rehearse restoration and migrations on an isolated copy. Compare all source/category columns and FKs with M28_SCHEMA_INVENTORY.json. Existing manually-created tables intentionally cause migration refusal: review exact schema alignment before an explicit adoption process; never drop them to bypass the check.
2. Run `manage.py migrate`, then `manage.py seed_cocurricular`. The category migration depends on staff_profile 0004; M28 depends on existing shared parents/masters. Run system checks, migration drift checks and OpenAPI validation.
3. Through authorized access administration, grant the minimum ACTIVITY scopes and optional global MASTER.UPDATE. Configure/maintain categories. Configure M13 institution access, scanner and private storage. Configure a deduplicating queued notification adapter if notifications are required.
4. Build frontend with `npm run build`, deploy matching static assets and API code, and restart the existing deployment services using the normal operations runbook. The generated service-worker asset manifest changes automatically; existing API NetworkOnly policy must remain.
5. Enable M28 and IAM flags only after staged acceptance. Smoke-test scoped list/create/draft edit/submit/independent review/return/approve, category-state choices, restricted upload/download/replacement, report/export and offline write protection using separate authorized/unauthorized accounts.
6. Monitor HTTP 403/409 rates, scanner/upload failures, audit writes, notification adapter failure event IDs and slow list/export queries. Reconcile retained status events against the notification queue when delivery fails.

Rollback: disable SIMS_COCURRICULAR_ENABLED first, restore compatible application/static assets and restart. Populated migration reversal is deliberately refused to preserve staff records/history. Empty reversal and reinstallation are tested only on an isolated test database. Category rollback separately refuses populated data. Restore a verified backup only through the institution's approved recovery procedure. Soft archive and evidence replacement do not physically purge data; retention/purge remains the institution's existing policy.

## Accessibility and verification scope

The UI uses labelled MUI controls/dialogs, required markers, inline errors and alert/status regions, responsive table/cards, keyboard-operable controls, focus-managed dialogs, offline restrictions and an unsaved-change guard. Automated UI tests exercise safe text rendering, permission-driven creation, offline behavior, stable create/workflow retry keys and a complete mocked-API form journey with dependent country/state selection. These are component/API integration tests, not physical-device or live-server end-to-end tests. MUI responsive breakpoints are implemented, but physical-device installation, 200% zoom, screen-reader review and production notification delivery require staging acceptance; they are not claimed as automated browser evidence.

Detailed test counts and final check results are recorded in M28_VERIFICATION.json. Field-to-code and all twelve prompt mappings are in M28_TRACEABILITY.json.


Final local results (2026-09-28): clean-database backend regression 605 tests plus 76 subtests passed; final M28 run 20 tests plus 6 subtests passed. Full UI regression 88 tests passed, followed by all 6 final M28 UI tests including the expanded form journey. Transport/PWA tests: 12 passed. TypeScript/Vite/PWA build, Django system checks, migration drift/pending checks, Ruff and OpenAPI validation passed. The existing M13 MySQL storage-key warning remains. No runtime flags, user grants or outbound notification adapter were enabled.
