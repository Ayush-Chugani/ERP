# Demo data

`uv run python -m app.cli seed-demo` loads a sample campus (one institution, three campuses, departments, programmes,
51 students, 16 staff, timetable, attendance, assessments, grievances, research records...) and one demo login for every
built-in role. It is for evaluation and development only - never load it into production.

All demo accounts share the password **`Campus@2026`** (published here on purpose; change or delete these accounts in
any shared environment).

| Username | Role | Sign-in entrance (portal) | Scope | What to try |
| --- | --- | --- | --- | --- |
| `demoadmin` | Super administrator (demo) | Administrator | everything | owner dashboard, users, roles, audit trail, jobs |
| `sysadmin` | SYSTEM_ADMIN | Administrator | global | users, reference data, calendar; note it cannot see student or marks data |
| `secadmin` | SECURITY_ADMIN | Administrator | global | users and access, audit trail only |
| `orgadmin` | INSTITUTION_ADMIN | Organisation administrator | the sample institution only | create the institution's registrar, faculty, students, exam and support logins |
| `vc` | VICE_CHANCELLOR | Department & campus heads | institution | read-only oversight and exports across every module |
| `dean` | DEAN_ACADEMICS | Department & campus heads | institution | curriculum and calendar, approve staff records and registrations |
| `campusadm` | CAMPUS_DIRECTOR | Department & campus heads | campus | approvals and oversight for one campus |
| `hod` | HEAD_DEPARTMENT | Department & campus heads | department | review staff records, assign teaching, reopen attendance registers |
| `registrar` | REGISTRAR | Registrar & admissions | institution | admissions pipeline, students, calendar, curriculum, documents |
| `admissions` | ADMISSION_OFFICER | Registrar & admissions | institution | process applications; no access to marks |
| `docverifier` | DOCUMENT_VERIFIER | Registrar & admissions | institution | verify submitted documents |
| `sectionofficer` | STUDENT_SECTION_OFFICER | Registrar & admissions | institution | student records and term/course registration |
| `examcell` | CONTROLLER_EXAMINATIONS | Examination cell | institution | calculate and publish results |
| `examofficer` | EXAMINATION_OFFICER | Examination cell | institution | enter assessments and results; cannot verify or publish |
| `resultapprover` | RESULT_APPROVER | Examination cell | institution | verify and approve results; cannot edit or publish |
| `teacher` | FACULTY + STAFF_SELF | Faculty | department (own classes) / self | mark attendance, enter marks, add own research records |
| `labinstructor` | LAB_INSTRUCTOR | Faculty | department (assigned classes) | attendance and marks for assigned classes |
| `evaluator` | EVALUATOR | Faculty | department (assigned papers) | enter marks for assigned papers only |
| `coursecoord` | COURSE_COORDINATOR | Faculty | department (assigned papers) | faculty work plus approving lesson plans and coverage |
| `ttcoord` | TIMETABLE_COORDINATOR | Faculty | department | build and assign the timetable |
| `progcoord` | PROGRAMME_COORDINATOR | Faculty | programme | curriculum and registration approvals |
| `semcoord` | SEMESTER_COORDINATOR | Faculty | programme | curriculum and registration approvals |
| `advisor` | FACULTY_ADVISOR | Faculty | programme (own mentees) | counselling sessions for mentees only |
| `mentor` | MENTOR | Faculty | programme (own mentees) | counselling sessions for mentees only |
| `support` | GRIEVANCE_OFFICER | Support & finance | institution | grievance workflow |
| `finance` | FINANCE_OFFICER | Support & finance | institution | admission fee clearance; read-only projects and consultancy |
| `auditor` | INTERNAL_AUDITOR | Support & finance | institution | read-only everywhere, audit trail, exports |
| `extauditor` | EXTERNAL_AUDITOR | Support & finance | institution | read-only everywhere, audit trail, exports |
| `student`, `student2` | STUDENT | Student | self | own record, timetable, results once published, feedback, requests |
| `parent` | PARENT_GUARDIAN | Student | self (linked student) | linked student's attendance and published results |
| `alumni` | ALUMNI | Student | self | published results, certificate requests |
| `applicant` | APPLICANT | Student | self | own application and documents |

Staff personas (`evaluator` to `mentor`) are linked to unlinked staff of the head of department's department; `parent`,
`alumni` and `applicant` are linked to unlinked students. If the sample data has fewer unlinked people than personas, the
remaining logins exist without a linked person and show empty data.

The login page offers one entrance per audience. The API checks that the account really belongs to the entrance it was
used from (`wrong_portal` otherwise), so a student cannot sign in through the Administrator entrance and vice versa.
Roles and what they may do are documented in `docs/ROLES.md`.

The application owner uses a real super administrator account created with `create-admin` (for example `admin`) and
signs in through **Administrator**; it lands on the **Owner dashboard** (`/owner`) with people, access, sign-in activity,
background jobs, workflow backlog and system health, and has every permission.

The seed refuses to run if students already exist (use `--force` to override) and never overwrites existing rows.

## Test-environment reset (Supabase) and sample content

For a shared test database every account can be given one easy password:

```
uv run python -m tools.reset_test_users --password "admin@123" --yes
uv run python -m app.cli seed-content
```

`reset_test_users` deletes all users except `admin` (kept so authored records stay valid; it becomes the super
administrator), re-points "created by" references to `admin`, and recreates one account per role (the usernames in the
table above, minus `demoadmin`) with the given password. It refuses to run with `SIMS_ENV=production`; the weak password
is for testing only and must never be used on a real installation.

`seed-content` is repeatable. It fills every section with sample rows (timetable, attendance, marks, results,
mentoring, announcements, grievances, certificate requests, admissions, fee clearances, feedback, staff research records,
documents, qualifications) and links every staff persona to its own class sections or mentees, so each login has data on
the pages its role can open.
