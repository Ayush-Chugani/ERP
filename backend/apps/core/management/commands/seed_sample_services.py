"""Sample student-services data: mentoring and counselling, grievances,
certificate requests and feedback question bank.

Run after seed_sample_data. Idempotent; development only.
"""

import random
from datetime import date, datetime, timedelta, timezone

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction


def M(name):
    return [m for m in apps.get_models() if m.__name__ == name][0]


MENTORS = ["EMP002", "EMP004", "EMP006", "EMP007"]
GRIEVANCE_CATEGORIES = [("HOSTEL", "Hostel and accommodation"), ("ACADEMIC", "Academic"), ("EXAM", "Examination"),
                        ("LIBRARY", "Library and resources"), ("TRANSPORT", "Transport"), ("FEES", "Fees and scholarships")]
GRIEVANCES = [
    ("Water supply interruption in hostel block B", "Water supply has been irregular in the mornings for the past week.", "HOSTEL", "HIGH", "ASSIGNED"),
    ("Clash between lab and tutorial timings", "The Data Structures lab overlaps with the Mathematics tutorial on Thursdays.", "ACADEMIC", "NORMAL", "UNDER_REVIEW"),
    ("Revaluation result not updated", "My revaluation result for Discrete Mathematics has not been reflected on the portal.", "EXAM", "HIGH", "RESOLVED"),
    ("Reference books unavailable", "Reference books for Computer Networks are not available in the library.", "LIBRARY", "LOW", "SUBMITTED"),
    ("Bus route extension request", "Request to extend the Gokul Road route to the new residential layout.", "TRANSPORT", "NORMAL", "SUBMITTED"),
    ("Scholarship disbursal delay", "Merit scholarship for the current term has not been credited.", "FEES", "URGENT", "ASSIGNED"),
    ("Wi-Fi coverage in library", "Wi-Fi signal is very weak on the second floor of the library.", "LIBRARY", "NORMAL", "CLOSED"),
    ("Attendance shortage condonation", "Requesting review of attendance for the days of the university sports event.", "ACADEMIC", "NORMAL", "REJECTED"),
]
CERT_TYPES = [("BONAFIDE", "Bonafide certificate"), ("TRANSCRIPT", "Academic transcript"), ("NOC", "No objection certificate"),
              ("CONDUCT", "Conduct certificate"), ("FEE", "Fee payment certificate")]
CERT_STATUS = ["SUBMITTED", "UNDER_REVIEW", "APPROVED", "ISSUED", "ISSUED", "REJECTED", "SUBMITTED", "APPROVED", "ISSUED", "CANCELLED"]
PURPOSES = ["Bank education loan", "Passport application", "Internship application", "Scholarship application", "Higher studies abroad"]
QUESTIONS = [
    ("Teaching", "The instructor explains concepts clearly.", "RATING"),
    ("Teaching", "The instructor is punctual and well prepared.", "RATING"),
    ("Course", "The course content is relevant and up to date.", "RATING"),
    ("Course", "Assessments reflect what was taught.", "RATING"),
    ("Facilities", "Laboratory and classroom facilities are adequate.", "RATING"),
    ("Overall", "What should be improved in this course?", "TEXT"),
]


class Command(BaseCommand):
    help = "Load sample mentoring, grievance, certificate and feedback data."

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(11)
        admin = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        students = list(M("Student").objects.filter(student_number__startswith="01FE24BCS").order_by("student_number"))
        more = list(M("Student").objects.filter(student_number__startswith="01FE24BAI").order_by("student_number")[:6])
        students += more
        mentors = list(M("Employee").objects.filter(employee_number__in=MENTORS).order_by("employee_number"))
        counts = {}

        # mentoring + counselling ------------------------------------------
        MA, CS = M("MentorAssignment"), M("CounsellingSession")
        sessions_added = 0
        for i, student in enumerate(students):
            ma, created = MA.objects.get_or_create(
                student=student, employee=mentors[i % len(mentors)],
                defaults=dict(start_date=date(2024, 8, 15), assignment_status="ACTIVE"),
            )
            counts["mentor_assignments"] = counts.get("mentor_assignments", 0) + int(created)
            if i < 10 and not CS.objects.filter(mentor_assignment=ma).exists():
                status = ["COMPLETED", "COMPLETED", "SCHEDULED", "FOLLOW_UP_REQUIRED", "COMPLETED"][i % 5]
                when = now - timedelta(days=rnd.randint(2, 60)) if status != "SCHEDULED" else now + timedelta(days=rnd.randint(2, 14))
                CS.objects.create(
                    mentor_assignment=ma, session_date=when, session_status=status,
                    confidentiality_level="RESTRICTED" if i % 4 == 0 else "NORMAL",
                    observations="Discussed academic progress and attendance." if status != "SCHEDULED" else None,
                    action_plan="Weekly review of lab records and revision plan." if status != "SCHEDULED" else None,
                    follow_up_date=(when + timedelta(days=14)).date() if status == "FOLLOW_UP_REQUIRED" else None,
                )
                sessions_added += 1
        counts["counselling_sessions"] = sessions_added

        # grievances --------------------------------------------------------
        GC, G, GA = M("GrievanceCategory"), M("Grievance"), M("GrievanceAction")
        cats = {c: GC.objects.get_or_create(category_code=c, defaults={"category_name": n})[0] for c, n in GRIEVANCE_CATEGORIES}
        added = 0
        for i, (subject, desc, cat, prio, status) in enumerate(GRIEVANCES):
            if G.objects.filter(subject=subject).exists():
                continue
            submitted = now - timedelta(days=rnd.randint(3, 45))
            g = G.objects.create(
                grievance_number=f"GR-26-{i + 100:04d}", student=students[(i * 2) % len(students)], grievance_category=cats[cat],
                submitted_at=submitted, subject=subject, description=desc, priority=prio, status=status,
                resolved_at=submitted + timedelta(days=5) if status in ("RESOLVED", "CLOSED") else None,
                resolution="Issue addressed by the concerned office." if status in ("RESOLVED", "CLOSED") else None,
            )
            GA.objects.create(grievance=g, action_at=submitted, action_type="SUBMITTED", new_status="SUBMITTED", action_notes="Grievance submitted.")
            if status != "SUBMITTED":
                step = {"ASSIGNED": "ASSIGNED", "UNDER_REVIEW": "REVIEW_STARTED", "RESOLVED": "RESOLVED", "REJECTED": "REJECTED", "CLOSED": "CLOSED"}[status]
                GA.objects.create(grievance=g, action_at=submitted + timedelta(days=2), action_type=step, new_status=status, action_notes="Status updated by the grievance cell.")
            added += 1
        counts["grievances"] = added

        # certificates ------------------------------------------------------
        CT, CR = M("CertificateType"), M("CertificateRequest")
        ctypes = [CT.objects.get_or_create(certificate_code=c, defaults={"certificate_name": n})[0] for c, n in CERT_TYPES]
        added = 0
        for i, status in enumerate(CERT_STATUS):
            number = f"SIMSR26{i + 1:05d}"
            if CR.objects.filter(request_number=number).exists():
                continue
            requested = now - timedelta(days=rnd.randint(1, 40))
            issued = status == "ISSUED"
            CR.objects.create(
                request_number=number, student=students[(i * 3) % len(students)], certificate_type=ctypes[i % len(ctypes)],
                requested_at=requested, purpose=PURPOSES[i % len(PURPOSES)], request_status=status,
                issued_at=requested + timedelta(days=3) if issued else None,
                certificate_number=f"CERT/2026/{i + 1:04d}" if issued else None,
            )
            added += 1
        counts["certificate_requests"] = added

        # feedback question bank -------------------------------------------
        Cat, Q = M("Category"), M("Question")
        inst = M("Institution").objects.order_by("pk").first()
        cat_fields = [f.name for f in Cat._meta.concrete_fields]
        name_field = next(n for n in cat_fields if n.endswith("name"))
        extra_cat = {k: v for k, v in (("actor", admin), ("institution", inst)) if k in cat_fields}
        added = 0
        for cname, text, rtype in QUESTIONS:
            cat = Cat.objects.filter(**{name_field: cname}).first() or Cat.objects.create(**{name_field: cname}, **({'category_code': cname.upper()} if 'category_code' in cat_fields else {}), **extra_cat)
            extra = dict(rating_min=1, rating_max=5, rating_step=1) if rtype == "RATING" else dict(text_limit=500)
            _, created = Q.objects.get_or_create(feedback_category=cat, question_text=text,
                                                 defaults=dict(response_type=rtype, actor=admin, **extra))
            added += int(created)
        counts["feedback_questions"] = added

        self.stdout.write(self.style.SUCCESS(f"Services data added: {counts}"))
