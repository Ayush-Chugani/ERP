# M9 Attendance and Lesson Plan ? implementation and handover

## Scope and accepted decisions

This implements the M9 prompt pack in dependency order. M8 publication revisions remain separate from M9 class-session snapshots. The user accepted versioned section attendance policies frozen at session creation, a different authorized correction reviewer, and ordered immutable lesson-plan revisions with dated partial coverage. Weekly M8 faculty workload semantics remain unchanged.

Runtime remains disabled by default. No real attendance, legacy registers or institutional policy values have been imported. The reference SQL manual was not modified.

## Stage and artifact inventory

| Stage | Artifacts and behavior |
|---|---|
| 1 Audit | M9_SCHEMA_REVIEW.md, M9_UPSTREAM_SCHEMA.md, scripts/m9_preflight.py |
| 2 Architecture | apps.attendance_lesson_plan; existing M7 roster, M8 occurrence, account and scope models reused |
| 3 Schema | M9 migrations 0001?0003; M8 0006 ownership candidates; tenancy 0008 module flag; M9_reviewed_migration.sql |
| 4 Session/lesson lifecycle | services.py: generation, exceptional sessions, replacement lineage, conduct/cancel, immutable topic revisions and partial coverage |
| 5 Registers | Date-valid roster snapshot, explicit unmarked values, atomic marking/finalization, version checks, approved reopening and roster reconciliation |
| 6 Corrections | One pending request per attendance row, requester/resolver evidence, separate reviewer, stale-status/version protection |
| 7 API | commands.py, api.py, urls.py, regenerated backend/openapi.yaml |
| 8 Reports/events | selectors.py, calculations.py, transactional outbox and consumer receipt in integrations.py; CSV and history |
| 9 UI | frontend/src/features/attendance; lazy /#/attendance route, staff workspace and student self-service |
| 10 Hardening | policies.py; scoped SQL queries, private no-store responses, strict serializers, bounded reports/submissions, throttle, audit/outbox atomicity |
| 11 Verification/import | tests/, frontend/tests/attendance.test.tsx, attendance_batch and attendance_generate management commands |
| 12 Rollout | scripts/verify-module9.ps1, attendance_health, seed_attendance_roles; this handover |

## Schema and workflow

The source composite attendance identity remains a unique constraint, with a surrogate attendance PK for Django and correction references. Composite section ownership FKs bind sessions to faculty assignments, timetable sessions, published occurrences and mapping session types; attendance binds to the exact session and roster section. FK types match actual parent keys, including the signed custom User key. The mapping session_type collation is explicitly matched. Pending correction uniqueness uses a generated nullable key. All actor relations protect evidence from deletion.

Lifecycle: PLANNED ? CONDUCTED ? register OPEN ? FINALIZED. Finalization refuses eligible unmarked students. Only authorized reviewers may reopen; ordinary marking cannot silently edit finalized evidence. A changed M7 roster blocks finalization until explicit reconciliation: removed members retain their rows and marks with an exclusion reason, contribute zero, and remain auditable. A changed M8 occurrence blocks operations until its discrepancy is resolved; historical evidence is not rewritten. Replacement requires an unopened planned source. Existing occurrence identity prevents duplicate generation.

All commands acquire the existing shared governance lock before reloading the actor and verifying permissions. This conservatively serializes writers across M7/M8/M9; measure contention before increasing throughput. Session aggregate versions coordinate marking/lifecycle changes; attendance versions coordinate corrections. API commands require actor-bound idempotency keys with canonical input digests, and replay rechecks current authority. Audit and outbox writes commit or roll back with the command.

## API inventory

Base /api/v1/attendance/. POST commands/{operation}/: configure-policy, create-session, transition-session, mark, reconcile-register, request-correction, decide-correction, revise-lessons, record-coverage.

GET sessions/, policies/, lessons/, coverage/, corrections/, statuses/, audit/; register/{id}/; lookups/{sections|occurrences|faculty|rooms}/; mine/; mine/corrections/; report/; export/; reconcile/; lesson-progress/{section}/; history/{attendance}/. Lists paginate; report/export require explicit date_from and date_to, at most 366 days and 20,000 attendance rows. Registers cap at 500 entries; reconciliation caps at 1,000 sessions; throttle is 120 requests per user per minute. UI selection lists cap at 100 and explicitly report overflow rather than present incomplete totals.

## Permission and privacy matrix

| Actor | Required permission and scope |
|---|---|
| Faculty | view/manage/mark_attendance plus current module-enabled membership, TEACHER scope and exact dated employee assignment |
| Coordinator | view/manage/exceptional/export_attendance and administrative institution/campus/department scope |
| Reviewer | review/reopen_attendance and administrative scope; cannot decide own request even as superuser |
| Policy administrator | configure_attendance and administrative scope |
| Student | verified AccountLink and enabled institution membership; own finalized attendance and own correction requests only |
| Superuser | global module flag still applies; institutional scope bypass follows existing platform convention |

Record limits for section/session/faculty/room are enforced server-side. Partial student allowlists never authorize a whole class register. Export authority is separate from read authority. CSV cells guard spreadsheet formula prefixes. Audit reads require reviewer authority and object scope. Django admin is inspection-only. No attendance payload is deliberately stored in localStorage or queued offline; API responses are private/no-store. Database administrators can bypass application immutability: deploy least-privilege database roles and independently retained backups; this is not a cryptographic ledger.

## Policy and calculation examples

No institutional threshold, edit window, correction window or status credit is automatically adopted. Seeded codes PRESENT, ABSENT, LATE, EXCUSED and ON_DUTY are identities, not policy decisions. Configure numerator/denominator weights explicitly, constrained to 0 ? credit ? denominator ? 1. SESSION multiplies by one; DURATION multiplies by actual scheduled contact minutes. For example only, two PRESENT contributions 1/1 and one ABSENT 0/1 yield 66.67%; a 0/0 excluded contribution does not change this. Zero total denominator gives undefined percentage and shortage, not zero percent. Compare thresholds before display rounding. Reports group by student, section and frozen policy revision rather than mixing incompatible bases.

## Calendar, events and observability

SIMS_ATTENDANCE_CALENDAR_ADAPTER must point to a callable accepting section and day and returning status=INSTRUCTIONAL plus a nonblank reference. Missing/unavailable calendar evidence blocks session creation. There is no fabricated holiday calendar. The test adapter is test-only and must not be used operationally.

Events use attendance.{action}.v1, with audit ID, section ID, record ID and resource. Outbox is committed atomically. integrations.deliver records consumer/event delivery; external consumers must deduplicate event IDs because a remote side effect cannot be made atomic with this database. No mail/SMS/notification provider is installed or invoked. Event transport and production notification templates require institution integration.

attendance_health --actor ID reports scoped timetable/roster discrepancies, unfinalized registers, pending corrections and events without delivery receipts. Command logs include operation, actor and request correlation key without register payload. Proposed operational alerts: nonzero reconciliation mismatches; conducted registers unfinalized beyond policy window; correction backlog older than the institution response target; undelivered events older than 15 minutes; sustained 403/404/409 rate spikes. These are handover targets, not configured external alerts. Set retention with institutional records owners; do not independently purge referenced audit/policy/history rows.

## Import and operator commands

Run from project root using backend/.venv/Scripts/python.exe backend/manage.py followed by:

- attendance_generate --actor ID --section ID --date-from YYYY-MM-DD --date-to YYYY-MM-DD --reason TEXT: dry-run published occurrences, max 31 days/100 occurrences; --apply commits. Reuse the same reason on retries.
- attendance_batch mapped.json --actor ID: dry-run an explicit list of {operation,data,key}, max 100 rows/1 MiB. --apply commits only when all rows pass. Stable source keys make retry safe. Invalid rows are reported as quarantined and the whole batch rolls back; save stdout in the controlled import evidence store.
- attendance_health --actor ID: read-only scoped health report.
- seed_attendance_roles: prepare permission groups; does not assign users, memberships or scope grants.

Resolve source student identifiers to actual date-valid M7 roster IDs, section/faculty/room IDs and approved policy before creating commands. Never guess an absent mark from a missing row. Import in reviewed stages: policy/session generation, roster opening, marks, finalization, then separately validated historical evidence. Compare source totals and status/date counts to finalized API report totals. Legacy correction history cannot be backdated into live decisions: retain the original source evidence and migrate only requests that legitimately pass current workflow. No supplied source dataset exists; no historical reconciliation has been certified. Dry-run generated IDs roll back; obtain committed session/register IDs before constructing later-stage batches.

## Rollout, rollback and support

1. Run verify-module9.ps1 against isolated MySQL test database. Back up the target database and verify restoration on staging before production changes.
2. Keep SIMS_ATTENDANCE_ENABLED=0 and institution flags false during schema expansion. Review migrate --plan, then apply migrations with Django. Generated SQL is reference only; Python status seeding must also run.
3. Deploy backend and frontend together. Older M8 code can retain its schema while additive candidate keys exist; do not downgrade schema underneath running M9 code.
4. Integrate and test the real academic calendar provider; obtain approved per-section weights/thresholds/windows and timezone configuration; create scoped role assignments. Validate teaching allocation and date-valid M7 roster first.
5. Enable only an approved pilot institution and global M9 flag in staging. Test all four personas, mobile/keyboard usage, concurrent marking, cancellation/replacement, offline recovery, exports, correction separation and retained policy interpretation.
6. Reconcile imports and approve restore/outbox recovery and institution totals before progressive production activation. Institutional owner approves the pilot; platform operator owns deployment; registrar owns roster/policy reconciliation; teaching coordinator owns missed sessions; reviewer owns correction escalation.

Emergency stop: disable the global flag to block M9 endpoints/writes; preserve database evidence. For read-only service, remove write permissions while retaining view access. Ordinary late edits require approved reopening with reason. Roster discrepancies use explicit reconciliation after reopening; timetable discrepancies require coordinator review, never direct SQL edits. Incorrect shortages: verify frozen policy ID, marked vs unmarked, excluded roster entries and report dates. Export failures: check permission, date bounds and row cap. Event backlog: inspect outbox/consumer receipts and retry with event-ID deduplication.

Rollback application code with the feature disabled while retaining additive tables. Reverse migrations only on empty, verified disposable data or after a reviewed backup/restore plan: reversing M9 destroys evidence. MySQL DDL is not transactionally reversible as a batch. This implementation does not authorize production deployment or activation.

## Verification and acceptance status

See final verification results below. Automated coverage includes calculation edge cases, raw composite FK rejection, generation retry, unmarked finalization refusal, atomic mark rollback, stale versions, frozen policies, roster drift/reconciliation, reviewer separation, pending uniqueness, student privacy, scope revocation, audit/outbox rollback, and genuine two-connection MySQL mark/finalize/reopen/correction races. Component checks cover student control visibility, offline submission and permission failures.

Browser end-to-end, accessibility audit, large-dataset load baseline, restored-backup drill, actual calendar/provider integration, notification transport and institutional policy/legacy-source sign-off are not certified in this local workspace. UI currently uses date-labelled session selection rather than a graphical calendar; exceptional-session creation is supported through the API/controlled command tool. These are explicit handover limitations, not production acceptance claims. Next integrations are student shortage notifications and academic eligibility consumers through the outbox, with approved privacy/policy contracts.

### Local verification ? 2026-09-23

- scripts/verify-module9.ps1: passed. Django system/database checks and migration drift check clean; 118 combined M9/M8/M7/M6/core tests passed against isolated MySQL; OpenAPI validation passed without warnings; 32 component tests passed; TypeScript and Vite/PWA production build passed.
- Final focused M9 service suite after import/health and scope refinements: 15 tests passed, including dry-run rollback and committed mapped import.
- Local sims_reference_dev migrations applied: teaching_timetable 0006, attendance_lesson_plan 0001?0003, tenancy 0008.
- Verified M7/M8/M9 global flags false; zero M9-enabled institutions; zero class sessions and policy revisions; five attendance status identities seeded.
- Original reference SQL remains untouched. No production deployment, operational activation or external notification occurred.
