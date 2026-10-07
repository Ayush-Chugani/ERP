# M4 rollout and recovery

## Current development database

The five M4 domain tables were absent during upstream profiling. Migrations 0001_initial and 0002_specialization_ownership plus tenancy 0003 were applied to the configured development MySQL 8.4.11 database. Migration SQL is recorded in M4_initial_migration.sql and M4_composite_fk.sql. Use Django migrations; do not execute the complete reference SQL against this application database.

## Deployment sequence

1. Record the application build, existing migration state and database version/collations. Back up the database and verify that a separate staging restore works. Retain the old application build and configuration.
2. Rehearse on a restored staging database. Run `python backend/manage.py migrate --plan`, inspect generated SQL and table names. If the five curriculum tables already exist, stop automatic adoption and reconcile schema/data; do not use --fake-initial to hide mismatches.
3. For legacy data, run the read-only M4_DATA_PROFILING.sql after confirming all referenced tables exist. Resolve orphan parents, collation-equivalent duplicate codes, mismatched specializations/categories, negative marks, invalid dates and graph cycles. Stage an explicit natural-key ownership mapping and retain row counts/hashes. No generic legacy importer is supplied or silently run.
4. Start with SIMS_CURRICULUM_CATALOG_ENABLED=0. Apply migrations once with the deployment account. Verify SHOW CREATE TABLE against the supplied SQL and support-table migrations, including unsigned BIGINT, YEAR, composite key and specialization ownership FK.
5. Run `scripts/verify-module4.ps1` (Windows) or the equivalent commands in `.github/workflows/calendar.yml` (Linux). Test accounts/factories belong in the disposable test database; do not seed demonstration courses into production.
6. Enable the global flag, then the institution curriculum flag for one pilot institution. Assign explicit Django permissions and existing scoped roles. Verify metadata, scoped lists, semester choices, draft creation, composition, readiness, activation, clone and retirement with pilot accounts.
7. Complete the browser checklist below, compare query plans with representative production-sized data and monitor lock wait time. Expand institution activation only after pilot acceptance.

## Browser and operational acceptance

- Desktop/mobile: keyboard-only course editor and parent autocomplete; labels, required fields, validation association and focus restoration.
- Actual authenticated browser: category -> course -> scheme -> composition -> prerequisite -> readiness -> activation -> clone. Confirm admin/API parity and reason recording.
- Two tabs: stale If-Match preserves unsaved editor input. Resolve by reloading and reconciling.
- Cross-institution/departments: lists, detail URLs, dropdowns, CSV and graph cannot expose hidden records. Sign out/in as another user and inspect the absence of retained curriculum data.
- Offline: visible warning, disabled writes, no queued success, no curriculum API/draft responses in service-worker caches. Reconnect and reload permissions.
- Decimal/date round trip and an ID above JavaScript's exact integer range retain their exact strings.
- Restore a backup into an isolated environment and reconcile records, revisions, audit and event cursor. Exercise module disable/re-enable without data loss.

These browser, staging and restore checks are pending; component tests do not replace them.

## Rollback

First disable the module globally and/or per institution and restore the previous compatible application build. Preserve domain and audit tables. Do not reverse initial migrations after accepting writes: reversal drops data. Restore a tested full backup only under a reviewed recovery procedure, with a plan to reconcile changes made after that backup. MySQL DDL is not transactionally reversible in the same way as ordinary application writes. This release's transaction guarantees concern governed data writes and their audit/events.

## Compatibility and limits

Active and retired scheme structures must be cloned, never retroactively rewritten. IDs remain stable for future enrolment, course offering and result references. Future downstream migrations must add real protected foreign keys before depending on these records; unimplemented consumers cannot be checked by the current ORM impact report.

The event table is a transactional durable log, not an external broker. Consumers own deduplication/checkpointing. Audit append-only behavior is application-enforced, not DBA-proof. Support audit access is restricted to platform superusers; audit reads themselves are not recorded as write events.

Prerequisites use the React/API editor because installed Django admin does not support composite primary keys. Coarse serialization and 5,000-node/edge graph and export limits are explicit capacity boundaries. The query-plan fixture is small and not a production load benchmark. Minimum-grade configuration must be approved before accepting nonnull grade requirements.
