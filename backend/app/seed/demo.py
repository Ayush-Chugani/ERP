"""Demo campus: sample students, staff, timetable and personas. Development / evaluation only."""
import sqlalchemy as sa

from app.core.security import hash_password
from app.db.session import db_session
from app.seed import loader

DEMO_PASSWORD = "Campus@2026"  # published in docs/DEMO_DATA.md; never use outside demos


def load_demo(force: bool = False) -> None:
    import app.models  # noqa: F401
    from app.rbac import catalogue

    pw = hash_password(DEMO_PASSWORD)

    def transform(table: str, rec: dict) -> dict:
        if table == "user_account":
            rec["password_hash"] = pw
            rec["must_change_password"] = False
        return rec

    with db_session() as db:
        loader.load(db, "base", only_if_empty=True)
        if not force and db.execute(sa.text("SELECT count(*) FROM student")).scalar():
            print("Database already contains people; use --force to load the demo data anyway.")
            return
        counts = loader.load(db, "demo", transform=transform)
        catalogue.sync(db)
        # Staff maintain their own research / professional records through the SELF-scoped STAFF_SELF role.
        for (uid,) in db.execute(sa.text("SELECT DISTINCT user_id FROM person_account_link WHERE employee_id IS NOT NULL")):
            catalogue.ensure_staff_self(db, uid)
    ensure_demo_org_admin()
    ensure_demo_personas()
    print(f"Demo data loaded ({sum(counts.values())} rows). Sign in as demoadmin / registrar / hod / teacher / "
          f"student with the password in docs/DEMO_DATA.md.")


def ensure_demo_org_admin() -> None:
    """The sample institution's own administrator, for trying the delegated-administration flow (idempotent)."""
    with db_session() as db:
        inst = db.execute(sa.text("SELECT institution_id FROM institution ORDER BY institution_id LIMIT 1")).scalar()
        if inst is None:
            return
        # demo logins all belong to the sample institution (leaves platform super administrators untouched)
        db.execute(sa.text("UPDATE user_account SET institution_id = :i WHERE institution_id IS NULL AND NOT is_superuser"), {"i": inst})
        if db.execute(sa.text("SELECT 1 FROM user_account WHERE username = 'orgadmin'")).first():
            return
        uid = db.execute(sa.text(
            "INSERT INTO user_account (username, email, first_name, last_name, password_hash, is_active, account_status, "
            "must_change_password, institution_id) VALUES ('orgadmin', 'orgadmin@sample.edu', 'Olivia', 'Organiser', :h, true, "
            "'ACTIVE', false, :i) RETURNING user_id"), {"h": hash_password(DEMO_PASSWORD), "i": inst}).scalar()
        db.execute(sa.text(
            "INSERT INTO user_role_assignment (user_id, role_id, scope_type, institution_id, valid_from, assignment_status) "
            "SELECT :u, role_id, 'INSTITUTION', :i, now(), 'ACTIVE' FROM role WHERE role_code = 'INSTITUTION_ADMIN'"),
                   {"u": uid, "i": inst})


# (username, role, scope, person) - one demo login per built-in role so every audience can be tried.
PERSONAS: list[tuple[str, str, str, str | None]] = [
    ("dean", "DEAN_ACADEMICS", "INSTITUTION", None), ("vc", "VICE_CHANCELLOR", "INSTITUTION", None),
    ("admissions", "ADMISSION_OFFICER", "INSTITUTION", None), ("docverifier", "DOCUMENT_VERIFIER", "INSTITUTION", None),
    ("sectionofficer", "STUDENT_SECTION_OFFICER", "INSTITUTION", None), ("examofficer", "EXAMINATION_OFFICER", "INSTITUTION", None),
    ("resultapprover", "RESULT_APPROVER", "INSTITUTION", None), ("finance", "FINANCE_OFFICER", "INSTITUTION", None),
    ("auditor", "INTERNAL_AUDITOR", "INSTITUTION", None), ("extauditor", "EXTERNAL_AUDITOR", "INSTITUTION", None),
    ("evaluator", "EVALUATOR", "DEPARTMENT", "employee"), ("labinstructor", "LAB_INSTRUCTOR", "DEPARTMENT", "employee"),
    ("coursecoord", "COURSE_COORDINATOR", "DEPARTMENT", "employee"), ("ttcoord", "TIMETABLE_COORDINATOR", "DEPARTMENT", "employee"),
    ("progcoord", "PROGRAMME_COORDINATOR", "PROGRAMME", "employee"), ("semcoord", "SEMESTER_COORDINATOR", "PROGRAMME", "employee"),
    ("advisor", "FACULTY_ADVISOR", "PROGRAMME", "employee"), ("mentor", "MENTOR", "PROGRAMME", "employee"),
    ("parent", "PARENT_GUARDIAN", "SELF", "student"), ("alumni", "ALUMNI", "SELF", "student"),
    ("applicant", "APPLICANT", "SELF", "student"),
    ("sysadmin", "SYSTEM_ADMIN", "GLOBAL", None), ("secadmin", "SECURITY_ADMIN", "GLOBAL", None),
]


def ensure_demo_personas() -> None:
    """Create the extra demo logins (idempotent). Staff personas are linked to unlinked staff of the head-of-department's
    department; parent / alumni / applicant are linked to unlinked students."""
    from app.rbac import catalogue

    with db_session() as db:
        inst = db.execute(sa.text("SELECT institution_id FROM institution ORDER BY institution_id LIMIT 1")).scalar()
        dept = db.execute(sa.text("SELECT department_id FROM user_role_assignment WHERE scope_type = 'DEPARTMENT' "
                                  "AND department_id IS NOT NULL ORDER BY 1 LIMIT 1")).scalar()
        if inst is None or dept is None:
            return
        programme = db.execute(sa.text("SELECT programme_id FROM programme WHERE department_id = :d ORDER BY 1 LIMIT 1"), {"d": dept}).scalar()
        if programme is None:
            programme = db.execute(sa.text("SELECT programme_id FROM programme ORDER BY 1 LIMIT 1")).scalar()
        free_staff = [e for (e,) in db.execute(sa.text(
            "SELECT e.employee_id FROM employee e WHERE NOT EXISTS (SELECT 1 FROM person_account_link l WHERE l.employee_id = e.employee_id) "
            "ORDER BY (EXISTS (SELECT 1 FROM employee_assignment a WHERE a.employee_id = e.employee_id AND a.end_date IS NULL "
            "AND a.department_id = :d)) DESC, e.employee_id"), {"d": dept})]
        free_students = [s for (s,) in db.execute(sa.text(
            "SELECT s.student_id FROM student s WHERE NOT EXISTS (SELECT 1 FROM person_account_link l WHERE l.student_id = s.student_id) "
            "ORDER BY s.student_id"))]
        pw = hash_password(DEMO_PASSWORD)
        scope_col = {"INSTITUTION": ("institution_id", inst), "DEPARTMENT": ("department_id", dept), "PROGRAMME": ("programme_id", programme)}
        for username, role, scope, person in PERSONAS:
            if db.execute(sa.text("SELECT 1 FROM user_account WHERE username = :u"), {"u": username}).first():
                continue
            owned = None if scope == "GLOBAL" else inst
            uid = db.execute(sa.text(
                "INSERT INTO user_account (username, email, first_name, last_name, password_hash, is_active, account_status, "
                "must_change_password, institution_id) VALUES (:u, :e, :f, 'Demo', :h, true, 'ACTIVE', false, :i) RETURNING user_id"),
                {"u": username, "e": f"{username}@sample.edu", "f": role.replace("_", " ").title(), "h": pw, "i": owned}).scalar()
            col, val = scope_col.get(scope, (None, None))
            db.execute(sa.text(
                f"INSERT INTO user_role_assignment (user_id, role_id, scope_type, {col or 'institution_id'}, valid_from, assignment_status) "  # noqa: S608
                "SELECT :u, role_id, :s, :v, now(), 'ACTIVE' FROM role WHERE role_code = :r"),
                {"u": uid, "s": scope, "v": val if col else None, "r": role})
            pool = free_staff if person == "employee" else free_students if person == "student" else None
            if pool:
                db.execute(sa.text(f"INSERT INTO person_account_link ({person}_id, user_id) VALUES (:p, :u)"),  # noqa: S608
                           {"p": pool.pop(0), "u": uid})
                if person == "employee":
                    catalogue.ensure_staff_self(db, uid)
