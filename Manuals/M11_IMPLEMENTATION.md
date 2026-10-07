# M11 Feedback implementation and release runbook

Implemented locally on 2026-09-23 after the M10 assessment/result implementation and regression verification. Source: `Prompts/M11-SIS_Module_11_Feedback_Implementation_Prompt_Pack.docx`. The source DOCX and reference SQL are unchanged. This document records implementation choices; it is not institutional approval to publish feedback or activate modules.

## Sequential prompt handoff

| Prompt | Delivered implementation |
| --- | --- |
| 1 Skeleton | `backend/apps/feedback`, installed app, `/api/v1/feedback/`, registry, global and institution flags |
| 2 Models | Eight baseline entities, explicit response types, unsigned baseline keys, custom-user administration fields |
| 3 Migrations | `feedback/0001_initial`, `tenancy/0010_institutionmodule_feedback`; additive tables, constraints and indexes; isolated MySQL rollback/forward test |
| 4 Bank | Scoped category/question/choice commands, validation, optimistic versions, administrative idempotency and audit |
| 5 Authoring | Ordered unique items, required flags, optional weights, readiness, activation, retirement and cloning |
| 6 Cycles | SCHEDULED/OPEN/CLOSED/CANCELLED transitions; immutable snapshot on open; explicit window, threshold and policy |
| 7 Eligibility | Existing M7 term/course/roster records and M8 faculty assignments; server-derived targets; no upstream writes |
| 8 Privacy | Keyed deduplication ledger separate from anonymous answers; independent receipts; fail-closed key changes |
| 9 Submission | Atomic typed validation and answer writes, exactly one logical submission, retry-safe receipt, concurrency locks |
| 10 API | DRF command/read APIs, bounded pagination, generated OpenAPI, protected CSV and text-review endpoints |
| 11 RBAC | Custom User permissions plus active institutional memberships and scope grants; student and own-faculty boundaries |
| 12 Reporting | Closed-cycle fixed-target aggregates, cohort/item/bin suppression, explicit score normalization and optional weights |
| 13 UI | React/TypeScript/MUI bank, builder, cycle controls, student questionnaire, faculty/admin aggregate dashboard |
| 14 PWA | Online-only mutations, existing API NetworkOnly policy, no answer persistence or background submission queue, retry keys and confirmation |
| 15 Tests | MySQL service, migration, model, validation, privacy, query-budget and concurrency tests; frontend submission tests |
| 16 Operations | Structured administration logs, append-only audit, `feedback_tick`, `feedback_health`, role seeding, schema/query report |
| 17 Integration | Combined regression script, local additive migration, disabled rollout, this runbook and explicit production acceptance gates |

## Ownership and schema decisions

M11 owns feedback data only. It reads organization, calendar, custom-user/account links, M7 registrations/section membership and M8 faculty assignments. M10 is verified but feedback does not mutate assessment results. No duplicate student, employee, course or academic-term tables were introduced.

Baseline table names are preserved. `feedback_response_item_choice` supplies multiple-choice selections: a Django surrogate primary key plus a unique item/choice constraint replaces a composite primary key without weakening uniqueness. Additional `platform_m11_ledger`, `platform_m11_audit` and `platform_m11_command` tables separate submission deduplication, administrative history and administrative retries. Foreign keys protect retained history. The baseline is extended with institution ownership, questionnaire lifecycle, explicit rating/text policy, programme targeting, frozen cycle snapshots, minimum cohorts and record versions. Runtime application services validate cross-table ownership and answer types; database constraints supplement these checks. Direct database writers must not bypass these services.

Activated questionnaires cannot have their content edited. Clone to a new draft for revisions. Cycle opening snapshots question text, type, choices, scoring and required status. Later bank deactivation does not rewrite an open or historical questionnaire. Closed cycles do not reopen.

## Target and policy contract

- COURSE: approved/completed registration in the cycle term and selected course offering.
- FACULTY: approved/completed registration and dated section-roster overlap with the selected M8 faculty assignment.
- PROGRAMME: explicit programme scope and an eligible registration in that programme.
- INSTITUTION: eligible registration in the institution/term, optionally narrowed to a programme.
- EXIT: completed enrolment (`COMPLETING` policy).
- OTHER: explicit vetted term-registration IDs (`EXPLICIT` policy), validated against institution, term and optional programme.

Other cycle types use `ENROLLED`. Only linked students submit in this implementation. Arbitrary respondent IDs, arbitrary targets and staff/guest submissions are rejected. Faculty see their own assignment results only, with permission, active account linkage and valid scope. Institution-level bank authoring requires an unrestricted institution administrator grant; campus/department coordinators can schedule active templates for programmes within their grants. Superusers follow the existing platform administrative bypass, but still need the global feature enabled.

The institution must supply rating minimum/maximum/step, text limits, question weights (if used), cycle window, result visibility, minimum cohort and text-review policy. No production questionnaire, cohort threshold, rating scale or feedback response is seeded. The structural minimum cohort is two, not a recommendation that two is a sufficient institutional privacy standard.

## Anonymity and reporting

Anonymous response rows have a null term-registration reference. The ledger stores an HMAC of cycle, stable student identity and logical target, an HMAC of retry request content, and an independently random receipt. It has no response foreign key, answer ID, response token or timestamp. The response token is not exposed in a receipt or API. Submission events deliberately do not create an actor-bearing audit trail. Administrative actions and protected export/text review are audited.

The privacy key must be a persistent random secret of at least 32 characters, backed up separately with controlled access. An open cycle retains a key fingerprint; changing the key rejects new submissions rather than permitting duplicates. Retain the correct key until cycle completion. Do not expose it in logs or source control. Anonymous content can still identify its author through free text; the UI warns against this. Database operators, infrastructure telemetry and timing correlation remain part of the institutional threat model. Application-level separation is not a guarantee against a privileged database/operator adversary.

Aggregates are available only after closure, for fixed cycle/target cohorts. HIDDEN returns no results. PUBLIC is a deliberate unauthenticated aggregate-only endpoint and still requires the institutional feature enabled. Whole cohorts below the threshold suppress counts and questions. Individual items suppress small answer/missing-answer complements; choice/rating distributions suppress when a nonzero bin is below the threshold. No arbitrary filters, date slices, raw respondent lists or response-token lookup APIs are provided. Eligible population and response rate remain null when no reliable denominator exists.

Rating scores normalize from explicit bounds to 0-100. Choice scores normalize against the configured choice-score range. Multiple-choice normalized scores average selected scores per respondent; option percentages count respondents selecting each choice and may sum above 100%. Weights are normalized by their positive sum. Text cannot carry a positive weight. A weighted score is withheld if any positively weighted item is suppressed or unscored. Text never appears in public/faculty aggregates or ordinary CSV. Separately authorized text review requires an explicit cycle opt-in, closed visible cycle, administration permission and suppression checks, and is audited; free text is not automatically anonymized.

## API and user interface

All paths are under `/api/v1/feedback/`. See `backend/openapi.yaml` for generated contracts.

- `commands/bank/`, `commands/items/`, `commands/questionnaire-action/`, `commands/create-cycle/`, `commands/cycle-action/`: POST, reason, optimistic version when updating, and `Idempotency-Key`.
- `categories/`, `questions/`, `choices/`, `questionnaires/`, `items/`, `cycles/`, `institutions/`, `programmes/`, `terms/`, `audit/`: scoped bounded reads.
- `available/`, `cycles/{id}/questionnaire/`, `cycles/{id}/submit/`: student workflow with server-derived target and final confirmation.
- `questionnaires/{id}/readiness/`: author readiness check.
- `cycles/{id}/targets/`, `cycles/{id}/results/`, `cycles/{id}/export/`, `cycles/{id}/text/`: authorized reporting.
- `public/cycles/{id}/results/?target=...`: published fixed-target aggregates only.

The application route is `/#/feedback`. No answer is written to localStorage, IndexedDB or an offline queue. Losing the page loses unsent answers. A repeated identical request retains its idempotency key; a successful retry returns the original independent receipt. All feedback responses are no-store; authenticated requests vary by credentials. The UI bounds administrative selectors to 100 records and asks for narrower scope/API pagination above that bound. Available targets are bounded, with no hidden truncation represented as complete coverage. Large institutional deployments should add paginated selector search before exceeding those limits.

## Verification and local migration

Run from repository root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-module11.ps1
backend/.venv/Scripts/python.exe backend/manage.py migrate --plan
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py shell -c "exec(open('scripts/m11_schema_report.py').read())"
```

The verification script checks the isolated test database name, rebuilds only that test database, runs M6-M11 and core regressions, checks migration drift, validates OpenAPI, runs UI tests and builds TypeScript/PWA assets. Fresh test database creation is intentional because rolled-back fixtures consume small unsigned auto-increment sequences. Do not run database test rebuilds concurrently. The rollback test runs only against the isolated test database and restores forward migrations afterward.

Recorded combined baseline: 180 backend tests and 39 frontend tests passed; Django checks, migration drift, OpenAPI validation and frontend production build passed. Final M11 run: 30 tests passed, including scoped coordinator lookup/revocation and simultaneous cycle close/submission (the earlier combined run included 28 M11 tests). A live browser connection was attempted through the browser skill; no browser was available. UI component tests do not replace browser acceptance. `M11_SCHEMA_AND_QUERY_PLANS.md` records local DDL and EXPLAIN evidence; empty-database plans do not prove production load capacity.

## Rollout and operations

Keep `SIMS_FEEDBACK_ENABLED=0` and institution `feedback=False` until acceptance. Configure `SIMS_FEEDBACK_PRIVACY_KEY` securely before opening any cycle. The example environment file documents these variables without containing a usable key. M10 remains independently disabled; this implementation does not certify its remaining policy/pilot gates.

1. Back up the application database and securely preserve the privacy key. Test restore on a separate staging instance; retain both schema and key configuration.
2. Apply additive migrations in staging; verify actual MySQL/MariaDB version, DDL, unsigned foreign keys, collation and rollback/forward behavior on that engine. Local automated tests use the project's MySQL container, not a separate MariaDB certification.
3. Run `manage.py seed_feedback_roles` if desired. This creates capability groups only; assign approved operators/students/faculty and active scope grants separately. Do not assign broad roles automatically.
4. Obtain approval for target population, anonymity explanation, minimum cohort, scales/weights, visibility (especially PUBLIC), text access and retention. Use synthetic data to test cross-institution isolation and own-faculty access in a browser.
5. Enable one pilot institution and the global flag; create a questionnaire draft, validate readiness, activate, schedule and open a cycle. Test duplicate clicks, dropped-network retry, service-worker update, mobile keyboard and accessibility with real browsers.
6. Schedule `manage.py feedback_tick --actor <operator-id>` using a dedicated approved scoped operator. Reads never open/close cycles. Run `manage.py feedback_health --actor <operator-id>` to detect overdue transitions. Monitor scheduler failures and application-level 400/403/404/409/429 counts without request bodies, respondent identifiers or receipt/answer correlation. Disable request-body tracing for submission endpoints at proxies/APM.
7. Close the pilot, review suppression and aggregate arithmetic, verify faculty scopes, protected CSV and separate text-review access. Test populated reporting and concurrent submissions against institutional volume before wider rollout.

The scheduler handles at most 500 scoped cycles per invocation; partition operators/scopes or extend pagination for larger backlogs. Submissions/admin commands currently share an existing governance lock to serialize permission-sensitive operations; measure throughput before high-volume rollout. Reports bound response items to 50,000 and fail explicitly beyond the bound; move large cohorts to reviewed batch aggregation rather than removing bounds blindly. Built-in per-user/anonymous throttles require a shared production cache and correct proxy configuration to be consistent across workers.

Emergency containment: turn off the global flag, disable the pilot institution flag if appropriate, and stop the scheduler; preserve existing answers and audit. Prefer forward fixes. A database migration rollback deletes M11 tables and is destructive once data exists; never use the test rollback recipe on populated production data. Responses, ledger and audit are append-only in application code. No automatic retention purge is installed: approve a retention/export/legal-hold procedure and a reviewed maintenance mechanism before collecting real responses. Reconcile counts and the privacy key after restore before reopening service.

## Remaining release gates

Institutional policy approval; real-browser and accessibility acceptance; populated load testing including governance-lock contention; staging backup/restore; verification on the deployment database engine; and production logging/retention review remain outstanding. The module is implemented and locally verified, not activated or production-certified.


## Final local state

Both M11 migrations applied successfully to `sims_reference_dev`. Post-migration checks found no pending migrations, no model drift and no Django database check issues. OpenAPI validation passed after the final scope changes. M11 and M10 global flags are false; zero institutions have feedback enabled, and there are zero feedback cycles/responses. No operational privacy key, real response data or production activation was introduced.
