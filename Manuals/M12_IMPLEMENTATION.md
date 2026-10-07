# M12 implementation contract

## Prompt 0: boundary, dependencies and invariants

The student_support app owns only mentor_assignment, counselling_session, grievance_category, grievance and grievance_action. Student, Employee, AccountLink, Department, Membership, ScopeGrant and ReferenceAuditEvent remain authoritative external dependencies. Interfaces call services/selectors; services call policies/models and the central audit adapter. Models never import interfaces.

All five canonical tables retain exactly the supplied columns, types, ENUM strings, nullability, defaults, uniqueness and foreign keys. No convenience ID, version, timestamp, actor column, extra index or constraint is added. grievance_action has no actor FK: central audit metadata records the authenticated custom user and action-row ID atomically, without narratives. Application validation supplies date and workflow invariants that the SQL does not enforce. Schema-preserving adoption validates existing tables before using them; no blanket fake migration.

Policy points: overlapping active mentors allowed (user selected), configurable per institution; student access is limited to their own NORMAL notes, with explicit view capability (user selected option 2); assignment-window enforcement explicit; completed session notes optional; future completion forbidden; follow-up date required and not before session date; no grievance reopening; resolved grievances preserve resolution on closure, rejected grievances carry rationale in protected action history and no resolution timestamp. Routing is department-only because no employee assignee field exists. Category administration is platform-wide because the canonical table has no institution ownership. Grievance numbers use a configurable prefix plus random collision-resistant identifier and bounded uniqueness retries, not MAX+1.

Authorization uses existing custom-user capabilities and active membership/scope grants. Assigned mentors receive no implied grievance access. Counselling levels require independent explicit capabilities. Student grievances derive ownership from AccountLink; staff routing must satisfy both old and new department scopes. Sensitive reads are audited using central metadata. Global feature and institution-ID allowlist settings default disabled/empty, avoiding additional database columns.

Risks: privileged database access, free-text identification, broad audit-reader access to metadata, legacy data violating application invariants, database ENUM/unsigned adoption fidelity, and workflow races. No confidential content is sent to notifications, logs or dashboards. Production acceptance requires approved access/retention policies, restore rehearsal and real-browser checks.

## Prompt 1: implementation sequence and file responsibilities

Follow prompts 0-17 in source order: contract; scaffold; models; policies; authorization; mentoring; counselling; categories/numbering; grievances; serializers; API; safe staff UI/admin; selectors/reporting; migrations; tests; operations; integration; release review.

- apps/student_support/apps.py: Django app registration.
- fields.py and models.py: exact canonical persistence mappings, with native MySQL field types.
- policies.py: configurable institutional decisions and explicit state vocabularies.
- permissions.py: centralized identity resolution and object/confidentiality scopes.
- audit.py: narrative-free adapter to existing ReferenceAuditEvent.
- services.py: locked, transactional workflow commands.
- selectors.py: scoped summaries, privileged detail and aggregate metrics.
- api/serializers.py, views.py, urls.py: strict use-case contracts and thin HTTP adapters.
- admin.py: disable generic mutation; read-only scoped administrative summaries.
- migrations/: verified canonical DDL adoption and Django state.
- tests/: mapping, services, privacy, API, rollback, concurrency and query budget evidence.
- frontend/src/features/student-support/StudentSupportApp.tsx: authorized staff/student workflows.

No new authentication, audit or notification store is introduced. No institution-specific category seed is invented.


## Delivered prompt map

| Prompt | Result |
| --- | --- |
| 0-1 | This contract, cohesive student_support app, directional dependencies and registry |
| 2 | Exact five-table model mappings; native ENUM/TEXT/DATETIME and unsigned auto keys |
| 3 | Named per-institution policies, date checks and explicit transition vocabulary |
| 4 | Existing capabilities/membership/scope authorization, explicit identity resolvers, narrative-free central audit |
| 5 | Assign, end, cancel, historical queries and atomic mentor change |
| 6 | Schedule, complete, cancel, reschedule, follow-up and privileged confidentiality changes |
| 7 | Platform-scoped category commands; configurable-prefix random numbering with bounded duplicate-key retry |
| 8 | Submit, department route, review, resolve, reject and close with locked state checks and append-only history |
| 9-10 | Strict per-use-case serializers, paginated scoped APIs, protected detail, throttling and generated OpenAPI |
| 11 | React staff/student workspace and read-only Django admin without narrative fields or workflow writes |
| 12 | Authorized mentoring/session history, due follow-up filter, submission-date grievance queue and minimized reports |
| 13 | Verified canonical DDL creation/adoption with data-retaining reverse; no invented category seed |
| 14 | Workflow, schema, permissions, IDOR, rollback, races, API/admin and frontend tests |
| 15 | Central atomic audit, low-cardinality operation outcome/timing logs, scoped health command; no narrative notifications |
| 16 | Existing People AccountLink and Student/Employee/Department relationships, inactive-person archival behavior |
| 17 | Combined verification script, schema report and operational release review below |

## Persistence and migration behavior

`student_support/0001_initial.py` uses SeparateDatabaseAndState. The database operation executes the canonical SQL frozen in `_canonical.py`; the state operation registers faithful Django models. No additional table, domain column, index or CHECK constraint is introduced. Existing rows are not rewritten. Foreign keys use their canonical RESTRICT/NO ACTION behavior. The Django model default for counselling status remains COMPLETED, as in SQL, while the schedule service explicitly creates SCHEDULED rows.

Before adoption, the migration compares column types (including exact ENUM literals), nullability, defaults, auto-increment, primary/unique/foreign-key indexes, FK targets/actions, engine and collation. All existing tables are checked before creating missing tables. A mismatch stops migration and needs a separately reviewed reconciliation; do not fake migration to bypass it. MySQL DDL is nontransactional: after an interrupted installation, reapply to verify/adopt already-created canonical tables and complete missing ones.

Reversing M12 removes its Django migration state but deliberately retains all five tables and all data. Reapplying verifies and adopts them. This safe reverse is tested; it is not a purge. Retained foreign keys mean upstream schema rollback must be planned separately. No automatic data deletion, retention job, soft-delete column or unapproved composite index is supplied. Manual destructive removal requires an approved backup and retention decision.

See `M12_SCHEMA_AND_QUERY_PLANS.md` for column-by-column mappings and local SHOW CREATE TABLE/EXPLAIN evidence. The source DOCX and shared manual SQL remain unchanged.

## Authorization contract

All endpoints require existing authentication. Global `SIMS_STUDENT_SUPPORT_ENABLED` defaults to 0. Non-superusers additionally need active membership in an active institution present in `SIMS_STUDENT_SUPPORT_INSTITUTIONS`. Scope grants restrict campus/department administrative capabilities. Unrecognized record-limited grants fail closed; support-specific allowlists were not added to the platform schema. Global superusers have the existing platform administrative bypass after the global flag is enabled; privileged narrative reads are still audited.

- Students submit through the own-grievance endpoint; AccountLink determines student identity. Payload student IDs, workflow status and resolution fields are rejected. They can read their own grievances with the read capability and active membership; non-ACTIVE students retain authorized historical reads but cannot submit new grievances.
- Assigned active employee mentors can see their mentoring relationships and conduct counselling only with explicit conduct/read-level capabilities. A mentor relationship grants no grievance access.
- NORMAL, RESTRICTED and HIGHLY_RESTRICTED each require their own view capability. Level permissions do not imply other levels. A student's relationship allows only their own NORMAL sessions when student_normal_notes is enabled. NORMAL notes still require view_counselling_normal.
- Broader counselling officers need view_counselling_all plus the relevant level capability and scope; mutations also need conduct_counselling. Confidentiality changes need change_counselling_confidentiality and permission for the new level. Access to both the existing and destination level is checked.
- Staff grievance permissions are separate for queue reading, triage/rejection, resolution, closure and aggregate reports. Routing checks both existing and destination scope. Unrouted grievances are available to institution-wide officers, not department-only staff.
- Category data are global in the supplied SQL. Category maintenance therefore requires manage_grievance_categories plus platform-access authority (or superuser); institutional membership alone does not grant global master-data administration.

`seed_support_roles` creates capability groups without assigning users or scopes. The Support Student group includes the user-approved NORMAL-note capability. Support Mentor does not include HIGHLY_RESTRICTED or grievance access. Assign roles deliberately; group creation does not activate the module.

## Workflow and policy decisions

| Entity | From | Action/result |
| --- | --- | --- |
| Mentor | ACTIVE | end -> COMPLETED; cancel -> CANCELLED; change -> end old then create new |
| Counselling | SCHEDULED | complete -> COMPLETED; follow-up -> FOLLOW_UP_REQUIRED; cancel -> CANCELLED; reschedule preserves status |
| Counselling | COMPLETED | follow-up -> FOLLOW_UP_REQUIRED |
| Counselling | FOLLOW_UP_REQUIRED | complete -> COMPLETED, clears outstanding follow-up date |
| Grievance | SUBMITTED | ASSIGNED, UNDER_REVIEW, REJECTED |
| Grievance | ASSIGNED | UNDER_REVIEW, RESOLVED, REJECTED |
| Grievance | UNDER_REVIEW | RESOLVED, REJECTED |
| Grievance | RESOLVED or REJECTED | CLOSED |
| Grievance | CLOSED | no further transitions |

No employee assignee is invented for a grievance; ASSIGNED means department routing. No reopen, arbitrary PATCH, bulk assignment or historical deletion endpoint exists. Mutations require the client's expected current status and acquire row locks. Shared governance locking serializes permission-sensitive operations with existing modules. Grievance creation and each transition insert an action and a central actor audit in the same transaction; any history/audit failure rolls back state.

Approved defaults: overlapping ACTIVE mentor date ranges are allowed; student NORMAL notes are readable only under the capability/ownership conditions above. Configure per institution with JSON, for example:

```text
SIMS_STUDENT_SUPPORT_POLICIES={"12":{"allow_overlapping_mentors":true,"student_normal_notes":true,"student_assignment_read":true,"session_within_assignment":true}}
```

These policy values must be JSON booleans. Assignment date ranges are inclusive; mentor change ends the original on the day before the replacement begins. Backdated assignments are accepted when valid. Sessions must fall within assignment dates by default; the explicit session_within_assignment policy can change this. Scheduling requires active assignment, student and employee. Future sessions cannot be completed. COMPLETED notes are optional; FOLLOW_UP_REQUIRED needs a follow-up date on/after the session date. Confidentiality defaults to RESTRICTED.

Resolution requires nonblank resolution and sets resolved_at atomically. Closing a resolved record preserves both. Rejection requires protected action rationale, leaves resolution/resolved_at null, and closure preserves that history. No SLA rule is invented. Numbering uses the configured 1-5 character uppercase alphanumeric/hyphen prefix plus 24 random hexadecimal characters, within VARCHAR(30), and retries unique collisions up to five times. It is not a chronological institutional sequence.

Narratives are plain text, rendered escaped by React. API text contracts bound characters; service validation additionally caps UTF-8 bytes below MySQL TEXT capacity. No rich HTML execution is supported.

## API and staff interface

Route: `/#/support`. API prefix: `/api/v1/support/`. See `backend/openapi.yaml` for request fields and enums.

| Method/path | Purpose |
| --- | --- |
| GET assignments/, assignments/{id}/ | scoped relationship/history reads; student_id/employee_id/status filters |
| POST assignments/create/ | assign mentor |
| POST assignments/{id}/end/, cancel/, change/ | explicit lifecycle commands |
| GET sessions/, sessions/{id}/ | scoped summaries and separately authorized/audited narrative detail |
| POST sessions/schedule/ | schedule counselling |
| POST sessions/{id}/complete/, follow-up/, cancel/, reschedule/, confidentiality/ | explicit counselling commands |
| GET categories/, category-admin/ | active submission choices / privileged complete category list |
| POST categories/create/, categories/{id}/edit/ | global category maintenance |
| GET own-grievances/, own-grievances/{id}/ | student-owned summaries/detail |
| POST own-grievances/submit/ | server-derived ownership |
| GET grievances/, grievances/{id}/, grievances/{id}/history/ | authorized queue/detail and paginated protected action notes |
| POST grievances/{id}/assign/, review/, resolve/, reject/, close/ | explicit state transitions |
| GET students/, employees/, departments/ | minimal scoped form choices |
| GET reports/ | authorized aggregate report, optional submitted_from/submitted_to |

Lists use bounded platform pagination (25 default, 100 maximum). No narrative search/order/export is provided. Lists omit descriptions, resolutions and counselling notes; protected detail rechecks authorization. Student/employee/department form selectors are bounded to 100 choices and fail visibly if more exist; large pilots should add scoped paginated picker search rather than silently dropping choices. History API is paginated; UI shows the first 100 entries and explicitly reports more entries. API authentication/CSRF behavior is inherited from the existing platform; generic admin writers are disabled.

Reports group authorized grievances by current status/category/department and filter by submission date. Mean turnaround uses submitted_at to resolved_at for records with a resolution timestamp, including subsequently closed resolved grievances. No narrative or student identifier is included, and no metric is labeled an SLA breach. Due follow-ups use institution display-date settings via Django localdate. The health command only prints scoped counts.

## Audit, logs and offline behavior

ReferenceAuditEvent is reused without schema changes. Its existing create/update action vocabulary is retained; `after.event` supplies the precise M12 operation (including read events). Metadata contains actor FK, target type/ID, central timestamp, generated request correlation, previous/current state or level, and linked grievance_action ID. It never contains observations, action_plan, subject, description, resolution or action notes. Actor identity is intentionally absent from grievance_action itself.

Operational logs contain operation name, success/failure and duration_ms; number collision logs contain only event type. Do not add record IDs as metric labels or send request/response bodies into APM. No outbound notifications are installed or sent. Any future notification must contain only minimal status/scheduling metadata and an authenticated link. Review central audit-reader permissions because even narrative-free access metadata is sensitive.

API responses use private,no-store with credential Vary headers. Existing PWA API NetworkOnly behavior is retained. Forms keep drafts only in memory, warn before page unload, require explicit confirmation, and block offline writes. There is no background retry/offline queue. A transport failure is ambiguous: refresh records before retrying a create operation. Identical grievance submissions are not automatically deduplicated because the canonical schema has no request-key store; random number uniqueness and locked workflow transitions are enforced.

## Operations and release gates

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-module12.ps1
backend/.venv/Scripts/python.exe backend/manage.py migrate --plan
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py shell -c "exec(open('scripts/m12_schema_report.py').read())"
# Optional capability groups; these commands do not assign users or activate anything.
backend/.venv/Scripts/python.exe backend/manage.py seed_support_roles
backend/.venv/Scripts/python.exe backend/manage.py support_health --actor <approved-operator-id>
```

Before real use: back up and restore a staging copy; verify canonical schema compatibility on the deployment engine; approve access, archival and retention policy; assign explicit capabilities/memberships/scopes; configure institution allowlist; then enable a single pilot. No categories are seeded: a platform administrator supplies approved codes/names. M11 stays independently disabled until its own remaining acceptance gates are met.

Containment is configuration-only: set SIMS_STUDENT_SUPPORT_ENABLED=0 and remove institution IDs from the allowlist; keep tables/history/audit. Reversing migration state is unnecessary for a feature rollback. Do not remove canonical tables or external FK dependencies without a separate approved data migration. No automatic purge is installed; retention and privileged database access remain operational responsibilities.

Remaining acceptance work: a real browser connection was attempted but no browser was available; mobile, accessibility, navigation-loss and real-cookie/CSRF checks remain manual release gates. Populated load testing, restore rehearsal, institutional access/retention approval and deployment-engine verification also remain. The shared governance lock and canonical FK-only indexes may constrain throughput; measure before institutional rollout. Additional indexes/actor columns/idempotency storage require separate schema approval and are deliberately excluded.


## Verification coverage matrix

| Rule | Automated evidence |
| --- | --- |
| Canonical field/default/index/FK fidelity | test_schema_fidelity; test_adoption_refuses_schema_drift |
| Safe reverse/re-adoption preserves rows | test_state_rollback_preserves_and_readopts_canonical_tables |
| Mentor overlap both policies | test_overlap_policy_both_modes |
| Assignment dates, historical reassignment and rollback | test_invalid_dates_and_unauthorized_assignment; test_reassignment_preserves_history_and_rolls_back |
| Counselling ownership and confidentiality | test_counselling_levels_and_idor; test_student_normal_policy_and_confidentiality_change |
| Follow-up and assignment-window rules | test_session_followup_date_and_assignment_window |
| Explicit grievance transitions/resolution | test_grievance_state_machine_and_history; test_cancel_and_reject_preserve_history |
| Atomic action/audit | test_history_and_audit_failures_rollback |
| Department route scope and no implied mentor grievance access | test_department_scope_ownership_and_no_mentor_grievance_access |
| Active categories and collision retry | test_inactive_category_and_number_collision_retry |
| Concurrent numbers / transitions | test_concurrent_numbers_are_unique; test_simultaneous_transitions_have_one_winner |
| Append-only validated action vocabulary | test_action_immutable_and_vocabulary |
| API identity spoofing, PATCH, anonymous access and redaction | test_api_rejects_spoofing_patch_and_redacts_lists |
| Student IDOR and historical read-only access | test_student_cannot_read_another_students_grievance; test_inactive_student_cannot_submit_but_can_read_own_history |
| Revocation / activation / limited grants | test_revocation_and_feature_gate; test_scope_limits_and_cross_institution_are_fail_closed |
| Admin bypass prevention | test_admin_is_read_only_and_omits_notes |
| Reports and queue query budgets | test_query_budget_reports_no_narratives; test_queue_query_budget_and_narrative_projection |
| Configuration booleans | test_text_boolean_fails_closed; test_explicit_false_disables_policy |
| Student frontend | confirmation and server identity; hidden staff controls; offline blocking without persistence |

Combined M6-M12/core run: 206 backend tests passed in 289.53 seconds. This run included the initial 24 M12 tests. Final focused results, UI results and database status are recorded below. Ruff lint/format checks apply to the new module; no Bandit installation was present. TypeScript compilation and OpenAPI validation are included in the verification script. No failing confidentiality or workflow-atomicity check is waived.


## Final local verification (2026-09-23)

- Combined M6-M12/core backend: 206 passed; final focused M12: 27 passed in 19.40 seconds. The focused run includes the final policy parsing and narrative-projection checks added after the combined run started.
- Frontend: all 42 tests passed across 11 files; TypeScript and Vite/PWA production build passed.
- OpenAPI validation with fail-on-warn passed. Ruff lint and format checks passed for all 26 module Python files.
- Migration applied to local `sims_reference_dev`; schema report successfully verified every canonical table. Django database checks pass, no migration drift and no pending migrations remain.
- `STUDENT_SUPPORT_ENABLED=False`; institution allowlist empty. All five M12 tables have zero rows. M11 remains disabled. No real categories, user assignments, support content or outbound notifications were created.
- Browser acceptance remains unverified because browser discovery returned no available browser. No populated load, production deployment or staging restore is claimed.

The implementation is locally verified and ready for a controlled acceptance pilot after operational configuration. The production acceptance gates above remain explicit.


## Local pilot configuration update

Following the user's selection of pilot setup, local backend/.env now enables M12 for BVB Campus (institution 1), the sole active institution. Explicit policy settings allow overlapping mentors and student access to their own NORMAL notes under the required capability; assignment-date enforcement and own-assignment reads remain enabled. Four Support capability groups were created; no users were assigned. A fresh Django process verified these settings and passed database system checks. An already-running Django process must reload/restart to read environment changes.

Pilot onboarding remains pending: there are no active BVB institution memberships and no approved grievance categories. Participant usernames, roles, department scopes where relevant, and institution-approved category codes/names are required before onboarding users and accepting grievances. No memberships, scope grants, account links, categories or confidential records were invented. M11 remains disabled. This updates the earlier disabled local verification snapshot; production/browser/restore acceptance gates remain outstanding.
