# M7 implementation and acceptance status

The remaining M7 prompt-pack stages are implemented locally. The earlier schema audit, architecture and three migrations were retained; the new work adds setup and allocation commands, course workflows, exact rosters, API/UI, integration contracts, controls and operator tooling.

## Accepted policies

- Registrar progression approval requires a separate permission, current offering/enrolment versions and a reason.
- Only REGISTERED and APPROVED term registrations reserve section/batch seats. Draft assignments are provisional.
- Institutional credit limits must be configured explicitly. No production numeric policy was assumed.
- Missing result/attempt/prerequisite or timetable eligibility blocks course registration. Registrar progression approval does not substitute for course eligibility.

## Stage evidence

| Pack stage | Implementation |
| --- | --- |
| 1–3 Schema, architecture, models | Existing eight source tables and fifteen composite ownership FKs; additive migration 0004 for policy, command receipts, outbox and consumer receipts |
| 4 Offering setup | Curriculum/semester/date validation; offering lifecycle; stable section/batch codes; capacity and deactivation checks; atomic bulk preview |
| 5 Term allocation | Drafts, current progression evidence, registration windows, approval/completion/cancellation, roll correction, explicit transfers and balanced allocation under the governance lock |
| 6 Course setup | Curriculum identity, availability and ownership validation; permissioned noncurriculum offerings; course lifecycle/capacity and exact session mappings |
| 7 Course/roster | Seven registration types, explicit eligibility provider, credit/course capacity checks, published timetable checks, approval/drop/withdrawal/completion, dated roster transfers |
| 8 DRF | /api/v1/registration/, strict command schemas, no-store responses, permissions and current scope on every replay, paginated reads/lookups, own-record student reads, CSV and reconciliation |
| 9 React/PWA | /#/registration, typed action forms and selectors, status/version display, occupancy/remaining seats, multi-select status updates, CSV preview/apply, own records and eligible term offerings, offline mutation rejection |
| 10 Security/reliability | Shared lock, optimistic versions, bounded atomic batches, payload digests, immutable audit/outbox, consumer deduplication, throttles, export formula escaping, inspect-only admin |
| 11 Verification | MySQL service/API/constraint/rollback/concurrency tests; M7/M8 integration regression; component tests; TypeScript/PWA build; OpenAPI validation |
| 12 Operations | Additive group seed, controlled CSV import, anomaly report, verification script, rollout and recovery runbook |

## Deliberate boundaries

- The upstream results/attempt/prerequisite service is absent. Its callable adapter must be implemented by the owning module and configured through SIMS_REGISTRATION_ELIGIBILITY_ADAPTER. An absent provider is not an eligibility approval.
- Student self-service is read-only: verified own registrations and currently progression-approved term offerings. Staff perform registration mutations using scoped permissions.
- Shared cross-programme electives are not implemented by relaxing ownership constraints. Noncurriculum offerings require explicit authority and course eligibility.
- Roster intervals use an exclusive end date. Same-day zero-length closure and retroactive rewrites are rejected; investigate and use an approved forward correction.
- Enrollment/roster IDs remain stable. The M8 operational schedule now overlays dated M7 membership while retaining immutable publication snapshots for revision history.
- No browser is connected in this environment. Component tests and build do not establish visual, keyboard, mobile or browser end-to-end acceptance.
- No production import, restore drill, load benchmark, external event delivery or deployment sign-off was performed. No flags were enabled.

See M7_IMPLEMENTATION.md for API/permission details, M7_ROLLOUT.md for operations, and M7_RELEASE_AUDIT.md for measured verification results.

Course status changes and class/roster transfers execute on the effective day. Future-dated state changes are rejected so they cannot release reserved seats early. New roster episodes may start later, while their course registration already reserves capacity. Scheduled transition jobs are not supplied.
