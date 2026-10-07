# M24 ? Industry / Faculty Internship

## Status

Implemented the prompt pack's application path: canonical model and native migration; shared sector master; transactional create/update; M15 scopes; API; PWA; shared-file evidence; staff-activity workflow; CSV reporting; validation; retry/version protection; seeds and tests. Runtime activation remains off. This is a tested local implementation, not a production deployment or a claim that preceding queued modules are complete.

The input DOCX and consolidated SQL were not edited. Instructions in the pack were treated as implementation requirements, not authority to send notifications, grant users access or deploy.

## Architecture and database mapping

- `faculty_internships.FacultyInternship` owns exactly `faculty_internship`. All 18 source columns are represented. `staff_activity_id` is both the one-to-one primary key and a protected FK to the existing canonical parent.
- `staff_profile.IndustrySector` owns `industry_sector`; external organizations remain in the existing `ExternalOrganization` master. No organization or sector business rows are invented by the seed.
- Employee, institution, campus, department, academic year, dates, actors, approval and verification remain on `StaffActivity`. Creation derives employee and organizational scope from a dated `EmployeeAssignment`, valid throughout the internship.
- MySQL/MariaDB migrations install frozen source DDL, including unsigned keys, native stipend ENUM, DECIMAL(14,2), CHAR(3), native TEXT, named FKs/checks and utf8mb4 collation. Existing source-table collisions require explicit adoption review. ORM deletions use PROTECT.
- Two explicitly named platform extensions belong to the shared `staff_activities` app: `platform_staff_activity_receipt` stores actor/key/payload-digest/parent retry receipts; `platform_staff_activity_attachment` links retained M13 FileObject versions to the shared parent. Neither duplicates binaries or employee context. The larger source `evidence_document` catalogue is not implemented by this module.
- Shared `staff_activities.workflow` uses the existing approval/verification status fields and M15 audit. No independent internship status column is introduced.
- The source parent/type compatibility is checked on every locked write. M22 also rejects parents already specialized as an internship.

See `M24_SCHEMA_INVENTORY.json` for exact source and installed DDL plus model/column mapping. Platform extensions intentionally use normal Django migrations and source-compatible referenced key types.

## Validation and editing policy

Required trimmed title; active host organization; active optional sector; valid optional mentor email; nonnegative optional stipend; uppercase three-letter currency. NONE clears the amount after rejecting negative input. No hard-coded organization/sector choices. Parent dates are required and ordered for internships.

Only DRAFT/RETURNED records are editable. Ownership and dates are immutable after creation: withdraw/recreate an incorrect context. This conservative correction policy prevents silent organizational reassignment; administrative context correction is not exposed. No direct workflow/status assignment or client-supplied institution/employee/actor fields are accepted. Unknown request fields fail validation.

Updates, archive, workflow and uploads require a current version. Versions include the latest audit identifier as well as parent/child/evidence state, preventing a rapid change-and-revert from accepting an old token. The detail response reads its data and version under the same parent lock.

Create and all workflow commands require `Idempotency-Key` (1?100 ASCII letters/digits/underscore/dot/colon/hyphen). Actor-row locking and a unique actor/key constraint serialize simultaneous attempts. Same key and payload returns the existing record after fresh scope checks; a different payload is HTTP 409. Failed transactions do not leave parent, subtype, receipt or audit fragments. Receipts are retained; do not reuse keys for new actions.

## API

Base: `/api/v1/faculty-internships/`.

| Method and path | Behavior |
| --- | --- |
| GET `activities/` | Scoped, bounded list |
| POST `activities/` | Create draft; Idempotency-Key required |
| GET `activities/{id}/` | Parent/child detail, current version, actions, scoped evidence, audit history |
| PATCH `activities/{id}/` | Edit draft/returned fields with version |
| DELETE `activities/{id}/` | Soft archive eligible state with version |
| POST `activities/{id}/workflow/` | Transition with action, remarks, version and Idempotency-Key |
| POST `activities/{id}/evidence/` | Multipart file/title/category/version; optional replaces |
| GET `activities/{id}/evidence/{attachment_id}/download/` | Reauthorize parent, link, file confidentiality and integrity; private stream |
| GET `activities/summary/` | Filtered report groups; amounts separated by currency |
| GET `activities/export/` | Same filtered READ ? EXPORT scope, CSV-safe values, maximum 10,000 rows |
| GET `lookups/` | Capabilities, default-own indication, evidence categories |
| GET `lookups/{assignments,organizations,sectors,years}/` | Searchable paginated choices; assignments constrained by CREATE scope |

List/report filters: employee, institution, campus, department, academic_year, organization, industry_sector, domain, stipend_type, status, date_from, date_to, mine=1 and search. Search covers title, organization, mentor and domain. Ordering is an explicit whitelist. Pagination defaults to 25, maximum 100. Dates use YYYY-MM-DD; monetary values use decimal strings; IDs are serialized as strings. Reports group by year/institution/campus/department/employee/host/sector/domain/stipend/status. CSV includes all internship fields, parent context, inclusive calendar duration and workflow status. Group displays are capped at 100 per dimension with explicit truncation metadata. Evidence/history detail is bounded to the most recent 100 entries; retained older files remain accessible through authorized link endpoints.

Example create body:

```json
{"context":{"employee_assignment_id":"42","academic_year_id":null,"start_date":"2026-10-01","end_date":"2026-10-31"},"activity":{"organization_id":"18","internship_title":"Industry placement","stipend_incentive_type":"NONE","currency_code":"INR"}}
```

Use actual authorized reference IDs. Send a new random Idempotency-Key for each distinct command and preserve it when retrying that command.

## Permission and workflow matrix

All codes start `FACULTY_INTERNSHIPS.ACTIVITY.`. M15 catalogue/evaluator and fresh principal checks govern all services, querysets and exports. Deny overrides win. Supported scopes are GLOBAL, INSTITUTION, CAMPUS, DEPARTMENT and SELF; SELF is the linked login principal, not an employee ID. Unsupported PROGRAMME scope grants no access here. Superuser alone does not bypass M15 business grants.

| Permission | Use |
| --- | --- |
| READ | Scoped list/detail/history; required with CREATE/UPDATE/workflow responses |
| CREATE | Create using an eligible assignment |
| UPDATE | Draft/returned edits, submit, withdraw and evidence upload |
| VERIFY | Independent review, return and verification |
| APPROVE | Independent approval/rejection |
| DELETE | Soft archive draft/returned/withdrawn/rejected |
| EXPORT | Reports/CSV intersected with READ scope |

DRAFT/RETURNED ? SUBMITTED; SUBMITTED ? UNDER_REVIEW; SUBMITTED/UNDER_REVIEW ? VERIFIED; SUBMITTED/UNDER_REVIEW/VERIFIED ? RETURNED or REJECTED; VERIFIED ? APPROVED. DRAFT/RETURNED/SUBMITTED may be WITHDRAWN. Verify/approve/reject/return require remarks. Creator and linked faculty owner cannot perform reviewer/approver actions on their own record. Return clears prior verification. Actor/time fields are server-owned. Status transitions and field-change names enter the append-only M15 audit; free-text mentor details and rationale are not copied into general audit logs. Latest rationale remains on the protected parent.

## Evidence and retention

Evidence categories cover offer letters, completion certificates, host letters, work reports, photographs, MoU and other evidence. Upload creates a new managed file; replacement references the previous link and preserves its file. Cross-record replacements and downloads are rejected. A one-to-one replacement relationship prevents branching replacement chains.

Uses M13 `upload_shared`/`download_shared`, its durable transaction cleanup, membership/shared-upload checks, file-level permissions, content parsing, scanner, size limits, random storage keys, download checksum verification and audit. The current shared provider permits PDF/PNG/JPEG only. Internship evidence is RESTRICTED; users additionally require M13 share/file-level permissions, and their institution must be enabled for M13. No arbitrary existing file ID can be attached. Files never appear as public storage URLs. Configure approved storage/scanner providers before rollout; no permissive substitute is installed.

Archiving retains the parent, child, receipts, audit and files. Reverse migrations refuse to drop populated canonical internship/sector tables or populated shared attachment/receipt tables. Normal workflow provides no hard-delete or purge path.

## PWA and user guides

Open `#/faculty-internships` from the navigation. Faculty linked to an employee default to My records; the scope selector can show the remainder of their authorized scope. Lists have mobile cards and an accessible desktop table, filters, ordering and pagination.

Faculty: choose New internship, select the dated assignment, enter dates and optional academic year, choose the host/sector, and enter work/mentor/financial/collaboration details. Save draft, upload permitted evidence, then Submit. Returned records can be edited and resubmitted. To correct ownership/dates, withdraw and create a corrected draft. Reviewers: open an authorized record, inspect evidence, then review/return/verify with remarks. Approvers can approve verified records or reject eligible records. Faculty cannot self-review even if their account has broad grants.

The UI shows server-permitted detail actions, field errors and conflict messages. Drafts live only in memory, with unsaved-navigation warnings. Offline writes/downloads are disabled, and API responses are private/no-store under the existing NetworkOnly service-worker policy. There is no background write queue. Preserve the open form and retry the same request after a network failure; refresh before attempting a conflicting edit. Evidence uploads use the record version, so a lost response followed by a stale retry cannot silently attach the same file twice.

Administrators: install required masters and permission catalogue, maintain canonical organizations/sectors through their owning master-data process, grant explicit scoped roles, configure M13, then enable the module in a coordinated release. Django admin is scoped read-only; mutations use the service-backed API/PWA.

## Installation and rollback

From the repository root, with the configured development/staging environment:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py migrate --noinput
backend/.venv/Scripts/python.exe backend/manage.py seed_faculty_internships
backend/.venv/Scripts/python.exe backend/manage.py check
```

Migrations: `staff_profile.0003_industrysector`, `faculty_internships.0001_initial`, `staff_activities.0003_activityattachment_activitycommandreceipt`. Source DDL requires MySQL/MariaDB. The seed reuses or installs stable FACULTY_INTERNSHIP type and necessary status codes, preserves existing labels, and rejects incompatible/inactive existing configuration. It creates seven permission definitions, never role assignments or organization/sector rows. M15 action catalogue must already exist.

Activation requires `SIMS_FACULTY_INTERNSHIPS_ENABLED=1` plus coordinated M15 identity/security activation, explicit scoped grants, and the M13 institution/storage/scanner setup for evidence. Default M24 request throttling is 120/minute per authenticated principal; configure `SIMS_FACULTY_INTERNSHIPS_RATE` and a shared production cache/edge limits as appropriate. Neither runtime flags nor deployment secrets were changed during implementation.

For rollback, disable the M24 flag first and keep historical tables/files. Reversing migrations is only supported while the affected tables are empty; populated history requires an approved retention/migration plan. Do not bypass the guards or disable foreign-key checks.

## Verification and remaining release work

See `M24_VERIFICATION.json` for final commands/results. Native tests ran on the real local MySQL test database. Clean test-database migrations and the existing development-database upgrade succeeded. List query count is constant from one to five rows; representative read-only EXPLAIN plans are in `M24_QUERY_PLANS.json`. Source PK/FK indexes were retained; no speculative indexes added. Empty/local distributions are not production performance evidence.

Remaining operational acceptance: real-browser keyboard/mobile viewport QA, institution role sign-off, representative-volume staging plans/load tests, configured document providers, coordinated flag activation and post-deploy smoke checks. These have not been performed or claimed.

Notification delivery is not available in the existing shared communication implementation (it currently supplies announcements). M24 records workflow audit events but does not invent an outbound delivery subsystem or send real messages. A future shared notification adapter can consume approved workflow events with the institution's delivery policy. XLSX/PDF exports are not added; existing safe CSV is used.

## Changed-file inventory

New: `backend/apps/faculty_internships/` (models, native migration helpers, services, scoped permissions, API/routes, read-only admin, seed command and tests); `backend/apps/staff_activities/workflow.py`; shared activity extension migration; sector migration/native helpers; `frontend/src/features/faculty-internships/InternshipsApp.tsx`; `frontend/tests/internships.test.tsx`; `scripts/m24_verification.py`; M24 manuals/artifacts.

Updated: shared staff models; staff-profile model; settings and URL registration; frontend navigation/test registration; M22 specialization check and standalone test action fixture; module execution queue.
