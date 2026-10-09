"""Academic demo content: teaching, attendance, assessments, results, lesson plans and mentoring for every staff persona.

``ensure_academic_content(db)`` is idempotent: every statement inserts only what is missing (``NOT EXISTS`` on a natural key),
so a second call adds nothing. It uses raw SQL, flushes nothing it does not need to, and never commits (the caller owns the
transaction). The return value maps table name -> rows inserted by this call.

What it guarantees on top of the base demo data (term 4 of the sample B.E. CSE programme, 12 students, 4 courses):
* every demo staff persona has an ACTIVE faculty assignment on its own course section with an enrolled roster (six more
  sample courses are offered to the same class so each persona gets a distinct section);
* each of those sections has a timetable in the PUBLISHED revision, finalised class sessions plus one OPEN register with
  attendance, assessments (conducted, published, planned) with marks, course results (published and calculated), a result
  publication log, a lesson plan with coverage and a pending attendance-correction request;
* the mentor and the faculty advisor have three active mentees each in their programme, with counselling sessions in
  several states.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

# Staff personas and the course each one is anchored to (the first four already exist in the base demo data).
PERSONA_COURSE = [
    ("hod", "CSE301"), ("teacher", "CSE302"), ("labinstructor", "CSE303"), ("coursecoord", "CSE304"),
    ("evaluator", "CSE401"), ("ttcoord", "CSE402"), ("progcoord", "CSE403"), ("semcoord", "CSE404"),
    ("advisor", "CSE201"), ("mentor", "CSE202"),
]
# Courses added to the sample class so that each persona owns a distinct section: code -> session type.
EXTRA_COURSES = {"CSE401": "LECTURE", "CSE402": "LECTURE", "CSE403": "LECTURE", "CSE404": "PROJECT", "CSE201": "LECTURE",
                 "CSE202": "PRACTICAL"}
ASSIGNMENT_ROLE = {"evaluator": "CO_INSTRUCTOR", "ttcoord": "PRIMARY_INSTRUCTOR", "progcoord": "PRIMARY_INSTRUCTOR",
                   "semcoord": "COORDINATOR", "advisor": "TUTOR", "mentor": "LAB_INSTRUCTOR"}
PUBLISHED_COURSES = {"CSE301", "CSE302", "CSE401", "CSE402", "CSE201"}      # results published; the rest stay CALCULATED
WITHHELD_COURSE = "CSE301"
TOPICS = ["Introduction and course outline", "Core concepts and definitions", "Worked examples and problem solving",
          "Applications and case study", "Revision and discussion"]
TERM_START, TERM_END = date(2026, 8, 1), date(2026, 12, 20)
FIRST_CLASS = date(2026, 9, 2)          # the first sample class of a new section falls on/after this date
OCCURRENCES_FROM = date(2026, 9, 28)
ATT_RULES = {"ABSENT": {"credit": "0.0000", "denominator": "1.0000"}, "PRESENT": {"credit": "1.0000", "denominator": "1.0000"}}

TOUCHED = ["course_offering", "course_offering_section", "student_course_registration", "course_offering_section_student",
           "faculty_course_assignment", "attendance_policy", "assessment_policy", "assessment_component", "timetable_session",
           "timetable_occurrence", "class_session", "student_attendance", "assessment_event", "student_assessment_mark",
           "student_course_result", "result_publication", "lesson_plan_revision", "lesson_coverage",
           "attendance_correction_request", "mentor_assignment", "counselling_session", "person_account_link"]


def ensure_academic_content(db: Session) -> dict[str, int]:
    """Insert the missing academic demo rows; returns ``{table: rows inserted}`` (empty when everything is present)."""
    return _Seeder(db).run()


class _Seeder:
    def __init__(self, db: Session):
        self.db = db
        self.added: Counter[str] = Counter()

    # ------------------------------------------------------------------------------------------------ helpers
    def rows(self, sql: str, **p):
        return self.db.execute(text(sql), p).all()

    def one(self, sql: str, **p):
        return self.db.execute(text(sql), p).first()

    def scalar(self, sql: str, **p):
        return self.db.execute(text(sql), p).scalar()

    def add(self, table: str, sql: str, **p) -> int:
        n = self.db.execute(text(sql), p).rowcount or 0
        if n > 0:
            self.added[table] += n
        return n

    # ------------------------------------------------------------------------------------------------ driver
    def run(self) -> dict[str, int]:
        self.admin = self.scalar("SELECT user_id FROM user_account WHERE is_superuser ORDER BY user_id LIMIT 1") \
            or self.scalar("SELECT min(user_id) FROM user_account")
        self.inst = self.scalar("SELECT institution_id FROM institution ORDER BY institution_id LIMIT 1")
        # the term the demo class is registered in: the programme term with the most registered students
        row = self.one("SELECT programme_term_offering_id, count(*) FROM student_term_registration "
                       "WHERE registration_status IN ('REGISTERED', 'APPROVED') GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 1")
        if self.admin is None or self.inst is None or row is None:
            return {}
        self.pto = row[0]
        pto = self.one("SELECT programme_id, curriculum_scheme_id FROM programme_term_offering WHERE programme_term_offering_id = :p",
                       p=self.pto)
        self.programme, self.scheme = pto
        self.class_section = self.scalar(
            "SELECT class_section_id FROM student_term_registration WHERE programme_term_offering_id = :p AND class_section_id IS NOT NULL "
            "GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 1", p=self.pto)
        if self.class_section is None:
            return {}
        self.link_personas()
        self.revision = self.published_revision()
        self.offerings_and_rosters()
        self.assign_faculty()
        self.policies()
        self.timetable()
        self.class_sessions()
        self.assessments()
        self.results()
        self.lessons()
        self.corrections()
        self.mentoring()
        self.db.flush()
        return {k: v for k, v in self.added.items() if v}

    # ------------------------------------------------------------------------------------------------ personas
    def link_personas(self) -> None:
        """Find each staff persona's employee; a persona without one gets a free employee linked to the login."""
        self.emp: dict[str, int] = {}
        self.user: dict[str, int] = {}
        names = [n for n, _ in PERSONA_COURSE]
        for username, uid, emp in self.rows(
                "SELECT u.username, u.user_id, l.employee_id FROM user_account u LEFT JOIN person_account_link l ON l.user_id = u.user_id "
                "AND l.employee_id IS NOT NULL WHERE u.username = ANY(:n)", n=names):
            self.user[username] = uid
            if emp is not None:
                self.emp[username] = emp
        dept = self.scalar("SELECT department_id FROM programme WHERE programme_id = :p", p=self.programme)
        for username in names:
            if username not in self.user or username in self.emp:
                continue
            free = self.scalar(
                "SELECT e.employee_id FROM employee e WHERE NOT EXISTS (SELECT 1 FROM person_account_link l WHERE l.employee_id = e.employee_id) "
                "ORDER BY (EXISTS (SELECT 1 FROM employee_assignment a WHERE a.employee_id = e.employee_id AND a.end_date IS NULL "
                "AND a.department_id = :d)) DESC, e.employee_id LIMIT 1", d=dept)
            if free is None:
                continue
            self.add("person_account_link", "INSERT INTO person_account_link (employee_id, user_id) VALUES (:e, :u)", e=free, u=self.user[username])
            self.emp[username] = free
            try:
                from app.rbac import catalogue
                catalogue.ensure_staff_self(self.db, self.user[username])
            except Exception:       # noqa: S110  # pragma: no cover - the self-service role is a convenience, never a blocker
                pass

    def published_revision(self) -> int:
        rev = self.scalar(
            "SELECT r.id FROM timetable_revision r JOIN timetable_plan p ON p.id = r.plan_id WHERE p.programme_term_offering_id = :p "
            "AND r.status = 'PUBLISHED' ORDER BY r.number DESC LIMIT 1", p=self.pto)
        if rev is not None:
            return rev
        plan = self.scalar("SELECT id FROM timetable_plan WHERE programme_term_offering_id = :p", p=self.pto)
        if plan is None:
            plan = self.scalar(
                "INSERT INTO timetable_plan (version, name, created_by_id, programme_term_offering_id, updated_by_id) "
                "VALUES (1, 'Class timetable', :a, :p, :a) RETURNING id", a=self.admin, p=self.pto)
        number = (self.scalar("SELECT max(number) FROM timetable_revision WHERE plan_id = :p", p=plan) or 0) + 1
        return self.scalar(
            "INSERT INTO timetable_revision (version, number, status, created_by_id, plan_id, updated_by_id) "
            "VALUES (1, :n, 'PUBLISHED', :a, :p, :a) RETURNING id", n=number, a=self.admin, p=plan)

    # ------------------------------------------------------------------------------------------------ offerings / rosters
    def offerings_and_rosters(self) -> None:
        for code, session_type in EXTRA_COURSES.items():
            self.add("course_offering",
                     "INSERT INTO course_offering (version, offering_code, registration_capacity, status, course_id, created_by_id, "
                     "curriculum_course_id, updated_by_id, programme_term_offering_id) "
                     "SELECT 1, c.course_code || '-ODD25', 60, 'ACTIVE', c.course_id, :a, (SELECT cc.curriculum_course_id FROM curriculum_course cc "
                     "WHERE cc.course_id = c.course_id AND cc.curriculum_scheme_id = :s ORDER BY 1 LIMIT 1), :a, :p FROM course_catalog c "
                     "WHERE c.course_code = :c AND NOT EXISTS (SELECT 1 FROM course_offering o WHERE o.programme_term_offering_id = :p "
                     "AND o.course_id = c.course_id) AND NOT EXISTS (SELECT 1 FROM course_offering o2 WHERE o2.offering_code = c.course_code || '-ODD25')",
                     a=self.admin, s=self.scheme, p=self.pto, c=code)
            self.add("course_offering_section",
                     "INSERT INTO course_offering_section (version, session_type, class_section_id, course_offering_id, created_by_id, "
                     "updated_by_id, programme_term_offering_id) SELECT 1, :t, :cs, o.course_offering_id, :a, :a, :p FROM course_offering o "
                     "JOIN course_catalog c ON c.course_id = o.course_id WHERE o.programme_term_offering_id = :p AND c.course_code = :c "
                     "AND NOT EXISTS (SELECT 1 FROM course_offering_section s WHERE s.course_offering_id = o.course_offering_id)",
                     t=session_type, cs=self.class_section, a=self.admin, p=self.pto, c=code)
        codes = list(EXTRA_COURSES)
        self.add("student_course_registration",
                 "INSERT INTO student_course_registration (version, registration_type, registration_date, registration_status, "
                 "course_offering_id, created_by_id, programme_term_offering_id, updated_by_id, term_registration_id) "
                 "SELECT 1, 'REGULAR', :d, 'REGISTERED', o.course_offering_id, :a, :p, :a, t.term_registration_id "
                 "FROM student_term_registration t CROSS JOIN course_offering o JOIN course_catalog c ON c.course_id = o.course_id "
                 "WHERE t.programme_term_offering_id = :p AND t.registration_status IN ('REGISTERED', 'APPROVED') "
                 "AND o.programme_term_offering_id = :p AND c.course_code = ANY(:codes) AND NOT EXISTS (SELECT 1 FROM student_course_registration r "
                 "WHERE r.term_registration_id = t.term_registration_id AND r.course_offering_id = o.course_offering_id)",
                 d=date(2026, 7, 22), a=self.admin, p=self.pto, codes=codes)
        self.add("course_offering_section_student",
                 "INSERT INTO course_offering_section_student (version, session_type, roster_status, effective_from, course_offering_id, "
                 "course_offering_section_id, created_by_id, updated_by_id, course_registration_id) "
                 "SELECT 1, s.session_type, 'ACTIVE', :f, s.course_offering_id, s.course_offering_section_id, :a, :a, r.course_registration_id "
                 "FROM student_course_registration r JOIN course_offering_section s ON s.course_offering_id = r.course_offering_id "
                 "JOIN course_offering o ON o.course_offering_id = r.course_offering_id JOIN course_catalog c ON c.course_id = o.course_id "
                 "WHERE o.programme_term_offering_id = :p AND c.course_code = ANY(:codes) AND r.registration_status = 'REGISTERED' "
                 "AND NOT EXISTS (SELECT 1 FROM course_offering_section_student x WHERE x.course_offering_section_id = s.course_offering_section_id "
                 "AND x.course_registration_id = r.course_registration_id)", f=TERM_START, a=self.admin, p=self.pto, codes=codes)

    def sections(self) -> list[dict]:
        """Sections of the demo term that have an active roster and an active instructor, in a stable order."""
        out = []
        for r in self.rows(
                "SELECT s.course_offering_section_id, s.course_offering_id, s.session_type, c.course_code, c.credits, "
                "(SELECT f.faculty_assignment_id FROM faculty_course_assignment f WHERE f.course_offering_section_id = s.course_offering_section_id "
                "AND f.assignment_status = 'ACTIVE' ORDER BY f.faculty_assignment_id LIMIT 1) "
                "FROM course_offering_section s JOIN course_offering o ON o.course_offering_id = s.course_offering_id "
                "JOIN course_catalog c ON c.course_id = o.course_id WHERE o.programme_term_offering_id = :p AND EXISTS "
                "(SELECT 1 FROM course_offering_section_student x WHERE x.course_offering_section_id = s.course_offering_section_id "
                "AND x.roster_status = 'ACTIVE') ORDER BY s.course_offering_section_id", p=self.pto):
            if r[5] is not None:
                out.append({"sid": r[0], "oid": r[1], "stype": r[2], "code": r[3], "credits": r[4], "fa": r[5]})
        return out

    # ------------------------------------------------------------------------------------------------ faculty assignments
    def section_for_code(self, code: str):
        return self.scalar(
            "SELECT s.course_offering_section_id FROM course_offering_section s JOIN course_offering o ON o.course_offering_id = s.course_offering_id "
            "JOIN course_catalog c ON c.course_id = o.course_id WHERE o.programme_term_offering_id = :p AND c.course_code = :c "
            "ORDER BY 1 LIMIT 1", p=self.pto, c=code)

    def assign_faculty(self) -> None:
        for username, code in PERSONA_COURSE:
            emp = self.emp.get(username)
            sec = self.section_for_code(code)
            if emp is None or sec is None:
                continue
            has = self.scalar(
                "SELECT 1 FROM faculty_course_assignment f JOIN course_offering_section s ON s.course_offering_section_id = f.course_offering_section_id "
                "JOIN course_offering o ON o.course_offering_id = s.course_offering_id WHERE f.employee_id = :e AND f.assignment_status = 'ACTIVE' "
                "AND o.programme_term_offering_id = :p AND EXISTS (SELECT 1 FROM course_offering_section_student x "
                "WHERE x.course_offering_section_id = s.course_offering_section_id AND x.roster_status = 'ACTIVE') LIMIT 1", e=emp, p=self.pto)
            if not has:
                self.insert_assignment(sec, emp, ASSIGNMENT_ROLE.get(username, "PRIMARY_INSTRUCTOR"), username != "hod")
        # the head of department's other active staff teach too
        hod_dept = self.scalar("SELECT department_id FROM user_role_assignment ura JOIN person_account_link l ON l.user_id = ura.user_id "
                               "JOIN role r ON r.role_id = ura.role_id WHERE r.role_code = 'HEAD_DEPARTMENT' AND ura.department_id IS NOT NULL "
                               "AND ura.assignment_status = 'ACTIVE' ORDER BY ura.user_id LIMIT 1")
        if hod_dept is not None:
            secs = [s["sid"] for s in self.sections()]
            staff = self.rows(
                "SELECT DISTINCT a.employee_id FROM employee_assignment a WHERE a.department_id = :d AND a.end_date IS NULL AND NOT EXISTS "
                "(SELECT 1 FROM faculty_course_assignment f WHERE f.employee_id = a.employee_id AND f.assignment_status = 'ACTIVE') "
                "ORDER BY 1", d=hod_dept)
            for i, (emp,) in enumerate(staff):
                if secs:
                    self.insert_assignment(secs[i % len(secs)], emp, "CO_INSTRUCTOR", False)

    def insert_assignment(self, section: int, emp: int, role: str, cross_department: bool) -> None:
        self.add("faculty_course_assignment",
                 "INSERT INTO faculty_course_assignment (version, assignment_role, workload_hours, start_date, end_date, assignment_status, "
                 "course_offering_section_id, created_by_id, employee_id, updated_by_id, cross_department_authorized) "
                 "SELECT 1, :r, 3.00, :s, :e, 'ACTIVE', :sec, :a, :emp, :a, :x WHERE NOT EXISTS (SELECT 1 FROM faculty_course_assignment f "
                 "WHERE f.course_offering_section_id = :sec AND f.employee_id = :emp AND f.assignment_status = 'ACTIVE')",
                 r=role, s=TERM_START, e=TERM_END, sec=section, a=self.admin, emp=emp, x=cross_department)

    # ------------------------------------------------------------------------------------------------ policies
    def policies(self) -> None:
        for s in self.sections():
            self.add("attendance_policy",
                     "INSERT INTO attendance_policy (number, basis, rules, threshold, edit_days, correction_days, reason, actor_id, section_id) "
                     "SELECT 1, 'SESSION', CAST(:rules AS jsonb), 75, 7, 7, 'Sample data', :a, :sec WHERE NOT EXISTS "
                     "(SELECT 1 FROM attendance_policy p WHERE p.section_id = :sec)", rules=json.dumps(ATT_RULES), a=self.admin, sec=s["sid"])
            self.add("assessment_policy",
                     "INSERT INTO assessment_policy (number, rules, reason, actor_id, course_offering_id, grade_scale_id) "
                     "SELECT 1, t.rules, 'Sample data', :a, :o, t.grade_scale_id FROM (SELECT rules, grade_scale_id FROM assessment_policy "
                     "ORDER BY id LIMIT 1) t WHERE NOT EXISTS (SELECT 1 FROM assessment_policy p WHERE p.course_offering_id = :o)",
                     a=self.admin, o=s["oid"])

    # ------------------------------------------------------------------------------------------------ timetable
    def timetable(self) -> None:
        slots = [r[0] for r in self.rows("SELECT time_slot_id FROM time_slot ORDER BY time_slot_id")]
        rooms = [r[0] for r in self.rows("SELECT room_id FROM room ORDER BY room_id")]
        if not slots or not rooms:
            return
        slot_a, slot_b = (8 if 8 in slots else slots[0]), (9 if 9 in slots else slots[-1])
        todo = [s for s in self.sections() if not self.scalar(
            "SELECT 1 FROM timetable_session WHERE revision_id = :r AND course_offering_section_id = :s LIMIT 1", r=self.revision, s=s["sid"])]
        for i, s in enumerate(todo):
            days = [(i % 5) + 1, ((i + 2) % 5) + 1] if i < 5 else [6, 6]
            slot_ids = [slot_a, slot_b]
            room = rooms[min(len(rooms) - 1, 35 + i)] if s["stype"] != "PRACTICAL" else rooms[min(len(rooms) - 1, 41)]
            for day, slot in zip(days, slot_ids, strict=True):
                self.add("timetable_session",
                         "INSERT INTO timetable_session (version, day_of_week, effective_from, effective_to, course_offering_section_id, created_by_id, "
                         "faculty_assignment_id, revision_id, room_id, time_slot_id, updated_by_id) "
                         "SELECT 1, :d, :f, :t, :sec, :a, :fa, :rev, :room, :slot, :a WHERE NOT EXISTS (SELECT 1 FROM timetable_session x "
                         "WHERE x.revision_id = :rev AND x.course_offering_section_id = :sec AND x.day_of_week = :d AND x.time_slot_id = :slot)",
                         d=day, f=TERM_START, t=TERM_END, sec=s["sid"], a=self.admin, fa=s["fa"], rev=self.revision, room=room, slot=slot)
        # weekly occurrences (6 weeks) for sessions that have none
        for ts_id, day, sec in self.rows(
                "SELECT t.timetable_session_id, t.day_of_week, t.course_offering_section_id FROM timetable_session t WHERE t.revision_id = :r "
                "AND NOT EXISTS (SELECT 1 FROM timetable_occurrence o WHERE o.session_id = t.timetable_session_id) "
                "AND t.faculty_assignment_id IS NOT NULL AND t.room_id IS NOT NULL", r=self.revision):
            sids = [r[0] for r in self.rows(
                "SELECT DISTINCT e.student_id FROM course_offering_section_student x JOIN student_course_registration cr "
                "ON cr.course_registration_id = x.course_registration_id JOIN student_term_registration t ON t.term_registration_id = cr.term_registration_id "
                "JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id WHERE x.course_offering_section_id = :s "
                "AND x.roster_status = 'ACTIVE' ORDER BY 1", s=sec)]
            first = OCCURRENCES_FROM + timedelta(days=(day - OCCURRENCES_FROM.isoweekday()) % 7)
            for k in range(6):
                self.add("timetable_occurrence",
                         "INSERT INTO timetable_occurrence (date, start_time, end_time, student_ids, course_offering_section_id, employee_id, room_id, "
                         "revision_id, session_id, class_section_id, class_batch_id) SELECT :d, sl.start_time, sl.end_time, CAST(:sids AS jsonb), "
                         "t.course_offering_section_id, fa.employee_id, t.room_id, t.revision_id, t.timetable_session_id, :cs, NULL "
                         "FROM timetable_session t JOIN time_slot sl ON sl.time_slot_id = t.time_slot_id "
                         "JOIN faculty_course_assignment fa ON fa.faculty_assignment_id = t.faculty_assignment_id "
                         "WHERE t.timetable_session_id = :ts AND NOT EXISTS (SELECT 1 FROM timetable_occurrence o WHERE o.session_id = t.timetable_session_id "
                         "AND o.date = :d)", d=first + timedelta(days=7 * k), sids=json.dumps(sids), cs=self.class_section, ts=ts_id)

    # ------------------------------------------------------------------------------------------------ class sessions / attendance
    def class_sessions(self) -> None:
        for s in self.sections():
            sid = s["sid"]
            fin = self.scalar("SELECT count(*) FROM class_session WHERE course_offering_section_id = :s AND register_status = 'FINALIZED'", s=sid)
            has_open = self.scalar("SELECT 1 FROM class_session WHERE course_offering_section_id = :s AND register_status = 'OPEN' LIMIT 1", s=sid)
            last = self.one("SELECT class_number, session_date, start_time, end_time, room_id FROM class_session "
                            "WHERE course_offering_section_id = :s ORDER BY class_number DESC LIMIT 1", s=sid)
            ts = self.one("SELECT t.timetable_session_id, t.day_of_week, sl.start_time, sl.end_time, t.room_id FROM timetable_session t "
                          "JOIN time_slot sl ON sl.time_slot_id = t.time_slot_id WHERE t.revision_id = :r AND t.course_offering_section_id = :s "
                          "ORDER BY t.day_of_week, sl.start_time LIMIT 1", r=self.revision, s=sid)
            room = (last[4] if last else None) or (ts[4] if ts else None) or self.scalar("SELECT min(room_id) FROM room")
            start, end = (last[2], last[3]) if last else ((ts[2], ts[3]) if ts else (None, None))
            if start is None:
                start, end = time(9, 0), time(10, 0)
            number = last[0] if last else 0
            if last:
                day = last[1] + timedelta(days=7)
            else:
                wd = ts[1] if ts else 1
                day = FIRST_CLASS + timedelta(days=(wd - FIRST_CLASS.isoweekday()) % 7)
            plan = ["FINALIZED"] * max(0, 4 - fin) + ([] if has_open else ["OPEN"])
            for status in plan:
                number += 1
                self.insert_session(s, number, day, start, end, room, ts[0] if ts else None, status)
                day = day + timedelta(days=7)
            self.mark_attendance(s)

    def insert_session(self, s: dict, number: int, day: date, start, end, room: int, ts_id, status: str) -> None:
        topic = TOPICS[(number - 1) % len(TOPICS)]
        finalized_at = datetime(day.year, day.month, day.day, 17, 30, tzinfo=UTC) if status == "FINALIZED" else None
        self.add("class_session",
                 "INSERT INTO class_session (occurrence_sequence, session_date, start_time, end_time, session_type, planned_topic, topic_covered, "
                 "class_number, session_status, register_status, finalized_at, calendar_reference, course_offering_section_id, created_by_id, "
                 "faculty_assignment_id, room_id, timetable_session_id, updated_by_id, policy_id) "
                 "SELECT 0, :d, :st, :en, :ty, :topic, :covered, :n, 'CONDUCTED', :rs, :fin, :ref, :sec, :a, :fa, :room, :ts, :a, "
                 "(SELECT p.id FROM attendance_policy p WHERE p.section_id = :sec ORDER BY p.number DESC LIMIT 1) "
                 "WHERE NOT EXISTS (SELECT 1 FROM class_session x WHERE x.course_offering_section_id = :sec AND (x.class_number = :n "
                 "OR (x.session_date = :d AND x.start_time = :st))) "
                 "AND EXISTS (SELECT 1 FROM attendance_policy p2 WHERE p2.section_id = :sec)",
                 d=day, st=start, en=end, ty=s["stype"], topic=topic, covered=topic if status == "FINALIZED" else "", n=number, rs=status,
                 fin=finalized_at, ref=f"{s['code']}-{day.isoformat()}", sec=s["sid"], a=self.admin, fa=s["fa"], room=room, ts=ts_id)

    def mark_attendance(self, s: dict) -> None:
        marker = self.scalar("SELECT l.user_id FROM faculty_course_assignment f JOIN person_account_link l ON l.employee_id = f.employee_id "
                             "WHERE f.faculty_assignment_id = :fa", fa=s["fa"]) or self.admin
        # a session without any attendance yet: finalised ones fully marked, the open register half marked (work in progress)
        self.add("student_attendance",
                 "INSERT INTO student_attendance (marked_at, remarks, credit, denominator, attendance_status_id, class_session_id, "
                 "course_offering_section_id, course_offering_section_student_id, marked_by_user_id, student_id, exclusion_reason, is_eligible) "
                 "SELECT cs.session_date + time '11:00', '', CASE WHEN ab THEN 0 ELSE 1 END, 1, "
                 "(SELECT attendance_status_id FROM attendance_status WHERE status_code = CASE WHEN ab THEN 'ABSENT' ELSE 'PRESENT' END), "
                 "cs.class_session_id, cs.course_offering_section_id, x.course_offering_section_student_id, :u, q.student_id, '', true "
                 "FROM class_session cs JOIN course_offering_section_student x ON x.course_offering_section_id = cs.course_offering_section_id "
                 "AND x.roster_status = 'ACTIVE' "
                 "JOIN LATERAL (SELECT e.student_id FROM student_course_registration cr JOIN student_term_registration t "
                 "ON t.term_registration_id = cr.term_registration_id JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
                 "WHERE cr.course_registration_id = x.course_registration_id) q ON true "
                 "CROSS JOIN LATERAL (SELECT ((q.student_id * 3 + cs.class_number * 5 + cs.course_offering_section_id) % 7 = 0) AS ab) z "
                 "WHERE cs.course_offering_section_id = :sec AND cs.register_status IN ('FINALIZED', 'OPEN') "
                 "AND NOT EXISTS (SELECT 1 FROM student_attendance a0 WHERE a0.class_session_id = cs.class_session_id) "
                 "AND (cs.register_status = 'FINALIZED' OR q.student_id % 2 = 0)", u=marker, sec=s["sid"])

    # ------------------------------------------------------------------------------------------------ assessments
    def assessments(self) -> None:
        components = [("IA1", "Internal Assessment 1", "INTERNAL_TEST", 50, 40, True), ("QZ1", "Quiz 1", "QUIZ", 20, 10, False)]
        events = [("IA-1", "IA1", date(2026, 9, 25), 50, "CONDUCTED"), ("Quiz 1", "QZ1", date(2026, 9, 15), 20, "PUBLISHED"),
                  ("IA-2", "IA1", date(2026, 10, 20), 50, "PLANNED")]
        for s in self.sections():
            oid = s["oid"]
            for code, name, ctype, mx, weight, mandatory in components:
                self.add("assessment_component",
                         "INSERT INTO assessment_component (version, component_code, component_name, component_type, maximum_marks, "
                         "weightage_percent, is_mandatory, actor_id, course_offering_id) SELECT 1, CAST(:c AS varchar), :n, :t, :m, :w, :mand, :a, :o "
                         "WHERE NOT EXISTS (SELECT 1 FROM assessment_component x WHERE x.course_offering_id = :o AND x.component_code = :c)",
                         c=code, n=name, t=ctype, m=mx, w=weight, mand=mandatory, a=self.admin, o=oid)
            policy = self.scalar("SELECT min(id) FROM assessment_policy WHERE course_offering_id = :o", o=oid)
            if policy is None:
                continue
            for title, comp, when, mx, status in events:
                self.add("assessment_event",
                         "INSERT INTO assessment_event (version, attempt_number, event_title, assessment_date, maximum_marks, details, status, "
                         "roster, actor_id, assessment_component_id, course_offering_id, policy_id) "
                         "SELECT 1, 1, CAST(:ti AS varchar), :d, :m, '', :st, CAST('[]' AS jsonb), :a, c.assessment_component_id, :o, :pol FROM assessment_component c "
                         "WHERE c.course_offering_id = :o AND c.component_code = :c AND NOT EXISTS (SELECT 1 FROM assessment_event e "
                         "WHERE e.course_offering_id = :o AND e.event_title = :ti AND e.attempt_number = 1)",
                         ti=title, d=when, m=mx, st=status, a=self.admin, o=oid, pol=policy, c=comp)
            evaluator = self.scalar("SELECT l.user_id FROM faculty_course_assignment f JOIN person_account_link l ON l.employee_id = f.employee_id "
                                    "WHERE f.faculty_assignment_id = :fa", fa=s["fa"]) or self.admin
            self.add("student_assessment_mark",
                     "INSERT INTO student_assessment_mark (version, attendance_status, marks_obtained, reduced_marks, remarks, evaluated_at, "
                     "actor_id, assessment_event_id, course_offering_id, course_registration_id) "
                     "SELECT 1, CASE WHEN z.ab THEN 'ABSENT' ELSE 'PRESENT' END, "
                     "CASE WHEN z.ab THEN NULL ELSE floor(ev.maximum_marks * (40 + ((cr.course_registration_id * 13 + ev.assessment_event_id * 7) % 55)) / 100.0) END, "
                     "NULL, '', ((ev.assessment_date + 2)::timestamp + interval '10 hours') AT TIME ZONE 'UTC', :a, ev.assessment_event_id, "
                     "ev.course_offering_id, cr.course_registration_id FROM assessment_event ev JOIN student_course_registration cr "
                     "ON cr.course_offering_id = ev.course_offering_id AND cr.registration_status = 'REGISTERED' "
                     "CROSS JOIN LATERAL (SELECT ((cr.course_registration_id * 5 + ev.assessment_event_id) % 23 = 0) AS ab) z "
                     "WHERE ev.course_offering_id = :o AND ev.status IN ('CONDUCTED', 'PUBLISHED') AND NOT EXISTS (SELECT 1 FROM student_assessment_mark m "
                     "WHERE m.assessment_event_id = ev.assessment_event_id AND m.course_registration_id = cr.course_registration_id)",
                     a=evaluator, o=oid)

    # ------------------------------------------------------------------------------------------------ results
    def results(self) -> None:
        exam_user = self.scalar("SELECT user_id FROM user_account WHERE username = 'examofficer'") or self.admin
        publisher = self.scalar("SELECT user_id FROM user_account WHERE username = 'examcell'") or self.admin
        mark = ("(SELECT m.marks_obtained FROM student_assessment_mark m JOIN assessment_event ev ON ev.assessment_event_id = m.assessment_event_id "
                "WHERE m.course_registration_id = cr.course_registration_id AND ev.course_offering_id = cr.course_offering_id "
                "AND ev.event_title = '{t}' LIMIT 1)")
        for s in self.sections():
            policy = self.scalar("SELECT min(id) FROM assessment_policy WHERE course_offering_id = :o", o=s["oid"])
            if policy is None:
                continue
            published = s["code"] in PUBLISHED_COURSES
            self.add("student_course_result",
                     "INSERT INTO student_course_result (version, attempt_number, internal_marks, external_marks, total_marks, grade_letter, "  # noqa: S608
                     "grade_point, credits_earned, result_status, result_date, remarks, evidence, state, actor_id, course_registration_id, policy_id, "
                     "is_withheld) SELECT 1, 1, i.internal, i.external, i.internal + i.external, "
                     "CASE WHEN w.withheld THEN '' ELSE g.letter END, CASE WHEN w.withheld THEN NULL ELSE g.gp END, "
                     "CASE WHEN w.withheld OR NOT t.passed THEN 0 ELSE :credits END, "
                     "CASE WHEN w.withheld THEN 'WITHHELD' WHEN t.passed THEN 'PASS' ELSE 'FAIL' END, "
                     "CASE WHEN :published THEN date '2026-10-08' END, '', CAST(:ev AS jsonb), "
                     "CASE WHEN w.withheld THEN 'WITHHELD' WHEN :published THEN 'PUBLISHED' ELSE 'CALCULATED' END, :actor, "
                     "cr.course_registration_id, :policy, w.withheld FROM student_course_registration cr "
                     "CROSS JOIN LATERAL (SELECT round(COALESCE(30.0 * " + mark.format(t="IA-1") + " / 50, 0) + COALESCE(10.0 * "
                     + mark.format(t="Quiz 1") + " / 20, 0), 2) AS internal, "
                     "(CASE WHEN (cr.course_registration_id * 7 + cr.course_offering_id) % 17 = 0 THEN 22 "
                     "ELSE 35 + (cr.course_registration_id * 11 + cr.course_offering_id * 5) % 26 END)::numeric AS external) i "
                     "CROSS JOIN LATERAL (SELECT i.internal + i.external AS total, "
                     "(i.external >= 35 AND i.internal >= 14 AND i.internal + i.external >= 40) AS passed) t "
                     "CROSS JOIN LATERAL (SELECT CASE WHEN NOT t.passed THEN 'F' WHEN t.total >= 90 THEN 'O' WHEN t.total >= 80 THEN 'A+' "
                     "WHEN t.total >= 70 THEN 'A' WHEN t.total >= 60 THEN 'B+' WHEN t.total >= 50 THEN 'B' ELSE 'P' END AS letter, "
                     "CASE WHEN NOT t.passed THEN 0 WHEN t.total >= 90 THEN 10 WHEN t.total >= 80 THEN 9 WHEN t.total >= 70 THEN 8 "
                     "WHEN t.total >= 60 THEN 7 WHEN t.total >= 50 THEN 6 ELSE 5 END AS gp) g "
                     "CROSS JOIN LATERAL (SELECT (CAST(:withhold AS boolean) AND cr.course_registration_id % 12 = 7) AS withheld) w "
                     "WHERE cr.course_offering_id = :o AND cr.registration_status = 'REGISTERED' AND NOT EXISTS (SELECT 1 FROM student_course_result x "
                     "WHERE x.course_registration_id = cr.course_registration_id AND x.attempt_number = 1)",
                     credits=s["credits"], published=published, ev=json.dumps({"source": "demo", "components": ["IA-1", "Quiz 1"]}),
                     actor=exam_user, policy=policy, withhold=s["code"] == WITHHELD_COURSE, o=s["oid"])
        self.add("result_publication",
                 "INSERT INTO result_publication (resource, record_id, number, data, actor_id, institution_id) "
                 "SELECT 'student_course_result', r.student_course_result_id, 1, jsonb_build_object('course_registration_id', r.course_registration_id, "
                 "'total_marks', r.total_marks, 'grade_letter', r.grade_letter, 'result_status', r.result_status, 'state', r.state), :a, :i "
                 "FROM student_course_result r JOIN student_course_registration cr ON cr.course_registration_id = r.course_registration_id "
                 "WHERE r.state = 'PUBLISHED' AND cr.programme_term_offering_id = :p AND NOT EXISTS (SELECT 1 FROM result_publication x "
                 "WHERE x.resource = 'student_course_result' AND x.record_id = r.student_course_result_id AND x.number = 1)",
                 a=publisher, i=self.inst, p=self.pto)

    # ------------------------------------------------------------------------------------------------ lesson plans
    def lessons(self) -> None:
        topics = [{"key": f"T{i + 1}", "title": t, "planned_minutes": 60} for i, t in enumerate(TOPICS)]
        for s in self.sections():
            actor = self.scalar("SELECT l.user_id FROM faculty_course_assignment f JOIN person_account_link l ON l.employee_id = f.employee_id "
                                "WHERE f.faculty_assignment_id = :fa", fa=s["fa"]) or self.admin
            self.add("lesson_plan_revision",
                     "INSERT INTO lesson_plan_revision (number, topics, reason, actor_id, section_id) SELECT 1, CAST(:t AS jsonb), 'Initial plan', :a, :s "
                     "WHERE NOT EXISTS (SELECT 1 FROM lesson_plan_revision x WHERE x.section_id = :s)", t=json.dumps(topics), a=actor, s=s["sid"])
            self.add("lesson_coverage",
                     "INSERT INTO lesson_coverage (topic_key, percent, minutes, remarks, actor_id, lesson_revision_id, session_id) "
                     "SELECT 'T' || (((cs.class_number - 1) % 5) + 1), CASE WHEN cs.class_number <= 3 THEN 100 ELSE 70 END, 60, "
                     "CASE WHEN cs.class_number <= 3 THEN 'Covered as planned' ELSE 'Partly covered; continue next class' END, :a, lp.id, cs.class_session_id "
                     "FROM class_session cs JOIN lesson_plan_revision lp ON lp.section_id = cs.course_offering_section_id "
                     "AND lp.number = (SELECT max(number) FROM lesson_plan_revision y WHERE y.section_id = cs.course_offering_section_id) "
                     "WHERE cs.course_offering_section_id = :s AND cs.register_status = 'FINALIZED' AND NOT EXISTS (SELECT 1 FROM lesson_coverage c "
                     "WHERE c.lesson_revision_id = lp.id AND c.session_id = cs.class_session_id)", a=actor, s=s["sid"])

    # ------------------------------------------------------------------------------------------------ attendance corrections
    def corrections(self) -> None:
        for s in self.sections():
            self.add("attendance_correction_request",
                     "INSERT INTO attendance_correction_request (attendance_version, reason, evidence_reference, request_status, resolution_remarks, "
                     "requested_at, old_status_id, requested_by_id, requested_status_id, attendance_id) "
                     "SELECT a.version, 'I attended this class but was marked absent; please recheck the register.', 'MEDICAL-NOTE-DEMO', 'PENDING', '', "
                     ":ts, a.attendance_status_id, COALESCE((SELECT l.user_id FROM person_account_link l WHERE l.student_id = a.student_id ORDER BY 1 LIMIT 1), :a), "
                     "(SELECT attendance_status_id FROM attendance_status WHERE status_code = 'PRESENT'), a.attendance_id "
                     "FROM student_attendance a JOIN class_session cs ON cs.class_session_id = a.class_session_id "
                     "WHERE a.course_offering_section_id = :sec AND cs.register_status = 'FINALIZED' "
                     "AND a.attendance_status_id = (SELECT attendance_status_id FROM attendance_status WHERE status_code = 'ABSENT') "
                     "AND NOT EXISTS (SELECT 1 FROM attendance_correction_request c JOIN student_attendance a2 ON a2.attendance_id = c.attendance_id "
                     "WHERE a2.course_offering_section_id = :sec AND c.request_status = 'PENDING') "
                     "ORDER BY (a.student_id IN (SELECT l2.student_id FROM person_account_link l2 JOIN user_account u2 ON u2.user_id = l2.user_id "
                     "WHERE u2.username IN ('student', 'student2'))) DESC, a.attendance_id LIMIT 1",
                     ts=datetime(2026, 10, 8, 10, 0, tzinfo=UTC), a=self.admin, sec=s["sid"])

    # ------------------------------------------------------------------------------------------------ mentoring
    SESSIONS = [  # (mentee index, when, status, confidentiality, observations, action plan, follow-up)
        (0, datetime(2026, 9, 10, 10, 0, tzinfo=UTC), "COMPLETED", "RESTRICTED", "Discussed academic progress and attendance.",
         "Weekly review of lab records and revision plan.", None),
        (0, datetime(2026, 9, 24, 11, 0, tzinfo=UTC), "FOLLOW_UP_REQUIRED", "RESTRICTED",
         "Attendance in two courses is close to the threshold.", "Meet again after the internal assessment; inform the parents.", date(2026, 10, 15)),
        (1, datetime(2026, 10, 14, 14, 0, tzinfo=UTC), "SCHEDULED", "NORMAL", None, None, None),
        (2, datetime(2026, 8, 20, 15, 0, tzinfo=UTC), "COMPLETED", "NORMAL", "Settled in well; interested in the coding club.",
         "Join the club and attend the placement orientation.", None),
        (2, datetime(2026, 10, 2, 15, 0, tzinfo=UTC), "CANCELLED", "NORMAL", None, None, None),
    ]

    def mentoring(self) -> None:
        for slot, username in enumerate(["mentor", "advisor"]):
            emp = self.emp.get(username) or self.scalar(
                "SELECT l.employee_id FROM person_account_link l JOIN user_account u ON u.user_id = l.user_id WHERE u.username = :u "
                "AND l.employee_id IS NOT NULL", u=username)
            if emp is None:
                continue
            programme = self.scalar(
                "SELECT ura.programme_id FROM user_role_assignment ura JOIN user_account u ON u.user_id = ura.user_id WHERE u.username = :u "
                "AND ura.scope_type = 'PROGRAMME' AND ura.programme_id IS NOT NULL AND ura.assignment_status = 'ACTIVE' ORDER BY 1 LIMIT 1",
                u=username) or self.programme
            students = [r[0] for r in self.rows(
                "SELECT DISTINCT student_id FROM student_programme_enrolment WHERE programme_id = :p AND enrolment_status = 'ACTIVE' ORDER BY 1",
                p=programme)]
            mentees = students[slot * 3: slot * 3 + 3]
            for idx, student in enumerate(mentees):
                self.add("mentor_assignment",
                         "INSERT INTO mentor_assignment (student_id, employee_id, start_date, assignment_status) SELECT :s, :e, :d, 'ACTIVE' "
                         "WHERE NOT EXISTS (SELECT 1 FROM mentor_assignment m WHERE m.student_id = :s AND m.employee_id = :e "
                         "AND m.assignment_status = 'ACTIVE')", s=student, e=emp, d=date(2024, 8, 15))
                aid = self.scalar("SELECT mentor_assignment_id FROM mentor_assignment WHERE student_id = :s AND employee_id = :e "
                                  "AND assignment_status = 'ACTIVE' ORDER BY 1 LIMIT 1", s=student, e=emp)
                for who, when, status, conf, obs, plan, follow in self.SESSIONS:
                    if who != idx:
                        continue
                    self.add("counselling_session",
                             "INSERT INTO counselling_session (mentor_assignment_id, session_date, observations, action_plan, follow_up_date, "
                             "session_status, confidentiality_level) SELECT :a, :w, :o, :p, :f, :st, :c WHERE NOT EXISTS "
                             "(SELECT 1 FROM counselling_session x WHERE x.mentor_assignment_id = :a AND x.session_date = :w)",
                             a=aid, w=when, o=obs, p=plan, f=follow, st=status, c=conf)
