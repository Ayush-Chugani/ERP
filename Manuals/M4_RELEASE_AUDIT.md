# M4 release audit

## Prompt sequence and traceability

| Prompt | Delivered evidence |
|---|---|
| 0 contract | M4_PROMPT_0_contract.md, declared public boundary |
| 1 domain review | M4_PROMPT_1_gap_analysis.md, M4_UPSTREAM_SCHEMA.md, approved ADR decisions |
| 2 scaffold | apps.py, registry, settings, tenancy activation, API namespace |
| 3 models | models.py, fields.py, migrations, SQL snapshots |
| 4 course services | services.py: allowlists, category semantics, parent/duplicate validation |
| 5 schemes | services.py and composition.py: immutable lifecycle, overlap, clone, version checks |
| 6 composition | marks/electives/credit totals, atomic bulk and reorder |
| 7 prerequisites | composite identity, bounded iterative graph validation and cycle detection |
| 8 authorization | policies.py, upstream adapter, queryset scoping and service checks |
| 9 API | api.py, urls.py, generated OpenAPI, metadata, exports, stable errors |
| 10 contracts | public.py, selectors.py, M4_QUERY_PLANS.md, transactional event records |
| 11 admin/audit | admin.py, bounded atomic audit, composite-key workflow exception |
| 12 UI | frontend/src/features/curriculum, form/workspace and component tests |
| 13 quality | backend tests, frontend tests, verify-module4.ps1, CI workflow |
| 14 rollout/review | M4_IMPLEMENTATION.md, M4_ROLLOUT.md, this audit |

## Invariant-to-test map

| Invariant | Automated evidence |
|---|---|
| SQL types/composite ownership/nonnegative/date checks | test_services.py, test_authorization.py |
| lifecycle/overlap/versioned clone and credits | test_services.py |
| partial bulk operations roll back including audit | test_services.py, test_authorization.py |
| graph cycles, long chains, DAG/diamond samples | test_concurrency.py |
| actual competing activation/duplicate creates/opposing edges | MySQL TransactionTestCase threads in test_concurrency.py |
| tenant, department, membership, module and record-limit negatives | test_authorization.py, test_api.py |
| hidden composition cannot authorize whole-scheme readiness/clone | test_services.py |
| explicit JSON, protected fields, stale headers and BIGINT serialization | test_api.py, frontend/tests/curriculum.test.tsx |
| admin service writes and bulk rejection | test_authorization.py |
| stable database errors outside rollback, audit failure rollback | test_authorization.py, test_services.py |
| bounded list query count, CSV formula neutralization | test_api.py |
| immutable public DTOs and scoped fake consumer calls | test_api.py, test_authorization.py |
| module/import boundaries | test_foundation.py |
| offline/capabilities/conflict/URL filters/decimal retention | frontend/tests/curriculum.test.tsx |

Factories explicitly construct institutions/campuses/departments/programmes/specializations, calendar semesters, roles and users in disposable MySQL test data. No assumption about production numeric IDs is needed. Denial scenarios are covered across service, API and admin layers; coverage percentage alone does not prove authorization completeness.

## Verification recorded 2026-09-20

- Full backend regression: 131 passed on MySQL, 80.54 seconds. Combined organization/tenancy/calendar/curriculum statement coverage 89.87% (80% gate).
- Django database checks and runtime-error lint passed; migration drift: no changes detected.
- OpenAPI validation with warnings treated as errors passed.
- Frontend Node checks: 12 passed. Initial full UI run hit one existing organization rendering timeout; retry passed all 16. Async rendering allowance raised from one to three seconds for shared CI CPU; no assertion removed.
- Additional prerequisite-removal and reorder-rollback tests and final UI/build checks are recorded below after completion.
- M4 query plans captured on MySQL 8.4.11 with temporary 100-course/20-scheme/100-mapping/99-edge fixtures, rolled back. Current-scheme index used; small course-list fixture chose a scan. This is not a high-volume performance claim.

## Architecture review and release disposition

Governed writes share services and transaction/audit behavior; private upstream ORM access is confined to declared adapters and relation definitions. Trusted list scope is applied before pagination; same checks protect exports and object writes. There are no duplicate authentication stores, unrestricted audit mutation endpoints or offline curriculum write queues. Global codes and category agreement reflect the approved decisions. Active structure is preserved through cloning.

Ready for local use and staging evaluation, subject to final checks below. Production release still requires browser/accessibility end-to-end acceptance, representative load profiling and a staging backup/restore rehearsal. Hosted CI and production deployment were not performed. Downstream registration, timetable and assessment integrations are contracts, not implemented consumers. The admin Semester adapter and some defensive error branches are not exercised by the full suite; real-browser navigation and pixel layout are not covered by jsdom.

These limitations are explicit release gates; this report does not certify production readiness or DBA-proof audit protection.

### Final checks

- Focused authorization suite: 9 passed, including two added regressions for prerequisite removal permission and reorder rollback/error translation. Together with the full run, 133 distinct backend tests have passed (the full run preceded these two additions).
- Final frontend UI: 16 passed; TypeScript `tsc --noEmit` and Vite production build passed.
- Regenerated final OpenAPI with explicit list/export query parameters: validation and warnings-as-errors passed. Final runtime lint passed.
- No production deployment or browser/staging acceptance was performed.
