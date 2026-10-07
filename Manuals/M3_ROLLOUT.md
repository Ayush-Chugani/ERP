# M3 Prompt 12: rollout and legacy calendar reconciliation

## Prerequisites and migration order

Use the [existing deployment guide](M2_DEPLOYMENT.md) for TLS, secret management, proxy isolation, database privileges, systemd and backup operations. Organization/Campus and the custom User must already exist. Calendar migration 0001 depends on them; tenancy migration 0002 adds academic_calendar=false. Run `manage.py migrate --plan`, inspect generated SQL, then migrate in a write-maintenance window. The initial migration creates academic_year, academic_term, semester, time_slot and platform_calendar_audit. Do not apply it to preexisting legacy tables without an adoption/reconciliation review. No tenant backfill is needed because shared ownership was approved.

Build and deploy the matching frontend after backend migration, then enable calendar for pilot institutions. Existing reference and organization URLs remain compatible. Configure campus timezone IDs before timetable datetime conversion. Assign minimal Django view/add/change/lifecycle permissions and test institution/campus isolation. Keep the global kill switch available for operational containment; disabling access is not a schema rollback.

## Legacy import report design

Prompt 12 requires a plan and report design; it does not authorize rewriting the legacy database. No production import has been performed. Implement an importer only against a reviewed export and approved mapping. Required report columns:

- source file/version and SHA-256; source table and source key;
- normalized natural key, mapped target parent key and proposed target ID;
- proposed values, existing values and operation (create, preserve, reviewed update, reject);
- validation codes, severity, conflict source rows, reviewer and disposition;
- batch ID, dry-run timestamp, counts and per-row canonical payload hash.

Natural keys are year_code; year_code + term_code; semester_number with independently unique semester_name; and reviewed institution/campus natural key + slot_code. Never assume numeric IDs align. Preserve semester name conflicts as explicit errors rather than automatically renaming. Normalize exactly as application fields do and check duplicates using the target MySQL collation, including case/accent variants.

Validate missing parents, code/ID width, dates, nullable registration endpoints, term containment, duplicate natural keys, incompatible statuses, more than one active shared year, active non-break overlaps and missing/invalid campus timezone mappings. Sort rows deterministically (parents before children). Flag incompatible legacy calendars for explicit human resolution; do not silently shift dates or combine institution-specific years into a shared calendar.

## Dry run and reconciliation

1. Export from a consistent read snapshot and retain an immutable encrypted source copy.
2. Load/validate into an isolated staging database matching production schema/collation. Produce the report without applying changes to live data.
3. Review every rejected/ambiguous row and approve the exact mapping, payload hashes and update policy. Administrator edits are preserved unless explicitly approved for update.
4. For actual ingestion, use calendar services with a designated actor and batch correlation IDs. Commit parent/child groups atomically. Persist an import checkpoint keyed by source checksum + normalized natural key + payload hash; resume only when input and approvals match.
5. On rerun, verify an already committed row has the expected hash; skip it without creating another audit. Treat divergent target data as a conflict. Do not infer success merely from an occupied key.
6. Reconcile source accepted/rejected/unchanged counts with target natural-key counts, canonical value hashes and audit events. Verify orphan count zero, one-or-zero active year, containment violations zero, prohibited slot overlaps zero and no unauthorized campus assignment.

Checkpoint/report storage and the importer itself are future operational tooling, not claimed implemented here. A live legacy adoption must wait for that reviewed reconciliation implementation and rehearsal.

## Rollback and recovery

Before migration take an encrypted, verified-restorable backup and record migration state, application release and configuration. If deployment fails without writes, roll back the app only after proving schema compatibility. After writes, prefer a forward fix; reversing the initial migration drops tables and is destructive. A database restore requires write downtime, a documented recovery point, preservation/reconciliation of subsequent writes and operational approval. Never drop legacy tables to make initial migration pass.

Retain old and new frontend bundles through the service-worker update window. Show the existing update prompt, refresh after rollout and verify API/admin navigation bypasses shell fallback. No calendar API cache invalidation is needed because such caching is disabled, but mounted clients must refresh permissions/data.

## Post-deployment checks and ownership

Platform operations owns backups, restore drills, migration execution, TLS and monitoring. Platform calendar administrators own shared periods and lifecycle reasons. Institution/campus administrators own authorized slots. Monitor API error/409 rates, 401/403/404 patterns, lock wait/deadlock frequency, request latency, audit failure counts, database storage and timezone-configuration failures. Do not log credentials, tokens or full request payloads.

Exit criteria: test a representative institution and a denied peer; verify a scoped list/detail/parent picker, permitted create/update/lifecycle, rejected duplicate/overlap, matching audit correlation and rollback on failed writes; perform real-browser keyboard/mobile and offline/PWA tests; rehearse restore in isolation. Production deployment and restore are not executed by this implementation.
