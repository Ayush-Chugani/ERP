# M8 local release audit — 23 September 2026

## Verified

`scripts/verify-module8.ps1` completed successfully:

- Django system/database checks: passed.
- Migration drift: no changes detected.
- Real MySQL combined core/M6/M7/M8 suite: **63 tests passed**, including concurrent publication, class/batch snapshots, immutability, scope limits, import preview, solver, workload override, historical supersession and outbox rollback/retry. The final focused API rerun also passed all nine tests, including a positive own-institution control alongside cross-institution denial and private no-store response headers.
- Frontend component suite: **23 tests passed across six files**, including four M8 UI tests.
- OpenAPI generation/validation with warnings treated as failures: passed after disambiguating the M8 transition serializer.
- TypeScript check and Vite/PWA production build: passed.

Local migrations applied successfully: teaching_timetable 0001–0005 and tenancy 0007. Post-migration Django database checks passed. `migrate --plan` reports no remaining operations. The operational check reports zero stalled/failed jobs, zero outbox events and no operational collision. No sample people, allocations, schedules, role memberships or published records were inserted into the application database by the test runs.

Repeated test-database reuse exposed unsigned TINYINT fixture-sequence exhaustion. The verification script now validates that the test database name starts with `test_` and differs from the application database, then rebuilds that isolated test database using `--create-db`. The complete fresh-database run passed. Verified names: application `sims_reference_dev`, test `test_sims_reference`.

`Manuals/M8_REVISED_SCHEMA.sql` is the complete generated migration DDL for review. Schema changes are additive to M1–M7. The raw composite FK migration has an explicit reverse. Existing M7 and M8 runtime switches were not enabled.

The M8 global flag was verified false and the count of enabled institutions was zero. The project root was not a Git repository, so stage commits were not created.

## Remaining release acceptance

- M7 offering/allocation/roster workflows remain unfinished upstream. Reconcile actual roster coverage before enabling operational scheduling.
- Browser runtime discovery returned no available browsers. No visual screenshot, full keyboard/mobile browser session or Playwright end-to-end result is claimed. Component tests and production builds passed.
- Production deployment, backup restoration, legacy production imports, realistic load/fault benchmarks and operator sign-off were not performed.
- Attendance, leave, facility and notification-provider implementations are absent upstream. M8 supplies published-occurrence and outbox contracts; no external messages were sent or provider integrations falsely marked complete.

Keep the module disabled until these gates are met. See M8_ROLLOUT.md for pilot enablement, import, recovery and incident procedures, and M8_IMPLEMENTATION_STATUS.md for prompt-to-artifact/test traceability.

## Subsequent M7 implementation

The unfinished M7 workflow statement above records the original M8 release state. M7 now has local offering/allocation/course/roster workflows and APIs/UI. M7_RELEASE_AUDIT.md records subsequent combined verification and M7_IMPLEMENTATION_STATUS.md lists current dependency gates. Runtime activation remains off.
