# M6 implementation status

The user approved the revised schema and selected authorized manual fee-clearance references. No new approval is needed for the remaining prompts.

## Implemented in this increment

- Application boundary, four domain models and platform-support audit/receipt/clearance/outbox models.
- Reversible Django migrations, including unconditional scheme/programme ownership and application/student composite foreign keys.
- Applicant and draft application writes with field allowlists; scoped review/selection/reopening commands; manual fee attestation under a separate permission.
- Atomic admission linking an existing activated student, canonical applicant link, enrolment/history/audit/outbox/receipt writes and deterministic retry response.
- Basic enrolment lifecycle with ordered immutable history and optimistic version checks.
- DRF list/detail/create/PATCH and dedicated workflow actions; scoped read-only Django admin; bounded duplicate candidates.
- Idempotent permission-bundle seed command, preserving existing administrator group edits.

## Not yet complete

This is not completion of all twelve prompts. New-student creation inside admission, transfer/scheme/date-correction commands, export, the React admission UI, durable outbox delivery, legacy import tooling and the full release gates remain outstanding. Current admission accepts an existing ACTIVE student with a valid primary address, using the governed People adapter. It never creates or merges a student implicitly.

The module is installed but **disabled by default** (`SIMS_ADMISSION_ENROLMENT_ENABLED=0`). Do not enable for production while these items remain incomplete. API route registration alone does not enable access.

## Endpoint and permission matrix

All paths start `/api/v1/admissions/`. Authentication, global module enablement, active institution membership/module grant and authorized scope are checked in addition to the named permission. Superusers bypass institution scope but not the global module switch. Object checks do not filter lists: the query is scoped before list filtering or object lookup.

| Endpoint | Methods | Required permission |
|---|---|---|
| applicants/ and applicants/{id}/ | GET | view_admissionapplicant |
| applicants/ | POST | add_admissionapplicant; institution-wide admissions scope |
| applicants/{id}/ | PATCH | change_admissionapplicant; draft-only references |
| applicants/{id}/duplicate-candidates/ | GET | view_admissionapplicant + sensitive_admission |
| applications/ and applications/{id}/ | GET | view_admissionapplication |
| applications/ | POST | add_admissionapplication; visible applicant |
| applications/{id}/ | PATCH | change_admissionapplication; DRAFT only |
| applications/{id}/transition/ | POST | review_admission, select_admission or reopen_admission according to target |
| applications/{id}/fee-clearance/ | POST | record_fee_clearance |
| applications/{id}/admit/ | POST | admit_admission plus scoped People student visibility |
| enrolments/ and enrolments/{id}/ | GET | view_studentprogrammeenrolment |
| enrolments/{id}/transition/ | POST | lifecycle_admission |
| history/ and history/{id}/ | GET | view_enrolmentstatushistory |

No DELETE, generic enrolment editing, history editing or public support-table API exists. Sensitive applicant birth/contact/caste/category fields additionally require `sensitive_admission` for reading or writing. Audit and fee evidence admin access is restricted to platform superusers. Admin is inspection-only to prevent bypass of versioned commands.

Lists use project pagination (default 25, bounded at 100), allowlisted ordering and prefix search. Applicant filter: institution_id; application filters: programme_id, academic_year_id, application_status, eligibility_status, admission_applicant_id; enrolment filters: programme_id, student_id, admission_academic_year_id, enrolment_status; history filter: enrolment_id. Examples: `applications/?programme_id=1&application_status=SELECTED&page=1&ordering=-application_date`, `history/?enrolment_id=1&ordering=sequence_number`.

## Example workflow

Use actual returned IDs and versions; these values are illustrative. Supply authentication using the existing session/client flow.

```http
POST /api/v1/admissions/applications/42/fee-clearance/
Content-Type: application/json
If-Match: 5

{"reference":"FINANCE-RECEIPT-2026-014"}
```

Returns 201 with no body. This records the authorized officer's attestation against application version 5. A subsequent application transition invalidates that clearance for conversion.

```http
POST /api/v1/admissions/applications/42/admit/
Content-Type: application/json
If-Match: 5
Idempotency-Key: admission-42-attempt-1

{"student_id":17,"curriculum_scheme_id":3,"admission_semester_id":1,"admission_date":"2026-09-01"}
```

Returns the enrolment representation with string `enrolment_id`, `application_id`, `student_id` and an integer version. Retrying the same key and payload returns the same enrolment; changed payload returns 409. A stale version or missing clearance also returns 409. Unauthorized operations return 403; out-of-scope IDs return 404; invalid payloads return 400. SQL is never included in mapped constraint errors.

## Local verification and rollout

From repository root:

```powershell
backend/.venv/Scripts/python.exe backend/manage.py check
backend/.venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
backend/.venv/Scripts/python.exe -m pytest backend/apps/admission_enrolment/tests -q --reuse-db
backend/.venv/Scripts/python.exe backend/manage.py migrate --plan
```

Only apply migrations to the intended configured database after backup according to existing project operations. `seed_admission_roles` creates groups but does not assign users, enable institutions or grant sensitive demographics. Admission integration also requires the existing People read permissions and scope.

Runtime writes and audit/outbox/receipt rows share an atomic transaction. Application-level append-only behavior is not database-administrator-proof protection. Outbox delivery is not implemented yet; rows are retained, and no emails or payment writes are performed. No production deployment or browser acceptance is claimed.

## Verified locally

Applied curriculum migration 0003, admission migrations 0001?0002 and tenancy migration 0005 to the configured local MySQL database. Nine focused tests passed, including a two-connection simultaneous admission retry, whole-transaction rollback, schema ownership constraints, permissions, mass assignment, stale versions and append-only history. Django system checks and migration drift checks passed. No frontend or production acceptance is claimed.
