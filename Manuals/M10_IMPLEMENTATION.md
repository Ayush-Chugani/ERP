# M10 Continuous Assessment and Results

## Implementation scope and defaults

Implemented in dependency order from M10-SIS_Module_10_Continuous_Assessment_Result_Prompt_Pack.docx. The DOCX lists the seven tables but omits their DDL; the relational baseline is section 10 of sims_v6_5_1_mariadb_full_schema.sql. The original manual is unchanged.

The implementation uses the recommended defaults presented during this session: immutable publication snapshots with a separate correction draft, half-open grade bands (lower inclusive, upper exclusive, with 100 included), and a publisher different from the evaluator/calculator. These are implementation defaults, not an assertion of institution policy approval. Operational activation still needs institutional sign-off.

No production grade scale, academic formula, result or mark is seeded. The global SIMS_ASSESSMENTS_RESULTS_ENABLED flag and per-institution assessments_results flag default false. M7/M8/M9 activation is unchanged.

## Prompt-to-artifact map

| Prompts | Implementation |
|---|---|
| 10.1 | backend/apps/assessments_results: models/, services/, selectors/, api/serializers/, api/views/, permissions.py, validators.py, admin.py, tests/, migrations/ |
| 10.2?10.7 | Seven source models with original identities/relationships/precision; additional policy, publication, audit and receipt tables |
| 10.8 | Explicit event conduct/cancel/publish/reopen, result calculate/publish/withhold/reopen commands |
| 10.9?10.10 | Current membership/module/scope permission checks, faculty roster restriction, strict command serializers, private versioned API |
| 10.11?10.14 | /#/assessments configuration, event/mark entry, course/term processing, student published results |
| 10.15 | Decimal policy primitives: weighted components, mean/best-of-N, reduced marks, mandatory components, special attendance, thresholds, grace, repeat selection, GPA/credits and visibility |
| 10.16 | Immutable audit with actor, authority, before/after, academic context, reason, correlation key; publication history |
| 10.17 | Existing FK/unique indexes plus offering/date/state index; scripts/m10_schema_report.py and generated SQL/query-plan reference |
| 10.18?10.21 | Calculation, MySQL service/API/ownership/privacy/rollback/concurrency tests and React/paste component tests |
| 10.22 | Migrations with no grade fixtures; scoped role preparation command; local verification and rollout instructions |

## Schema audit and changes

All seven source tables remain: assessment_component, assessment_event, student_assessment_mark, grade_scale, grade_rule, student_course_result, student_term_result. Original unique keys are retained. Native Django choices plus database checks represent workflow states; there are no destructive changes to an existing M10 table in the development database.

Migrations 0001?0004 create the M10 schema and ownership FKs. Tenancy 0009 adds its disabled module flag. Composite MySQL FKs enforce event/component/offering and mark/event/registration/offering ownership. The source unsigned TINYINT course-result attempt type is preserved, and attempts are bounded 1?255. The actual signed custom User key is reused for actors. Result marks remain Decimal(7,2), grade points Decimal(4,2), course credits Decimal(4,1), term credits Decimal(6,1), GPA Decimal(4,2).

Additions: grade_scale institution FK; immutable course-offering calculation policy revisions; event attempt, frozen roster and policy; actor/version fields; result evidence/state/withholding flag; immutable publication snapshots, audit and idempotency receipts. Calculation and publication are separate. Withholding persists through reopening until approved publication. Result identity remains one course registration/attempt or one term registration, while publication versions retain historical values.

Grade-scale names retain source-wide uniqueness. Use a distinct versioned name for a changed scale; do not mutate rules after use. Grade scales and their complete band set are created atomically. Bands must be contiguous over 0?100 without overlap. Used component structure is locked; new configuration needs a successor component/policy. Planned events may be edited; conducted/published structure is protected.

## Policy contract

Every policy explicitly supplies internal_weight and external_weight (total 100); minimum_internal and minimum_external; aggregation MEAN or BEST_N; positive best_n; ABSENT/EXEMPTED/MALPRACTICE behavior ZERO, EXCLUDE or BLOCK; rounding HALF_UP/HALF_EVEN/DOWN; repeat LATEST/BEST; gpa_statuses; credit_statuses; max_grade_point; grace; event_maximum EQUAL_COMPONENT/INDEPENDENT; failure_grade identifying a FAIL rule; and boolean show_marks for student visibility.

No executable formula input is accepted. All academic arithmetic uses Decimal. Events normalize raw or reduced marks to percentages, components aggregate them and apply explicit weights, and course results combine internal/external percentages with explicit weights. Internal/external/total result fields in this implementation are normalized marks out of 100, not sums of heterogeneous raw maxima. External percentage is an authorized result-cell input retained in audit/publication; integration with a separate external-exam system is not configured.

Reduced marks are derived proportionally with the frozen rounding policy; inconsistent user-supplied reductions are rejected. Special attendance retains its explicit mark status and requires null raw/reduced marks. ZERO contributes zero; EXCLUDE removes that event from averaging; BLOCK refuses result calculation. A mandatory component without countable evidence blocks calculation. Component weights must total 100. Threshold failures use the explicitly configured failing grade, even when the total percentage falls in a higher band. Grace is a configured percentage addition capped at 100 and never bypasses minimum internal/external thresholds.

Grade resolution uses the exact pre-display-rounding percentage. For example, bands [0,50) and [50,100] assign exactly 50 to the latter. GPA uses credit-weighted published grade points with configured status inclusion. Zero countable credits gives null GPA. Credits are frozen from the course catalog at calculation. Repeat attempts select latest or best according to the frozen policy; cumulative repeated courses are deduplicated by catalog course within one programme enrolment. Incompatible GPA/attempt policies block calculation instead of silently mixing scales. Audit and credit-transfer registrations fail closed until an approved programme-specific extension is supplied; they are not assumed to earn standard credits.

## Workflows and API

Canonical namespace /api/v1/assessments/ matches existing module-oriented APIs. This deliberately consolidates the prompt's example top-level endpoint names.

GET offerings/, components/, events/, policies/, scales/, grades/, registrations/, terms/, course-results/, term-results/, audit/; events/{id}/marks/; mine/; reports/{mark-sheet|exceptions|grade-distribution}/; export/{course-results|term-results}/. GET lists paginate, and offering_id filters apply to offering-owned resources. Mark-sheet/exception reports require event_id. Student mine/ ignores client student IDs and resolves the verified account link.

POST commands/{operation}/ accepts configure-scale, configure-policy, component, create-event, update-event, transition-event, mark, calculate-course, calculate-term, transition-result. Every command requires Idempotency-Key, reason, and relevant expected_version/expected_number. POST bulk/ accepts 1?100 {operation,data} commands and commits all or none. Wrong-state/stale/digest conflicts return 409; invalid fields/rows return 400; unavailable scoped objects return 404. Unknown writable fields are rejected.

A conducted event freezes its eligible course-registration roster. Faculty see/mark only students on their date-valid M7 section roster and assigned M8 faculty allocation. Publication requires all event roster members evaluated, current registration eligibility, and a reviewer different from each evaluator. Event versions serialize marks and lifecycle changes. Reopening an event preserves its last published snapshot while a new evaluation is reviewed.

Course calculation requires all noncancelled attempt events published under one policy and all mandatory evidence. Result publication revalidates exact event/mark versions and credit evidence. A changed source cannot publish an old calculation. Term calculation consumes authoritative published course snapshots, including prior terms for cumulative GPA. Term publication verifies source publication identities again. Previous published values remain available while a correction draft exists; explicit withholding hides values, including dependent term results, immediately.

## Authorization and privacy

| Persona | Permissions and authority |
|---|---|
| Assigned faculty | view_assessment and mark_assessment; active verified employee, dated allocation and student roster, enabled institution/module, scoped TEACHER grant |
| Coordinator | view/configure_assessment; administrative institution/campus/department scope |
| Result cell | view/calculate/export_assessment; scoped administrative authority |
| Reviewer | view/publish/correct_assessment; scoped administrative authority and evaluator/calculator separation |
| Student | Verified student AccountLink, active membership and enabled institution; own published snapshots only |
| Superuser | Existing platform scope bypass; global M10 switch and separate-review rule still apply |

Group names do not grant scope. seed_assessment_roles prepares permissions but assigns no users/memberships. Record allowlists restrict, never expand, ownership. Unsupported or partial scopes fail closed. Students cannot read audit/internal remarks/evidence. show_marks=false omits internal/external/total values from the student API; unconfigured visibility never defaults to disclosure. API responses are private/no-store; existing PWA rules keep API/admin requests NetworkOnly. No offline mark persistence or background synchronization is provided.

Django admin is inspection-only. Evidence immutability is enforced in application managers and commands, not against a privileged DBA; use least-privilege operational database credentials and controlled backups.

## Frontend

The staff workspace provides offering/event selectors, locked-state feedback, accessible mark inputs, sticky identity cells, explicit unentered status, atomic save, stale errors, unsaved-change protection, reason fields and offline disabling. Paste accepts at most 500 tab-separated rows mapped by student number, rejects unknown/duplicate students, formula-like numeric input and oversized remarks, and displays a review before submission. Publication and withholding require a confirmation dialog. Calculation never happens on page load.

Configuration forms cover components/events/scales/policies and explicit course/term calculation. Result lists expose individual and selected atomic publication plus withholding/reopening. Student self-service shows published course/term outcomes without staff remarks. Lists currently cap at 100 with an explicit overflow message; use narrower scope/API pagination for larger workspaces. CSV result exports are permission checked and formula escaped. XLSX/PDF exports and a production transcript template are not enabled without an institutional format/policy.

## Operations and verification

Run from repository root:

- powershell -ExecutionPolicy Bypass -File scripts/verify-module10.ps1
- backend/.venv/Scripts/python.exe backend/manage.py assessment_batch mapped.json --actor ID --key SOURCE-BATCH: dry-run 1?100 explicitly mapped commands, max file 1 MiB. Add --apply to commit. Retain stable keys and source evidence; failures roll back the entire batch. Dry-run IDs are provisional and rolled back.
- backend/.venv/Scripts/python.exe backend/manage.py assessment_health --actor ID: scoped unpublished/withheld counts and stale/unresolved calculation findings.
- backend/.venv/Scripts/python.exe backend/manage.py seed_assessment_roles: prepare groups without user assignments.
- backend/.venv/Scripts/python.exe backend/manage.py shell -c "exec(open('scripts/m10_schema_report.py').read())": record actual MySQL DDL and representative EXPLAIN plans.

The verification script checks database/system configuration, migration drift, isolated MySQL tests including M6?M10/core regression, OpenAPI validation, frontend tests and TypeScript/Vite/PWA build. Genuine separate-connection tests race marks/publication and result publication. Other tests cover raw composite FK ownership, missing evaluations, grade boundaries, nonfinite values, Decimal/best-of-N behavior, separate review, rollback, idempotency, disabled APIs, student privacy, faculty scope/revocation, stale results and persistent withholding.

Bounded reads currently use object authorization for some faculty/result scopes: 2,000 event/term records, 5,000 course registrations, 1,000 student results. This prioritizes correctness but can issue many queries. Representative EXPLAIN output on an empty development database is not a populated load benchmark; production query budgets and pagination refinements remain a pilot acceptance gate. Requests are throttled to 120 per user/minute; exports cap at 10,000 records.

## Rollout and rollback

Keep global and institution flags off while deploying additive schema and code. Inspect migrate --plan and back up/restore-rehearse the target before production migrations. Apply Django migrations, not only generated SQL. No official grade or formula values were supplied, so do not seed test fixtures into operational tables.

Before a pilot: approve the scale/boundaries, policy version, date effectiveness, source credit interpretation, special attendance, repeat/GPA rules, student visibility and reviewer separation; configure memberships/permissions; validate M7 registrations and M8 allocations; reconcile sample source marks and expected totals. Verify four personas, keyboard/mobile behavior, paste preview, stale conflicts, course/term correction chains, withholding and exports in a browser. Rehearse backup restoration and application downgrade with flags off. Only then enable an approved pilot institution.

Operational owners: academic/result cell approves formula and grading; registrar owns enrolment/credit reconciliation; faculty owns mark evidence; reviewer owns publication/withholding; platform operations owns migration/backups/availability. Alert on unresolved inputs, due conducted events without publication, unexpected authorization failures, conflict spikes and stale term snapshots following course corrections. assessment_health supplies local diagnostics; no external monitoring or notification transport has been configured or contacted.

Emergency: disable M10 globally to stop its API workflows; preserve marks and publication evidence. For read-only operation, remove write permissions while retaining view. Application rollback leaves additive tables intact. Do not reverse data-bearing M10 migrations without an approved restore/retention plan; MySQL DDL is not an atomic multi-migration rollback.

## Explicit remaining acceptance gates

This is a local implementation, not production certification. No official grades/formulas, legacy source records or external-exam provider were supplied. Browser E2E/accessibility acceptance, populated-dataset load measurements, staging restoration, official export formats and institution pilot sign-off remain outstanding. The M7 eligibility adapter remains unchanged: do not wire academic progression to these results until the institution approves that integration contract.

## Verified local results ? 2026-09-23

- Combined M6?M10/core MySQL regression suite: 147 passed. After final policy/privacy/read refinements, focused M10 suite: 33 passed (overlaps the combined run; not additive).
- Frontend: 36 tests passed across nine suites. Two earlier legacy-suite timeouts under parallel resource load were resolved by limiting Vitest to two concurrent workers, without relaxing assertions or timeouts.
- TypeScript, Vite and PWA build passed. OpenAPI generation passed validation with warnings treated as failures. Django database/system checks passed; no migration drift.
- Applied local migrations assessments_results 0001?0004 and tenancy 0009 to sims_reference_dev.
- Verified M10 global flag false, zero enabled M10 institutions, zero grade scales, zero calculation policies, zero marks and zero course results. M9 remains disabled.
- Actual DDL and representative indexed EXPLAIN plans: M10_SCHEMA_AND_QUERY_PLANS.md. Migration SQL reference: M10_reviewed_migration.sql. Plans use an empty development database and do not certify production performance.
- No production deployment, operational activation, external messages or real academic-data import occurred.
