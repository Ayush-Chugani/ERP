# M4 Curriculum and Course Catalog: implementation and operation

## Scope and approved decisions

M4 implements five domain resources: course categories, courses, curriculum schemes, semester composition and prerequisites. The user's confirmation approved global codes, platform-maintained shared categories, draft-only structural editing, nonoverlapping active schemes per programme/specialization, same-institution course reuse and one equal-credit alternative per semester/elective group. A category override is deliberately forbidden; no override permission grants an exception to the approved exact-category rule.

The application preserves the custom User and existing memberships, ScopeGrant roles and record limits. It does not implement student registration, timetable, assessment or attendance. Those future modules must consume the public contracts below.

## Start and use

From the workspace in PowerShell, with the configured MySQL server running:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py runserver
```

In a second terminal:

```powershell
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173/#/curriculum`. Sign in using an existing account. Platform superusers can maintain shared categories and access the module. For other users, enable `InstitutionModule.curriculum_catalog` for their institution, retain an active membership and scoped managerial role, and assign the relevant Django permissions. Semester choices also require the existing Academic Calendar module/read permissions. No users, official categories or production courses are automatically seeded.

Suggested workflow: create category as platform maintainer; create department-owned courses; create a draft programme scheme; add semester composition and prerequisites; review Impact and Validate; activate with a reason. Clone an active scheme to revise its structure. Archive using lifecycle actions rather than hard deletion.

Global kill switch: `SIMS_CURRICULUM_CATALOG_ENABLED=0`. Approved minimum grade codes can be configured with comma-separated `SIMS_CURRICULUM_GRADE_CODES`; without configuration, leave minimum_grade empty.

## Endpoint and permission matrix

Base URL: `/api/v1/curriculum/`. All requests require the existing authenticated session/token mechanism. Session writes require CSRF. Every operation also requires active user/module status; non-superusers require active institution membership, matching role and campus/department/record scope. Payload institution IDs never confer authority.

| Endpoint | Methods | Django permission / additional policy |
|---|---|---|
| `course-categories/`, `{id}/` | GET; POST; PUT/PATCH | view_coursecategory; all writes platform-superuser only |
| `courses/`, `{id}/` | GET; POST; PUT/PATCH | view/add/change_coursecatalog respectively |
| `schemes/`, `{id}/` | GET; POST; PUT/PATCH | view/add/change_curriculumscheme; edit DRAFT only |
| `curriculum-courses/`, `{id}/` | GET; POST; PUT/PATCH | view/add/change_curriculumcourse plus change_curriculumscheme for writes |
| `prerequisites/`, `{course_id}:{required_id}/` | GET; POST; PUT/PATCH | view_courseprerequisite; manage_courseprerequisite and change_coursecatalog for writes |
| categories or courses `{id}/activate/`, `deactivate/` | POST | corresponding activate/deactivate model permission; category platform-only |
| schemes `{id}/activate/`, `retire/`, `clone/` | POST | activate/retire/clone_curriculumscheme; clone also checks add permissions for copied records |
| schemes `{id}/validate/` | GET | scoped scheme view; complete composition visibility required |
| schemes `{id}/bulk-composition/` | POST | change_curriculumscheme and each row's add/change/compose permission |
| schemes `{id}/reorder/` | POST | change_curriculumscheme and compose_curriculumcourse for every semester row |
| mappings `{id}/remove/` | POST | compose_curriculumcourse plus change_curriculumscheme; DRAFT only |
| prerequisites `{pair}/remove/` | POST | manage_courseprerequisite plus change_coursecatalog; no active/historical scheme usage |
| any resource `{id}/impact/` | GET | scoped view; hidden dependencies give only a generic protection indicator |
| any resource `export/` | GET | export_<model>; same list scope; maximum 5,000 rows; formula-safe CSV |
| `metadata/`, `choices/{kind}/` | GET | active user; per-resource/choice scope and permissions determine returned data |
| any resource | DELETE | unavailable |
| audit history in Django admin | GET | active staff superuser only; no create/update/delete |

TEACHER and STUDENT scoped roles are read-only regardless of write codenames. Draft schemes and composition require design authority (change_curriculumscheme and managerial scope). Categories are shared, with read access subject to valid module grants. Lists are filtered before pagination, search, export and dropdown selection; object permission checks are an additional defense, not the list filter. Prerequisite endpoints scope both course endpoints independently. Out-of-scope IDs return 404, and lists omit them.

## Lists and wire types

Every list supports `page`, `page_size` (25 default, 100 maximum), `search` (100 characters maximum) and allowlisted `ordering` (writable fields/primary key, comma-separated, optional `-`). Unsupported or repeated query parameters are rejected. Additional filters:

| Resource | Filters |
|---|---|
| course-categories | is_active |
| courses | owning_department_id, course_category_id, course_type, is_active |
| schemes | programme_id, specialization_id (including `null`), status |
| curriculum-courses | curriculum_scheme_id, semester_id, course_id, is_mandatory, elective_group_code |
| prerequisites | course_id, prerequisite_course_id |

Booleans in query strings are `true` or `false`. IDs and versions are returned as strings to preserve BIGINT precision. Decimals remain strings; dates use ISO YYYY-MM-DD. Each row includes its id, parent IDs/labels where relevant, version and permitted actions. List responses use count/next/previous/results. Responses forbid storage with Cache-Control: no-store.

Examples (IDs are illustrative; use actual scoped parent IDs):

```http
GET /api/v1/curriculum/courses/?owning_department_id=12&is_active=true&search=math&ordering=course_code
```

```http
POST /api/v1/curriculum/courses/
Content-Type: application/json

{"owning_department_id":"12","course_category_id":"2","course_code":"MATH101","course_title":"Mathematics I","course_type":"THEORY","credits":"3.0","lecture_hours":"3.0"}
```

Successful create returns 201 with a full row, including `"id":"..."`, `"version":"1"`, `"credits":"3.0"`, `"is_active":true` and capabilities. Never assume the illustrated version for later requests; read it from the response.

```http
PATCH /api/v1/curriculum/courses/41/
Content-Type: application/json
If-Match: "1"

{"course_title":"Mathematics I — revised title"}
```

```http
POST /api/v1/curriculum/schemes/8/activate/
Content-Type: application/json
If-Match: "7"

{"reason":"Academic approval recorded"}
```

```http
POST /api/v1/curriculum/schemes/8/clone/
Content-Type: application/json
If-Match: "8"

{"reason":"Prepare next regulation","values":{"scheme_code":"BSC-2027","scheme_name":"BSc 2027","regulation_year":2027,"effective_from":"2027-06-01"}}
```

Updates and lifecycle commands require If-Match. A stale version returns 409 with `error.code=stale_version`; reload/reconcile rather than blindly retry. Expected database conflicts return 409 `curriculum_conflict`; validation returns 400, denied operations 403 or scoped 404, unsupported DELETE 405. The shared envelope is `{ "error": { "code": "...", "message": "...", "details": ... } }`. Internal SQL is not exposed. OpenAPI is generated in `backend/openapi.yaml`.

## Domain and database guarantees

DRAFT -> ACTIVE -> RETIRED; drafts may retire directly, retirement is terminal. Active/retired structures are immutable. Activation checks all composition rows, ownership, semester bounds, validity intervals, category agreement, marks and credit target. Inclusive active intervals may not overlap for a programme/specialization. Ungraded courses have zero marks; graded mappings need positive marks at activation. Passing marks cannot exceed total marks. Mandatory rows have no elective group; electives require a normalized group with equal credits. One alternative per semester/group contributes to the scheme total.

Prerequisites reject self-links, duplicate pairs, cross-institution endpoints and cycles, including concurrent opposing edges. Grade codes require explicit configuration. Graph operations are bounded at 5,000 edges/nodes. Writes serialize on the existing organization ContentType lock, so authorization/ownership changes and competing activations cannot race through validation. This coarse lock favors correctness; measure contention before large production workloads.

MySQL utf8mb4_unicode_ci uniqueness is checked through the actual database and constraints remain the final defense. The composite specialization/programme FK is retained. Curriculum row IDs are unsigned BIGINT; prerequisites retain the native composite primary key; regulation year uses YEAR with 1901–2155 validation. Additional CHECK constraints and indexes are recorded in the migrations. Historical IDs are preserved; no cascading lifecycle deactivation occurs.

## Admin, audit and events

Four single-key domain models are registered with scoped lists, relation choices and service-backed writes. Django 5.2 admin cannot register a composite-primary-key model: prerequisites use the dedicated React/API workflow, linked from courses. In split-port development open the frontend URL above; the admin's relative shortcut assumes same-origin deployment. Admin bulk lifecycle changes are atomic and cannot bypass readiness or audit. If a governed save fails, admin redirects with an error; API/React preserves editor input.

Platform support tables `platform_curriculum_revision`, `platform_curriculum_audit` and `platform_curriculum_event` are additions to the five domain tables. Changes and bounded audit/event records commit together. Audit records contain actor, resource/key, action, timestamp, institution, correlation and before/after values; no credentials/tokens are recorded. Public audit mutation APIs do not exist. Application append-only rules are not protection against a database administrator or unrestricted ORM bulk SQL.

Events use `<resource>.<action>.v1`, schema_version=1 and a UUID idempotency key. Payloads contain resource, record_key, institution_id, action and correlation_id. The `public.events` support-only polling contract takes after_audit_id and limit (max100). Consumers must persist their cursor and deduplicate UUIDs in their own transaction; retry is at least once. There is no delivery worker or external event delivery guarantee in this release.

## Integration boundary

Import `apps.curriculum_catalog.public`, not private managers. Public functions require actor and trusted institution_id: course(course_id), current_scheme(programme_id, specialization_id, on_date), semester_curriculum(scheme_id, semester_id), prerequisite_graph(), dependency_impact(course_id), credit_totals(scheme_id), elective_groups(scheme_id, semester_id), eligibility_inputs(course_id). Returned CourseInfo, SchemeInfo and MappingInfo DTOs are immutable, with string IDs/decimals. Ambiguous current schemes fail rather than selecting arbitrarily. Complete credit/eligibility inputs fail closed when required rows are hidden; elective_groups is a scoped listing.

Registration/offering should retain scheme and mapping IDs; timetable consumes course labels; assessment/results consume marks and grade inputs without rewriting historical structures. Eligibility inputs are not a student eligibility decision. Future consumers are not yet installed and their integrations are not claimed as tested. Declared upstream adapters isolate organization/tenancy models and academic calendar public reads; one admin-only adapter supplies scoped Semester querysets.

## Verification

Run `./scripts/verify-module4.ps1` with the local backend venv, frontend dependencies and MySQL configured. It checks Django/database, focused runtime lint, full backend regression/coverage, migration drift, OpenAPI, frontend tests and production build. The existing GitHub workflow includes curriculum gates; hosted CI has not been run here. See M4_RELEASE_AUDIT.md for measured results and outstanding release checks.
