# M5 prompts 1–3: schema audit, boundaries and domain decisions

Source: M5-Student_and_Staff_Master_Modules_Prompt_Pack.docx, extracted in M5_prompt_pack_extracted.txt. Scope is the fifteen Student and Staff Master tables in its appendix/section 5 of the repository schema. The IDE selection of mentoring/grievance is not part of this module request.

## Prompt 1: severity-ranked schema audit

Live read-only inspection on 2026-09-20: MySQL 8.4.11; all fifteen target tables absent. Actual upstream DDL is saved in M5_UPSTREAM_SCHEMA.md. No domain data or credentials were read. The existing custom User remains authoritative for authentication.

Strengths: independent student/employee roots; exact decimal storage; reusable demographic foreign keys; explicit unsigned identifiers; generated-column uniqueness for current primary addresses/assignment; department/campus composite ownership; unique competency pair; InnoDB foreign-key protection with no cascade deletion.

| Severity | Finding | Migration-safe resolution |
|---|---|---|
| Critical | Student has no institution/campus/department ownership but APIs must isolate institutions before lookup | Pending user decision: single home institution with explicit scope versus shared identity with institution access links. Do not create dependent ownership migrations until resolved. |
| High | SQL guarantees at most one open primary, not exactly one | Pending user decision: require one at activation with draft onboarding, or preserve optional zero-or-one. Draft state/default would be an explicit baseline divergence. |
| High | Employee agency FK does not bind agency institution to employee institution | Service validates source.is_external, agency requirement and institution equality under lock; consider composite FK as defense after adding referenced owner key. |
| High | Generated current primary columns test end date NULL, not today's date | Preserve exact generated expressions. Scheduled future open-ended primaries occupy the slot; do not substitute a nondeterministic CURRENT_DATE generated expression. Promotion closes previous row atomically. |
| High | Nullable unique email/seat/registration/year fields permit multiple NULLs | Preserve SQL behavior; normalize optional blank to NULL. Validate with database collation. Do not add COALESCE sentinel uniqueness without a separate requirement. |
| High | Students/employee demographic relationships individually valid but may contradict category/caste/sub-caste or state/country | Validate chains on new/changed assignments; permit unchanged inactive historical references. |
| High | Temporal overlap, source semantics and scope cannot be secured by serializer checks alone | Lock root and trusted scope during service workflows; independent database generated-key uniqueness remains final concurrency defense. |
| High | Optional account provisioning can hijack an existing account if matched by email alone | Explicit reviewed link, proof via single-use expiring invitation; no email-based automatic linkage or role escalation. Credentials stay in User. |
| Medium | Residence, competency and mentor-independent employment dates lack order checks | Add end >= start checks where both present; residence current flag consistent with open interval in services. |
| Medium | Income/fees/education percentages lack bounds | Add nonnegative income/fee/marks; percentage 0–100; month 1–12; rank positive; obtained <= maximum when both supplied. Do not assume entrance scores are nonnegative for exams allowing negative marking. |
| Medium | Staff taxonomy deactivation does not define child behavior | Non-cascading active flags; block new inactive parent assignments, retain history. Platform-only shared taxonomy maintenance. |
| Medium | Employee competency uses composite PK | Preserve pair; use public curriculum contract for scoped course validation. Installed Django admin cannot register composite-PK models; dedicated governed editor required. |
| Medium | SQL timestamps use ON UPDATE while Django automatic fields cover only application saves | Document ORM-managed timestamps or retain database behavior through explicit migration SQL; never silently promise both. |
| Medium | YEAR zero semantics differ from ordinary date years | Validate nonnull years 1901–2155, preserve YEAR storage; legacy zero requires explicit cleaning. |
| Medium | Existing role set lacks HR/registrar/auditor/employee self-service | Reuse memberships/scope and Django permissions; document capability bundles, extend existing scope roles only where necessary. Do not introduce a parallel authentication/RBAC system. |

### Table-level invariants and validation ownership

All tables: immutable primary keys, explicit writable fields, PROTECT/RESTRICT deletion, database collation uniqueness, service authorization before writes, optimistic version on updates. Root statuses change through commands with reasons. New assignments require active parents; historic unchanged references remain resolvable.

| Table | Identity/unique rules | Local/database rules | Service/workflow rules |
|---|---|---|---|
| student | unsigned BIGINT; global number, nullable unique seat/email | required name/display name; status enumeration | ownership pending; demographic chain, nonfuture birth/admission sanity, identifier changes audited |
| student_address | unsigned BIGINT; generated unique current_primary_student_id | address type, required country/city/line, end >= start | state belongs to country; root lock and atomic primary switch; cardinality decision pending |
| student_parent_guardian | unsigned BIGINT; student FK | relationship enum; nullable nonnegative income | guardian PII restricted; optional country required when state set; primary contact is not silently made unique |
| student_residence | unsigned BIGINT | residence enum; end >= start | current/open period consistency; overlap policy explicit, retain ended history |
| student_previous_education | unsigned BIGINT; student/level/registration unique with NULL behavior | bounded month/year, marks/percentage constraints | supplied percentage may reflect board conversion: no automatic arithmetic overwrite |
| student_entrance_exam | unsigned BIGINT; student/exam/year unique with NULL behavior | positive nullable rank, nonnegative fee, valid YEAR | score may be negative; no fabricated exam maxima or rankings |
| staff_type | unsigned TINYINT; unique code/name | boolean active | platform maintenance, protected historical children |
| staff_category | unsigned SMALLINT; global code unique | staff_type parent | active parent on new assignments; category names need not be globally unique |
| employment_source | unsigned TINYINT; unique code/name | external flag, active | freeze external semantics once referenced; never reinterpret historical employees |
| external_agency | unsigned BIGINT; institution/code unique | contract end >= start | scope owner immutable; new external employment requires compatible active agency and contract dates |
| designation | unsigned SMALLINT; global code and category/name unique | category parent | scoped taxonomy maintenance; no invented classification additions |
| employee | unsigned BIGINT; global number/email; agency/agency-number pair | joining date and employment enums | institution owner, source/agency agreement, demographics, lifecycle and account separated |
| employee_address | unsigned BIGINT; generated unique primary owner | same rules as student address | employee authorization and atomic primary switch |
| employee_assignment | unsigned BIGINT; generated unique primary owner | end >= start; composite department/campus FK retained | campus belongs to employee institution; designation active; root lock, date and scope checks |
| employee_competency | composite employee/course PK | level enum; validity order | same-institution scoped course access; immutable pair, protected historical course identity |

### Index and constraint plan

Preserve baseline unique/generated keys and ordinary FK indexes. Add checks named per table for date order, money, percentage/month/rank and local enum domains. Add compound indexes based on scoped queries: employee(institution_id, employment_status, employee_number), agency(institution_id, is_active, agency_code), assignment(employee_id, end_date, start_date), assignment(campus_id, department_id, end_date), child owner/effective-date indexes. Student indexes depend on ownership decision. Avoid redundant copies of leading FK/unique indexes. Validate EXPLAIN with realistic volumes before claiming performance.

No existing target data requires backfill in this development database. Other installations must inspect existing tables before migration; never fake initial migration over incompatible SQL. Seed staff taxonomy with supplied codes, lookup parents by natural key, preserve administrator edits, and only reverse rows provably created by the seed and still unreferenced. Schema rollback after writes must preserve data/backups, not casually drop tables.

## Prompt 2: bounded context and dependencies

Own app: apps.people_master. Student and employee remain independent concrete aggregates. Shared utility functions/abstract timestamp mixins do not create a Person table. No login credentials in domain models.

| Dependency | Allowed boundary | Forbidden behavior |
|---|---|---|
| accounts | custom User and explicit optional account-link/invitation services | auto-link by email, duplicate password store, implicit superuser creation |
| common_reference | declared read adapter for demographics/geography | changing reference tables through people endpoints |
| organization/tenancy | declared trusted-scope adapter, string model relations for migrations | trusting payload institution IDs or importing private helpers throughout app |
| curriculum_catalog | public course DTO validation, declared FK for competency integrity | direct unscoped course lookup from views |
| admissions/registration | future public student identity/scope DTOs | deriving today's permissions from unimplemented enrolment tables |
| attendance/HR/finance/documents | purpose-specific employee/student DTOs | exposing guardian income, caste or notes through general directory APIs |
| plugins | versioned redacted event log, consumer-owned cursor/deduplication | personal data broadcasts or silently claiming broker delivery |

Package plan: models.py, enums.py, services.py, selectors.py, permissions.py, filters.py, serializers.py, api.py, urls.py, admin.py, public.py, integrations/, migrations/, management/commands/, tests/. APIs under /api/v1/people/. React feature under features/people. No signals containing business writes.

Public contracts will require actor plus trusted institution context, return immutable minimal DTOs with string IDs and decimal strings, and fail closed when scope is unavailable. Event names use people.<resource>.<action>.v1 with UUID idempotency; avoid names/contact details in event payloads. Transactional write audits and confidential-read access events have distinct purpose and retention hooks.

## Prompt 3: proposed lifecycle and confidentiality specification

Student baseline states: APPLICANT, ACTIVE, SUSPENDED, WITHDRAWN, COMPLETED, ALUMNUS, DECEASED. Employee states: ACTIVE, ON_LEAVE, SUSPENDED, RESIGNED, RETIRED, TERMINATED. Status change commands require reason/version. Terminal student deceased status cannot be casually reopened; reactivation of withdrawn/completed employment requires explicit workflow permission and review. Exact activation preconditions depend on the pending primary-record decision; no draft/default divergence is implemented yet.

Temporal promotion uses inclusive dates: previous primary closes before the successor's start date; reject zero/negative historical intervals and future overlapping primaries. The database's NULL-end uniqueness is preserved independently of service overlap checks. Address types may coexist; primary means one designated current contact address across types, not one per type.

Privacy classes: directory (IDs, permitted display name, staff designation); confidential contact (email, phone, addresses, birth date, guardians); restricted demographics/financial notes (religion, caste, social category, income, free text). Reads must be purpose/permission scoped and masked; no PII in normal logs/events or offline caches. Self-service is linked-root-only and does not imply peer directory access. Admin cannot bypass confidentiality; read-only auditor requires explicit grant, not a broad view permission assumption.

Optional account-link model should permit one link per domain root and one link per user per root type, allowing the same account to be both student and employee. No account exists by default. Invitation tokens are hashed, expiring and single use; delivery is not authorized until specifically requested/configured. Unlink does not delete the person or automatically disable a shared account. Account activation and domain status transitions remain separate commands.

## Decision status and execution ledger

- Prompts 1–3 reviewed; this is the concrete decision log, pending two ownership/cardinality answers.
- Prompt 4 can proceed as an inert, disabled scaffold; it must expose no personal data or fake business endpoints.
- Prompts 5–20 depend on the decisions above and are not complete.
- The pack says: “Review and approve changes identified through Prompt 1 before generating final migrations.” The two questions request missing domain policy, not general permission to perform the already-authorized implementation.

## Confirmed decisions (2026-09-20)

The user selected option 1 for both questions: one home institution with campus/department scope per student; primary address required when activating either root and primary assignment required when activating employees. Student creation therefore defaults to APPLICANT; employee creation adds DRAFT and defaults to DRAFT. These are explicit approved onboarding divergences from the SQL ACTIVE defaults. Student institution/campus/department ownership fields are additions; ownership never changes through ordinary PATCH. Original generated NULL-end uniqueness remains intact.

## M5 current status

The original pending ownership/cardinality discussion above is superseded by the user's two option-1 confirmations. Models, migrations, governed APIs/admin, account linkage and React workflows are implemented. Current behavior, validation and remaining production gates are documented in M5_IMPLEMENTATION.md and M5_RELEASE_AUDIT.md.
