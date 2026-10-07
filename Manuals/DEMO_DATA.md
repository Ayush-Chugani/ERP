# Demo data and role-based accounts

Development only. Never run these against a production database.

```powershell
backend/.venv/Scripts/python.exe backend/manage.py seed_sample_all
```

All seeders are idempotent (re-running adds nothing). Individually:

| Command | Adds |
|---|---|
| `seed_sample_data` | Students (50) with addresses/guardians, staff (15), courses (16), admissions and enrolments, announcements, academic years/terms, time slots, buildings and rooms |
| `seed_sample_academics` | CSE semester-3 teaching slice: course offerings, faculty assignments, student registrations, class sessions with attendance, internal-test marks, published weekly timetable |
| `seed_sample_staff` | Awards, memberships, contributions, conferences, consultancy, funded projects, proposals, internships, co- and extra-curricular activities (mixed verification/approval states) |
| `seed_sample_services` | Mentor assignments, counselling sessions, grievances with actions, certificate requests, feedback question bank |
| `seed_sample_users` | Role-based demo users (below) wired to people records, scope grants and IAM roles |

## Accounts

`admin` keeps whatever password you set (the seeders never touch it). Every other
account uses `DEMO_PASSWORD` defined at the top of
`backend/apps/core/management/commands/seed_sample_data.py`.

| Username | Role | Data scope | Linked record | What to expect |
|---|---|---|---|---|
| `admin` | Superuser | Everything | - | All modules, all data |
| `registrar` | Registrar | Institution | - | People (manage), admissions, registration, documents; read-only staff activities; no timetable/attendance |
| `campusadm` | Campus director | Campus 1 | - | Org/curriculum/calendar management for its campus, staff-activity review |
| `hod` | Head of department | CSE school | Employee EMP002 | Department students/staff, timetable planning, attendance, assessments, staff-activity verification |
| `teacher` | Faculty | CSE school | Employee EMP004 | Own sections' attendance, marks and timetable; own staff activities |
| `examcell` | Controller of examinations | Institution | - | Assessments/results, read-only calendar/curriculum |
| `support` | Student support officer | Institution | - | Mentoring, counselling, grievances |
| `student`, `student2` | Student | Own record | Students 01FE24BCS001 / 002 | Own attendance, registrations, documents, feedback |

## How access is enforced

1. **Django groups** (model permissions) gate the core modules: people, organization,
   calendar, curriculum, admissions, registration, attendance, timetable, assessments,
   support, documents, communication, feedback.
2. **IAM roles** (`role`, `role_permission`, `user_role_assignment`) gate the staff-activity
   modules (awards, conferences, consultancy, ...). The module installers grant these to
   SUPER_ADMIN only; `seed_sample_users` also grants sensible actions to FACULTY,
   HEAD_DEPARTMENT, CAMPUS_DIRECTOR and REGISTRAR.
3. **Scope grants** (`platform_organization_scope`) narrow rows by institution, campus,
   department or own record; `platform_institution_module` switches modules per institution.
4. The frontend hides navigation entries (and shows "Access restricted" for typed URLs) using
   `/auth/me/` (`permissions`, `access_modules`, `groups`). This is cosmetic: every endpoint
   re-checks permission and scope.
