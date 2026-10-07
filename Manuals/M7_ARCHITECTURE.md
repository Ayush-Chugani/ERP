# M7 architecture — Prompt 2

App: `apps.term_registration`. API namespace: `/api/v1/registration/`. Global runtime flag and institution module flag default to disabled during rollout.

## Package and aggregate boundaries

```text
term_registration/
  models.py             eight domain tables and local constraints
  support.py            audit, idempotency receipts, policy attestations/outbox
  policies.py           transition, eligibility and permission rules
  selectors.py          scoped lists, occupancy, current/as-of rosters
  services.py           commands and transaction boundary
  integrations/         declared upstream and downstream contracts
  serializers.py        explicit read/write/command payloads
  api.py / urls.py       thin versioned endpoints
  admin.py              governed inspection/commands; no hard deletion
  management/commands/  reconciliation and controlled imports
  tests/                policies, MySQL constraints/races, API isolation
```

Offering aggregate: programme-term offering, sections, batches, course offerings and section mappings. Registration aggregate: term registration and course registrations. Roster episodes reference exact course registrations and mappings; their IDs remain stable for downstream attendance.

Upstream masters remain owned by organization, calendar, curriculum, people and admission apps. Use declared adapters/public interfaces to obtain immutable eligibility inputs and scoped enrolment identity. Do not write upstream student, enrolment, term or curriculum records from M7. Finance is not implied by the active editor's SQL or by M6's manual admission fee clearance.

## Commands and concurrency

All commands accept actor, explicit values, correlation ID and reason when material. Existing rows require an expected version. Retriable create/bulk/allocation commands additionally require an idempotency key and canonical payload digest. Reauthorize before returning an earlier receipt; changed input under a reused key is a conflict.

Lock order: existing shared organization governance row first; reload actor and grants; then offering IDs ascending, section IDs ascending, batch IDs ascending, course offering IDs ascending, registration IDs ascending, roster episode IDs ascending. Every path taking these locks uses the same order. The shared lock conservatively coordinates upstream deactivation and scope changes with registration writes.

Capacity: only REGISTERED/APPROVED term rows consume section/batch seats. Check both section and batch limits within the same transaction; count a moving registration once and exclude its old assignment when evaluating the destination. Course seats use the analogous active registration states. Never use an unlocked count followed by an insert.

Balanced allocation: choose eligible active sections by lowest occupied/capacity ratio, then stable primary key; use occupied count for unlimited capacity. Apply the same rule to a required batch inside the selected section. Full capacity returns a stable error without allocating elsewhere silently. Draft assignment is provisional and checked again on registration.

Bulk commands are bounded and atomic per submitted batch, with row-indexed validation errors. Dry-run uses the same validation and rolls back all domain, receipt and audit writes. No partial-success import without an explicit caller-selected contract.

## Query and event contracts

Selectors apply institution/campus/department/programme/record scope before filtering, pagination or object lookup. Student self-service additionally requires a verified student/account link; knowing an enrolment ID is insufficient. Avoid applicant contact/demographic fields in rosters.

Event names are versioned: `registration.offering.changed.v1`, `registration.term.changed.v1`, `registration.course.changed.v1`, `registration.roster.changed.v1`. Write identifiers, actor, request ID, version and bounded before/after state to immutable audit/outbox records in the transaction. Publish only after commit; consumers deduplicate event IDs. Expected consumers: timetable, attendance, assessment and reporting. None may assume those modules already exist.

## Required policy inputs

Progression approval uses the user-approved registrar attestation with a recorded reason. Result/attempt/prerequisite and timetable adapters must return an explicit eligible/ineligible/unavailable result. Unavailable does not mean eligible. Credit limits and special registration exceptions require configured, authorized policy; values are not invented by the module.

## Verification plan

Test every composite FK through direct SQL/ORM writes, then test stricter service relationships separately. Use two real MySQL connections for final-seat allocation, duplicate registration and transfers. Add stale-version, disabled-module, cross-institution list/detail/parent, self-service substitution, audit rollback and idempotency tests. Browser tests must exercise offline rejection, conflict recovery, filtered selectors and import review. No browser result is inferred from a successful build.

## Approved progression policy

User selected option 1: authorized registrar approval with a recorded reason. Only REGISTERED and APPROVED term registrations reserve seats. No further confirmation of these policies is required.

## Implementation follow-through

The implemented command catalogue is in commands.py, setup/course/roster services in workflows.py, policy/receipt/event models in support.py, and bulk transaction handling in execution.py. M7_IMPLEMENTATION.md supersedes the earlier proposed package tree. Student access is read-only through verified account links. The result/attempt/prerequisite callable is an explicit upstream dependency; absence blocks course registration. M8 operational membership overlays dated rosters while revision-history membership retains publication snapshots.
