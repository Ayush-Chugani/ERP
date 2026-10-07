# M8 architecture working notes

Target app: `apps.teaching_timetable`; API prefix `/api/v1/timetable/`.

## Boundaries

- Faculty allocation: employee/course-section/date/role and planned workload. Reuse M5 employee and competency masters, never duplicate them.
- Timetable planning: recurring sessions, selected room/time-slot, scope derived from M7 offering → programme → department → campus → institution.
- Publication: immutable operational occurrence snapshots belonging to explicitly published revisions, separate from later draft edits. The user confirmed this revision model.
- Exceptions: approved dated changes to an identified published occurrence, retaining the original and effective change history.
- Solver jobs: immutable input snapshot/digest, bounded configuration, deterministic seed, candidate results and explicit acceptance. Run outside web workers; accept through the same validation and locking services as manual scheduling.

## Lock and transaction design

Acquire the existing shared governance lock first, reload the actor and grants, then lock publication/planning roots and affected resource rows in stable ID order. This coordinates upstream scope/deactivation changes and scheduling writes. Before commit, repeat occurrence collision and workload checks against current operational data.

Write domain changes, bounded immutable audit evidence, idempotency receipts and outbox events together. Post-commit dispatch can wake a worker; a durable outbox must remain the recovery source. No notifications are sent inside a transaction or merely because a solver produced a candidate.

## Proposed integration contracts

`published_occurrences(actor, scope, date_from, date_to)` returns only resolved authorized operational occurrences with stable identity/revision information. Attendance must not query draft session rows directly.

`faculty_eligibility(employee, course_section, dates)` and `room_suitability(room, requirements, dates)` return eligible/ineligible/unavailable with structured reasons. Missing availability, facilities or competency evidence must not automatically mean eligible.

Events: assignment changed, timetable published/superseded/withdrawn, occurrence cancelled/moved/substituted. Payloads contain identifiers, effective dates, revision and correlation ID; avoid unnecessary student or employee personal data. Consumers deduplicate event IDs and reconcile against published occurrences.

## Accepted design decisions (23 September 2026)

1. Separate draft and published timetable revisions, confirmed by the user.
2. Publication requires both a room and an instructor, confirmed by the user.
3. Workload means weekly teaching hours, confirmed by the user. Institution-specific maximum hours must be configured; no numeric institutional limit is assumed.

Publication materializes dated occurrences with clock-time snapshots. Later time-slot edits cannot silently rewrite published schedules. Exceptions are append-only dated overlays. A programme-term offering owns a plan; multiple revisions share that plan. Publishing supersedes its earlier operational revision atomically. Source faculty/session table names remain unchanged. Support tables use the platform_m8 prefix.

The shared organization governance lock is acquired before plan, revision, assignment and resource writes. All commands reload actor permissions after acquiring it. Solver computation is outside transactions; candidate acceptance rechecks current domain inputs under the lock. Immutable audit and outbox rows commit with each command. Resource locking is deliberately coarse until measured contention justifies partitioning.

Employee eligibility reuses dated EmployeeAssignment and EmployeeCompetency. Room ownership follows building/campus. Class ownership follows CourseOfferingSection, never request-supplied institution IDs. Missing upstream availability/facility data requires explicit evidence or blocks the relevant operation; absence is not proof of availability. M7 remains independently disabled until its own release gates pass.
