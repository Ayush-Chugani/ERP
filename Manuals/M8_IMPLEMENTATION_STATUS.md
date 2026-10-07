# M8 implementation and acceptance status

The prompt pack was used in dependency order, with the user's three policy decisions recorded in M8_ARCHITECTURE.md. Implementation spans schema/architecture, models, allocation, collision validation, generation, publication/exceptions, API, React, local integration contracts, controls and rollout tooling. This is a local implementation, not production acceptance of the entire prompt pack.

| Pack stage | Implemented evidence | Acceptance boundary |
|---|---|---|
| 1–3 Schema, architecture, migrations | Core preserved tables; revision/occurrence/exception/support records; composite FK; named checks/indexes; MySQL migration tests | Legacy adoption requires mapped import and staging restore proof |
| 4 Allocation | Planned/active/completed/cancelled commands; dated eligibility; weekly limits; authorized overrides; planned amendments; bulk preview/apply | Active episodes use successors rather than destructive edits |
| 5 Collision engine | Actual clock/date overlap; room/faculty/course/class/batch and shared-roster occupancy; capacity; serialized writes | Depends on complete M7 rosters and explicit availability evidence |
| 6 Generation | Seeded bounded backtracking, weekly-workload checks, idle-time scoring, up to three ranked candidates, quotas, background jobs, cancellation, stale-input checks and explicit acceptance | Bounded search reports whether exploration completed; no global optimality claim |
| 7 Publication | Draft/review/approval/publication/supersession/withdrawal/archive; immutable occurrence snapshots; dated exception sequences; historical revision comparison | Historical comparison resolves recorded exceptions; upstream source history is not recreated |
| 8 API | Strict command schemas; scope/permissions; idempotency; optimistic versions; bounded lists/lookups; personal schedules | No unrestricted model CRUD |
| 9 React/PWA | Planner actions; grid/list; faculty/room/class/batch filters; availability; generation; exceptions; CSV import preview; print/export; offline mutation controls | Browser visual/keyboard/mobile acceptance unavailable in this environment; no Playwright end-to-end result claimed |
| 10 Integrations | Published-occurrence contract, atomic outbox, idempotent local consumption, CSV/print | Attendance/leave/facilities/notification providers absent upstream; no external delivery or iCalendar subscription configured |
| 11 Controls | Tenant and record limits; immutable audit; quotas/throttle; rollback tests; command timing logs; stalled-job/conflict check | Production load/chaos tests, external monitoring dashboards and retention policy require deployment environment |
| 12 Handover | Verification script; allocation/session imports; quarantine reports; rollback and recovery runbook | No production deployment, restore or sign-off performed |

## Test traceability

- `tests/test_intervals.py`: inclusive dates, matching weekdays, half-open clocks, batch boundaries, assignment coverage, date upper bounds.
- `tests/test_services.py`: snapshots, draft separation, mandatory publication resources, availability, stale versions, exceptions, audit immutability, outbox rollback, composite FK, bulk rollback and workload overrides.
- `tests/test_api.py`: retry receipts, changed-payload collisions, unknown fields, permissions, record limits, unscoped access, published-only schedules, bounded dates.
- `tests/test_solver.py`: deterministic generation, no automatic session persistence, acceptance, stale revision rejection, cancellation and consumer deduplication/retry.
- `tests/test_concurrency.py`: two simultaneous publication transactions cannot double-book shared room/faculty resources. It is a real MySQL threaded test, not a sequential approximation.
- `frontend/tests/timetable.test.tsx`: read-only controls, accessible list, offline state and denied access.

Automated results and local migration state are recorded in M8_RELEASE_AUDIT.md after final verification. Runtime remains disabled until upstream and manual release gates are satisfied.

## M7 integration update

M7 now includes scoped workflows, APIs/UI and dated rosters; see M7_IMPLEMENTATION_STATUS.md. Operational M8 membership resolves M7 episodes on each session date, including closed episodes before their exclusive end. Publication snapshots and explicit revision-history reads remain unchanged. Both module switches remain off; result/attempt/prerequisite provider and manual acceptance are still required.
