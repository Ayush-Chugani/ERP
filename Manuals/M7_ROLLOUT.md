# M7 rollout and recovery

## Preconditions

Use the existing backend environment and configured local database. Global SIMS_TERM_REGISTRATION_ENABLED and each institution's term_registration flag remain off after implementation. M8 remains off too. Superuser access does not replace the global switch.

Before activation, the registrar must configure programme credit limits and verify progression permissions. Implement and validate the real results/attempt/prerequisite eligibility provider; set SIMS_REGISTRATION_ELIGIBILITY_ADAPTER to that provider, never a test fixture. Configure M8 scheduling policy, faculty and room availability, and publish the cohort timetable before admitting course registrations.

## Verification and migration

From the repository root:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-module7.ps1
    backend/.venv/Scripts/python.exe backend/manage.py migrate --plan
    backend/.venv/Scripts/python.exe backend/manage.py migrate term_registration
    backend/.venv/Scripts/python.exe backend/manage.py check --database default
    backend/.venv/Scripts/python.exe backend/manage.py seed_registration_groups

The verification script checks the isolated test database name, rebuilds only that test database, and runs real MySQL M6/M7/M8/core tests, schema validation, UI tests and build. Rebuilding avoids unsigned TINYINT fixture sequence exhaustion. It does not activate modules or seed application records.

Migration 0004 is additive: policy, immutable command receipts, registration events and consumer receipts, plus a read permission. It does not rewrite the eight source tables or import historical rows. The SQL review artifact M7_INCREMENTAL_SCHEMA.sql is generated with sqlmigrate; Django migrations remain authoritative.

Group seeding creates additive permissions only. Assign users and scope grants deliberately. Narrow programme/student/resource allowlists never expand institution membership. Coordinator and registrar groups are separate from the policy administrator.

## Pilot sequence

1. In staging, restore a current backup and record row counts/ownership checks before migration. Reconcile all legacy collisions before applying constraints.
2. Apply schema, deploy backend and frontend with switches off, validate schema and health checks.
3. Configure eligibility provider and institutional policies. Use test identities in staging to prove positive and denied decisions for all seven course registration types.
4. Configure scoped groups/memberships. Enable only the pilot institution through the existing deployment/configuration process.
5. Create offering, sections, batches, course offerings and mappings. Open the academic registration window and then the programme offering.
6. Registrar records version-bound progression approval. Create drafts, allocate groups and register terms. Review occupancy before approving.
7. Configure and publish M8 cohort sessions. Open course offerings. Register eligible courses, approve and assign each required session roster.
8. Check scoped personal schedules, rosters, exports, audit and reconciliation. Complete browser keyboard/mobile/refresh/conflict/offline acceptance.
9. Pilot monitored real traffic; measure final-seat contention, lock waits, queue lag and query latency before wider rollout.

Changing the offering or enrolment version invalidates old progression evidence. Do not reuse outdated approval when reopening or correcting source records.

## Imports and reconciliation

Prepare an explicit mapping from legacy IDs to current enrolment/offering/section/batch/course IDs. Preserve a protected copy of the original file and its checksum. Import operation,data CSV in dependency order, at most 100 commands/1 MB per batch.

    backend/.venv/Scripts/python.exe backend/manage.py import_registrations mapped.csv --actor <user-id> --key <batch-key>
    backend/.venv/Scripts/python.exe backend/manage.py import_registrations mapped.csv --actor <user-id> --key <batch-key> --apply
    backend/.venv/Scripts/python.exe backend/manage.py check_registration --actor <user-id>

The first invocation is a rollback-only preview. The second revalidates and commits atomically. Keep the batch key unchanged only for an identical retry. Changed files require a new key and a fresh review. Returned preview IDs are not reserved.

Unknown or cross-owner IDs, duplicate registrations, roll collisions, zero capacities, stale versions and invalid transitions are rejected. Do not fix them by bypassing FKs or editing status columns. Capture row-indexed failures, correct the mapping, and preview again. The importer does not invent historical progression evidence, reconstruct unavailable result records, or backdate live roster operations.

Existing historical episodes require a separately reviewed, offline migration with complete source evidence. Application commands intentionally reject retroactive changes. The reconciliation command is read-only and fails with anomalies; investigate missing rosters and over-capacity groups before opening wider access.

## Transfers and term closure

For unallocated drafts, use balanced allocation. Drafts do not reserve seats; registration checks capacity again. Explicit transfers require a reason and version. Transfers with active courses require an effective date and destination mappings; all old/new roster changes commit atomically. No destination match or timetable conflict means the entire transfer rolls back.

Roster dates are half-open. A recorded closure preserves historical membership before its end. Same-day zero-length closure is rejected. Use forward corrections with registrar review instead of rewriting historical episodes.

Close or complete course registrations first, then term registrations and course offerings, then the programme offering. Cancellation cannot silently erase active dependencies. Treat roll corrections as versioned commands with audit.

## Monitoring and incident recovery

Monitor HTTP 409/400 rates, registration command duration at the request layer, database lock waits/deadlocks, unapplied event age, reconciliation findings and external consumer failures. Registration events remain queued until an explicitly configured consumer acknowledges them. External consumers must deduplicate event IDs.

If contention or integration failure occurs, disable new registration writes through the global/institution feature gates, preserve evidence, and inspect failed keys/versions and eligibility availability. Do not automatically retry changed payloads. Reconcile before reopening.

Migration 0004 can be reversed to 0003 only in an unused environment after checking no policy, receipt, event or delivery records exist and deploying compatible old code. Once operational data exists, prefer disabling writes and a forward repair. Reversal deletes support evidence. Do not drop domain tables.

For production recovery: take an approved consistent database backup and required log position, restore to an isolated instance, run migrations/checks/reconciliation, compare ownership/occupancy/roster counts, verify personal scope and outbox deduplication, and obtain operator sign-off. This runbook supplies steps; no production restore drill was executed here.

## Acceptance record

Automated evidence is in M7_RELEASE_AUDIT.md. Browser visual/keyboard/mobile tests, realistic load/fault tests, production restoration and institutional sign-off remain release gates. No connected browser was available during implementation. No external notifications were sent.

Course status changes and class/roster transfers execute on the effective day. Future-dated state changes are rejected so they cannot release reserved seats early. New roster episodes may start later, while their course registration already reserves capacity. Scheduled transition jobs are not supplied.
