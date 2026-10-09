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
submit -> `UPDATE`, verify/review -> `VERIFY`, approve/reject -> `APPROVE`, publish -> `PUBLISH`). A `DENY` grant overrides any
`ALLOW`. Administrators manage users and custom roles in the UI under **Administration -> Users / Roles and permissions**.

## The role matrix (least privilege)

The authoritative definition is `backend/app/rbac/matrix.py`; this page is derived from it (if they differ, the matrix wins). Letters used below:
**R** read, **C** create, **U** update, **D** delete, **A** approve, **V** verify, **P** publish, **S** assign,
**X** export, **F** configure. "R/X" means read and export. Delete (**D**) is held only by the super administrator,
the system administrator (reference data and academic calendar) and staff for their own records; no role other than the
super administrator holds the sensitive staff identifier permissions.

Roles that are sign-in-only helpers (not in `matrix.py`): **SUPER_ADMIN** (platform owner, every permission including
Aadhaar/PAN/bank), **DATABASE_ADMIN** (platform operations) and **INSTITUTION_ADMIN** (delegated organisation administrator,
see the last section).

### Platform
| Role | Assigned at | Can do | Must not |
| --- | --- | --- | --- |
| SUPER_ADMIN | global | everything; the only holder of the sensitive staff-identifier permissions | - |
| SYSTEM_ADMIN | global | users and access (IAM RCUSFX), reference data RCUDX, academic calendar RCUDPX, communication RCUPX, institution RCUX, audit R/X, reporting R/X | see or edit student, staff, marks, results or admissions data; approve anything |
| SECURITY_ADMIN | global | users and access (IAM RCUSFX), audit trail R/X | touch any academic, student or staff data |

### Leadership
| Role | Assigned at | Can do | Must not |
| --- | --- | --- | --- |
| VICE_CHANCELLOR | institution | read and export every operational module (admissions, assessment, attendance, results, students, staff, grievances, timetable ...), audit R/X, staff research records R/A/X | create, edit, delete, verify or publish anything; read Aadhaar/PAN/bank numbers |
| DEAN_ACADEMICS | institution | curriculum and academic calendar RCUAPX, registration R/A/X, students R/A/X, results R/X, staff research records R/A/V/X, read and export most other modules, audit R/X | edit student records, marks or results; publish results; create admissions |
| CAMPUS_DIRECTOR | campus | students R/A/X, staff R/A/X, grievances R/A/S/X, timetable R/A/P/X, results R/A/X, admissions R/X, institution R/U/X, communication RCUPX, staff research records R/A/V/X, read and export other modules | verify or publish results; change curriculum; edit students |
| HEAD_DEPARTMENT | department | teaching RCUSX, timetable RCUASX, attendance R/A/X (reopen registers), results R/V/X, mentoring RCUSX, curriculum RCUX, registration R/A/X, communication RCU, staff research records R/A/V/X, read and export students, staff, assessment, admissions, documents, feedback, reporting; grievances R | approve or publish results; mark attendance or enter marks directly; read sensitive staff identifiers |

### Registrar and admissions
| Role | Assigned at | Can do | Must not |
| --- | --- | --- | --- |
| REGISTRAR | institution | students RCUAX, admissions RCUAVX, registration RCUAX, academic calendar and curriculum RCUAPX, documents RCUAVPX, communication RCUAP, reference data RCUX, audit R/X; read and export assessment, results, attendance, staff, timetable, teaching, reporting; read feedback, mentoring, grievances, staff research records | enter or change marks and results, publish results, review staff research records |
| ADMISSION_OFFICER | institution | admissions RCUAVX; read students, documents, communication | touch results, marks, registration or staff data |
| DOCUMENT_VERIFIER | institution | documents R/V; read students and admissions | create or edit documents or students; (field-level restriction not implemented, see gaps) |
| STUDENT_SECTION_OFFICER | institution | students RCUX, registration RCUAX, documents R/V; read admissions and communication | admit or approve admissions; touch marks or results |

### Examination cell
| Role | Assigned at | Can do | Must not |
| --- | --- | --- | --- |
| CONTROLLER_EXAMINATIONS | institution | assessments RCUAPX, results RCUAVPX (the only role that can publish), registration R/U/X, documents RCUAVPX, communication RCUP, read students and attendance, reporting R/X | edit student master data or staff data |
| EXAMINATION_OFFICER | institution | assessments RCUX, course and term results create/update, results R/X, read registration, students, documents, communication | verify, approve or publish results (segregation of duties) |
| EVALUATOR | department (limited to assigned papers) | read assessments and registration, student marks RCU, read the student record of assigned papers | see other papers; verify or publish; anything beyond marks |
| RESULT_APPROVER | institution | results R/A/V/X; read assessments, students, registration, documents | create or edit results or marks; publish results |

### Faculty
| Role | Assigned at | Can do | Must not |
| --- | --- | --- | --- |
| FACULTY | department (limited to assigned classes) | read calendar, curriculum, timetable, teaching, students, registration, feedback, communication, mentoring; class sessions, student attendance, lesson coverage, lesson-plan revisions and attendance-correction requests RCU; assessment events and student marks RCU; counselling sessions RCU | delete, approve or publish anything; see results of others; reach classes they are not assigned to |
| LAB_INSTRUCTOR | department (limited to assigned classes) | same permissions as FACULTY | as FACULTY (not restricted to lab sections, see gaps) |
| COURSE_COORDINATOR | department (limited to assigned papers) | everything FACULTY can, plus assessments RCU and approval of lesson-plan revisions and lesson coverage | publish or verify results |
| TIMETABLE_COORDINATOR | department | timetable RCUSA, teaching RCUS; read attendance, calendar, registration, curriculum, institution, staff | touch students, marks or attendance entries |
| PROGRAMME_COORDINATOR | programme | curriculum RCU, registration R/A/X; read students, calendar, teaching, timetable | touch marks, results or attendance |
| SEMESTER_COORDINATOR | programme | same as PROGRAMME_COORDINATOR | same as PROGRAMME_COORDINATOR |
| FACULTY_ADVISOR | programme (limited to own mentees) | mentoring RCUX; read students, attendance, results, communication | see non-mentees; change marks or attendance |
| MENTOR | programme (limited to own mentees) | same as FACULTY_ADVISOR | same as FACULTY_ADVISOR |
| STAFF_SELF | self (added automatically to staff who are linked to an account) | create, read, update and delete one's own research, awards, conferences, consultancy, funded projects, proposals, internships, memberships, contributions, co-/extra-curricular records and evidence | review or approve (own or others'); see other staff members' records |

### Support, finance and audit
| Role | Assigned at | Can do | Must not |
| --- | --- | --- | --- |
| GRIEVANCE_OFFICER | institution | grievances R/U/S/A/X; read students, mentoring, communication | create or delete grievances; touch marks, results or staff data |
| FINANCE_OFFICER | institution | read admissions, funded projects, consultancy, reporting; admission fee clearance R/V/X | edit admissions; no fee modules exist yet (see gaps) |
| INTERNAL_AUDITOR | institution | read and export every operational module, the audit trail and staff records | write anything |
| EXTERNAL_AUDITOR | institution | same as INTERNAL_AUDITOR | write anything |

### Self-service
| Role | Assigned at | Can do | Must not |
| --- | --- | --- | --- |
| STUDENT | self | own profile (R/U) and addresses (RCU), timetable, attendance, published results, admissions, documents, feedback; certificate requests, document uploads, attendance-correction requests, term/course registration RCU; grievances RC; feedback responses RC | see other students; see unpublished results; delete anything |
| APPLICANT | self | own applicant record and application RCU, upload documents | see other applicants or any student data |
| PARENT_GUARDIAN | self | read the linked student's record, attendance, published results and communication | change anything |
| ALUMNI | self | own record R, published results, documents, certificate requests RCU, feedback responses RC | change anything else |

## Rules worth knowing
* **Segregation of duties.** The people who enter a record cannot approve it: examination officers enter results but only
  the result approver verifies/approves and only the controller publishes; the finance officer can verify fee clearance but cannot
  edit admissions; reviewers can never verify or approve a record they own.
* **Results reach students only after publication.** Students, parents and alumni see only results the examination cell has published.
* **Submitted records are locked.** Staff records cannot be edited after submission until
  they are returned or withdrawn.
* **Sensitive staff identifiers need specific permissions.** Aadhaar, PAN and bank accounts require
  `EMPLOYEE_AADHAAR` / `EMPLOYEE_PAN` / `EMPLOYEE_BANK_ACCOUNT`; module-wide grants never cover them and only the super
  administrator holds them.
* **Deny wins.** A `DENY` grant overrides any `ALLOW`.
* **Built-in roles are reconciled to `matrix.py`.** `python -m app.cli bootstrap` makes the database match the matrix
  exactly: missing grants are added and grants not in the matrix are removed. Edits made to a built-in role in the UI are
  reverted on the next deployment. To customise access, **create a new role** (Administration -> Roles and permissions)
  and assign that instead.
* **Teaching roles are row-limited.** Faculty, lab instructors, evaluators and course coordinators reach only the class
  sections / papers they are assigned to through `faculty_course_assignment` (class sessions, attendance, lesson
  coverage, lesson-plan revisions, correction requests, assessment events, marks, section rosters). Mentors and faculty
  advisors reach only their mentees through `mentor_assignment` (the student record, address, attendance, results and
  correction requests of those mentees; counselling sessions and mentor assignments are visible only to the mentor
  themselves). A person who also holds a wider role (for example head of department) is not restricted.
* **Programme-scoped roles see students through enrolment.** Programme coordinators, semester coordinators and the like see
  the students enrolled in their programme.

## Known gaps
* There are no fees, library, hostel, transport or placement modules. The finance officer is therefore limited to admission
  fee clearance and read-only views of projects and consultancy; add the role grants when those modules arrive.
* The lab instructor has the same permissions as faculty and is limited to assigned classes, not to lab sections only.
* The document verifier verifies whole document records; a field-level restriction (for example verify but never see
  contact data) is not implemented.

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
