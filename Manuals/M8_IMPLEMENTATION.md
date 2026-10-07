# Teaching allocation and timetable (M8)

The user approved separate draft/published revisions, mandatory room and instructor at publication, and weekly workload hours on 23 September 2026. Institutional workload limits are explicit configuration, never an assumed number. Source faculty/session table names and upstream masters are preserved.

## Runtime and dependencies

Backend: `apps.teaching_timetable`. Frontend: `/#/timetable`. API: `/api/v1/timetable/`. The module defaults off through `SIMS_TEACHING_TIMETABLE_ENABLED=0`; ordinary users also require the institution's `teaching_timetable` flag, active membership, scope grant and Django permission. Superusers bypass institution scope but not the global switch. Existing M7 enablement is never changed as a side effect.

M7 offerings, class sections, batches and active dated rosters must be reconciled before operational use. M7 workflows now have a local implementation; see M7_IMPLEMENTATION_STATUS.md for the eligibility provider and release gates. Attendance, staff leave, room facility inventories and notification delivery are not implemented upstream: do not represent M8 as an integrated production deployment. Availability attestations explicitly record scheduling evidence; they do not import or verify an external leave calendar. Practical sessions require a LAB room; specific equipment/accessibility requirements still need an upstream facilities contract.

## Files and architecture

- `models.py`, migrations 0001 onward: assignments, plans, revisions, sessions, immutable occurrence snapshots, append-only dated exceptions, policies, availability, workload overrides, audit, idempotency, outbox and solver jobs.
- `engine.py`, `intervals.py`: inclusive dates, half-open clocks, actual slot overlap, faculty coverage, room capacity, course/class/batch/student cohort collisions, weekly workload and eligibility.
- `services.py`: shared governance lock, fresh actor permissions, explicit commands, optimistic versions, audit and outbox in the same transaction.
- `solver.py`: deterministic bounded backtracking through supplied alternatives; background management worker; current-input validation on explicit acceptance.
- `api.py`, `serializers.py`, `selectors.py`, `lookups.py`: bounded lists, strict command fields, scoped querysets, personal published schedules, CSV and resource choices.
- `integrations.py`: local transactional consumer receipts and retry semantics. No outbound messages are sent.
- `frontend/src/features/timetable/`: typed client, planning actions, read-only personal schedule, grid/list, filters, print, CSV, generation and exception controls. Scheduling API data is not persisted offline.

## Workflow

1. Configure institutional weekly limit and competency policy using `configure-policy`.
2. Ensure active employees have dated campus/department employment and current course competencies. Allocate faculty in PLANNED state, then activate.
3. Record room and faculty availability with reasons. These are affirmative attestations, not absence-of-conflict guesses.
4. Create a revision for a programme-term offering. Save recurring sessions; only DRAFT revisions can change.
5. Move DRAFT -> REVIEW -> APPROVED -> PUBLISHED. Approval and publication both revalidate current resources, availability, workload and collisions. Publication replaces the operational revision of that plan atomically and retains the old snapshots.
6. Make dated cancellations, moves or substitutions through `exception`, with the current exception sequence. Published source rows remain unchanged.
7. Prepare a new revision to replace recurring schedules; withdraw a published revision when necessary. Superseded/withdrawn revisions can be archived. Historical snapshots and audit remain available to platform administrators.

Assignment changes are allowed while PLANNED; active historical episodes require dated successor assignments. Cross-department assignments require `cross_department_teaching`, a dated employment assignment in the same campus, and a recorded reason. Workload overrides require `override_workload` at institution scope and cover complete Monday–Sunday weeks. Neither authority can override room/faculty/cohort collisions.

## API inventory

GET `assignments/`, `revisions/`, `sessions/`, `jobs/`: scoped paginated planner lists. `page_size` is capped at 100. Supported list filters: applicable `revision_id`, `employee_id`, `course_offering_section_id`.

GET `lookups/{offerings|sections|rooms|employees|time-slots|institutions|policies}/`: bounded scoped selectors.

GET `occurrences/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`: committed resolved operational occurrences, maximum 93 days. Teachers/students additionally require explicit People account links; personal access never exposes student roster identifiers. GET `export/` uses the same dates and authorization, returning CSV with formula protection and `no-store`.

POST `commands/{operation}/` requires `Idempotency-Key` (1–100 characters). Mutations include their current `expected_version`; exception commands use `expected_sequence`. Same actor/key/input retries return the original receipt after current scope is rechecked. Reusing a key with different input returns 409. Unknown fields return 400. Missing scope is 404; absent permission/disabled module is 403. Collisions and stale versions return 409 in the common error envelope.

| Operation | Request fields besides reason | Permission |
|---|---|---|
| configure-policy | institution_id, optional expected_version, values: weekly_limit, require_competency, max_sessions, max_solver_jobs | configure_timetable |
| create-assignment | course_offering_section_id, employee_id, assignment_role, workload_hours, start_date, end_date, optional cross_department_authorized | manage_timetable; extra cross-department authority when requested |
| amend-assignment | pk, expected_version, values: workload_hours, start_date, end_date | manage_timetable |
| transition-assignment | pk, expected_version, target | manage_timetable |
| workload-override | values: employee_id, effective_from, effective_to, weekly_limit | override_workload, institution scope |
| create-revision | offering_id, name | manage_timetable |
| save-session | revision_id, expected_version, optional pk, values: course_offering_section_id, faculty_assignment_id, room_id, time_slot_id, day_of_week, effective_from, effective_to | manage_timetable |
| remove-session | revision_id, expected_version, pk | manage_timetable |
| transition-revision | pk, expected_version, target | manage_timetable / approve_timetable / publish_timetable by transition |
| attest-availability | exactly one of room_id or employee_id; day_of_week, effective_from, effective_to, start_time, end_time | manage_timetable, institution scope |
| exception | occurrence_id, expected_sequence, values: kind, date, start_time, end_time, room_id, faculty_assignment_id | change_occurrence |
| queue-job | revision_id, expected_version, seed, choices (list of requested sessions, each containing alternatives in session-values shape) | manage_timetable |
| cancel-job / accept-job | pk, expected_version | manage_timetable |

POST `bulk-assignments/`: `rows` in assignment-command shape, `dry_run` (default true), and reason. Maximum 50 rows. Dry runs report conflicts and roll back all domain/audit/outbox writes. A committed batch is atomic. Use a new idempotency key when moving from dry-run to apply.

Example publication:

```http
POST /api/v1/timetable/commands/transition-revision/
Idempotency-Key: publish-revision-12-v4
Content-Type: application/json

{"pk":"12","expected_version":4,"target":"PUBLISHED","reason":"Approved departmental timetable"}
```

BIGINT identifiers are returned as strings. Use returned versions rather than guessed values. Exact command request schemas are published in OpenAPI and defined in `serializers.py`. `accept-job` additionally accepts `candidate_index` (0–2, default 0); generation ranks up to three candidates by faculty/class idle minutes and checks weekly contact workload during search.

GET `workload/` with the same date range returns planned allocations by department/term/role and published contact hours by employee/ISO week. GET `revisions/{id}/history/` returns authorized historical snapshots for revision comparison. POST `conflicts/` accepts the session command shape and rolls back its preview. POST `import-allocations/` accepts `csv_text`, `reason`, and `dry_run` (default true); the UI provides preview and explicit apply.

GET `workload/export/` downloads the scoped workload CSV. GET `availability/` takes `date_from`, `date_to`, `kind` (`room` or `faculty`) and `resource_id`, returning recorded availability windows and published busy intervals without exposing other cohorts' identities. Every M8 API response is private/no-store, and the service worker treats APIs as network-only.

## Solver and integrations

Run `backend/.venv/Scripts/python.exe backend/manage.py run_timetable_jobs --limit 5` from a supervised scheduler outside web workers. Per-institution active-job quota defaults to 2; request maximum is 100 alternatives in total, at most 20 per requested session. Search is capped at 20,000 nodes and 10 seconds. Results distinguish feasible, infeasible and budget-limited outcomes. A feasible result is a candidate, not an optimum or an operational timetable. Accepting it rechecks inputs, permissions, collisions and contact workload. Cancelling a RUNNING job is checked during search. A crashed worker leaves a detectable stalled job; cancel it and submit a new job.

Events include assignment changes, policy/availability changes, revision changes, timetable publication/supersession/withdrawal, dated cancellation/move/substitution and solver queue/accept/cancel. Event payloads contain identifiers and correlation IDs, not personal profiles. `published_occurrences(actor, date_from, date_to)` is the attendance/calendar contract. Consumers deduplicate event UUIDs, then reconcile against that contract. Local DB handlers use `integrations.consume`; external delivery adapters must maintain retry state and use event UUIDs as idempotency keys. No notification provider or calendar subscription is silently configured.
