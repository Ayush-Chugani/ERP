"""Sample staff-activity data: awards, memberships, contributions, conferences,
consultancy, funded projects, proposals, internships, co- and extra-curricular.

Run after seed_sample_data. Idempotent (keyed on activity titles); development only.
"""

from datetime import date
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction


def M(name):
    return [m for m in apps.get_models() if m.__name__ == name][0]


# lookups ---------------------------------------------------------------------
ORGS = [("IEEE", "IEEE"), ("ACM", "Association for Computing Machinery"), ("CSI", "Computer Society of India"),
        ("ISTE", "Indian Society for Technical Education"), ("DST", "Department of Science and Technology"),
        ("AICTE", "All India Council for Technical Education"), ("VGST", "Vision Group on Science and Technology"),
        ("INFOSYS", "Infosys Limited"), ("BOSCH", "Bosch Global Software Technologies"), ("TCS", "Tata Consultancy Services"),
        ("VTU", "Visvesvaraya Technological University"), ("KSCST", "Karnataka State Council for Science and Technology")]
FUNDING_TYPES = [("GOVT", "Government"), ("INDUSTRY", "Industry"), ("INTERNAL", "Institutional seed grant")]
FUNDERS = [("DST", "GOVT"), ("AICTE", "GOVT"), ("VGST", "GOVT"), ("KSCST", "GOVT"), ("INFOSYS", "INDUSTRY")]
AWARD_CATS = [("TEACH", "Teaching excellence"), ("RESEARCH", "Research excellence"), ("PAPER", "Best paper")]
MEMBERSHIP_TYPES = [("LIFE", "Life member"), ("PROF", "Professional member"), ("SENIOR", "Senior member")]
CONTRIB_TYPES = [("REVIEWER", "Journal reviewer"), ("GUEST", "Guest lecture"), ("BOS", "Board of Studies member"),
                 ("PAPERSET", "Question paper setter"), ("EXAMINER", "External examiner")]
COCUR_CATS = [("HACK", "Hackathon / coding contest"), ("WORKSHOP", "Workshop / FDP")]
EXTRA_CATS = [("SPORTS", "Sports"), ("NSS", "NSS / community service"), ("CULTURAL", "Cultural")]
CONF_TYPES = [("PAPER", "Paper presentation"), ("KEYNOTE", "Keynote / invited talk"), ("ATTENDEE", "Participation")]
STAFF_NUMBERS = ["EMP002", "EMP003", "EMP004", "EMP005", "EMP006", "EMP007", "EMP008", "EMP010", "EMP011"]


class Command(BaseCommand):
    help = "Load sample staff-activity records across all staff-profile modules."

    @transaction.atomic
    def handle(self, *args, **opts):
        admin = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        inst = M("Institution").objects.order_by("pk").first()
        staff = list(M("Employee").objects.filter(employee_number__in=STAFF_NUMBERS).order_by("employee_number"))
        Assignment = M("EmployeeAssignment")
        years = M("AcademicYear").objects.order_by("pk").first()
        M("ActivityType").objects.get_or_create(
            activity_type_code="CONFERENCE_ACTIVITY",
            defaults=dict(activity_type_name="Conference activity", activity_group="CONFERENCE"))
        types = {t.activity_type_code: t for t in M("ActivityType").objects.all()}
        ver = {v.status_code: v for v in M("VerificationStatus").objects.all()}
        apr = {a.status_code: a for a in M("ApprovalStatus").objects.all()}
        research = {r.status_code: r for r in M("ResearchStatus").objects.all()}

        def get_or_create(model, key, **defaults):
            obj, _ = M(model).objects.get_or_create(**key, defaults=defaults)
            return obj

        orgs = {c: get_or_create("ExternalOrganization", {"organization_code": c}, organization_name=n) for c, n in ORGS}
        ftypes = {c: get_or_create("FundingType", {"funding_type_code": c}, funding_type_name=n) for c, n in FUNDING_TYPES}
        agencies = {}
        for code, ft in FUNDERS:
            agencies[code] = M("FundingAgency").objects.get_or_create(organization=orgs[code], funding_type=ftypes[ft])[0]
        award_cats = {c: get_or_create("AwardCategory", {"category_code": c}, category_name=n) for c, n in AWARD_CATS}
        mtypes = {c: get_or_create("MembershipType", {"type_code": c}, type_name=n) for c, n in MEMBERSHIP_TYPES}
        ctypes = {c: get_or_create("ProfessionalContributionType", {"contribution_code": c}, contribution_name=n) for c, n in CONTRIB_TYPES}
        cocats = {c: get_or_create("CoCurricularCategory", {"category_code": c}, category_name=n) for c, n in COCUR_CATS}
        excats = {c: get_or_create("ExtraCurricularCategory", {"category_code": c}, category_name=n) for c, n in EXTRA_CATS}
        conf_types = {c: get_or_create("ConferenceContributionType", {"type_code": c}, type_name=n) for c, n in CONF_TYPES}

        made = {}
        counter = [0]

        def activity(kind, title, emp, start, end=None, v="VERIFIED", a="APPROVED"):
            """Return (parent, created); skip if an activity with this title exists."""
            existing = M("StaffActivity").objects.filter(activity_title=title).first()
            if existing:
                return existing, False
            assign = Assignment.objects.filter(employee=emp, is_primary=True).select_related("department__campus").first()
            parent = M("StaffActivity").objects.create(
                employee=emp, activity_type=types[kind], academic_year=years, institution=inst,
                campus=assign.campus if assign else None, department=assign.department if assign else None,
                activity_title=title, start_date=start, end_date=end,
                verification_status=ver[v], approval_status=apr[a],
                created_by_user=admin, updated_by_user=admin,
            )
            made[kind] = made.get(kind, 0) + 1
            return parent, True

        def pick(i):
            return staff[i % len(staff)]

        # awards -----------------------------------------------------------
        for i, (name, cat, body, when, v, a) in enumerate([
            ("Best Teacher Award 2025", "TEACH", "VTU", date(2025, 9, 5), "VERIFIED", "APPROVED"),
            ("Excellence in Research Award", "RESEARCH", "KSCST", date(2025, 11, 14), "VERIFIED", "APPROVED"),
            ("Best Paper Award - ICCCNT 2026", "PAPER", "IEEE", date(2026, 7, 3), "PENDING", "SUBMITTED"),
            ("Young Faculty Recognition", "TEACH", "ISTE", date(2026, 2, 20), "PENDING", "UNDER_REVIEW"),
        ]):
            p, new = activity("AWARD_RECOGNITION", name, pick(i), when, when, v, a)
            if new:
                M("StaffAward").objects.create(staff_activity=p, award_category=award_cats[cat], awarding_organization=orgs[body],
                                               award_name=name, award_date=when, cash_prize_amount=Decimal(25000), currency_code="INR")

        # memberships -------------------------------------------------------
        for i, (body, mt, num, start, status) in enumerate([
            ("IEEE", "SENIOR", "IEEE-9921345", date(2018, 1, 1), "ACTIVE"), ("ACM", "PROF", "ACM-4402188", date(2020, 3, 1), "ACTIVE"),
            ("CSI", "LIFE", "CSI-L-18734", date(2015, 6, 1), "LIFETIME"), ("ISTE", "LIFE", "ISTE-LM-77412", date(2012, 8, 1), "LIFETIME"),
            ("IEEE", "PROF", "IEEE-8845120", date(2021, 1, 1), "EXPIRED"), ("ACM", "PROF", "ACM-5521903", date(2024, 4, 1), "ACTIVE"),
        ]):
            title = f"{body} membership - {num}"
            p, new = activity("PROFESSIONAL_MEMBERSHIP", title, pick(i + 1), start, None, "VERIFIED", "APPROVED")
            if new:
                M("StaffProfessionalMembership").objects.create(
                    staff_activity=p, organization=orgs[body], membership_type=mtypes[mt], membership_number=num,
                    membership_start_date=start, is_lifetime_membership=status == "LIFETIME",
                    membership_expiry_date=date(2025, 12, 31) if status == "EXPIRED" else None,
                    renewal_required=status == "ACTIVE", membership_status=status)

        # professional contributions ---------------------------------------
        for i, (title, ct, when, v, a) in enumerate([
            ("Reviewer - IEEE Transactions on Education", "REVIEWER", date(2026, 3, 10), "VERIFIED", "APPROVED"),
            ("Guest lecture: Cloud-native architectures", "GUEST", date(2026, 4, 18), "VERIFIED", "APPROVED"),
            ("Member, Board of Studies (CSE) - VTU", "BOS", date(2025, 12, 1), "VERIFIED", "APPROVED"),
            ("Question paper setter - Operating Systems", "PAPERSET", date(2026, 1, 12), "PENDING", "SUBMITTED"),
            ("External examiner - M.Tech viva", "EXAMINER", date(2026, 6, 25), "PENDING", "DRAFT"),
        ]):
            p, new = activity("ACADEMIC_PROFESSIONAL_CONTRIBUTION", title, pick(i + 2), when, when, v, a)
            if new:
                M("StaffProfessionalContribution").objects.create(
                    staff_activity=p, professional_contribution_type=ctypes[ct], title_topic=title, contribution_date=when)

        # conferences -------------------------------------------------------
        events = [
            ("International Conference on Computing and Networks 2026", "Bengaluru", date(2026, 7, 2), date(2026, 7, 4)),
            ("National Symposium on AI in Education", "Hubballi", date(2026, 2, 12), date(2026, 2, 13)),
            ("IEEE INDICON 2025", "Delhi", date(2025, 12, 19), date(2025, 12, 21)),
        ]
        ev = {}
        for title, city, s, e in events:
            ev[title] = M("ConferenceEvent").objects.get_or_create(conference_title=title, defaults=dict(city=city, start_date=s, end_date=e, is_active=True))[0]
        for i, (paper, evt, ct, v, a) in enumerate([
            ("Federated learning for rural healthcare analytics", events[0][0], "PAPER", "VERIFIED", "APPROVED"),
            ("Teaching algorithms with visual tools", events[1][0], "KEYNOTE", "VERIFIED", "APPROVED"),
            ("Edge caching strategies for campus networks", events[2][0], "PAPER", "PENDING", "UNDER_REVIEW"),
            ("Participation - IEEE INDICON 2025", events[2][0], "ATTENDEE", "PENDING", "SUBMITTED"),
        ]):
            e = ev[evt]
            p, new = activity("CONFERENCE_ACTIVITY", paper, pick(i), e.start_date, e.end_date, v, a)
            if new:
                M("ConferenceActivity").objects.create(staff_activity=p, conference_event=e, conference_contribution_type=conf_types[ct], paper_title=paper)

        # consultancy -------------------------------------------------------
        for i, (title, client, kind, amount, status, v, a) in enumerate([
            ("Embedded firmware audit for Bosch", "BOSCH", "CONSULTANCY", 450000, "ONGOING", "VERIFIED", "APPROVED"),
            ("Faculty upskilling programme - TCS", "TCS", "TRAINING_SERVICE", 180000, "COMPLETED", "VERIFIED", "APPROVED"),
            ("Industry sponsored project: Smart attendance", "INFOSYS", "INDUSTRY_SPONSORED_PROJECT", 750000, "APPROVED", "PENDING", "UNDER_REVIEW"),
            ("Software testing service - local startup", "TCS", "TESTING_SERVICE", 60000, "PROPOSED", "PENDING", "DRAFT"),
        ]):
            p, new = activity("CONSULTANCY_PROJECT", title, pick(i + 3), date(2026, 1 + i, 5), None, v, a)
            if new:
                M("ConsultancyProject").objects.create(
                    staff_activity=p, client_organization=orgs[client], principal_consultant_employee=p.employee,
                    consultancy_title=title, consultancy_type=kind, project_start_date=date(2026, 1 + i, 5),
                    consultancy_amount=Decimal(amount), amount_received=Decimal(amount) if status == "COMPLETED" else Decimal(0),
                    currency_code="INR", status=status)

        # research proposals + funded projects -----------------------------
        proposals = []
        for i, (title, funder, domain, amount, rs, v, a) in enumerate([
            ("Low-cost IoT sensing for precision farming", "VGST", "IoT", 1200000, "SUBMITTED", "PENDING", "SUBMITTED"),
            ("Explainable ML for student dropout prediction", "AICTE", "Machine learning", 800000, "UNDER_REVIEW", "PENDING", "UNDER_REVIEW"),
            ("Secure edge computing framework", "DST", "Security", 2500000, "APPROVED", "VERIFIED", "APPROVED"),
            ("Vernacular speech interface for e-governance", "KSCST", "NLP", 600000, "DRAFT", "PENDING", "DRAFT"),
        ]):
            p, new = activity("RESEARCH_PROPOSAL", title, pick(i), date(2026, 2, 1 + i), None, v, a)
            if new:
                assign = Assignment.objects.filter(employee=p.employee, is_primary=True).first()
                proposals.append(M("ResearchProposal").objects.create(
                    staff_activity=p, principal_investigator_employee=p.employee, department=assign.department,
                    funding_agency=agencies[funder], funding_type=agencies[funder].funding_type, research_status=research[rs],
                    proposal_title=title, research_domain=domain, proposal_submission_date=date(2026, 2, 1 + i),
                    requested_amount=Decimal(amount), currency_code="INR"))
        for i, (title, funder, req, san, rec, used, rs, v, a) in enumerate([
            ("Smart campus energy analytics", "DST", 1500000, 1350000, 900000, 640000, "ONGOING", "VERIFIED", "APPROVED"),
            ("Assistive reading tool for low-vision learners", "AICTE", 700000, 650000, 650000, 612000, "COMPLETED", "VERIFIED", "APPROVED"),
            ("Industry 4.0 testbed for MSME", "INFOSYS", 2000000, 1800000, 600000, 150000, "SANCTIONED", "PENDING", "UNDER_REVIEW"),
        ]):
            p, new = activity("FUNDED_RESEARCH_PROJECT", title, pick(i + 4), date(2025, 9, 1), None, v, a)
            if new:
                assign = Assignment.objects.filter(employee=p.employee, is_primary=True).first()
                M("FundedResearchProject").objects.create(
                    staff_activity=p, project_title=title, principal_investigator_employee=p.employee, department=assign.department,
                    funding_agency=agencies[funder], funding_type=agencies[funder].funding_type, requested_amount=Decimal(req),
                    sanctioned_amount=Decimal(san), amount_received=Decimal(rec), amount_utilized=Decimal(used), currency_code="INR",
                    sanction_date=date(2025, 8, 15), sanction_order_number=f"SO/{2025}/{100 + i}", project_start_date=date(2025, 9, 1),
                    research_status=research[rs])

        # internships ------------------------------------------------------
        for i, (title, org, domain, v, a) in enumerate([
            ("Faculty internship - cloud platforms at Infosys", "INFOSYS", "Cloud computing", "VERIFIED", "APPROVED"),
            ("Industry immersion - embedded systems at Bosch", "BOSCH", "Embedded systems", "VERIFIED", "APPROVED"),
            ("Summer internship - data engineering at TCS", "TCS", "Data engineering", "PENDING", "SUBMITTED"),
        ]):
            p, new = activity("FACULTY_INTERNSHIP", title, pick(i + 5), date(2026, 5, 15), date(2026, 6, 15), v, a)
            if new:
                M("FacultyInternship").objects.create(staff_activity=p, organization=orgs[org], internship_title=title,
                                                      internship_domain=domain, stipend_incentive_type="NONE", currency_code="INR")

        # co-curricular and extra-curricular --------------------------------
        for i, (name, cat, when, v, a) in enumerate([
            ("Faculty mentor - Smart India Hackathon", "HACK", date(2025, 12, 10), "VERIFIED", "APPROVED"),
            ("Coordinator - FDP on modern pedagogy", "WORKSHOP", date(2026, 1, 20), "VERIFIED", "APPROVED"),
            ("Judge - inter-college coding contest", "HACK", date(2026, 3, 8), "PENDING", "SUBMITTED"),
        ]):
            p, new = activity("CO_CURRICULAR", name, pick(i + 1), when, when, v, a)
            if new:
                M("CocurricularActivity").objects.create(staff_activity=p, cocurricular_category=cocats[cat], event_name=name, event_date=when)
        for i, (name, cat, when, v, a) in enumerate([
            ("Staff cricket tournament - runners up", "SPORTS", date(2026, 1, 26), "VERIFIED", "APPROVED"),
            ("NSS village adoption camp", "NSS", date(2026, 2, 14), "VERIFIED", "APPROVED"),
            ("Annual day cultural coordinator", "CULTURAL", date(2026, 3, 30), "PENDING", "DRAFT"),
        ]):
            p, new = activity("EXTRA_CURRICULAR", name, pick(i + 6), when, when, v, a)
            if new:
                M("ExtracurricularActivity").objects.create(staff_activity=p, extracurricular_category=excats[cat], event_name=name, event_date=when)

        self.stdout.write(self.style.SUCCESS(f"Staff activities added: {made}"))
