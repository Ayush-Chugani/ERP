# M4 Prompt 0 — Curriculum and Course Catalog implementation contract

Status: Prompt 0 completed; business implementation has not started. The user requested the next prompt after completing M3. The next supplied pack is `E:/Django_projects/Prompts/M4-Curriculum_and_Course_Catalog_Module_Prompt_Pack.docx`, whose Prompt 0 explicitly says: "Do not implement business features yet." Its foundation gaps are recorded below before advancing to migrations or governed writes.

## 1. Repository baseline and module boundary

One Django modular monolith, custom `accounts.User`, DRF, MySQL, React TypeScript/MUI and the existing Vite PWA. No service extraction, credential store or parallel RBAC system. Proposed app: `apps.curriculum_catalog`; registry code `CURRICULUM_CATALOG`; permission namespace `curriculum_catalog`; URL namespace `curriculum_catalog`; API prefix `/api/v1/curriculum/`; frontend route `/#/curriculum`.

Owned tables: course_category, course_catalog, curriculum_scheme, curriculum_course, course_prerequisite. Preserve SQL singular table names and identifiers, including course_id and the prerequisite pair identity. No teaching allocations, enrolments, course offerings or student masters are implemented in this increment. SQL describing later modules is a dependency reference, not evidence of working Django applications.

Proposed layout: apps.py, models.py, migrations/, services.py, selectors.py, policies.py, permissions.py, api/, admin.py, integrations/, public.py, events.py, tests/. Cross-module model declarations use string foreign-key references. Runtime ORM access to another feature module is confined to explicitly documented integration adapters until a stable upstream public contract exists. No import-time queries or core workflows hidden in signals.

## 2. Verified upstream references and dependency map

Read-only MySQL 8.4.11 inspection is saved in [M4_UPSTREAM_SCHEMA.md](M4_UPSTREAM_SCHEMA.md). Django/database system checks passed with zero issues. All five target curriculum domain tables are absent in the configured development database.

| Upstream | Verified structure | Curriculum use |
| --- | --- | --- |
| accounts.User | Existing AUTH_USER_MODEL | Trusted actor and protected audit attribution |
| organization.Institution | institution_id SMALLINT UNSIGNED | Resolved tenancy, not caller-declared ownership |
| organization.Campus | campus_id and institution_id SMALLINT UNSIGNED | Parent scope of owning department |
| organization.Department | department_id and campus_id SMALLINT UNSIGNED; unique (department_id,campus_id) | Course ownership and department edit scope |
| organization.Programme | programme_id/department_id SMALLINT UNSIGNED; duration_semesters TINYINT UNSIGNED | Scheme ownership and semester range |
| organization.ProgrammeSpecialization | specialization_id/programme_id SMALLINT UNSIGNED; UNIQUE(specialization_id,programme_id) in the required order | Scheme specialization must belong to its programme; composite database FK is feasible |
| academic_calendar.Semester | semester_id TINYINT UNSIGNED; semester_number/name independently unique | Shared reference via scoped public interface |
| tenancy.Membership/ScopeGrant/InstitutionModule | Existing platform support models; active membership, institution/campus/department roles and record limits | Reuse and extend for curriculum; do not assume generic legacy workflow tables exist |
| core | Registry, error envelope, pagination, unsigned fields and append-only audit support | Shared platform conventions |

Dependency direction:

```text
Accounts + Core + existing Tenancy
                  |
Organization ----+----> Curriculum Catalog <---- Academic Calendar
                              |
           Future Admissions / Enrolment / Course Registration
           Teaching / Attendance / Assessment / Results / Lesson Plans
```

Curriculum must not import future consumer implementations. Consumers use curriculum/public.py and stable IDs, not copied catalogue state. Registry dependencies will include CORE, ACCOUNTS, ORGANIZATION, ACADEMIC_CALENDAR. The full SQL uses module label CURRICULUM in later platform inserts, while the pack requires CURRICULUM_CATALOG: use the pack's code for the new static registry and document an explicit legacy alias/mapping if those SQL registries are adopted later. Do not silently import their rows.

## 3. Trusted institution context and ownership

Proposed immutable context: actor ID, validated institution ID, permitted campus/department/programme IDs, module state and relevant permission capabilities. A requested institution header/URL parameter is only a candidate: validate active user, Membership, ScopeGrant shape, active ancestor chain and curriculum activation before constructing context. Recheck authority inside write transactions. Superusers explicitly bypass ordinary membership scope, but their governed writes remain audited.

Course ownership derives from owning_department -> campus -> institution. Scheme ownership derives from programme -> department -> campus -> institution. Mapping rows inherit scheme ownership and separately validate authorized course/category/semester choices. Prerequisite edges inherit the owning course's scope and must validate the required course independently. List/count/search/export/parent selectors filter first; object checks are additional protection.

course_category has no institution field: proposed shared master with platform-only maintenance. Supplied category_code/category_name/course_code/scheme_code uniqueness remains global unless Prompt 1 records an approved schema change. M3 shared-calendar approval does not automatically approve all M4 business policies. Cross-institution course reuse, category overrides and prerequisite edges default to denied until explicitly designed. Record limits narrow scope and do not grant it. Existing organization's module flag must not accidentally confer curriculum authority.

## 4. Permission and scope matrix (proposed contract)

Capability names below are not new role rows. Compose existing scoped assignments with Django permission codenames. Plain group membership, staff status or possession of an object ID does not authorize a curriculum operation.

| Capability | Read | Course/category maintenance | Scheme/mapping maintenance | Governed lifecycle | Audit |
| --- | --- | --- | --- | --- | --- |
| Catalog reader | Permitted institution/department records with view permission | None | None | None | None |
| Department editor | Own permitted department | Course drafts/allowed metadata with add/change permissions; shared categories denied | Only if also a designer | No activation/retirement from edit permission alone | None |
| Curriculum designer | Authorized programme/department | No implied category authority | Draft schemes/mappings and clone with explicit permissions | Submit/review behavior only if approved in Prompt 1; no invented status | Own scoped history only if separately granted |
| Approver | Relevant scoped records | No implied ordinary edit authority | Review | Explicit activate/retire permissions and approved policy, dependency checks and reason | Relevant history if granted |
| Auditor | Separately authorized scoped read/history | None | None | None | Read-only, filtered before serialization |
| Platform superuser | All | Shared categories and governed course edits | All through services | Explicit audited bypass of membership requirements | Read-only audit access |
| Inactive principal/membership or disabled module | None | None | None | None | None |

Standard codenames: view/add/change for coursecategory, coursecatalog, curriculumscheme, curriculumcourse and courseprerequisite. Proposed additional permissions: activate_coursecatalog, deactivate_coursecatalog, activate_curriculumscheme, retire_curriculumscheme, clone_curriculumscheme, manage_courseprerequisite, view_curriculumaudit. No public or admin hard deletion even if a Django delete permission exists. Exact workflow separation, self-approval and confidentiality semantics are unresolved business decisions; no generic workflow-authority or confidentiality engine is implemented in this repository. Fail closed for any requested feature requiring unsupported authority.

## 5. Proposed public contracts

All read APIs accept a trusted actor/institution context and return immutable DTOs rather than unrestricted model managers. All write commands have explicit writable fields and carry actor, correlation and optional required reason; request objects stay out of domain services.

| Surface | Proposed operations |
| --- | --- |
| Organization integration adapter | department_context, programme_context, specialization_context; return IDs, ownership, active ancestry and programme duration; validate read/manage scope |
| Calendar integration adapter | authorized_semesters using academic_calendar.public.semesters; calendar view permission and activation are deliberate dependencies, not bypassed via direct ORM |
| Selectors | list/get categories, scoped courses, scheme by ID/code, effective scheme candidates, semester mappings, prerequisite edges; multiple effective candidates cause explicit ambiguity rather than choosing one |
| Policies | can_view/edit_course, can_design_scheme, can_activate/retire_scheme, can_manage_prerequisites, can_view_audit; shared between API/admin/background jobs |
| Services | create/update course, deactivate/reactivate course, create/edit draft scheme, clone scheme, activate/retire scheme, add/update mapping, add/remove prerequisite edge through audited policy |
| DTOs | CourseSummary, SchemeSummary, CurriculumMapping, PrerequisiteEdge, ScopeContext, MutationResult |
| Events | Versioned course.changed, scheme.activated/retired, prerequisite.changed payload proposals containing IDs and correlation only; no durable delivery promise until transactional outbox support exists |

Proposed resources: `/course-categories/`, `/courses/`, `/schemes/`, `/curriculum-courses/`, `/prerequisites/`. Preserve prerequisite pair identity in API routing (course ID + prerequisite ID) unless an approved schema decision changes it. Lifecycle routes are POST actions, separate from PUT/PATCH. Later consumers must not edit source catalogue records through integration selectors.

## 6. Transaction and audit standard

Central services use atomic transactions, trusted-parent locks and a deterministic lock order. Reuse the organization lock initially where ancestor changes could race curriculum validation. Prerequisite cycle detection must serialize graph changes across the entire permitted graph (locking only the two endpoints cannot prevent a cycle formed by concurrent edges). Active scheme interval conflicts similarly need a stable programme/specialization lock even when no scheme rows exist. Compare Decimal values exactly; do not calculate credits/marks with binary floats.

Run database-collation-aware duplicate validation and retain database UNIQUE/CHECK/FK constraints as the concurrency defense. Catch expected IntegrityError after leaving the failed atomic/savepoint and translate to stable project errors. Database SQL must not appear in API errors. Unknown operational errors remain server errors and must not be relabelled as duplicates.

Separate platform-support CurriculumAudit: protected actor, trusted institution (null for shared category), action, table/resource, stable identity, timestamp, correlation and bounded allowlisted before/after values. Compound prerequisite identity must record both IDs. Reason required for sensitive lifecycle changes. Mutation and audit insertion commit together; audit failure rolls back mutation. No credential/token or unnecessary personal-data snapshots. Read access is scoped and ordinary update/delete prohibited. Application append-only is not DBA-proof tamper protection. Existing audit tables are module-specific: reuse conventions and shared support, not their unrelated resource semantics.

## 7. API, frontend and PWA conventions

Use project `{error:{code,message,details}}` responses, 25-row pagination with maximum 100, deterministic PK tie-breakers, bounded search and explicit filter/order allowlists. Return canonical identifiers, parent labels, lifecycle/active state and server-derived available actions. Validate new inactive-parent assignments while preserving unchanged historical references. Reject protected/unknown writable fields; never infer scope from payload alone. Optimized selectors use related loading and batched capability checks.

Frontend reuses authenticatedFetch, the existing memory-token/refresh coordinator and explicit JSON media type for JSON writes. Use React TypeScript/MUI, lazy navigation, server-side filters/pagination, accessible labels, preserved validation inputs and explicit lifecycle confirmations. No second session store. Dates are date-only; Decimal values use lossless string input/serialization as needed. Browser actions are UX, never authorization.

PWA caches static assets; sensitive and authorization-dependent curriculum reads remain network-only initially. No queued writes, graph updates or lifecycle actions offline. Display disconnected/stale state and disable mutations. Any later reference snapshot requires an explicit user/tenant/TTL/security review.

## 8. Foundation gaps and decision gates

| Gap | Evidence / consequence | Required next action |
| --- | --- | --- |
| Organization has selectors but no public organization DTO interface | Directly importing selectors across every curriculum layer would breach the pack's boundary | Document and implement one integration adapter/public facade in scaffolding before services |
| Curriculum activation and record-limit names absent | InstitutionModule has only organization_structure and academic_calendar; ScopeGrant validates existing resource names | Add an explicit curriculum flag/default false and validated resource keys in a reviewed migration; no blanket bypass |
| Workflow/confidentiality extensions assumed by pack are absent | Existing ScopeGrant roles are institution/campus/department admin, teacher, student; no generic authority/confidentiality models | Prompt 1 must state the limited Django-permission policy and decide whether further foundation work is required before governed workflows |
| UnsignedAutoField supports only 8/16/32 bits | curriculum_course_id is BIGINT UNSIGNED | Implement a migration-safe unsigned 64-bit field; serialize IDs without JavaScript precision loss |
| Composite prerequisite PK and specialization FK need explicit handling | Baseline pair PK; specialization composite unique key confirmed | Review Django/DRF/admin composite-key support and migration SQL; do not add a surrogate ID silently |
| MySQL YEAR has distinct storage/range | regulation_year YEAR | Decide faithful custom field vs approved portable mapping in Prompt 1 |
| Global codes and business invariants unresolved | SQL global uniqueness vs pack multi-institution alternatives | Record decisions before migration: code scopes, categories/overrides, elective groups, semester ranges, active overlaps, graph boundaries and lifecycle immutability |
| Durable event delivery not implemented | Registry/audit exist; no active outbox engine | No claimed outbox guarantees; introduce only if a real consumer requires durable events |

These gaps block advancement to business implementation, not completion of this review-only contract. No migration or production path is created with TODO placeholders. Prompt 1 is the next bounded task and must resolve/record decisions before Prompt 2 scaffolding and Prompt 3+ model work.

## 9. Migration, compatibility and recovery

Django migrations are authoritative for the new application. Never import the entire reference SQL into the managed database, automatically fake an existing table, or replace legacy records to satisfy a migration. Preserve parent unsigned types, the specialization composite key order, global uniqueness until approved otherwise, protected references and later consumer IDs. Existing organization and calendar URLs/data must remain compatible.

Plan additive platform support migrations, an inspected curriculum initial migration and explicit forward/reverse SQL. Before production use, compare information_schema to the expected baseline, profile duplicate natural keys and prepare a backup plus restore rehearsal. If legacy tables appear, stop initial creation and produce an adoption/reconciliation plan. Roll back application code only if schema-compatible; reversing table-creation migrations after writes is destructive and requires separately approved recovery. Prefer forward fixes after committed domain data.

## 10. Standard prompt response and verification gates

Every subsequent prompt reports: (1) decisions/assumptions, (2) files changed, (3) implementation, (4) authorization/scope, (5) migrations, (6) tests/results, (7) verification commands, (8) unresolved risks/next decision. Failed relevant checks block advancement. No success claim based solely on file creation.

From workspace root:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py check --database default
backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
# Once the app and tests exist:
backend/.venv/Scripts/python.exe -m pytest backend/apps/curriculum_catalog/tests
backend/.venv/Scripts/python.exe -m ruff check backend/apps/curriculum_catalog --select E9,F63,F7,F82
backend/.venv/Scripts/python.exe backend/manage.py spectacular --file backend/openapi.yaml --validate --fail-on-warn
npm --prefix frontend test
npm --prefix frontend run test:ui
npm --prefix frontend run build
```

Use real MySQL for unsigned widths, collation, YEAR, composite constraints and concurrency tests. Exercise cycles created by concurrent requests, scheme overlaps, tenant isolation, record restrictions, nullable specialization, elective/marks boundaries, protected history and audit rollback. Add request-layer tests for headers and error preservation. Run full regression checks after integration changes; do not rerun unrelated application suites merely for this documentation-only step.

## Prompt 0 outcome

Created this repository-aware contract and captured six upstream SHOW CREATE TABLE results. The required composite unique key and unsigned parent types are confirmed. All five target table names are absent. `manage.py check --database default` passed. No models, business features, permissions or migrations were changed. Full implementation acceptance is intentionally pending the subsequent prompts and foundation decisions above.
