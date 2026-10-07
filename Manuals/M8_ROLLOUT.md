# M8 rollout, imports and recovery

## Local verification

Run `./scripts/verify-module8.ps1` from PowerShell. It checks Django, migration drift, real MySQL M6/M7/M8 tests, OpenAPI, frontend component tests, type checking and the production build. `--import-mode=importlib` avoids the legacy root-package import problem in this workspace. SQLite is not the M8 acceptance database.

The script also checks core regression tests and recreates only the explicitly isolated `test_` database. This prevents repeated rolled-back fixtures from exhausting 8-bit master-key sequences. Do not point test configuration at an application database.

MySQL migration 0002 adds the composite assignment/section FK absent from Django's ordinary single-column FK mapping. Its reverse explicitly drops that FK. Migration 0001 includes its prerequisite candidate key. Later migrations add optional job timestamps and authorized allocation support. Model state remains consistent with these physical constraints. `M8_REVISED_SCHEMA.sql` is generated from the migrations for inspection; deploy through Django migrations, not both methods.

Migration 0005 adds immutable class/batch snapshots, backfills them from existing occurrence-to-section relationships, then makes the class snapshot mandatory. If upgrading a database with existing published occurrences, reconcile historical section mappings before that backfill: it cannot reconstruct past upstream edits. The local database had no published occurrences during this upgrade.

## Release gates and deployment

1. Validate the implemented M7 workflows and real course eligibility provider, then reconcile actual dated course memberships. Verify account links and staff competency/employment data. Keep M8 disabled until these dependencies are ready.
2. Back up the target database and prove restoration on a separate staging instance. Record the backup location, checksum, server version and recovery time. No production restore has been performed by this implementation.
3. Run `manage.py migrate --plan`. Review existing source tables before adoption: never fake the initial migration against unverified legacy M8 tables. The local preflight found both M8 source tables absent.
4. Deploy schema while `SIMS_TEACHING_TIMETABLE_ENABLED=0`. Keep every institution flag false. MySQL DDL cannot be rolled back merely by enclosing it in a Django transaction.
5. Run `manage.py seed_timetable_groups`. This adds permissions to named bundles and never assigns users or scope. Assign explicit memberships and approved institution/campus/department grants through established governance.
6. Configure workload limits; import and reconcile faculty allocations and draft sessions; attest availability. Reject orphan IDs, duplicate source IDs, reversed dates, invalid ownership and collisions.
7. Run the verification script, accessibility/browser acceptance and backup/replay recovery checks. Pilot one institution only after these gates pass. Set the global switch and that institution's flag explicitly.
8. Run the solver worker via a supervised scheduled process: `manage.py run_timetable_jobs --limit 5`. Poll `manage.py check_timetable_operations` and alert on nonzero stalled jobs or operational conflicts. Monitor failed jobs, publication failures, command durations and consumer-specific outbox backlog. API throttle is 120 requests/minute/user; use a shared cache for a multi-worker production throttle.

## Import

Map legacy IDs to verified upstream IDs first. Never identify a person by display name. Preserve the mapping and source file checksum. Faculty CSV columns are documented in the UI and implementation guide. Session CSV columns are `source_id,course_offering_section_id,faculty_assignment_id,room_id,time_slot_id,day_of_week,effective_from,effective_to`.

```powershell
backend/.venv/Scripts/python.exe backend/manage.py import_timetable_allocations mapped-allocations.csv --actor 1 --reason 'Reviewed legacy mapping' --report allocation-preview.json
backend/.venv/Scripts/python.exe backend/manage.py import_timetable_sessions mapped-sessions.csv --actor 1 --revision 12 --version 1 --reason 'Reviewed legacy mapping' --report session-preview.json
```

Both commands default to dry-run. Inspect the JSON report and resolve quarantined rows before adding `--apply`. Imports are atomic and never publish automatically. Repeating the same actor/import payload uses a deterministic receipt. Changed payloads are new imports; changed legacy records require explicit review rather than silent overwrite. The API/UI allocation import provides the same preview/apply distinction. Normalize legacy time slots against campus clock intervals; equal slot IDs alone do not prove non-overlap. Open-ended legacy sessions must be explicitly bounded to the accepted term end in the mapped CSV.

## Operator procedures

- Allocation: check employment, competency and workload; use planned amendments or dated successor episodes. Overrides require separate permission, full-week date bounds and an immutable reason.
- Collision: inspect the reported date/resource category. Change time, room, faculty or cohort; collisions have no override permission.
- Emergency change: use a dated MOVE or SUBSTITUTE exception; publication rules are rechecked. Cancellation retains the original occurrence and its sequence history.
- Withdrawal: use the versioned revision transition with a reason. Downstream consumers receive the outbox event and reconcile; do not delete occurrences linked to attendance.
- Stuck job: inspect worker logs and `started_at`; cancel with current job version, then queue a new job. Never mark stale output accepted manually.
- Outbox failure: retry the same event UUID; receipts deduplicate local consumption. External delivery adapters must be idempotent. A notification provider and preferences must be configured before sending notifications.
- Rollback: turn off institution/global writes and preserve audit/outbox/occurrence data. Before any live data, reviewed reverse migrations can remove the empty module. After operational use, prefer a forward repair or an independently tested restore plus event reconciliation. Do not drop attendance-linked history.
- Incident: disable affected scope, preserve logs and immutable evidence, reconcile published occurrences against downstream consumers, apply a reviewed correction, then rerun acceptance gates.

## Security and performance notes

Commands take the shared governance lock first and reload the actor; publication, manual changes and solver acceptance use the same services. Deadlock/lock-timeout errors return retryable 409 responses; clients retain the same idempotency key. No automatic unbounded retry occurs. Scoped querysets and per-resource allowlists restrict planner reads and writes. Strict serializers reject mass assignment. CSV cells are neutralized for spreadsheet formulas. API responses and service-worker routing prevent offline timetable caching/mutations.

Audit captures actor, effective grants, institution, action, bounded material before/after fields, reason, correlation ID and time. It is append-only through application paths, not tamper-proof against database administrators. Apply institutional retention policy and protected backup access; no retention period is invented.

Indexes support assignment employee/date searches, revision sections, room/faculty date/time occurrence searches and queued jobs. Roster/availability rows are loaded once per session and exception sequences once per schedule query. The governance lock deliberately favors correctness over write throughput. Realistic multi-institution load benchmarks, index EXPLAIN review and lock-contention thresholds remain staging acceptance work; the small automated fixture is not a production performance claim.
