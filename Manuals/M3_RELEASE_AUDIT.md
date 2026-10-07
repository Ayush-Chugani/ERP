# M3 Prompt 13: final architecture review

Review date: 2026-09-20. This stage is read-only with respect to implementation; findings below do not silently authorize schema changes. Scope is the completed Academic Calendar module and its integration with existing tenancy, organization, authentication, admin and frontend.

## Recommendation

**Conditional go for development/staging acceptance; no-go for production until the operational and browser exit criteria below are met.** Automated evidence supports the approved shared-calendar model. No unresolved critical implementation failure was observed in the exercised paths. Statement coverage and component tests cannot establish complete authorization branch coverage, accessibility or production readiness.

## Verification evidence

| Evidence | Result |
| --- | --- |
| App scaffold import without database | Passed |
| Fresh MySQL migrations in automated tests | Passed |
| Working-database migrations | academic_calendar/0001 and tenancy/0002 applied |
| Full scripts/verify-module3.ps1 run | 102 backend tests passed; organization/tenancy/calendar combined statement coverage 92.88% |
| Additional final focused calendar run, including three newly added tests | 25 tests and 7 subtests passed; calendar-only statement coverage 89.93% |
| Frontend Node tests | 10 passed |
| Frontend component/offline tests | 11 passed, including 5 calendar tests |
| Runtime-error lint, Django/database checks | Passed |
| Migration drift | No changes detected |
| OpenAPI validation with fail-on-warning | Passed |
| TypeScript + Vite/PWA production build | Passed |
| MySQL EXPLAIN | Captured in M3_QUERY_PLANS.md using rolled-back representative fixtures |
| Hosted Linux CI | Configuration supplied; no hosted run claimed |
| Browser accessibility/PWA/mobile walkthrough | Not completed by the agent |
| Production deployment, legacy import and backup restoration | Not performed |

The final focused run includes the added schema uniqueness/FK tests and remaining public selector coverage after the 102-test full run. These are separate runs, not a claim that a 105-test full run occurred. Tests run against MySQL 8.4.11. MariaDB and the advertised lower MySQL 8.0.16 boundary have not been independently exercised.

The user reported a live create form failure (HTTP unsupported text/plain media type). Frontend calendar writes now explicitly set application/json for create, update and lifecycle. The regression test asserts header and parsed request body for all three. API tests exercise JSON writes. A post-fix live-browser confirmation by the user is still separate from this automated evidence.

## Requirements traceability

Paths below are relative to backend/apps/academic_calendar unless otherwise stated.

| Baseline or invariant | Implementation | Verification |
| --- | --- | --- |
| academic_year ID/code/dates/status | models.py AcademicYear; migration 0001 | test_models.test_mysql_named_checks_collations_and_unsigned_widths; test_services.test_database_constraints_unsigned_and_timezone |
| unique year_code | AcademicYear.year_code; full_clean + atomic error translation | test_models.test_each_baseline_unique_and_foreign_key |
| chk_academic_year_dates | models.py named CheckConstraint + clean | test_services.test_database_constraints_unsigned_and_timezone |
| academic_term fields and unsigned parent/ID | models.py AcademicTerm; migration 0001 | test_models schema inspection and FK cases |
| uq_term_code | named UniqueConstraint + full_clean | test_models.test_each_baseline_unique_and_foreign_key |
| chk_term_dates and chk_term_registration_dates | named CHECKs + clean | test_services.test_database_bypasses_still_reject_local_invalid_values; test_nullable_registration_and_outside_year |
| fk_term_academic_year | Django-generated FK name; PROTECT and explicit db_column | test_models FK cases; test_services protected-year deletion |
| semester fields and both unique values | models.py Semester | test_models unique cases; test_audit_rollback_and_collation |
| chk_semester_number | named CHECK and unsigned tiny storage | test_database_constraints_unsigned_and_timezone |
| time_slot fields, uq_time_slot, chk_time_slot | models.py TimeSlot and migration | test_models unique/schema cases; test_database_bypasses_still_reject_local_invalid_values |
| fk_time_slot_campus | Django-generated FK name; PROTECT | test_models FK and protected campus deletion |
| Allowed year/term/type enum values | TextChoices + additional DB CHECKs | test_database_bypasses_still_reject_local_invalid_values and named CHECK inspection |
| Containment, nullable registration endpoints | AcademicTerm.clean + services.validate_rules | test_nullable_registration_and_outside_year; test_lifecycle_containment_cardinality_and_retry |
| Shared one-active-year | services.execute shared lock + validate_rules | test_concurrency.test_concurrent_year_activation |
| Term lifecycle and closed immutability | TRANSITIONS, execute, readonly API/admin | test_lifecycle_containment_cardinality_and_retry; test_closed_year_blocks_child_changes_and_dst_ambiguity |
| Non-break active slot overlap, adjacency | validate_rules half-open intersection under shared lock | test_slot_adjacency_break_overlap_activation_and_isolation; test_concurrency.test_concurrent_overlapping_slots |
| Campus ownership and inactive parents | policies.campuses/scoped + service recheck | test_slot_campus_scope_and_workflow_permission; test_slot_scope_rejects_wrong_campus_and_deactivated_parent_assignment |
| Django permissions, roles, module activation | policies.py, existing tenancy models | test_permissions_activation_and_limits; test_teacher_view_requires_permissions_and_cannot_write; test_disabled_module_blocks_even_superuser_without_breaking_other_modules |
| List scope and object authorization | scoped querysets + CalendarPermission + service checks | API cross-campus and foreign detail tests |
| Hidden conflict details | scoped overlap response | test_record_limited_overlap_does_not_disclose_hidden_slot |
| Transactional auditing and bounded fields | CalendarAudit, snapshot, execute | test_audit_rollback_and_collation; test_response_request_id_matches_audit_and_invalid_reason_is_400 |
| Admin uses services; atomic bulk transitions | CalendarAdmin.save_model/perform_transition | test_admin_writes_audit_and_bulk_failure_rolls_back; test_admin_scope_readonly_fields_and_audit_protection |
| Explicit campus zones and DST | scheduling.py | test_database_constraints_unsigned_and_timezone; test_closed_year_blocks_child_changes_and_dst_ambiguity |
| Trusted institution read context + typed contracts | selectors.py/public.py | test_selector_context_public_dtos_and_registration_boundaries; test_all_public_selectors_return_scoped_read_contracts |
| Read performance and indexes | selected parents, list action batch lookups, named indexes | test_list_query_count_bounded_and_cache_disabled; M3_QUERY_PLANS.md |
| Mass-assignment/filter rejection, no delete | CalendarSerializer, viewset methods/filter validation | test_crud_filters_schema_and_lifecycle_routes |
| Frontend roles/forms/errors/JSON headers/offline | CalendarApp.tsx, api.ts | frontend/tests/calendar.test.tsx |
| Static-only PWA; no false queued writes | existing vite.config.ts network-only API rule; online state guards | frontend/tests/pwa.test.cjs and calendar offline test |
| Rollout safety and reconciliation | M3_ROLLOUT.md | Documented design only; no live legacy data rewritten |

FK physical names use Django's deterministic generated names rather than copying the baseline fk_* names; referenced tables/columns and protection semantics are preserved. CHECK/compound uniqueness names are explicit. ENUM is represented by character fields plus checks. TIME uses Django time(6) precision. These are documented framework mappings, not a byte-identical SQL schema claim. Existing legacy tables require an adoption review.

## Severity-ranked findings and residual risks

| Severity | Finding / evidence | Measurable exit criterion |
| --- | --- | --- |
| High, production gate | No staged production deployment or verified restore. M3_ROLLOUT.md is a runbook, not an executed recovery test. | Run Linux deployment with reviewed production lock, verify TLS/proxy/admin/API behavior and restore an encrypted backup into an isolated database; record timings and recovery point. |
| High, existing-database adoption gate | Initial migrations assume these domain table names are absent. Legacy institution-specific periods cannot be automatically interpreted as approved shared calendars. | Complete source/target mapping, zero unresolved duplicate/containment/ownership conflicts, approved reconciliation hashes and an idempotent importer rehearsal before adopting legacy tables. |
| Medium | Live browser acceptance remains incomplete; user surfaced a transport defect now regression-tested. | Confirm create/edit/lifecycle live after refresh; keyboard and screen-reader form/error/focus behavior; mobile layouts; PWA install/update/offline and account-change tests. |
| Medium | Campus timezone is configuration rather than a campus column; missing zone blocks conversion. | Configure and validate every participating campus ID, including a DST case if applicable. No guessed fallback is allowed. |
| Medium | Broad shared write lock limits concurrency throughput despite correctness tests. services.execute shares organization's ContentType lock. | Load-test expected traffic and lock-wait/error budgets before production. Any finer-grained lock design requires new race tests. |
| Medium | Service-only global cardinality/interval rules can be bypassed by raw ORM/SQL. DB constraints cover local checks and uniqueness only. | Inventory all writers, route them through services, restrict runtime database identities; do not claim DBA-proof policy enforcement. |
| Medium | Future dependent modules conservatively block edits/transitions when reverse FKs exist. No course-registration integration exists yet. | Define and test lifecycle dependency contracts before enabling those modules; no silent bypass. |
| Medium | CI config has not run on hosted Linux and supported-version portability is unverified. | Execute .github/workflows/calendar.yml and test the actual deployment MySQL/Python environment. |
| Low | Calendar admin error handling redirects after a transactional service rejection, so an operator may need to reenter values. React form values are preserved. | Include admin invalid-write UX in acceptance; no integrity bypass observed. |
| Low | Campus-slot EXPLAIN chose a table scan on a 24-row fixture. Other predicates used expected year/term/natural-key indexes. | Repeat EXPLAIN and latency measurements with representative production distribution; do not force an index based on the tiny fixture. |

No application fixes were introduced during this final review stage. The distinction between implemented code, automated verification and unperformed operational acceptance remains explicit.
