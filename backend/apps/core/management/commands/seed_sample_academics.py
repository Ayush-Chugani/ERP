"""Sample teaching, attendance and assessment data (run after seed_sample_data).

Builds one coherent slice for B.E. Computer Science and Engineering, semester 3:
term offering -> section -> course offerings -> faculty -> student registrations
-> class sessions with attendance -> an internal test with marks.
Idempotent; development only.
"""

import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

CSE_PROGRAMME_ID = 4
COURSE_CODES = ["CSE301", "CSE302", "CSE303", "CSE304"]
FACULTY_NUMBERS = ["EMP002", "EMP004", "EMP006", "EMP007"]
SESSION_WEEKS = 5


def model(name):
    return [m for m in apps.get_models() if m.__name__ == name][0]


class Command(BaseCommand):
    help = "Load sample timetable-adjacent teaching, attendance and marks data."

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(7)
        admin = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        programme = model("Programme").objects.get(pk=CSE_PROGRAMME_ID)
        scheme = model("CurriculumScheme").objects.filter(programme=programme).first()
        term = model("AcademicTerm").objects.filter(term_code="ODD25").first()
        sem = model("Semester").objects.get(semester_number=3)
        enrolments = list(model("StudentProgrammeEnrolment").objects.filter(programme=programme).select_related("student"))
        if not (scheme and term and enrolments):
            raise CommandError("Run `seed_sample_data` first.")

        pto, _ = model("ProgrammeTermOffering").objects.get_or_create(
            academic_term=term, programme=programme, curriculum_scheme=scheme, semester=sem,
            defaults=dict(status="ACTIVE", created_by=admin, updated_by=admin),
        )
        section, _ = model("ClassSection").objects.get_or_create(
            programme_term_offering=pto, section_code="A",
            defaults=dict(section_name="Section A", capacity=60, created_by=admin, updated_by=admin),
        )

        # term + course registrations for every enrolled student
        TermReg = model("StudentTermRegistration")
        regs = []
        for roll, en in enumerate(sorted(enrolments, key=lambda e: e.student.student_number), start=1):
            tr, _ = TermReg.objects.get_or_create(
                enrolment=en, programme_term_offering=pto,
                defaults=dict(programme=programme, class_section=section, roll_number=f"{roll:02d}",
                              registration_date=date(2026, 7, 20), registration_status="APPROVED",
                              created_by=admin, updated_by=admin),
            )
            regs.append(tr)

        Offering = model("CourseOffering")
        OSection = model("CourseOfferingSection")
        Faculty = model("FacultyAssignment")
        CReg = model("StudentCourseRegistration")
        OSStudent = model("CourseOfferingSectionStudent")
        Policy = model("PolicyRevision")
        Calc = model("CalculationPolicy")
        Component = model("AssessmentComponent")
        Event = model("AssessmentEvent")
        Mark = model("StudentAssessmentMark")
        Session = model("ClassSession")
        Attendance = model("StudentAttendance")
        present = model("AttendanceStatus").objects.get(status_code="PRESENT")
        absent = model("AttendanceStatus").objects.get(status_code="ABSENT")
        grade_scale = model("GradeScale").objects.first()
        room = model("Room").objects.filter(building__campus=programme.department.campus).first()
        calc_rules = Calc.objects.first().rules if Calc.objects.exists() else {}
        now = datetime.now(timezone.utc).replace(microsecond=0)
        counts = dict(offerings=0, sessions=0, attendance=0, marks=0)

        for code, emp_no in zip(COURSE_CODES, FACULTY_NUMBERS):
            course = model("CourseCatalog").objects.filter(course_code=code).first()
            employee = model("Employee").objects.filter(employee_number=emp_no).first()
            if not course or not employee:
                continue
            curriculum_course = model("CurriculumCourse").objects.filter(curriculum_scheme__programme=programme, course=course).first()
            offering, created = Offering.objects.get_or_create(
                programme_term_offering=pto, course=course, offering_code=f"{code}-ODD25",
                defaults=dict(curriculum_course=curriculum_course, registration_capacity=60, status="ACTIVE",
                              created_by=admin, updated_by=admin),
            )
            counts["offerings"] += int(created)
            osec, _ = OSection.objects.get_or_create(
                course_offering=offering, programme_term_offering=pto, class_section=section, session_type="LECTURE",
                defaults=dict(created_by=admin, updated_by=admin),
            )
            fa, _ = Faculty.objects.get_or_create(
                course_offering_section=osec, employee=employee, assignment_role="PRIMARY_INSTRUCTOR",
                defaults=dict(workload_hours=Decimal(4), start_date=date(2026, 8, 1), end_date=date(2026, 12, 20),
                              assignment_status="ACTIVE", created_by=admin, updated_by=admin),
            )
            rosters = []
            for tr in regs:
                cr, _ = CReg.objects.get_or_create(
                    term_registration=tr, course_offering=offering,
                    defaults=dict(programme_term_offering=pto, registration_date=date(2026, 7, 22),
                                  created_by=admin, updated_by=admin),
                )
                ros, _ = OSStudent.objects.get_or_create(
                    course_offering_section=osec, course_registration=cr,
                    defaults=dict(course_offering=offering, session_type="LECTURE", effective_from=date(2026, 8, 1),
                                  created_by=admin, updated_by=admin),
                )
                rosters.append((cr, ros, tr.enrolment.student))

            # attendance policy + class sessions
            policy = Policy.objects.filter(section=osec).first() or Policy.objects.create(
                section=osec, number=1, basis="SESSION", threshold=Decimal("75.00"), edit_days=7, correction_days=7,
                rules={"ABSENT": {"credit": "0.0000", "denominator": "1.0000"},
                       "PRESENT": {"credit": "1.0000", "denominator": "1.0000"}},
                reason="Sample data", actor=admin,
            )
            for week in range(SESSION_WEEKS):
                day = date(2026, 8, 31) + timedelta(weeks=week, days=("CSE301 CSE302 CSE303 CSE304".split().index(code)))
                session, s_created = Session.objects.get_or_create(
                    course_offering_section=osec, session_date=day, class_number=week + 1,
                    defaults=dict(faculty_assignment=fa, start_time=time(9 + COURSE_CODES.index(code), 0),
                                  end_time=time(10 + COURSE_CODES.index(code), 0), room=room, session_type="LECTURE",
                                  planned_topic=f"Unit {week + 1} lecture", topic_covered=f"Unit {week + 1} lecture",
                                  session_status="CONDUCTED", register_status="FINALIZED", finalized_at=now,
                                  policy=policy, calendar_reference=f"{code}-{day.isoformat()}", created_by=admin, updated_by=admin),
                )
                if not s_created:
                    continue
                counts["sessions"] += 1
                for cr, ros, student in rosters:
                    was_present = rnd.random() < 0.86
                    Attendance.objects.create(
                        class_session=session, course_offering_section_student=ros, course_offering_section=osec,
                        student=student, attendance_status=present if was_present else absent,
                        marked_at=now, marked_by_user=admin, is_eligible=True,
                        credit=Decimal("1") if was_present else Decimal("0"), denominator=Decimal("1"),
                    )
                    counts["attendance"] += 1

            # internal test and marks
            calc = Calc.objects.filter(course_offering=offering).first() or Calc.objects.create(
                course_offering=offering, number=1, grade_scale=grade_scale, rules=calc_rules, actor=admin, reason="Sample data",
            )
            component, _ = Component.objects.get_or_create(
                course_offering=offering, component_code="IA1",
                defaults=dict(component_name="Internal Assessment 1", component_type="INTERNAL_TEST",
                              maximum_marks=Decimal(50), weightage_percent=Decimal(40), is_mandatory=True, actor=admin),
            )
            event, e_created = Event.objects.get_or_create(
                assessment_component=component, course_offering=offering, attempt_number=1, event_title="IA-1",
                defaults=dict(policy=calc, assessment_date=date(2026, 9, 25), start_time=time(10, 0), end_time=time(11, 30),
                              maximum_marks=Decimal(50), status="CONDUCTED", roster=[], actor=admin),
            )
            # a planned follow-up test so the dashboard has upcoming assessments
            Event.objects.get_or_create(
                assessment_component=component, course_offering=offering, attempt_number=1,
                event_title="IA-2",
                defaults=dict(policy=calc, assessment_date=date.today() + timedelta(days=9 + COURSE_CODES.index(code) * 3),
                              start_time=time(10, 0), end_time=time(11, 30), maximum_marks=Decimal(50),
                              status="PLANNED", roster=[], actor=admin),
            )
            if e_created:
                for cr, ros, student in rosters:
                    ok = rnd.random() > 0.05
                    Mark.objects.create(
                        assessment_event=event, course_registration=cr, course_offering=offering,
                        attendance_status="PRESENT" if ok else "ABSENT",
                        marks_obtained=Decimal(rnd.randint(18, 49)) if ok else None,
                        evaluated_at=now, actor=admin,
                    )
                    counts["marks"] += 1

        # weekly timetable (draft-free, approved revision) ------------------------
        Plan, Revision, TSession = model("TimetablePlan"), model("TimetableRevision"), model("TimetableSession")
        plan, _ = Plan.objects.get_or_create(
            programme_term_offering=pto, defaults=dict(name="B.E. CSE - Semester 3 timetable", created_by=admin, updated_by=admin))
        revision, _ = Revision.objects.get_or_create(
            plan=plan, number=1, defaults=dict(status="APPROVED", created_by=admin, updated_by=admin))
        campus = programme.department.campus
        slots = {t.slot_code: t for t in model("TimeSlot").objects.filter(campus=campus)}
        rooms = list(model("Room").objects.filter(building__campus=campus, building__building_code="MAIN").order_by("room_code")[:4])
        added_tt = 0
        for i, code in enumerate(COURSE_CODES):
            osec = OSection.objects.filter(course_offering__offering_code=f"{code}-ODD25").first()
            fa = Faculty.objects.filter(course_offering_section=osec).first() if osec else None
            if not osec or not fa:
                continue
            for day in sorted({i % 5 + 1, (i + 2) % 5 + 1, (i + 4) % 5 + 1}):
                slot = slots[f"S{(day + i) % 4 + 1}"]
                _, created = TSession.objects.get_or_create(
                    revision=revision, course_offering_section=osec, day_of_week=day, time_slot=slot,
                    defaults=dict(faculty_assignment=fa, room=rooms[i % len(rooms)], effective_from=date(2026, 8, 1),
                                  effective_to=date(2026, 12, 20), created_by=admin, updated_by=admin),
                )
                added_tt += int(created)
        counts["timetable_sessions"] = added_tt

        # publish the revision and materialise upcoming occurrences (next 5 weeks)
        Occurrence = model("PublishedOccurrence")
        student_ids = [tr.enrolment.student_id for tr in regs]
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        added_occ = 0
        for ts in TSession.objects.filter(revision=revision).select_related("time_slot", "faculty_assignment", "course_offering_section"):
            for week in range(-1, 5):
                day = monday + timedelta(weeks=week, days=ts.day_of_week - 1)
                _, created = Occurrence.objects.get_or_create(
                    revision=revision, session=ts, date=day,
                    defaults=dict(course_offering_section=ts.course_offering_section, class_section=section,
                                  employee=ts.faculty_assignment.employee, room=ts.room, start_time=ts.time_slot.start_time,
                                  end_time=ts.time_slot.end_time, student_ids=student_ids),
                )
                added_occ += int(created)
        if revision.status != "PUBLISHED":
            revision.status = "PUBLISHED"
            revision.save(update_fields=["status"])
        counts["published_occurrences"] = added_occ

        self.stdout.write(self.style.SUCCESS(f"Academics ready: {counts}"))
