# M7 local release audit — 23 September 2026

## Implemented scope

Completed the remaining local M7 workflow/API/UI work after the accepted foundation: offering/section/batch setup, progression and term allocation, course offerings/mappings, course registration and dated rosters, scoped API, React workspace, audit/outbox, idempotent bulk/CSV operations, permission seed and reconciliation/recovery tooling.

The source consultancy schema selected in the IDE was not changed.

## Measured verification

- scripts/verify-module7.ps1 completed successfully.
- Combined real MySQL core/M6/M7/M8 suite: **87 passed** in the final complete run.
- Subsequent focused M7 workflow suite: **14 passed**, including the added regression that completed courses still count toward the term credit limit. This focused run overlaps the complete suite; do not sum those counts as distinct tests.
- Final M7/M8 operational-membership and exception service check: **12 passed** before the last combined run.
- Frontend: **29 tests passed across 7 files**. Six M7 tests cover student read-only access, offline controls, API failures, import preview gating, unchanged idempotent retries, and preview-before-apply.
- TypeScript compilation and Vite/PWA production build passed.
- OpenAPI generation with validation and fail-on-warning passed.
- Django database checks passed; no migration drift; no pending migrations after local application.

MySQL concurrency tests use separate connections for the last section seat, duplicate draft creation and competing class transfers. Existing M8 tests prove competing publications cannot double-book. Bulk preview/failure, audit/outbox failure, scope revocation/replay, cross-institution substitution, record allowlists, missing eligibility, credit/capacity limits and effective roster history are covered.

## Local database/configuration state

Applied term_registration migration 0004_alter_programmetermoffering_options_and_more to the existing configured local development database. Earlier M7 0001–0003, M8 0001–0005 and tenancy migrations remain applied.

The verification script guards the test database name and rebuilds only the isolated test database. Fixture students and registrations are test data, not application imports.

Confirmed after migration:
- TERM_REGISTRATION_ENABLED = False.
- TEACHING_TIMETABLE_ENABLED = False.
- Institutions with term_registration enabled: 0.
- Institutions with teaching_timetable enabled: 0.

No users/groups were assigned, institutional numeric credit policy invented, eligibility provider configured, application records imported, external events delivered or production deployment performed. The permission-seeding command is supplied for deliberate operator execution.

## Integration behavior

M8 operational membership now resolves M7 effective-dated episodes, including historical membership of closed episodes before their exclusive end. Original publication student/cohort snapshots and explicit revision-history results remain immutable. Exception conflict checks use membership effective on the proposed date.

Course drops/completions and class/roster transfers execute on their effective day, preventing early seat release by a future-dated status change. Administrative course completion can occur after the teaching term ends. Same-day zero-length roster episodes remain rejected and require forward correction.

## Remaining acceptance gates

The real result/attempt/prerequisite provider is an explicit upstream dependency. Course registration fails closed until it is supplied and configured. Institutional credit policies, M8 availability and publication also require authorized operational configuration.

Browser setup was attempted using the browser skill. Discovery returned no connected browsers. No screenshot, visual, keyboard, mobile or Playwright end-to-end acceptance is claimed.

Production-size query/load/fault benchmarks, real legacy migration reconciliation, backup restoration, external consumer integration and institutional sign-off were not performed. The runbook describes these gates. This is verified local implementation, not production acceptance.

The workspace has no Git repository; no commits were created. See M7_IMPLEMENTATION_STATUS.md, M7_IMPLEMENTATION.md and M7_ROLLOUT.md for the stage inventory, interfaces and operator steps.
