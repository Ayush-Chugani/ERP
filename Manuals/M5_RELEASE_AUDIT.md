# M5 release runbook and final audit

## Prompt sequence and evidence

| Prompt | Implementation/evidence |
|---|---|
| 0 common context | Existing custom User, modular registry, MySQL, DRF and React architecture retained |
| 1 schema audit | M5_PROMPTS_1_3_review.md; live M5_UPSTREAM_SCHEMA.md |
| 2 boundaries | people_master package, declared integrations/upstream adapter, public immutable DTOs |
| 3 invariants | approved home-institution/activation decisions; validation.py, services.py, database checks |
| 4 scaffold | AppConfig/settings/registry/namespace; M5_PROMPT_4_foundation.md is historical |
| 5 models | all15 source tables, unsigned/generated/composite fields, explicit approved changes |
| 6 migrations/seeds | four people migrations plus tenancy flag; natural-key source-defined seeds |
| 7 identity | optional AccountLink, hashed invitations, provisioning/claim, unlink and platform account management |
| 8 workflows | atomic Command execution, primary history, lifecycle, bulk_save import boundary |
| 9 serializers | explicit read/write contracts, string IDs, validation, field masking |
| 10 APIs | fifteen resource paths, filtering, pagination, version headers, generated OpenAPI |
| 11 authorization | scope before lookup, capability codenames, field permissions, self-service limits |
| 12 audit/events | atomic redacted write records, access/denial audit, correlation IDs, durable versioned log |
| 13 administration | fourteen standard registrations; governed composite competency editor; atomic actions; no delete |
| 14 React feature | people API client, routes, query lifecycle, metadata-driven typed forms |
| 15 forms/grid | React Hook Form, Zod, MUI DataGrid and scoped autocomplete; component tests |
| 16 PWA | existing NetworkOnly API/admin rules, memory-only people data, offline denial/logout clearing |
| 17 tests | foundation, service/API/privacy/admin/identity tests and real MySQL concurrent primary test |
| 18 performance | M5_QUERY_PLANS.md, bounded-query test, indexed directory filters |
| 19 security/privacy | M5_IMPLEMENTATION.md classifications and controls; review below |
| 20 release | this runbook, scripts/verify-module5.ps1 and CI gates |

This ledger records implemented work, not a claim that manual production acceptance has been completed. Invitation delivery, a graphical invitation-claim page, and jurisdiction-specific retention automation are not supplied. Provisioning/claim APIs are available for integration with the institution's approved account-delivery flow. CSV imports have a trusted service boundary, not an unrestricted upload endpoint.

## Automated evidence (2026-09-20)

- Full verification script passed: 152 backend tests on MySQL8.4.11 in95.37 seconds; combined measured module coverage87.90% against an80% gate.
- M5-focused run before final documentation/contract additions:19 tests passed; M5 statement coverage86%.
- Frontend:19 component tests and12 Node checks passed. TypeScript type checking, Vite build and PWA generation passed.
- Django checks, migration drift and validated OpenAPI with warnings-as-errors passed.
- npm reported0 vulnerabilities after the required DataGrid installation. This is a package audit result, not a complete security certification.
- One Django6 URL form-default deprecation warning remains in a test. Application photo URLs already require HTTPS; no Django6 compatibility claim is made.
- A final focused run after small API schema/public-contract changes is recorded at the end of this report.

### Test traceability

| Invariant | Test evidence |
|---|---|
| No premature authentication grants/global disable | test_foundation.py |
| Primary uniqueness/history/readiness | test_student_activation_and_primary_history, test_employee_onboarding_requires_address_and_assignment |
| Concurrent primary races | TransactionTestCase ThreadPoolExecutor/Barrier test_competing_primary_promotions |
| Atomic audit failure and stale versions | test_audit_failure_rollback_and_stale_version |
| Masking and protected fields | test_scope_masking_and_no_mass_assignment |
| Filter inference and self-service record limits | test_masked_filter_inference_and_self_service_record_limits |
| Department choices and internal/agency rules | test_cross_department_choices_and_agency_consistency |
| Invitation binding/replay/claim | test_invitation_is_user_bound_and_single_use, test_provision_claim_and_no_account_hijacking |
| Global account lifecycle/unlink | test_account_unlink_and_global_management_are_guarded |
| API response types and constant query growth | test_create_api_returns_read_contract_and_bounded_queries |
| Admin services, no delete and all-or-nothing actions | test_admin_scoped_and_no_delete, test_admin_bulk_rollback_and_actual_form_save |
| Null uniqueness/range constraints | test_nullable_uniqueness_and_local_ranges |
| Formula-safe exports, lifecycle and list allowlists | test_api_lifecycle_export_and_metadata |
| Immutable contracts, import rollback and append-only storage | test_public_contract_audit_integrity_and_import_rollback |
| Frontend stale state/string BIGINT/JSON headers | frontend/tests/people.test.tsx |
| Offline denial and masked controls | frontend/tests/people.test.tsx plus existing service-worker Node tests |

Factories use explicit institutions, campuses, departments, countries and synthetic people in disposable MySQL test transactions. No SQLite substitution is used for generated/composite/unsigned behavior. Some invalid-state/adapter branches remain uncovered; coverage is a measure of executed statements, not proof of every permission combination. Existing tests do not emulate future admissions/finance/attendance consumers.

## Privacy/security review

High priority controls implemented: scoped object queries, independent service authorization, protected field allowlists, masked-field filter rejection, reference validation, optimistic versions, transaction locks, token hashing/expiry/replay checks, validated passwords, no implicit account-by-email linking, no domain-triggered global account changes, and no sensitive offline caching.

Exports require explicit permissions, apply row/field scope and neutralize spreadsheet formulas. They still contain authorized personal information and require operator handling controls. Untrusted photo URLs are HTTPS text references; backend never fetches them and UI does not automatically embed them. The module has no file upload execution path. Free-text audit reasons are bounded but remain operator-provided, so operational guidance forbids personal details there.

Audit reads are platform-only and mutation APIs are absent. Database owners can still alter application-enforced append-only storage. Protect database credentials, restrict DBA access and maintain independently controlled backups/log retention. Approve retention periods, legal holds and deletion procedures with the institution's policy owner before enabling automated deletion; no arbitrary retention duration is invented here. Deployment-level encryption and TLS are responsibilities of the hosting configuration, not capabilities implied by model names.

Architecture exceptions are explicit: schema foreign-key declarations necessarily name upstream models; runtime adapters handle trusted organization/reference/catalogue access. Installed Django5.2 does not support composite-PK model registration in admin, so competencies use the governed React/API editor. Standard admin saves redirect with a generic validation failure if the command rejects; React preserves entered data and provides field errors.

## Performance acceptance

Run the read-only schema inspection with `scripts/m5_preflight.py` and the rollback-only synthetic query plan fixture with `scripts/m5_query_plans.py` (set PYTHONPATH=backend). The recorded plans use1,000 synthetic students and are not a production throughput benchmark. The optimizer chose a table scan for the low-selectivity single-institution/status fixture; identifier lookup uses a unique lookup. Do not force an index based solely on this fixture.

Before rollout test representative distributions at10k/100k people, multiple institutions and campus/department restrictions. Include name substring search, common status filters, assignment directory, dropdown search, maximum-page reads and concurrent address promotions. Proposed operational investigation thresholds: API p95 above500ms or persistent lock waits above1s. These are starting monitoring thresholds, not measured SLAs. Capture MySQL slow queries without personal bind values. Assess keyset pagination and alternative search indexes when deep offsets/substring scans become material.

## Staged deployment

1. Record application build, database version, migration state and configuration. Take a database backup and prove restoration into an isolated staging environment.
2. Set SIMS_PEOPLE_MASTER_ENABLED=0 during initial rollout. Keep institution flags off until pilot approval. Confirm upstream common-reference, organization, accounts and curriculum migrations are applied.
3. Inspect `python backend/manage.py migrate --plan` and M5_initial_migration.sql. On legacy installations with target tables already present, reconcile generated columns, keys, collations, ownership/backfills and indexes first. Do not use --fake-initial as an adoption shortcut.
4. Apply migrations with the deployment account. Verify staff seed counts/codes and that existing administrator values were retained. No production demo data should be imported.
5. Run `./scripts/verify-module5.ps1`, or the corresponding Linux CI commands with MySQL8.4 and configured environment. The GitHub workflow is prepared; hosted execution has not been observed here.
6. Build frontend with npm ci and npm run build. Deploy static dist through the existing Nginx arrangement and Django through Gunicorn with production settings/TLS. Run collectstatic using the existing deployment procedure. Keep DEBUG off; never log request bodies or invitation tokens at proxy/application layers.
7. Verify existing `/api/v1/core/live/` and `/api/v1/core/ready/`. Enable the global flag and a single pilot institution; grant explicit registrar/HR permissions to selected accounts.
8. Smoke test student onboarding/address/activation and employee onboarding/address/assignment/activation, cross-scope rejection, metadata, masked responses, conflict recovery and an invitation in an approved delivery channel. Confirm audit/event evidence.
9. Watch error rates, lock waits, query latency, audit storage growth, token failures and rejected writes using request correlation IDs without PII. Expand institution flags after pilot acceptance.

## Browser and restore gates still pending

Browser discovery returned no connected browsers, so no live visual, keyboard, mobile or screen-reader validation was possible. Component tests are not WCAG certification. Complete:

- Keyboard-only form/autocomplete/DataGrid workflows, required-field focus, dialogs and error association at desktop/mobile widths.
- Two-tab stale version reconciliation and unsaved-navigation behavior.
- Actual authenticated student and employee onboarding through activation, primary-history changes and scoped competency selection.
- Same-browser signout/signin as another institution; verify personal records are absent from persistent caches/history previews. Test offline and service-worker update behavior.
- Verify token claim over TLS through the intended account UI/integration without logging or URL storage.
- Staging backup restoration, count/ID reconciliation, audit/event cursor recovery and a deployment rollback rehearsal.

## Rollback and definition of done

For functional rollback disable the module globally/institutionally and restore the previous compatible application build. Preserve people/audit/link tables. Do not reverse initial migrations after collecting data: they drop tables. Database restore requires the institution's reviewed recovery plan and reconciliation of writes after the backup. MySQL DDL and ordinary atomic data writes have different rollback behavior.

Development implementation and automated checks are complete subject to final checks below. Production definition of done additionally requires browser/accessibility acceptance, representative load results, approved account delivery and retention ownership, staging restore/rollback evidence, production configuration review and pilot sign-off. Production deployment has not been performed.

## Final follow-up checks

- Final focused M5 suite after API/public-contract changes:20 passed.
- Added seed repetition/administrator-edit preservation test and reran the API lifecycle/export check:2 passed. M5 now has21 distinct tests verified across these runs; the complete regression run above preceded the two latest additions (154 distinct backend tests verified across full/focused runs).
- Final TypeScript/Vite/PWA build passed after the primary-action label adjustment. Final schema validation passed with explicit read responses and list/lifecycle parameters.
- All four people migrations and the tenancy module-flag migration are applied. Final migration drift check reported no changes.
- No connected browser was available. No production deployment, invitation delivery, or staging restore rehearsal was performed.
