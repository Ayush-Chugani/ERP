"""Populate a development database with realistic campus sample data.

Idempotent: records are keyed on natural identifiers (student/employee numbers,
course codes, ...) so re-running never duplicates. Dev/demo use only.

    python manage.py seed_sample_data

The three existing demo accounts (admin, teacher, student) are given
DEMO_PASSWORD so the UI can be explored; change it below if you like.
"""

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

DEMO_PASSWORD = "Campus@2026"  # dev only

FIRST_M = ["Aarav", "Vihaan", "Arjun", "Rohan", "Karthik", "Siddharth", "Pranav", "Manoj", "Harsha", "Naveen", "Abhishek", "Rahul", "Sandeep", "Varun", "Chetan", "Deepak", "Girish", "Mahesh", "Nikhil", "Prathamesh"]
FIRST_F = ["Ananya", "Diya", "Meera", "Priya", "Shreya", "Kavya", "Sneha", "Aishwarya", "Divya", "Nandini", "Pooja", "Rashmi", "Swati", "Tanvi", "Vaishnavi", "Bhavana", "Chaitra", "Deepika", "Harini", "Lakshmi"]
LAST = ["Patil", "Kulkarni", "Hegde", "Naik", "Shetty", "Joshi", "Desai", "Gowda", "Reddy", "Rao", "Bhat", "Kamath", "Hiremath", "Pawar", "Deshpande", "Nayak", "Shenoy", "Menon", "Iyer", "Sharma"]
CITIES = ["Hubballi", "Dharwad", "Belagavi", "Bengaluru", "Mysuru", "Vijayapura", "Davanagere", "Ballari", "Mangaluru", "Kalaburagi"]
STREETS = ["Vidyanagar", "Gokul Road", "Keshwapur", "Saptapur", "Navanagar"]
OCCUPATIONS = ["Teacher", "Farmer", "Businessperson", "Engineer", "Government employee", "Doctor", "Bank officer"]

# programme_id -> (USN branch code, student count)
BRANCHES = {4: ("CS", 12), 5: ("AI", 9), 7: ("EC", 9), 9: ("ME", 8), 3: ("CV", 6), 6: ("EE", 6)}

FEMALE_STAFF = {"Sunita", "Latha", "Geeta", "Kavitha", "Neha", "Shobha", "Pooja"}

STAFF = [
    # first, last, designation_id, department_id, employment_type
    ("Sunita", "Hegde", 1, 1, "REGULAR"),
    ("Ramesh", "Kulkarni", 1, 4, "REGULAR"),
    ("Anil", "Deshpande", 2, 1, "REGULAR"),
    ("Latha", "Shenoy", 2, 2, "REGULAR"),
    ("Mohan", "Rao", 3, 1, "REGULAR"),
    ("Pooja", "Naik", 3, 1, "REGULAR"),
    ("Vikram", "Joshi", 3, 3, "REGULAR"),
    ("Geeta", "Patil", 3, 4, "REGULAR"),
    ("Suresh", "Gowda", 3, 5, "CONTRACT"),
    ("Kavitha", "Menon", 3, 2, "REGULAR"),
    ("Prakash", "Bhat", 2, 4, "REGULAR"),
    ("Neha", "Kamath", 3, 1, "VISITING"),
    ("Basavaraj", "Hiremath", 4, 9, "REGULAR"),
    ("Shobha", "Desai", 8, 1, "REGULAR"),
    ("Imran", "Shaikh", 6, 1, "REGULAR"),
]

COURSES = [
    # code, title, type, lecture, tutorial, practical, credits, dept, semester
    ("MAT101", "Engineering Mathematics I", "THEORY", 3, 1, 0, 4, 15, 1),
    ("PHY101", "Engineering Physics", "THEORY_LAB", 3, 0, 2, 4, 15, 1),
    ("CSE101", "Problem Solving with C", "THEORY_LAB", 3, 0, 2, 4, 1, 1),
    ("ENG101", "Technical English", "THEORY", 2, 0, 0, 2, 15, 1),
    ("MAT201", "Engineering Mathematics II", "THEORY", 3, 1, 0, 4, 15, 2),
    ("CSE201", "Data Structures", "THEORY_LAB", 3, 0, 2, 4, 1, 2),
    ("EEE201", "Basic Electrical Engineering", "THEORY", 3, 1, 0, 4, 5, 2),
    ("CSE202", "Digital Logic Design", "THEORY", 3, 0, 0, 3, 1, 2),
    ("CSE301", "Object Oriented Programming", "THEORY_LAB", 3, 0, 2, 4, 1, 3),
    ("CSE302", "Discrete Mathematics", "THEORY", 3, 1, 0, 4, 1, 3),
    ("CSE303", "Computer Organization", "THEORY", 3, 0, 0, 3, 1, 3),
    ("CSE304", "Database Management Systems", "THEORY_LAB", 3, 0, 2, 4, 1, 3),
    ("CSE401", "Operating Systems", "THEORY_LAB", 3, 0, 2, 4, 1, 4),
    ("CSE402", "Design and Analysis of Algorithms", "THEORY", 3, 1, 0, 4, 1, 4),
    ("CSE403", "Computer Networks", "THEORY_LAB", 3, 0, 2, 4, 1, 4),
    ("CSE404", "Mini Project", "PROJECT", 0, 0, 4, 2, 1, 4),
]

ANNOUNCEMENTS = [
    ("Semester registration opens", "Students may register for the upcoming semester through the Registration module until the end of the month.", "STUDENTS", "APPROVED", -3),
    ("Faculty meeting - Friday 3 PM", "All teaching staff are requested to attend the monthly faculty meeting in the main seminar hall.", "STAFF", "APPROVED", -2),
    ("Internal assessment schedule published", "The IA-1 timetable is now available. Please check your department notice board and the calendar.", "ALL", "APPROVED", -1),
    ("Library hours extended during exams", "The central library will remain open until 9 PM during the examination period.", "ALL", "APPROVED", 0),
    ("Annual sports meet - volunteers needed", "Interested students may register with the sports committee by next Wednesday.", "STUDENTS", "PENDING", 0),
    ("Holiday on account of local festival", "The campus will remain closed on the notified date. Regular schedules resume the next working day.", "ALL", "DRAFT", 1),
]


def model(name):
    found = [m for m in apps.get_models() if m.__name__ == name]
    if not found:
        raise LookupError(name)
    return found[0]


class Command(BaseCommand):
    help = "Load realistic sample campus data (idempotent, development only)."

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(2026)
        User = get_user_model()
        admin = User.objects.filter(is_superuser=True).order_by("pk").first()
        if admin is None:
            self.stderr.write("No superuser exists; run createsuperuser first.")
            return

        inst = model("Institution").objects.order_by("pk").first()
        India = model("Country").objects.filter(iso_code="IN").first()
        KA = model("State").objects.filter(state_code="KA").first()
        Gender = model("Gender")
        genders = {
            code: Gender.objects.get_or_create(gender_code=code, defaults={"gender_name": name})[0]
            for code, name in (("M", "Male"), ("F", "Female"), ("O", "Other"))
        }
        blood = list(model("BloodGroup").objects.all())
        religions = list(model("Religion").objects.all())
        categories = list(model("SocialCategory").objects.all())

        Programme = model("Programme")
        prog = {p.programme_id: p for p in Programme.objects.select_related("department__campus")}

        # --- Students -----------------------------------------------------
        Student = model("Student")
        Address = model("StudentAddress")
        Guardian = model("StudentParentGuardian")
        n_students = 0
        students_by_prog = {}
        for pid, (branch, count) in BRANCHES.items():
            programme = prog.get(pid)
            if programme is None:
                continue
            dept = programme.department
            for i in range(1, count + 1):
                usn = f"01FE24B{branch}{i:03d}"
                female = rnd.random() < 0.45
                first = rnd.choice(FIRST_F if female else FIRST_M)
                last = rnd.choice(LAST)
                city = rnd.choice(CITIES)
                year = rnd.choice([2005, 2006, 2006, 2007])
                status = "ACTIVE" if i < count else rnd.choice(["ACTIVE", "SUSPENDED"])
                s, created = Student.objects.get_or_create(
                    student_number=usn,
                    defaults=dict(
                        university_seat_number=usn,
                        first_name=first,
                        last_name=last,
                        display_name=f"{first} {last}",
                        date_of_birth=date(year, rnd.randint(1, 12), rnd.randint(1, 28)),
                        gender=genders["F" if female else "M"],
                        blood_group=rnd.choice(blood) if blood else None,
                        primary_email=f"{first.lower()}.{last.lower()}{i}@students.sample.edu",
                        primary_phone=f"98{rnd.randint(10000000, 99999999)}",
                        nationality_country=India,
                        religion=rnd.choice(religions) if religions else None,
                        social_category=rnd.choice(categories) if categories else None,
                        admission_date=date(2024, 8, rnd.randint(1, 10)),
                        student_status=status,
                        institution=inst,
                        campus=dept.campus,
                        department=dept,
                    ),
                )
                students_by_prog.setdefault(pid, []).append(s)
                if not created:
                    continue
                n_students += 1
                Address.objects.create(
                    student=s,
                    address_type="PERMANENT",
                    address_line_1=f"{rnd.randint(1, 250)}, {rnd.choice(STREETS)}",
                    city=city,
                    state=KA,
                    country=India,
                    postal_code=f"5{rnd.randint(80000, 99999)}",
                    valid_from=date(2024, 8, 1),
                    is_primary=True,
                )
                Guardian.objects.create(
                    student=s,
                    relationship_type="FATHER",
                    full_name=f"{rnd.choice(FIRST_M)} {last}",
                    occupation=rnd.choice(OCCUPATIONS),
                    phone=f"97{rnd.randint(10000000, 99999999)}",
                    city=city,
                    state=KA,
                    country=India,
                    is_primary_contact=True,
                )
        self.stdout.write(f"students: +{n_students}")

        # --- Staff --------------------------------------------------------
        Employee = model("Employee")
        Assignment = model("EmployeeAssignment")
        Department = model("Department")
        Designation = model("Designation")
        source = model("EmploymentSource").objects.get(source_code="INSTITUTION")
        n_staff = 0
        for idx, (first, last, desg_id, dept_id, etype) in enumerate(STAFF, start=2):
            dept = Department.objects.select_related("campus").filter(pk=dept_id).first()
            desg = Designation.objects.filter(pk=desg_id).first()
            if not dept or not desg:
                continue
            emp, created = Employee.objects.get_or_create(
                employee_number=f"EMP{idx:03d}",
                defaults=dict(
                    institution=inst,
                    employment_source=source,
                    first_name=first,
                    last_name=last,
                    display_name=f"{'Dr. ' if desg_id <= 2 else ''}{first} {last}",
                    date_of_birth=date(rnd.randint(1968, 1992), rnd.randint(1, 12), rnd.randint(1, 28)),
                    gender=genders["F" if first in FEMALE_STAFF else "M"],
                    primary_email=f"{first.lower()}.{last.lower()}@staff.sample.edu",
                    primary_phone=f"99{rnd.randint(10000000, 99999999)}",
                    nationality_country=India,
                    joining_date=date(rnd.randint(2005, 2023), rnd.randint(1, 12), 1),
                    employment_type=etype,
                    employment_status="ACTIVE",
                ),
            )
            if created:
                n_staff += 1
                Assignment.objects.create(
                    employee=emp, campus=dept.campus, department=dept, designation=desg,
                    start_date=emp.joining_date, is_primary=True,
                )
        self.stdout.write(f"staff: +{n_staff}")

        # --- Curriculum ---------------------------------------------------
        Semester = model("Semester")
        sems = {
            n: Semester.objects.get_or_create(semester_number=n, defaults={"semester_name": f"Semester {n}"})[0]
            for n in range(1, 9)
        }
        Scheme = model("CurriculumScheme")
        scheme = Scheme.objects.filter(programme_id=4).first() or Scheme.objects.first()
        core = model("CourseCategory").objects.filter(category_code="CORE").first()
        Course = model("CourseCatalog")
        CurCourse = model("CurriculumCourse")
        n_courses = 0
        for order, (code, title, ctype, lh, th, ph, cr, dept_id, sem) in enumerate(COURSES, start=1):
            dept = Department.objects.filter(pk=dept_id).first()
            course, created = Course.objects.get_or_create(
                course_code=code,
                defaults=dict(
                    owning_department=dept,
                    course_category=core,
                    course_title=title,
                    course_type=ctype,
                    lecture_hours=Decimal(lh),
                    tutorial_hours=Decimal(th),
                    practical_hours=Decimal(ph),
                    self_study_hours=Decimal(2),
                    credits=Decimal(cr),
                    is_active=True,
                ),
            )
            n_courses += int(created)
            if scheme:
                CurCourse.objects.get_or_create(
                    curriculum_scheme=scheme,
                    semester=sems[sem],
                    course=course,
                    defaults=dict(
                        course_category=core,
                        is_mandatory=True,
                        display_order=order,
                        internal_max_marks=Decimal(50),
                        external_max_marks=Decimal(50),
                    ),
                )
        self.stdout.write(f"courses: +{n_courses}")

        # --- Admissions (applicants, applications, enrolments) -----------
        Applicant = model("AdmissionApplicant")
        Application = model("AdmissionApplication")
        Enrolment = model("StudentProgrammeEnrolment")
        adm_cats = list(model("AdmissionCategory").objects.all())
        year = model("AcademicYear").objects.order_by("pk").first()
        n_adm = 0
        for pid, studs in students_by_prog.items():
            programme = prog[pid]
            sch = Scheme.objects.filter(programme=programme).first()
            if sch is None:
                sch = Scheme.objects.create(
                    programme=programme,
                    scheme_code=f"SCH2024-{programme.programme_code.rsplit('_', 1)[-1]}",
                    scheme_name="2024 Scheme",
                    regulation_year=2024,
                    effective_from=date(2024, 8, 1),
                    status="ACTIVE",
                )
            for s in (studs if pid == 4 else studs[:4]):
                if Application.objects.filter(admitted_student=s).exists():
                    continue
                ap = Applicant.objects.create(
                    institution=inst,
                    canonical_student=s,
                    first_name=s.first_name,
                    last_name=s.last_name,
                    display_name=s.display_name,
                    date_of_birth=s.date_of_birth,
                    gender=s.gender,
                    primary_email=s.primary_email,
                    primary_phone=s.primary_phone,
                    nationality_country=India,
                    created_by=admin,
                    updated_by=admin,
                )
                app = Application.objects.create(
                    application_number=f"APP-24-{s.student_number[-6:]}",
                    admission_applicant=ap,
                    admitted_student=s,
                    programme=programme,
                    academic_year=year,
                    admission_category=rnd.choice(adm_cats) if adm_cats else None,
                    application_date=date(2024, 6, rnd.randint(1, 28)),
                    application_status="ADMITTED",
                    eligibility_status="ELIGIBLE",
                    created_by=admin,
                    updated_by=admin,
                )
                if sch:
                    Enrolment.objects.create(
                        application=app,
                        student=s,
                        programme=programme,
                        curriculum_scheme=sch,
                        admission_academic_year=year,
                        admission_date=s.admission_date or date(2024, 8, 5),
                        admission_semester=sems[1],
                        enrolment_status="ACTIVE",
                        created_by=admin,
                        updated_by=admin,
                    )
                n_adm += 1
        pipeline = ["SUBMITTED", "UNDER_REVIEW", "ELIGIBLE", "WAITLISTED", "REJECTED", "SELECTED", "SUBMITTED", "UNDER_REVIEW"]
        for i, status in enumerate(pipeline, start=1):
            number = f"APP-26-{i:04d}"
            if Application.objects.filter(application_number=number).exists():
                continue
            female = i % 2 == 0
            first = rnd.choice(FIRST_F if female else FIRST_M)
            last = rnd.choice(LAST)
            ap = Applicant.objects.create(
                institution=inst,
                first_name=first,
                last_name=last,
                display_name=f"{first} {last}",
                gender=genders["F" if female else "M"],
                primary_email=f"{first.lower()}.{last.lower()}@mail.sample.com",
                primary_phone=f"96{rnd.randint(10000000, 99999999)}",
                nationality_country=India,
                created_by=admin,
                updated_by=admin,
            )
            Application.objects.create(
                application_number=number,
                admission_applicant=ap,
                programme=prog[rnd.choice(list(BRANCHES))],
                academic_year=year,
                admission_category=rnd.choice(adm_cats) if adm_cats else None,
                application_date=date(2026, rnd.randint(1, 6), rnd.randint(1, 28)),
                application_status=status,
                eligibility_status="ELIGIBLE" if status in ("ELIGIBLE", "SELECTED", "WAITLISTED") else "PENDING",
                created_by=admin,
                updated_by=admin,
            )
            n_adm += 1
        self.stdout.write(f"admissions: +{n_adm}")

        # --- Announcements ------------------------------------------------
        Announcement = model("Announcement")
        AType = model("AnnouncementType")
        general = AType.objects.get_or_create(type_code="GENERAL", defaults={"type_name": "General"})[0]
        exams = AType.objects.get_or_create(type_code="EXAMINATION", defaults={"type_name": "Examination"})[0]
        events = AType.objects.get_or_create(type_code="EVENT", defaults={"type_name": "Events"})[0]
        now = datetime.now(timezone.utc).replace(microsecond=0)
        n_ann = 0
        for title, desc, aud, status, offset in ANNOUNCEMENTS:
            atype = exams if "assessment" in title else events if "sports" in title else general
            _, created = Announcement.objects.get_or_create(
                institution=inst,
                title=title,
                defaults=dict(
                    announcement_type=atype,
                    description=desc,
                    audience_type=aud,
                    approval_status=status,
                    publish_from=now + timedelta(days=offset),
                ),
            )
            n_ann += int(created)
        self.stdout.write(f"announcements: +{n_ann}")

        # --- Academic calendar and campus infrastructure -----------------
        AYear = model("AcademicYear")
        ATerm = model("AcademicTerm")
        years = {}
        for code, start, end, status in (
            ("2024-25", date(2024, 6, 1), date(2025, 5, 31), "CLOSED"),
            ("2026-27", date(2026, 6, 1), date(2027, 5, 31), "PLANNED"),
        ):
            years[code] = AYear.objects.get_or_create(
                year_code=code, defaults=dict(start_date=start, end_date=end, status=status)
            )[0]
        for ycode, tcode, name, ttype, start, end, status in (
            ("2024-25", "ODD24", "Odd Semester 2024", "ODD", date(2024, 8, 1), date(2024, 12, 20), "CLOSED"),
            ("2024-25", "EVEN25", "Even Semester 2025", "EVEN", date(2025, 1, 15), date(2025, 5, 30), "CLOSED"),
            ("2026-27", "ODD26", "Odd Semester 2026", "ODD", date(2026, 8, 1), date(2026, 12, 20), "PLANNED"),
            ("2026-27", "EVEN27", "Even Semester 2027", "EVEN", date(2027, 1, 15), date(2027, 5, 30), "PLANNED"),
        ):
            ATerm.objects.get_or_create(
                term_code=tcode,
                defaults=dict(academic_year=years[ycode], term_name=name, term_type=ttype,
                              start_date=start, end_date=end, status=status),
            )
        Campus = model("Campus")
        TimeSlot = model("TimeSlot")
        Building = model("Building")
        Room = model("Room")
        for campus in Campus.objects.all():
            slots = (("S1", 9, 0, 10, 0), ("S2", 10, 0, 11, 0), ("BRK", 11, 0, 11, 15), ("S3", 11, 15, 12, 15),
                     ("S4", 12, 15, 13, 15), ("LUN", 13, 15, 14, 0), ("S5", 14, 0, 15, 0), ("S6", 15, 0, 16, 0))
            from datetime import time as _t
            for code, sh, sm, eh, em in slots:
                TimeSlot.objects.get_or_create(
                    campus=campus, slot_code=code,
                    defaults=dict(start_time=_t(sh, sm), end_time=_t(eh, em), is_break=code in ("BRK", "LUN")),
                )
            for bcode, bname, floors in (("MAIN", "Main Block", 3), ("LAB", "Laboratory Block", 2)):
                b = Building.objects.get_or_create(campus=campus, building_code=bcode, defaults={"building_name": bname})[0]
                for f in range(1, floors + 1):
                    for n in (1, 2, 3):
                        rcode = f"{bcode[0]}{f}0{n}"
                        Room.objects.get_or_create(
                            building=b, room_code=rcode,
                            defaults=dict(room_name=f"Room {rcode}", room_type="LAB" if bcode == "LAB" else "CLASSROOM",
                                          capacity=30 if bcode == "LAB" else 60),
                        )
        self.stdout.write("calendar, time slots, buildings and rooms ensured")

        # --- Demo logins --------------------------------------------------
        for name in ("teacher", "student"):  # never touch the admin password
            u = User.objects.filter(username=name).first()
            if u:
                u.set_password(DEMO_PASSWORD)
                u.must_change_password = False
                u.failed_login_count = 0
                u.locked_until = None
                u.save()
        self.stdout.write(self.style.SUCCESS("Sample data ready. Demo logins: teacher / student (password: DEMO_PASSWORD in this file)."))
