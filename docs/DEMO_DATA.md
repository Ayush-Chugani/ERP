# Demo data

`uv run python -m app.cli seed-demo` loads a sample campus (one institution, three campuses, departments, programmes,
51 students, 16 staff, timetable, attendance, assessments, grievances, research records…). It is for evaluation and
development only — never load it into production.

All demo accounts share the password **`Campus@2026`** (published here on purpose; change or delete these accounts in
any shared environment).

| Portal (sign-in entrance) | Username | Role | Scope | Try |
| --- | --- | --- | --- | --- |
| Organisation administrator | `orgadmin` | INSTITUTION_ADMIN | the sample institution only | create the institution's registrar, faculty, students, exam and support logins |
| Administrator | `demoadmin` | Super administrator (demo) | everything | owner dashboard, users, roles, audit trail, jobs |
| Student | `student`, `student2` | STUDENT | self | own record, timetable, results once published, feedback, requests |
| Faculty | `teacher` | FACULTY + STAFF_SELF | department / self | mark attendance, enter marks, add own research records |
| Department & campus heads | `hod` | HEAD_DEPARTMENT | department | review staff records, reopen attendance registers |
| Department & campus heads | `campusadm` | CAMPUS_DIRECTOR | campus | approvals and oversight for one campus |
| Registrar & admissions | `registrar` | REGISTRAR | institution | admissions pipeline, students, calendar, curriculum |
| Examination cell | `examcell` | CONTROLLER_EXAMINATIONS | institution | calculate and publish results |
| Support & finance | `support` | GRIEVANCE_OFFICER | institution | grievance workflow |

The login page offers one entrance per audience. The API checks that the account really belongs to the entrance it was
used from (`wrong_portal` otherwise), so a student cannot sign in through the Administrator entrance and vice versa.

The application owner uses a real super administrator account created with `create-admin` (for example `admin`) and
signs in through **Administrator**; it lands on the **Owner dashboard** (`/owner`) with people, access, sign-in activity,
background jobs, workflow backlog and system health, and has every permission.

The seed refuses to run if students already exist (use `--force` to override) and never overwrites existing rows.
