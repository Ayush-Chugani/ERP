# M5 Student and Staff Masters: implementation and usage

## Approved scope and schema decisions

Implemented the fifteen M5 domain resources in apps.people_master. Student and Employee are independent concrete roots; the abstract LocalValidation helper has no table or demographic fields. Existing accounts.User remains the authentication identity.

The user approved one home institution with explicit campus/department scope for each student, and primary records required at activation. Therefore student has added institution/campus/department FKs and defaults to APPLICANT; employee adds DRAFT and defaults to DRAFT. Student activation requires a current primary address; employee activation requires a current primary address and assignment. Future/ended records do not satisfy readiness. Ownership is immutable through ordinary updates; cross-institution transfers are not an implemented workflow.

Generated NULL-end primary keys, unsigned IDs, nullable unique behavior, decimal precision, YEAR columns and the employee/course composite primary key are preserved. The department/campus composite FK is applied separately. Added local checks cover enum values, date ranges, education marks/percentage/month and nonnegative income/fees. Django manages created_at/updated_at through governed ORM saves; raw SQL updates do not reproduce the baseline ON UPDATE timestamp behavior. The review and SQL snapshots document these divergences.

## Run locally

With configured MySQL running, from the workspace:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py migrate
backend/.venv/Scripts/python.exe backend/manage.py runserver
```

In a second terminal:

```powershell
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173/#/people`. Use an existing platform superuser initially. For ordinary users enable InstitutionModule.people_master, activate membership and scope grants, and assign explicit people_master permissions. SIMS_PEOPLE_MASTER_ENABLED=0 disables the module globally. Installation alone does not grant access.

Migrations applied in development:

1. people_master.0001_initial: domain tables and local checks.
2. people_master.0002_peopleaudit_peopleevent_peoplerevision_and_more: audit/events/revisions and optional account invitations/links.
3. people_master.0003_assignment_ownership: department/campus composite FK.
4. people_master.0004_staff_baseline: source-defined natural-key staff seeds.
5. tenancy.0004_institutionmodule_people_master: per-institution flag.

Seed values come only from the supplied SQL: 2 staff types, 8 staff categories, 2 employment sources and 13 designations. Parent resolution uses codes. get_or_create preserves existing administrator values; reversing the seed is intentionally a no-op because deleting edited/referenced data is unsafe. No demo students/employees or login credentials are seeded. Do not execute the complete reference SQL over the Django database or fake these migrations over legacy tables.

## Operator workflows

Student: create APPLICANT -> create address with valid_from -> Set primary -> change status to ACTIVE with reason. Employee: create DRAFT -> create address and select primary -> create assignment with start_date and select primary -> activate with reason. Children are reachable from root Details and have separate scoped list/edit pages. The shared metadata-driven forms support guardians, residences, previous education, entrance exams, agencies, staff taxonomy, assignment history and competencies.

Primary selection locks the workflow, closes the previous open primary the day before the replacement starts, then selects the new primary in one transaction. The previous record remains historical. Conflicting or overlapping effective periods are rejected. Open primary cardinality is also protected by the database generated UNIQUE key. Ordinary writes cannot set is_primary. A later date edit cannot silently remove the primary required by an ACTIVE root.

Student states: APPLICANT -> ACTIVE or WITHDRAWN; ACTIVE -> SUSPENDED/WITHDRAWN/COMPLETED/DECEASED; SUSPENDED -> ACTIVE/WITHDRAWN/DECEASED; COMPLETED -> ALUMNUS/DECEASED; WITHDRAWN -> APPLICANT/DECEASED; ALUMNUS -> DECEASED. DECEASED is terminal. Employee DRAFT -> ACTIVE; ACTIVE -> ON_LEAVE/SUSPENDED/RESIGNED/RETIRED/TERMINATED; leave/suspension -> ACTIVE/RESIGNED/TERMINATED. Final employment states are terminal here. No ordinary update can bypass these transitions.

External employment requires an agency from the same institution and a joining date compatible with its contract. Internal employment must not contain an agency/agency employee number. Referenced employment-source external/internal semantics cannot be changed. Department must belong to assignment campus; campus must belong to employee institution. New inactive parent selections are rejected, while unchanged historical links remain valid. Taxonomy deactivation is non-cascading. Elective or attendance policies belong to their respective modules.

## Endpoint and permission inventory

Base `/api/v1/people/`. JWT authentication uses the existing session/token client; all personal API responses are no-store. IDs and versions are strings; decimals are strings and dates are ISO YYYY-MM-DD. Competency IDs use `employee_id:course_id`.

| Resource path | Model permission suffix |
|---|---|
| students | student |
| student-addresses | studentaddress |
| guardians | studentparentguardian |
| residences | studentresidence |
| previous-education | studentpreviouseducation |
| entrance-exams | studententranceexam |
| staff-types | stafftype |
| staff-categories | staffcategory |
| employment-sources | employmentsource |
| agencies | externalagency |
| designations | designation |
| employees | employee |
| employee-addresses | employeeaddress |
| assignments | employeeassignment |
| competencies | employeecompetency |

For every row above, the following matrix applies with `<model>` replaced by its suffix:

| Endpoint | Method | Permission and policy |
|---|---|---|
| resource/ | GET | view_<model>; scope filtered before pagination |
| resource/{id}/ | GET | view_<model>; scoped lookup, masked fields, read audit |
| resource/ | POST | add_<model>; explicit writable fields and scoped parent validation |
| resource/{id}/ | PUT/PATCH | change_<model>; current If-Match version; ownership fixed |
| resource/export/ | GET | export_<model> plus view for serializer visibility; max500 rows, masked values, formula-safe CSV, audit |
| students or employees/{id}/status/ | POST | transition_<model>; reason, If-Match, valid transition and readiness |
| address or assignments/{id}/set-primary/ | POST | transition_<model> for selected and prior primary; reason and If-Match |
| taxonomy or agencies/{id}/activate/, deactivate/ | POST | transition_<model>; reason and If-Match; taxonomy platform-only |
| students or employees/{id}/invite/ | POST | change_<model> and manage_accountlink; target account must have same-institution membership |
| students or employees/{id}/provision/ | POST | above plus accounts.manage_platform_access; new inactive account, no roles/password |
| students or employees/{id}/unlink/ | POST | change_<model> and manage_accountlink; explicit reason |
| students or employees/{id}/account/ | POST | platform superuser only; explicit global account activation/email changes; protected superuser/self accounts excluded |
| invitations/accept/ | POST | active authenticated intended user and valid single-use token |
| invitations/claim/ | POST | invitation token plus validated password, anonymous rate limit; only newly provisioned inactive/unusable-password accounts |
| metadata/ | GET | active authenticated module access; resource/field capabilities derived from permissions |
| choices/{resource}/{field}/ | GET | scoped, active reference choices; paginated search |
| any resource | DELETE | unavailable |
| audit admin | GET | platform superuser only; no write/delete actions |

Shared staff taxonomy writes are platform-only even if ordinary users hold model write permissions. No view permission or superuser claim in a request body grants access. Field changes require confidential_<model> or restricted_<model> permissions where relevant. Lists mask those fields and reject hidden-field filtering to prevent inference through counts.

### Role/scope matrix

| Operator | Required grants | Result |
|---|---|---|
| Platform superuser | active account/global module | all institutions; separately audited writes and reads |
| Institution admin | active institution membership + INSTITUTION_ADMIN + model codenames | institution-wide permitted resources |
| Registrar | same existing institutional scope role, student capability permission bundle | student workflows only; no automatic employee/taxonomy rights |
| HR | institutional scope role and employee/agency permission bundle | employee onboarding and institution employment workflows |
| Department staff | DEPARTMENT_ADMIN, matching campus/department, explicit codenames | matching students and employees whose current primary assignment matches scope |
| Read-only auditor | scoped managerial grant + view codenames only; field permissions as explicitly approved | scoped read only, masked by default |
| Student/employee self-service | verified AccountLink, active institution grant, view codenames | own linked roots/children only; no peer access or writes |

Registrar/HR/auditor are capability bundles, not newly created password or role tables. Existing TEACHER/STUDENT roles cannot use people write permissions to become managers. Employee drafts have no assignment scope yet; institutional HR/admin performs initial onboarding. Self-service links do not bypass record limits or grant permissions. A linked account may represent both an employee and a student, but generated unique link keys prevent multiple roots of the same type per user.

### Filters and examples

Lists: page, page_size (shared maximum100), search (maximum100 characters), ordering. Ordering allows pk and the resource's public directory name/code fields, with optional descending `-`. Search is restricted to names/public identifiers, not private contact or demographic values. Resource FK filters and enum/active/primary filters are allowlisted; masked fields cannot be filters. Repeated/unknown parameters are rejected. Querysets are scoped before any filtering, object lookup or export; object checks alone would not secure lists.

```http
POST /api/v1/people/students/
Content-Type: application/json

{"student_number":"S-2026-001","first_name":"Example","display_name":"Example Student","institution_id":"1","campus_id":"2","department_id":"3"}
```

Returns 201 with a full readable row including `"id":"..."`, `"student_status":"APPLICANT"`, `"version":"1"`, `actions` and `masked_fields`. IDs are illustrative; select real scoped references from Choices. After creating an address:

```http
POST /api/v1/people/student-addresses/12/set-primary/
Content-Type: application/json
If-Match: "1"

{"reason":"Address confirmed during onboarding"}
```

```http
POST /api/v1/people/students/8/status/
Content-Type: application/json
If-Match: "1"

{"status":"ACTIVE","reason":"Onboarding review complete"}
```

Updates return a new version and ETag. Missing If-Match gives 400; stale version gives409 stale_version. A schema/ownership/mark validation error gives400; a current-primary/lifecycle conflict gives409 people_conflict; denied operation403; hidden ID404; DELETE405. Errors use the existing `{error:{code,message,details}}` envelope. Expected database errors are translated outside the rolled-back transaction; SQL is not exposed. Frontend keeps unsaved values after conflicts.

## Account provisioning and delivery

An existing account is linked only by explicit invitation, never by matching email. `/invite/` accepts user_id/reason; the authenticated intended user submits its token to `/invitations/accept/`. `/provision/` accepts username/email/reason and creates a new inactive account with an unusable password and no roles. The recipient submits token/password to `/invitations/claim/`; password validators run and activation/linkage commit together. Tokens are returned once to the authorized operator, expire after24 hours, are stored only as hashes and cannot be replayed. No email was sent and no delivery worker is configured. Operators must use an approved delivery channel; never log or put tokens in URLs.

Provisioning does not grant people permissions or scope roles. Assign them explicitly after identity review. Domain status and account activity are separate. Unlink invalidates outstanding invitations without deleting the person or globally disabling a shared account. `/account/` changes the linked account globally and is platform-only; a domain contact email change never silently changes login email.

## Audit, privacy and integration

Support tables platform_people_revision, platform_people_audit, platform_people_event, platform_people_account_link and platform_people_invitation are explicitly separate from domain data. Mutations and redacted audit/event records commit atomically. Audit includes actor, institution, resource/key, timestamp, source, correlation, reason, outcome and changed field names. API denied operations log HTTP outcome without rejected personal values. Read accesses are audited; list/export events record operation/count without listing PII. Free-text reasons should not contain personal details.

Contact/demographic/financial fields are classified in catalogue.py. They are removed from unauthorized responses, not merely hidden by CSS. Audit before/after values redact sensitive fields; names and free-text values are also redacted. General logs and events contain no passwords/tokens/guardian income. Exports remain sensitive even when authorized and must follow institution handling policy.

Append-only managers/model methods and read-only admin are application controls, not DBA-proof tamper protection. No retention deletion job runs automatically. Operational owners must approve retention periods, legal holds and purge procedures before production; preservation is the safe default. Use deployment-managed encryption at rest/TLS and secret storage; this module does not claim field-level encryption or encrypted offline storage.

Public consumers import apps.people_master.public: identity(actor,institution_id,kind,record_id) -> immutable PersonIdentity; current_assignment(actor,institution_id,employee_id) -> AssignmentIdentity or None; events(actor,institution_id,after_audit_id,limit) -> versioned support-only event records. Events use people.<resource>.<action>.v1 and UUID deduplication IDs. Consumers own cursor/checkpoint transactions and retry deduplication. The durable log is not a broker or external delivery guarantee. Admissions, attendance, HR, finance and document modules are future consumers and are not claimed as implemented integrations.

Admin uses scoped service-backed saves, reason-required atomic lifecycle actions, optimized relation loading and no hard deletion. Composite-PK competencies use the React/API editor linked from Employee admin because installed Django5.2 admin cannot register them. In split-port development open the frontend explicitly; the relative shortcut assumes same-origin deployment. No raw CSV import endpoint exists; trusted import code can use services.bulk_save for bounded validated all-or-nothing batches. CSV export is available through the governed API.

## Frontend and offline behavior

React Hook Form and Zod validate typed metadata forms; MUI DataGrid uses server pagination/filtering/sorting. Parent choices are scoped/paginated and unchanged inactive IDs remain visible as saved selections. Details link to child histories. Loading, empty, stale version, field errors, dirty navigation and offline states are explicit. DataGrid columns expose public directory values only; detail/edit obey server masking.

The existing service worker remains NetworkOnly for all API/admin traffic and caches static assets only. People query caches are memory-only with zero retention after unmount, cleared on offline transition and unmounted on logout/session expiry. Personal API responses have no-store. Offline writes are disabled and are never queued. No browser visual/keyboard/accessibility certification is claimed from component tests.
