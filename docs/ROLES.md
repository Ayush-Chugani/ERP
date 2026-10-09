# Roles, scopes and permissions

Access is decided by **permission codes** (`MODULE.RESOURCE.ACTION`, e.g. `ADMISSION.ALL.APPROVE`) held through
**roles**, each assigned to a user at a **scope**:

| Scope | Rows the holder can reach |
| --- | --- |
| `GLOBAL` | everything |
| `INSTITUTION` | the institution and every campus, department and programme beneath it |
| `CAMPUS` | the campus and its departments and programmes |
| `DEPARTMENT` | the department and its programmes |
| `PROGRAMME` | the programme |
| `SELF` | only records belonging to the person linked to the account (their own student/employee data) |

`MODULE.ALL.ACTION` covers every resource of a module; a finer `MODULE.<TABLE>.ACTION` grants one resource. Actions:
`READ CREATE UPDATE DELETE APPROVE VERIFY PUBLISH ASSIGN EXPORT CONFIGURE`. Workflow buttons map to actions (for example
submit → `UPDATE`, verify/review → `VERIFY`, approve/reject → `APPROVE`, publish → `PUBLISH`). A `DENY` grant overrides any
`ALLOW`. Administrators manage all of this in the UI under **Administration → Users / Roles and permissions**.

## Built-in roles (summary)
| Role | Level | Main responsibilities |
| --- | --- | --- |
| SUPER_ADMIN / SYSTEM_ADMIN / SECURITY_ADMIN | global | platform, users, roles, configuration |
| VICE_CHANCELLOR, DEAN_ACADEMICS | institution | oversight, approvals, curriculum |
| REGISTRAR | institution | admissions, students, registration, calendar, curriculum, documents |
| ADMISSION_OFFICER, STUDENT_SECTION_OFFICER, DOCUMENT_VERIFIER, FINANCE_OFFICER | institution | one part of the student lifecycle each |
| CONTROLLER_EXAMINATIONS, EXAMINATION_OFFICER, RESULT_APPROVER, EVALUATOR | institution / department | assessments, results, publication |
| GRIEVANCE_OFFICER | institution | grievance workflow |
| INTERNAL_AUDITOR, EXTERNAL_AUDITOR | institution | read-only oversight, audit trail |
| CAMPUS_DIRECTOR | campus | campus-wide approvals and oversight |
| HEAD_DEPARTMENT, TIMETABLE_COORDINATOR, COURSE_COORDINATOR | department | timetable, teaching, review of staff records |
| PROGRAMME_COORDINATOR, SEMESTER_COORDINATOR, FACULTY_ADVISOR, MENTOR | programme | curriculum, registration, mentoring |
| FACULTY, LAB_INSTRUCTOR | department | attendance, marks, mentoring for their classes |
| **STAFF_SELF** | self | create and edit one's *own* research, awards, memberships and other staff records (added automatically with teaching roles) |
| STUDENT, APPLICANT, PARENT_GUARDIAN, ALUMNI | self | own record, requests, registrations, published results, feedback |

Defaults live in `backend/app/rbac/catalogue.py` (`EXTRA_GRANTS`) and the packaged base fixture; `python -m app.cli bootstrap`
only ever **adds** grants, so changes you make in the UI are never undone by a deployment.

## Rules worth knowing
* Reviewers can never verify/approve a record they own.
* Submitted staff records are locked until returned or withdrawn.
* Students see results only after the examination office publishes them.
* Staff identifiers (Aadhaar, PAN, bank accounts) require the specific `EMPLOYEE_AADHAAR` / `EMPLOYEE_PAN` /
  `EMPLOYEE_BANK_ACCOUNT` permission; only super administrators hold them by default.


## Delegated administration (organisations)

```
Super administrator (platform owner)
  -> creates an organisation and its Organisation administrator    POST /api/v1/security/organisations
       -> Organisation administrator (role INSTITUTION_ADMIN, scoped to that organisation)
            -> creates registrar, faculty, heads, examination cell, support, students ...
               POST /api/v1/security/users {role_code, scope_type, scope_id}
```

* Every login belongs to an organisation (`user_account.institution_id`). Organisation administrators can list, create,
  edit, reset, lock and assign roles **only inside their own organisation**; other organisations' accounts and the
  platform owner's accounts answer `404`.
* They cannot create or assign `SUPER_ADMIN`, `SYSTEM_ADMIN`, `SECURITY_ADMIN`, `DATABASE_ADMIN` or `INSTITUTION_ADMIN`
  (only a super administrator can), cannot assign a role holding permissions they do not hold themselves, and cannot
  assign a scope outside their organisation. They cannot edit role definitions, see background jobs or the owner dashboard.
* Temporary passwords are generated, returned once, and must be replaced at first sign-in.
* Account and access tables are not exposed through the generic resource API to anyone but super administrators;
  accounts are managed from the Administration pages.
