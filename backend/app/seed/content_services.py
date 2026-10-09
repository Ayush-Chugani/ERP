"""Demo content for the non-academic services (communication, grievances, certificates, admissions, documents,
family records, feedback, registration policy, staff research records, staff HR extras and the alumni / applicant journeys).

``ensure_service_content(db)`` is idempotent: every insert is guarded by a natural key (a number, a title, an e-mail ...), so
running it again adds nothing. It returns ``{table: rows_added}`` for the rows it really inserted. It only uses raw SQL, relies
on the personas created by :mod:`app.seed.demo` (looked up by user name, never by id) and skips any block whose prerequisites are
missing, so it is safe on a partially seeded database. Demo / evaluation use only.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session


class _Ctx:
    """Lookups shared by the sections plus a running tally of inserted rows."""

    def __init__(self, db: Session):
        self.db = db
        self.counts: dict[str, int] = {}
        self.now = datetime.now(UTC)
        self.users: dict[str, int] = dict(db.execute(text("SELECT username, user_id FROM user_account")).all())
        self.actor = (self.users.get("demoadmin") or self.users.get("registrar") or self.users.get("sysadmin")
                      or db.execute(text("SELECT min(user_id) FROM user_account")).scalar())
        self.inst = db.execute(text("SELECT institution_id FROM institution ORDER BY institution_id LIMIT 1")).scalar()
        self.dept = db.execute(text("SELECT a.department_id FROM user_role_assignment a JOIN user_account u USING (user_id) "
                                    "WHERE a.scope_type = 'DEPARTMENT' AND a.department_id IS NOT NULL "
                                    "ORDER BY (u.username = 'hod') DESC, a.department_id LIMIT 1")).scalar()
        # persona -> student / employee through person_account_link
        self.student: dict[str, int] = {}
        self.employee: dict[str, int] = {}
        for uname, sid, eid in db.execute(text("SELECT u.username, l.student_id, l.employee_id FROM person_account_link l "
                                               "JOIN user_account u USING (user_id)")):
            if sid:
                self.student[uname] = sid
            if eid:
                self.employee[uname] = eid
        taken = set(self.student.values())
        extra = [s for (s,) in db.execute(text("SELECT student_id FROM student WHERE student_status = 'ACTIVE' ORDER BY student_id"))
                 if s not in taken]
        for i, sid in enumerate(extra[:8], start=1):
            self.student[f"o{i}"] = sid

    def ago(self, days: float = 0, hours: float = 0) -> datetime:
        return self.now - timedelta(days=days, hours=hours)

    def run(self, table: str, sql: str, **params) -> int:
        n = self.db.execute(text(sql), params).rowcount or 0
        if n > 0:
            self.counts[table] = self.counts.get(table, 0) + n
        return n


# ------------------------------------------------------------------------------------------------ communication
ANNOUNCEMENTS = [
    # title, body, type, status, audience, department?, publish_from days ago, publish_to days ahead
    ("Mid-semester examination timetable released", "The mid-semester examination timetable is available on the portal. "
     "Check your hall ticket and report 15 minutes early.", "EXAMINATION", "APPROVED", "STUDENTS", False, 3, None),
    ("Faculty development programme on outcome-based education", "A two-day workshop for all teaching staff on outcome-based "
     "curriculum design, hosted by the academic council.", "EVENT", "APPROVED", "STAFF", False, 4, 20),
    ("Campus Wi-Fi maintenance on Saturday", "Wireless access will be unavailable between 10:00 and 14:00 on Saturday "
     "for a scheduled upgrade.", "GENERAL", "APPROVED", "ALL", False, 2, 10),
    ("Department seminar: trends in machine learning", "An invited talk for the department on practical machine learning, "
     "open to staff and students.", "EVENT", "APPROVED", "DEPARTMENT", True, 1, 14),
    ("Scholarship applications close next week", "Students applying for the merit scholarship must submit documents to the "
     "student section before the deadline.", "GENERAL", "APPROVED", "STUDENTS", False, 5, 7),
    ("Library membership renewal drive", "Staff and students may renew library membership at the front desk.", "GENERAL",
     "APPROVED", "ALL", False, 6, None),
    ("Revised attendance policy for the new term", "Draft circular describing the minimum attendance rules, awaiting "
     "approval from the dean.", "GENERAL", "PENDING", "ALL", False, 0, None),
    ("Annual technical fest - volunteer registration", "Students may register as volunteers for the annual technical fest.",
     "EVENT", "PENDING", "STUDENTS", False, 0, None),
    ("Staff appraisal submission reminder", "All staff must complete their annual research and service records before "
     "the review committee meets.", "GENERAL", "PENDING", "STAFF", False, 0, None),
    ("Lab maintenance schedule for the department", "Laboratories will be closed on alternate afternoons this week for equipment "
     "servicing; sessions are rescheduled in the timetable.", "GENERAL", "APPROVED", "DEPARTMENT", True, 2, 12),
    ("Department project exhibition - call for entries", "Faculty guides may nominate final-year projects for the department "
     "exhibition.", "EVENT", "PENDING", "DEPARTMENT", True, 0, None),
    ("Alumni meet planning note", "Internal draft: plan for the alumni meet, venue and speakers to be decided.", "EVENT",
     "DRAFT", "ALL", False, 0, None),
    ("Exam seating arrangement (draft)", "Draft seating plan for the end-semester examinations.", "EXAMINATION", "DRAFT",
     "STUDENTS", False, 0, None),
    ("Last year's convocation notice", "Convocation notice for the previous academic year.", "GENERAL", "ARCHIVED", "ALL",
     False, 120, None),
]


def _announcements(c: _Ctx) -> None:
    for title, body, atype, status, audience, dept, ago, ahead in ANNOUNCEMENTS:
        c.run("announcement",
              "INSERT INTO announcement (announcement_type_id, department_id, title, description, publish_from, publish_to, "
              "approval_status, audience_type, institution_id) "
              "SELECT t.announcement_type_id, CAST(:d AS int), CAST(:title AS varchar), CAST(:body AS text), CAST(:pf AS timestamptz), "
              "CAST(:pt AS timestamptz), CAST(:st AS varchar), CAST(:aud AS varchar), CAST(:i AS int) FROM announcement_type t "
              "WHERE t.type_code = :tc AND CAST(:i AS int) IS NOT NULL AND NOT EXISTS (SELECT 1 FROM announcement a WHERE a.title = :title)",
              d=c.dept if dept else None, title=title, body=body, pf=c.ago(days=ago, hours=1),
              pt=(c.now + timedelta(days=ahead)) if ahead else None, st=status, aud=audience, tc=atype, i=c.inst)


def _notifications(c: _Ctx) -> None:
    role_of = {u: [r for (r,) in c.db.execute(text(
        "SELECT r.role_code FROM user_role_assignment a JOIN role r USING (role_id) WHERE a.user_id = :u"), {"u": uid})]
        for u, uid in c.users.items()}
    by_role = {
        "STUDENT": [("Your grievance has been assigned", "The grievance cell has picked up your request.", "/r/support/grievance"),
                    ("Certificate request update", "Check the status of your certificate requests.", "/r/documents/certificate-request"),
                    ("Feedback cycle open", "Share your feedback on this semester's courses.", "/feedback")],
        "PARENT_GUARDIAN": [("Progress update available", "Your ward's attendance and results are available.", "/r/student/student")],
        "ALUMNI": [("Your certificate has been issued", "Your requested certificate is ready for download.", "/r/documents/certificate-request")],
        "APPLICANT": [("Your application is under review", "The admissions office is reviewing your application.", "/r/admissions/admission-application"),
                      ("Upload pending documents", "Some of your documents are awaiting verification.", "/r/documents/student-document")],
        "GRIEVANCE_OFFICER": [("New grievances awaiting assignment", "Open grievances need your attention.", "/r/support/grievance")],
        "REGISTRAR": [("Certificate requests awaiting review", "Review and approve pending certificate requests.", "/r/documents/certificate-request"),
                      ("Announcements awaiting approval", "Pending announcements need approval.", "/r/communication/announcement")],
        "ADMISSION_OFFICER": [("Applications awaiting review", "New admission applications were submitted.", "/r/admissions/admission-application")],
        "DOCUMENT_VERIFIER": [("Documents awaiting verification", "Student documents are waiting in your queue.", "/r/documents/student-document")],
        "FINANCE_OFFICER": [("Fee clearances pending", "Selected applicants are awaiting fee clearance.", "/r/admissions/admission-fee-clearance")],
        "HEAD_DEPARTMENT": [("Research records awaiting review", "Staff activities were submitted for verification.", "/r/staff-activities/staff-activity")],
        "DEAN_ACADEMICS": [("Research records awaiting approval", "Verified staff activities need approval.", "/r/staff-activities/staff-activity")],
        "VICE_CHANCELLOR": [("Quarterly review pack ready", "Institution-wide summaries are available.", "/r/staff-activities/staff-activity")],
        "FACULTY": [("Faculty meeting on Friday", "Meeting at 3 PM in the conference room.", "/r/communication/announcement")],
    }
    for uname, uid in c.users.items():
        items = [("Welcome to the campus portal", "Your account is ready. Explore the menu to get started.", "/", 6)]
        for role in role_of.get(uname, []):
            items += [(t, b, link, 1) for (t, b, link) in by_role.get(role, [])]
        for idx, (title, body, link, days) in enumerate(items):
            c.run("notification",
                  "INSERT INTO notification (user_id, title, body, link, created_at, read_at) "
                  "SELECT CAST(:u AS bigint), CAST(:t AS varchar), CAST(:b AS varchar), CAST(:l AS varchar), CAST(:ca AS timestamptz), "
                  "CAST(:ra AS timestamptz) WHERE NOT EXISTS (SELECT 1 FROM notification n WHERE n.user_id = :u AND n.title = :t)",
                  u=uid, t=title, b=body, l=link, ca=c.ago(days=days, hours=idx), ra=c.ago(days=days - 1) if idx == 0 else None)


# ---------------------------------------------------------------------------------------------------- grievances
GRIEVANCE_CATEGORIES = [("INFRA", "Campus facilities"), ("TEACHING", "Teaching and faculty"), ("PLACEMENT", "Placement and internships"),
                        ("IT", "IT services and Wi-Fi")]
# number, student key, category, department?, subject, priority, status, resolution, days ago
GRIEVANCES = [
    ("GR-26-D001", "student", "LIBRARY", False, "Reference books unavailable in the library", "NORMAL", "SUBMITTED", None, 1),
    ("GR-26-D002", "student", "FEES", False, "Scholarship amount not reflected in fee ledger", "HIGH", "UNDER_REVIEW", None, 6),
    ("GR-26-D003", "student", "TRANSPORT", False, "Bus route 4 is overcrowded in the mornings", "LOW", "RESOLVED",
     "An additional bus has been added on route 4 from this week.", 20),
    ("GR-26-D004", "student", "EXAM", False, "Internal marks missing for one lab course", "URGENT", "REJECTED",
     "Marks were entered correctly; please contact the course instructor for the re-evaluation form.", 15),
    ("GR-26-D005", "student2", "HOSTEL", False, "Hot water not available in block B", "HIGH", "SUBMITTED", None, 2),
    ("GR-26-D006", "student2", "ACADEMIC", True, "Timetable clash between elective and lab session", "NORMAL", "ASSIGNED", None, 5),
    ("GR-26-D007", "student2", "IT", False, "Cannot log in to the learning portal", "NORMAL", "UNDER_REVIEW", None, 8),
    ("GR-26-D008", "student2", "INFRA", False, "Classroom projector not working in room 204", "LOW", "RESOLVED",
     "The projector lamp was replaced.", 25),
    ("GR-26-D009", "student2", "LIBRARY", False, "Late fee charged despite timely return", "NORMAL", "CLOSED",
     "Fine reversed and ledger corrected.", 40),
    ("GR-26-D010", "parent", "FEES", False, "Receipt for last term fee not received", "NORMAL", "ASSIGNED", None, 4),
    ("GR-26-D011", "parent", "TRANSPORT", False, "Request to change pick-up point", "LOW", "RESOLVED", "Pick-up point updated.", 18),
    ("GR-26-D012", "alumni", "EXAM", False, "Transcript shows incorrect grade for one course", "HIGH", "RESOLVED",
     "The grade was corrected after verification by the examination office.", 30),
    ("GR-26-D013", "o1", "TEACHING", True, "Lectures frequently cancelled without notice", "NORMAL", "SUBMITTED", None, 3),
    ("GR-26-D014", "o2", "PLACEMENT", False, "Placement training schedule overlaps with classes", "NORMAL", "ASSIGNED", None, 7),
    ("GR-26-D015", "o3", "ACADEMIC", False, "Request for revaluation process clarification", "LOW", "UNDER_REVIEW", None, 9),
    ("GR-26-D016", "o4", "HOSTEL", False, "Mess food quality complaint", "HIGH", "RESOLVED", "Caterer changed and menu reviewed.", 35),
]
ACTION_CHAIN = {
    "SUBMITTED": [("SUBMITTED", "SUBMITTED", "Grievance submitted.")],
    "ASSIGNED": [("SUBMITTED", "SUBMITTED", "Grievance submitted."), ("ASSIGNED", "ASSIGNED", "Assigned to the grievance cell.")],
    "UNDER_REVIEW": [("SUBMITTED", "SUBMITTED", "Grievance submitted."), ("ASSIGNED", "ASSIGNED", "Assigned to the grievance cell."),
                     ("REVIEW_STARTED", "UNDER_REVIEW", "Review started.")],
    "RESOLVED": [("SUBMITTED", "SUBMITTED", "Grievance submitted."), ("ASSIGNED", "ASSIGNED", "Assigned to the grievance cell."),
                 ("RESOLVED", "RESOLVED", "Resolution recorded.")],
    "REJECTED": [("SUBMITTED", "SUBMITTED", "Grievance submitted."), ("REJECTED", "REJECTED", "Grievance rejected with remarks.")],
    "CLOSED": [("SUBMITTED", "SUBMITTED", "Grievance submitted."), ("RESOLVED", "RESOLVED", "Resolution recorded."),
               ("CLOSED", "CLOSED", "Closed after the student confirmed.")],
}


def _grievances(c: _Ctx) -> None:
    for code, name in GRIEVANCE_CATEGORIES:
        c.run("grievance_category",
              "INSERT INTO grievance_category (category_code, category_name, is_active) SELECT CAST(:c AS varchar), CAST(:n AS varchar), true "
              "WHERE NOT EXISTS (SELECT 1 FROM grievance_category WHERE category_code = :c OR category_name = :n)", c=code, n=name)
    for number, who, cat, dept, subject, prio, status, resolution, days in GRIEVANCES:
        sid = c.student.get(who)
        if sid is None:
            continue
        done = status in ("RESOLVED", "CLOSED", "REJECTED")
        c.run("grievance",
              "INSERT INTO grievance (grievance_number, student_id, grievance_category_id, department_id, submitted_at, subject, "
              "description, priority, status, resolved_at, resolution) "
              "SELECT CAST(:n AS varchar), CAST(:s AS bigint), g.grievance_category_id, CAST(:d AS int), CAST(:sa AS timestamptz), "
              "CAST(:subj AS varchar), CAST(:desc AS text), CAST(:p AS varchar), CAST(:st AS varchar), CAST(:ra AS timestamptz), CAST(:res AS text) FROM grievance_category g "
              "WHERE g.category_code = :cat AND NOT EXISTS (SELECT 1 FROM grievance WHERE grievance_number = :n)",
              n=number, s=sid, d=c.dept if dept else None, sa=c.ago(days=days), subj=subject,
              desc=f"{subject}. Raised through the student portal; please look into this at the earliest.", p=prio, st=status,
              ra=c.ago(days=max(days - 3, 0)) if done else None, res=resolution, cat=cat)
        for k, (action, new_status, note) in enumerate(ACTION_CHAIN[status]):
            c.run("grievance_action",
                  "INSERT INTO grievance_action (grievance_id, action_at, action_type, action_notes, new_status) "
                  "SELECT g.grievance_id, CAST(:at AS timestamptz), CAST(:a AS varchar), CAST(:note AS text), CAST(:ns AS varchar) FROM grievance g WHERE g.grievance_number = :n "
                  "AND NOT EXISTS (SELECT 1 FROM grievance_action x WHERE x.grievance_id = g.grievance_id AND x.action_type = :a)",
                  n=number, at=c.ago(days=days) + timedelta(hours=k * 5), a=action, note=note, ns=new_status)


# ------------------------------------------------------------------------------------------------------ certificates
# number, student key, type code, status, purpose, days ago, certificate number
CERTIFICATES = [
    ("SIMSR26D001", "student", "BONAFIDE", "UNDER_REVIEW", "Bank education loan", 3, None),
    ("SIMSR26D002", "student", "CONDUCT", "APPROVED", "Passport application", 9, None),
    ("SIMSR26D003", "student", "FEE", "ISSUED", "Scholarship claim", 25, "CERT/2026/D001"),
    ("SIMSR26D004", "student", "NOC", "REJECTED", "Internship outside the city", 14, None),
    ("SIMSR26D005", "student2", "BONAFIDE", "SUBMITTED", "Travel concession", 1, None),
    ("SIMSR26D006", "student2", "TRANSCRIPT", "UNDER_REVIEW", "Higher studies application", 5, None),
    ("SIMSR26D007", "student2", "CONDUCT", "APPROVED", "Visa application", 10, None),
    ("SIMSR26D008", "student2", "FEE", "ISSUED", "Employer reimbursement", 22, "CERT/2026/D002"),
    ("SIMSR26D009", "student2", "NOC", "REJECTED", "Research internship abroad", 12, None),
    ("SIMSR26D010", "parent", "BONAFIDE", "SUBMITTED", "Insurance claim for ward", 2, None),
    ("SIMSR26D011", "parent", "FEE", "ISSUED", "Income tax rebate", 20, "CERT/2026/D003"),
    ("SIMSR26D012", "alumni", "TRANSCRIPT", "ISSUED", "Master's admission abroad", 28, "CERT/2026/D004"),
    ("SIMSR26D013", "alumni", "CONDUCT", "ISSUED", "Employer background verification", 26, "CERT/2026/D005"),
    ("SIMSR26D014", "alumni", "BONAFIDE", "SUBMITTED", "Alumni association membership", 2, None),
    ("SIMSR26D015", "applicant", "BONAFIDE", "CANCELLED", "Entrance counselling", 15, None),
    ("SIMSR26D016", "o1", "TRANSCRIPT", "UNDER_REVIEW", "Scholarship renewal", 4, None),
    ("SIMSR26D017", "o2", "BONAFIDE", "APPROVED", "Bank account opening", 7, None),
    ("SIMSR26D018", "o3", "NOC", "SUBMITTED", "Summer internship", 1, None),
]


def _certificates(c: _Ctx) -> None:
    for number, who, ctype, status, purpose, days, cert_no in CERTIFICATES:
        sid = c.student.get(who)
        if sid is None:
            continue
        c.run("certificate_request",
              "INSERT INTO certificate_request (request_number, student_id, certificate_type_id, requested_at, purpose, request_status, "
              "issued_at, certificate_number) "
              "SELECT CAST(:n AS varchar), CAST(:s AS bigint), t.certificate_type_id, CAST(:ra AS timestamptz), CAST(:p AS varchar), "
              "CAST(:st AS varchar), CAST(:ia AS timestamptz), CAST(:cn AS varchar) FROM certificate_type t "
              "WHERE t.certificate_code = :tc AND NOT EXISTS (SELECT 1 FROM certificate_request WHERE request_number = :n) "
              "AND (CAST(:cn AS varchar) IS NULL OR NOT EXISTS (SELECT 1 FROM certificate_request WHERE certificate_number = :cn))",
              n=number, s=sid, ra=c.ago(days=days), p=purpose, st=status, tc=ctype, cn=cert_no,
              ia=c.ago(days=max(days - 4, 0)) if status == "ISSUED" else None)


# ------------------------------------------------------------------------------------------------------- documents
DOCUMENT_TYPES = [("SSLC_MARKS", "SSLC marks card", True), ("PUC_MARKS", "PUC / Class 12 marks card", True),
                  ("AADHAAR", "Aadhaar card", True), ("TRANSFER_CERT", "Transfer certificate", True),
                  ("CASTE_CERT", "Caste certificate", True), ("PHOTO", "Passport photograph", False)]
# student key, document code, status, remarks, days ago
STUDENT_DOCUMENTS = [
    ("student", "SSLC_MARKS", "VERIFIED", "Original sighted by the section officer.", 40),
    ("student", "PUC_MARKS", "VERIFIED", None, 40),
    ("student", "AADHAAR", "PENDING", None, 2),
    ("student", "TRANSFER_CERT", "REJECTED", "The scan is unreadable; please upload a clear copy.", 12),
    ("student2", "SSLC_MARKS", "VERIFIED", None, 38),
    ("student2", "PUC_MARKS", "PENDING", None, 3),
    ("student2", "AADHAAR", "PENDING", None, 1),
    ("student2", "CASTE_CERT", "REJECTED", "Certificate is older than the permitted validity.", 10),
    ("parent", "SSLC_MARKS", "PENDING", None, 4),
    ("parent", "AADHAAR", "VERIFIED", None, 30),
    ("alumni", "SSLC_MARKS", "VERIFIED", None, 400),
    ("alumni", "PUC_MARKS", "VERIFIED", None, 400),
    ("alumni", "TRANSFER_CERT", "VERIFIED", None, 400),
    ("applicant", "SSLC_MARKS", "PENDING", None, 3),
    ("applicant", "PUC_MARKS", "PENDING", None, 3),
    ("applicant", "AADHAAR", "VERIFIED", None, 6),
    ("applicant", "TRANSFER_CERT", "REJECTED", "Name on the document does not match the application.", 5),
    ("o1", "SSLC_MARKS", "PENDING", None, 2),
    ("o1", "PUC_MARKS", "VERIFIED", None, 20),
    ("o2", "AADHAAR", "REJECTED", "Photograph not visible.", 9),
    ("o2", "SSLC_MARKS", "PENDING", None, 1),
    ("o3", "CASTE_CERT", "EXPIRED", "Validity ended; renewal required.", 90),
    ("o3", "AADHAAR", "PENDING", None, 2),
    ("o4", "PUC_MARKS", "PENDING", None, 5),
]


def _documents(c: _Ctx) -> None:
    for code, name, verify in DOCUMENT_TYPES:
        c.run("document_type",
              "INSERT INTO document_type (document_code, document_name, requires_verification, is_active) "
              "SELECT CAST(:c AS varchar), CAST(:n AS varchar), CAST(:v AS boolean), true "
              "WHERE NOT EXISTS (SELECT 1 FROM document_type WHERE document_code = :c OR document_name = :n)", c=code, n=name, v=verify)
    for who, code, status, remarks, days in STUDENT_DOCUMENTS:
        sid = c.student.get(who)
        if sid is None:
            continue
        key = f"demo/student-documents/{sid}-{code.lower()}.pdf"
        owner = c.users.get(who) or c.actor
        c.run("file_object",
              "INSERT INTO file_object (storage_provider, storage_key, original_file_name, mime_type, file_size_bytes, stored_file_name, "
              "file_extension, confidentiality_level, is_encrypted, uploaded_by_user_id) "
              "SELECT 'local', CAST(:k AS varchar), CAST(:fn AS varchar), 'application/pdf', 48213, CAST(:fn AS varchar), 'pdf', "
              "'CONFIDENTIAL', false, CAST(:u AS bigint) WHERE EXISTS (SELECT 1 FROM document_type WHERE document_code = :c) "
              "AND NOT EXISTS (SELECT 1 FROM file_object WHERE storage_key = :k)",
              k=key, fn=f"{code.lower()}.pdf", u=owner, c=code)
        c.run("student_document",
              "INSERT INTO student_document (student_id, document_type_id, file_object_id, document_number, issue_date, expiry_date, "
              "verification_status, verified_at, remarks) "
              "SELECT CAST(:s AS bigint), d.document_type_id, f.file_object_id, CAST(:num AS varchar), CAST(:iss AS date), "
              "CAST(:exp AS date), CAST(:st AS varchar), CAST(:va AS timestamptz), CAST(:r AS varchar) "
              "FROM document_type d JOIN file_object f ON f.storage_key = :k WHERE d.document_code = :c "
              "AND NOT EXISTS (SELECT 1 FROM student_document x WHERE x.student_id = :s AND x.document_type_id = d.document_type_id)",
              s=sid, num=f"DEMO-{code}-{sid}", iss=(c.now - timedelta(days=days + 365)).date(),
              exp=(c.now - timedelta(days=5)).date() if status == "EXPIRED" else None, st=status,
              va=c.ago(days=max(days - 2, 0)) if status in ("VERIFIED", "REJECTED") else None, r=remarks, k=key, c=code)


# ----------------------------------------------------------------------------------------------------- admissions
# number, first, last, programme, status, eligibility, clearance reference, days ago
NEW_APPLICATIONS = [
    ("APP-26-D001", "Ananya", "Rao", 4, "SUBMITTED", "PENDING", None, 2),
    ("APP-26-D002", "Rohit", "Verma", 4, "UNDER_REVIEW", "PENDING", None, 6),
    ("APP-26-D003", "Sneha", "Patil", 5, "ELIGIBLE", "ELIGIBLE", None, 9),
    ("APP-26-D004", "Kiran", "Joshi", 4, "SELECTED", "ELIGIBLE", "RCPT-D001", 14),
    ("APP-26-D005", "Divya", "Hegde", 9, "SELECTED", "ELIGIBLE", None, 12),
    ("APP-26-D006", "Manoj", "Kulkarni", 3, "SELECTED", "ELIGIBLE", "RCPT-D002", 16),
    ("APP-26-D007", "Farhan", "Qureshi", 6, "INELIGIBLE", "INELIGIBLE", None, 8),
    ("APP-26-D008", "Lakshmi", "Bhat", 7, "REJECTED", "ELIGIBLE", None, 18),
    ("APP-26-D009", "Tejas", "Naik", 4, "WAITLISTED", "ELIGIBLE", None, 11),
    ("APP-26-D010", "Pooja", "Shetty", 5, "DRAFT", "PENDING", None, 1),
    ("APP-26-D011", "Varun", "Gokhale", 4, "SELECTED", "ELIGIBLE", "RCPT-D003", 20),
]


def _application(c: _Ctx, number: str, by_email: str | None, by_student: int | None, prog: int, status: str, elig: str, reviewer, days: int,
                 k: int) -> None:
    c.run("admission_application",
          "INSERT INTO admission_application (application_number, application_date, application_status, eligibility_status, remarks, "
          "academic_year_id, admission_applicant_id, admission_category_id, created_by_id, updated_by_id, programme_id, reviewer_id) "
          "SELECT CAST(:n AS varchar), CAST(:d AS date), CAST(:st AS varchar), CAST(:el AS varchar), CAST(:rm AS text), "
          "(SELECT academic_year_id FROM academic_year ORDER BY academic_year_id LIMIT 1), ap.admission_applicant_id, "
          "(SELECT admission_category_id FROM admission_category ORDER BY admission_category_id OFFSET :k LIMIT 1), CAST(:u AS bigint), "
          "CAST(:u AS bigint), p.programme_id, CAST(:rv AS bigint) "
          "FROM admission_applicant ap, programme p WHERE ((CAST(:by_email AS varchar) IS NOT NULL AND ap.primary_email = :by_email) "
          "OR (CAST(:by_student AS bigint) IS NOT NULL AND ap.canonical_student_id = :by_student)) AND p.programme_id = :pr "
          "AND NOT EXISTS (SELECT 1 FROM admission_application WHERE application_number = :n) "
          "ORDER BY ap.admission_applicant_id DESC LIMIT 1",
          n=number, d=(c.now - timedelta(days=days)).date(), st=status, el=elig, k=k,
          rm="Documents under verification." if status in ("UNDER_REVIEW", "SUBMITTED") else
          "Ineligible: aggregate below the cut-off." if status == "INELIGIBLE" else None,
          u=c.actor, pr=prog, rv=reviewer if status not in ("SUBMITTED", "DRAFT") else None, by_email=by_email, by_student=by_student)


def _admissions(c: _Ctx) -> None:
    reviewer = c.users.get("admissions") or c.actor
    for i, (number, first, last, prog, status, elig, receipt, days) in enumerate(NEW_APPLICATIONS):
        email = f"{first.lower()}.{last.lower()}@applicants.example.edu"
        c.run("admission_applicant",
              "INSERT INTO admission_applicant (first_name, last_name, display_name, date_of_birth, primary_email, primary_phone, "
              "created_by_id, updated_by_id, institution_id, nationality_country_id) "
              "SELECT CAST(:f AS varchar), CAST(:l AS varchar), CAST(:dn AS varchar), CAST(:dob AS date), CAST(:e AS varchar), "
              "CAST(:ph AS varchar), CAST(:u AS bigint), CAST(:u AS bigint), CAST(:i AS int), (SELECT min(country_id) FROM country) "
              "WHERE CAST(:i AS int) IS NOT NULL AND NOT EXISTS (SELECT 1 FROM admission_applicant WHERE primary_email = :e)",
              f=first, l=last, dn=f"{first} {last}", dob=datetime(2007, 1 + i % 12, 5 + i, tzinfo=UTC).date(), e=email,
              ph=f"+9198000{10000 + i}", u=c.actor, i=c.inst)
        _application(c, number, email, None, prog, status, elig, reviewer, days, i)
        if receipt:
            c.run("admission_fee_clearance",
                  "INSERT INTO admission_fee_clearance (reference, recorded_at, application_version, actor_id, application_id) "
                  "SELECT CAST(:r AS varchar), CAST(:at AS timestamptz), a.version, CAST(:u AS bigint), a.application_id "
                  "FROM admission_application a WHERE a.application_number = :n "
                  "AND NOT EXISTS (SELECT 1 FROM admission_fee_clearance x WHERE x.application_id = a.application_id)",
                  r=receipt, at=c.ago(days=max(days - 3, 0)), u=c.users.get("finance") or c.actor, n=number)
    # the applicant persona: open applications beside the (already admitted) historical one
    sid = c.student.get("applicant")
    if sid is not None:
        _application(c, "APP-26-D012", None, sid, 4, "UNDER_REVIEW", "PENDING", reviewer, 7, 2)
        _application(c, "APP-26-D013", None, sid, 5, "SUBMITTED", "PENDING", None, 3, 3)


# ----------------------------------------------------------------------------------------- family and background
def _family(c: _Ctx) -> None:
    c.run("student_parent_guardian",
          "INSERT INTO student_parent_guardian (relationship_type, full_name, occupation, annual_income, email, phone, city, "
          "is_primary_contact, country_id, state_id, student_id) "
          "SELECT 'FATHER', 'Mr. ' || s.first_name || ' ' || coalesce(s.last_name, '') || ' Sr.', 'Businessman', 600000 + s.student_id * 1000, "
          "'father' || s.student_id || '@parents.example.edu', '+91981000' || lpad((s.student_id % 10000)::text, 4, '0'), 'Hubballi', true, "
          "(SELECT min(country_id) FROM country), (SELECT min(state_id) FROM state WHERE state_name = 'Karnataka'), s.student_id "
          "FROM student s WHERE NOT EXISTS (SELECT 1 FROM student_parent_guardian g WHERE g.student_id = s.student_id)")
    c.run("student_address",
          "INSERT INTO student_address (address_type, address_line_1, city, postal_code, is_primary, country_id, state_id, student_id) "
          "SELECT 'PERMANENT', '12, Vidyanagar Main Road', 'Hubballi', '580031', true, (SELECT min(country_id) FROM country), "
          "(SELECT min(state_id) FROM state WHERE state_name = 'Karnataka'), s.student_id FROM student s "
          "WHERE (SELECT min(country_id) FROM country) IS NOT NULL "
          "AND NOT EXISTS (SELECT 1 FROM student_address a WHERE a.student_id = s.student_id)")
    c.run("student_residence",
          "INSERT INTO student_residence (residence_type, hostel_name, room_number, start_date, is_current, student_id) "
          "SELECT CASE s.student_id % 3 WHEN 0 THEN 'HOSTEL' WHEN 1 THEN 'DAY_SCHOLAR' ELSE 'PG' END, "
          "CASE WHEN s.student_id % 3 = 0 THEN 'Bhagirathi Hostel' END, CASE WHEN s.student_id % 3 = 0 THEN 'B-' || (100 + s.student_id % 40) END, "
          "coalesce(s.admission_date, DATE '2025-08-01'), true, s.student_id FROM student s "
          "WHERE NOT EXISTS (SELECT 1 FROM student_residence r WHERE r.student_id = s.student_id)")
    for level, exam, maxm, year_back in (("SSLC", "SSLC (Class 10)", 625, 6), ("PUC_II", "II PUC (Class 12)", 600, 4)):
        c.run("student_previous_education",
              "INSERT INTO student_previous_education (qualification_level, examination_name, institution_name, board_university, "
              "registration_number, month_of_passing, year_of_passing, result_class, marks_obtained, maximum_marks, percentage, student_id) "
              "SELECT CAST(:lv AS varchar), CAST(:ex AS varchar), CASE WHEN CAST(:lv AS varchar) = 'SSLC' THEN 'Government High School, Dharwad' "
              "ELSE 'Vidyaniketan PU College, Hubballi' END, 'Karnataka Secondary Education Board', CAST(:lv AS varchar) || '-' || s.student_id, "
              "CASE WHEN CAST(:lv AS varchar) = 'SSLC' THEN 3 ELSE 4 END, CAST(extract(year FROM now()) AS int) - :yb, "
              "'First class with distinction', round((70 + (s.student_id * 7) % 29) * CAST(:mx AS numeric) / 100), CAST(:mx AS numeric), "
              "70 + (s.student_id * 7) % 29, s.student_id "
              "FROM student s WHERE NOT EXISTS (SELECT 1 FROM student_previous_education e WHERE e.student_id = s.student_id "
              "AND e.qualification_level = CAST(:lv AS varchar))", lv=level, ex=exam, mx=maxm, yb=year_back)
    c.run("registration_policy",
          "INSERT INTO registration_policy (programme_id, minimum_credits, maximum_credits, version, updated_by_id) "
          "SELECT p.programme_id, 16, 26, 0, CAST(:u AS bigint) FROM programme p "
          "WHERE NOT EXISTS (SELECT 1 FROM registration_policy r WHERE r.programme_id = p.programme_id)", u=c.actor)


# ------------------------------------------------------------------------------------------- alumni and applicant
def _alumni_and_applicant(c: _Ctx) -> None:
    sid = c.student.get("alumni")
    if sid is not None:
        c.run("student", "UPDATE student SET student_status = 'ALUMNUS', updated_at = now() WHERE student_id = :s "
              "AND student_status <> 'ALUMNUS'", s=sid)
        # a completed, published final-term result so the transcript / certificate flows have something real to show
        c.run("student_term_result",
              "INSERT INTO student_term_result (version, term_registration_id, credits_registered, credits_earned, sgpa, cgpa, result_status, "
              "published_at, state, evidence, actor_id, is_withheld) "
              "SELECT 0, t.term_registration_id, coalesce(cr.credits, 0), coalesce(cr.credits, 0), 8.60, 8.45, 'PASS', now() - interval '60 days', "
              "'PUBLISHED', CAST(:ev AS jsonb), CAST(:u AS bigint), false FROM student_term_registration t "
              "JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
              "LEFT JOIN LATERAL (SELECT sum(cat.credits) AS credits FROM student_course_registration r "
              "JOIN course_offering o ON o.course_offering_id = r.course_offering_id JOIN course_catalog cat ON cat.course_id = o.course_id "
              "WHERE r.term_registration_id = t.term_registration_id) cr ON true "
              "WHERE e.student_id = :s AND NOT EXISTS (SELECT 1 FROM student_term_result x WHERE x.term_registration_id = t.term_registration_id)",
              s=sid, u=c.actor, ev=json.dumps({"source": "demo", "note": "final term"}))
        c.run("student_course_result",
              "INSERT INTO student_course_result (version, course_registration_id, policy_id, attempt_number, internal_marks, external_marks, "
              "total_marks, grade_letter, grade_point, credits_earned, result_status, result_date, remarks, evidence, state, actor_id, is_withheld) "
              "SELECT 0, r.course_registration_id, pol.id, 1, 36 + r.course_registration_id % 4, 48 + (r.course_registration_id * 3) % 10, "
              "84 + (r.course_registration_id * 3) % 10 + r.course_registration_id % 4, CASE WHEN r.course_registration_id % 2 = 0 THEN 'A' ELSE 'B' END, "
              "CASE WHEN r.course_registration_id % 2 = 0 THEN 9.0 ELSE 8.0 END, cat.credits, 'PASS', current_date - 60, '', CAST(:ev AS jsonb), "
              "'PUBLISHED', CAST(:u AS bigint), false FROM student_course_registration r "
              "JOIN student_term_registration t ON t.term_registration_id = r.term_registration_id "
              "JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
              "JOIN course_offering o ON o.course_offering_id = r.course_offering_id JOIN course_catalog cat ON cat.course_id = o.course_id "
              "JOIN LATERAL (SELECT id FROM assessment_policy p WHERE p.course_offering_id = o.course_offering_id ORDER BY number DESC LIMIT 1) pol ON true "
              "WHERE e.student_id = :s AND NOT EXISTS (SELECT 1 FROM student_course_result x WHERE x.course_registration_id = r.course_registration_id "
              "AND x.attempt_number = 1)", s=sid, u=c.actor, ev=json.dumps({"source": "demo"}))
        c.run("student_course_registration", "UPDATE student_course_registration r SET registration_status = 'COMPLETED' "
              "FROM student_term_registration t JOIN student_programme_enrolment e ON e.enrolment_id = t.enrolment_id "
              "WHERE r.term_registration_id = t.term_registration_id AND e.student_id = :s AND r.registration_status <> 'COMPLETED' "
              "AND EXISTS (SELECT 1 FROM student_course_result x WHERE x.course_registration_id = r.course_registration_id)", s=sid)
        c.run("student_term_registration", "UPDATE student_term_registration t SET registration_status = 'COMPLETED' "
              "FROM student_programme_enrolment e WHERE e.enrolment_id = t.enrolment_id AND e.student_id = :s "
              "AND t.registration_status <> 'COMPLETED' "
              "AND EXISTS (SELECT 1 FROM student_term_result x WHERE x.term_registration_id = t.term_registration_id)", s=sid)
    sid = c.student.get("applicant")
    if sid is not None:
        c.run("student", "UPDATE student SET student_status = 'APPLICANT', updated_at = now() WHERE student_id = :s "
              "AND student_status <> 'APPLICANT'", s=sid)


# ---------------------------------------------------------------------------------------------------------- feedback
QUESTIONNAIRE_CODE = "DEMO-COURSE-FB"
# question text -> (response type, category code, required); existing questions are re-used, missing ones are created
FEEDBACK_QUESTIONS = [
    ("The instructor explains concepts clearly.", "RATING", "TEACHING", True),
    ("The instructor is punctual and well prepared.", "RATING", "TEACHING", True),
    ("The course content is relevant and up to date.", "RATING", "COURSE", True),
    ("Assessments reflect what was taught.", "RATING", "COURSE", True),
    ("The pace of the course was", "SINGLE_CHOICE", "COURSE", True),
    ("Laboratory and classroom facilities are adequate.", "RATING", "FACILITIES", False),
    ("What should be improved in this course?", "TEXT", "OVERALL", False),
]
PACE_CHOICES = [("Too slow", 1), ("Just right", 3), ("Too fast", 2)]
COMMENTS = ["More worked examples would help.", "Great course, the labs were very useful.", "Please share lecture notes earlier.",
            "The pace was fine, but assignments were heavy.", "Would like more industry case studies."]


def _frozen_snapshot(db: Session, questionnaire_id: int) -> dict:
    items = []
    for r in db.execute(text(
            "SELECT i.questionnaire_item_id, i.weightage, i.is_required, q.feedback_question_id, q.question_text, q.response_type, "
            "q.rating_min, q.rating_max, q.rating_step, q.text_limit FROM feedback_questionnaire_item i "
            "JOIN feedback_question q USING (feedback_question_id) WHERE i.questionnaire_id = :q ORDER BY i.display_order"),
            {"q": questionnaire_id}):
        choices = [{"id": str(cid), "text": ct, "score": str(sc) if sc is not None else None} for cid, ct, sc in db.execute(text(
            "SELECT feedback_choice_id, choice_text, score FROM feedback_choice WHERE feedback_question_id = :f ORDER BY display_order"),
            {"f": r.feedback_question_id})]
        items.append({"id": str(r.questionnaire_item_id), "text": r.question_text, "choices": choices, "weightage": None,
                      "rating_max": str(r.rating_max) if r.rating_max is not None else None,
                      "rating_min": str(r.rating_min) if r.rating_min is not None else None,
                      "text_limit": r.text_limit, "is_required": r.is_required, "question_id": str(r.feedback_question_id),
                      "rating_step": str(r.rating_step) if r.rating_step is not None else None, "response_type": r.response_type})
    return {"name": "End-semester course feedback", "type": "COURSE", "items": items, "weighted": False, "anonymous": True}


def _feedback(c: _Ctx) -> None:
    db = c.db
    if not db.execute(text("SELECT 1 FROM academic_term WHERE term_code = 'ODD25'")).first():
        return
    c.run("feedback_questionnaire",
          "INSERT INTO feedback_questionnaire (version, questionnaire_code, questionnaire_name, questionnaire_type, is_anonymous, status, "
          "actor_id, institution_id) SELECT 1, CAST(:code AS varchar), 'End-semester course feedback', 'COURSE', true, 'ACTIVE', "
          "CAST(:u AS bigint), CAST(:i AS int) WHERE CAST(:i AS int) IS NOT NULL AND NOT EXISTS "
          "(SELECT 1 FROM feedback_questionnaire WHERE questionnaire_code = :code)", code=QUESTIONNAIRE_CODE, u=c.actor, i=c.inst)
    qid = db.execute(text("SELECT questionnaire_id FROM feedback_questionnaire WHERE questionnaire_code = :c"), {"c": QUESTIONNAIRE_CODE}).scalar()
    if qid is None:
        return
    for order, (qtext, rtype, cat, required) in enumerate(FEEDBACK_QUESTIONS, start=1):
        c.run("feedback_question",
              "INSERT INTO feedback_question (version, question_text, response_type, is_active, rating_min, rating_max, rating_step, "
              "text_limit, actor_id, feedback_category_id) "
              "SELECT 1, CAST(:t AS varchar), CAST(:rt AS varchar), true, CASE WHEN :rt = 'RATING' THEN 1 END, "
              "CASE WHEN :rt = 'RATING' THEN 5 END, CASE WHEN :rt = 'RATING' THEN 1 END, CASE WHEN :rt = 'TEXT' THEN 500 END, "
              "CAST(:u AS bigint), k.feedback_category_id FROM feedback_question_category k WHERE k.category_code = :cat "
              "AND NOT EXISTS (SELECT 1 FROM feedback_question WHERE question_text = :t)", t=qtext, rt=rtype, cat=cat, u=c.actor)
        c.run("feedback_questionnaire_item",
              "INSERT INTO feedback_questionnaire_item (weightage, display_order, is_required, feedback_question_id, questionnaire_id) "
              "SELECT NULL, :o, CAST(:req AS boolean), f.feedback_question_id, :q FROM feedback_question f WHERE f.question_text = :t "
              "AND NOT EXISTS (SELECT 1 FROM feedback_questionnaire_item i WHERE i.questionnaire_id = :q "
              "AND (i.feedback_question_id = f.feedback_question_id OR i.display_order = :o))", o=order, req=required, q=qid, t=qtext)
    for order, (label, score) in enumerate(PACE_CHOICES, start=1):
        c.run("feedback_choice",
              "INSERT INTO feedback_choice (version, choice_text, score, display_order, is_active, actor_id, feedback_question_id) "
              "SELECT 1, CAST(:ct AS varchar), :sc, :o, true, CAST(:u AS bigint), f.feedback_question_id FROM feedback_question f "
              "WHERE f.question_text = 'The pace of the course was' AND NOT EXISTS (SELECT 1 FROM feedback_choice x "
              "WHERE x.feedback_question_id = f.feedback_question_id AND x.choice_text = :ct)", ct=label, sc=score, o=order, u=c.actor)
    frozen = json.dumps(_frozen_snapshot(db, qid))
    cycles = [("End-semester feedback - Odd 2025", "OPEN", c.ago(days=3), c.now + timedelta(days=25), "FACULTY", "demo-open-cycle"),
              ("Mid-semester feedback - Odd 2025", "CLOSED", c.ago(days=60), c.ago(days=40), "PUBLIC", "demo-closed-cycle")]
    import hashlib
    for name, status, start, end, visibility, secret in cycles:
        c.run("feedback_cycle",
              "INSERT INTO feedback_cycle (version, cycle_name, start_at, end_at, result_visibility, status, minimum_cohort, allow_text_review, "
              "target_policy, explicit_registrations, frozen, key_fingerprint, academic_term_id, actor_id, programme_id, questionnaire_id) "
              "SELECT 1, CAST(:n AS varchar), CAST(:s AS timestamptz), CAST(:e AS timestamptz), CAST(:v AS varchar), CAST(:st AS varchar), 3, true, "
              "'ENROLLED', '[]'::jsonb, CAST(:fr AS jsonb), CAST(:k AS varchar), t.academic_term_id, CAST(:u AS bigint), NULL, :q "
              "FROM academic_term t WHERE t.term_code = 'ODD25' AND NOT EXISTS (SELECT 1 FROM feedback_cycle WHERE cycle_name = :n)",
              n=name, s=start, e=end, v=visibility, st=status, fr=frozen, k=hashlib.sha256(secret.encode()).hexdigest(), u=c.actor, q=qid)
    closed = db.execute(text("SELECT feedback_cycle_id FROM feedback_cycle WHERE cycle_name = 'Mid-semester feedback - Odd 2025'")).scalar()
    if closed is None or db.execute(text("SELECT count(*) FROM feedback_response WHERE feedback_cycle_id = :c"), {"c": closed}).scalar():
        return
    items = db.execute(text("SELECT i.questionnaire_item_id, q.response_type, q.feedback_question_id FROM feedback_questionnaire_item i "
                            "JOIN feedback_question q USING (feedback_question_id) WHERE i.questionnaire_id = :q ORDER BY i.display_order"),
                       {"q": qid}).all()
    offerings = [o for (o,) in db.execute(text(
        "SELECT o.course_offering_id FROM course_offering o JOIN programme_term_offering p USING (programme_term_offering_id) "
        "JOIN academic_term t ON t.academic_term_id = p.academic_term_id WHERE t.term_code = 'ODD25' ORDER BY 1 LIMIT 4"))]
    n = 0
    for oi, offering in enumerate(offerings):
        for k in range(5):  # five anonymous responses per course (above the minimum cohort of three)
            n += 1
            token = hashlib.sha256(f"demo-response|{closed}|{offering}|{k}".encode()).hexdigest()[:24]
            rid = db.execute(text(
                "INSERT INTO feedback_response (feedback_cycle_id, course_offering_id, target_key, response_token, submitted_at) "
                "VALUES (:c, :o, :t, :tok, :at) RETURNING feedback_response_id"),
                {"c": closed, "o": offering, "t": f"{offering}:0", "tok": token, "at": c.ago(days=55 - k)}).scalar_one()
            c.counts["feedback_response"] = c.counts.get("feedback_response", 0) + 1
            for item_id, rtype, question_id in items:
                score = 3 + (n + len(rtype) + item_id) % 3 if rtype == "RATING" else None
                comment = COMMENTS[(n + oi) % len(COMMENTS)] if rtype == "TEXT" else None
                iid = db.execute(text(
                    "INSERT INTO feedback_response_item (feedback_response_id, questionnaire_item_id, numeric_score, text_response) "
                    "VALUES (:r, :i, :n, :t) RETURNING feedback_response_item_id"),
                    {"r": rid, "i": item_id, "n": score, "t": comment}).scalar_one()
                c.counts["feedback_response_item"] = c.counts.get("feedback_response_item", 0) + 1
                if rtype == "SINGLE_CHOICE":
                    c.run("feedback_response_item_choice",
                          "INSERT INTO feedback_response_item_choice (feedback_response_item_id, feedback_choice_id) "
                          "SELECT :i, feedback_choice_id FROM feedback_choice WHERE feedback_question_id = :q "
                          "ORDER BY display_order OFFSET :off LIMIT 1", i=iid, q=question_id, off=(n + k) % len(PACE_CHOICES))


# ------------------------------------------------------------------------------------------- staff research records
# (verification status, approval status, reviewed?, approved?) per workflow state
STAFF_STATES = {
    "DRAFT": ("PENDING", "DRAFT"), "SUBMITTED": ("PENDING", "SUBMITTED"), "UNDER_REVIEW": ("PENDING", "UNDER_REVIEW"),
    "RETURNED": ("PENDING", "RETURNED"), "VERIFIED": ("VERIFIED", "VERIFIED"), "APPROVED": ("VERIFIED", "APPROVED"),
    "REJECTED": ("REJECTED", "REJECTED"),
}
# the state order is rotated per employee so every reviewer sees every state
STATE_CYCLE = ["SUBMITTED", "UNDER_REVIEW", "VERIFIED", "APPROVED", "RETURNED", "REJECTED", "DRAFT", "SUBMITTED", "APPROVED"]
KIND_CYCLE = ["journal", "award", "conference", "funded", "proposal", "membership", "evidence", "consultancy", "journal"]
KIND_TITLES = {
    "journal": ["Federated learning for campus analytics", "A survey of edge caching in university networks",
                "Predictive models for student retention", "Energy-aware scheduling in cloud labs"],
    "award": ["Excellence in Teaching Award", "Best Paper Award - regional symposium", "Outstanding Mentor Recognition"],
    "conference": ["Presented: scalable microservices for education", "Invited talk: outcome-based assessment", "Paper at national AI workshop"],
    "funded": ["Sponsored project: smart campus energy monitor", "Seed-grant project: low-cost IoT lab kits"],
    "proposal": ["Proposal: explainable AI for course recommendation", "Proposal: secure data lakes for institutions"],
    "membership": ["Professional membership renewal", "Senior member upgrade"],
    "evidence": ["Evidence: faculty development programme certificate", "Evidence: NPTEL course completion"],
    "consultancy": ["Consultancy: ERP performance audit", "Consultancy: network design for a partner college"],
}


def _research_masters(c: _Ctx) -> dict:
    db = c.db
    for code, name in (("INTL", "International journal"), ("NATL", "National journal")):
        c.run("journal_type", "INSERT INTO journal_type (journal_type_code, journal_type_name, is_active) SELECT CAST(:c AS varchar), "
              "CAST(:n AS varchar), true WHERE NOT EXISTS (SELECT 1 FROM journal_type WHERE journal_type_code = :c OR journal_type_name = :n)",
              c=code, n=name)
    for code, name in (("JOURNAL_ARTICLE", "Journal article"), ("CONFERENCE_PAPER", "Conference paper")):
        c.run("publication_type", "INSERT INTO publication_type (publication_type_code, publication_type_name, is_active) "
              "SELECT CAST(:c AS varchar), CAST(:n AS varchar), true WHERE NOT EXISTS (SELECT 1 FROM publication_type "
              "WHERE publication_type_code = :c OR publication_type_name = :n)", c=code, n=name)
    for name, issn in (("IEEE Transactions on Education", "0018-9359"), ("Journal of Systems and Software", "0164-1212"),
                       ("International Journal of Computer Applications", "0975-8887")):
        c.run("journal", "INSERT INTO journal (journal_name, journal_type_id, issn, is_peer_reviewed_default, is_active) "
              "SELECT CAST(:n AS varchar), (SELECT min(journal_type_id) FROM journal_type), CAST(:i AS varchar), true, true "
              "WHERE (SELECT min(journal_type_id) FROM journal_type) IS NOT NULL "
              "AND NOT EXISTS (SELECT 1 FROM journal WHERE journal_name = :n OR issn = :i)", n=name, i=issn)

    def one(sql, **p):
        return db.execute(text(sql), p).scalar()
    return {
        "pub_type": one("SELECT min(publication_type_id) FROM publication_type WHERE publication_type_code = 'JOURNAL_ARTICLE'"),
        "journal": one("SELECT min(journal_id) FROM journal"), "org": one("SELECT min(organization_id) FROM external_organization "
                                                                        "WHERE organization_code IN ('IEEE', 'ACM', 'CSI')"),
        "client": one("SELECT min(organization_id) FROM external_organization"),
        "award_cat": one("SELECT min(award_category_id) FROM award_category"),
        "conf": one("SELECT min(conference_event_id) FROM conference_event WHERE conference_title NOT LIKE 'Sample%'")
        or one("SELECT min(conference_event_id) FROM conference_event"),
        "contrib": one("SELECT min(conference_contribution_type_id) FROM conference_contribution_type WHERE type_code = 'PAPER'"),
        "agency": one("SELECT min(funding_agency_id) FROM funding_agency"),
        "funding_type": one("SELECT min(funding_type_id) FROM funding_type WHERE funding_type_code = 'GOVT'")
        or one("SELECT min(funding_type_id) FROM funding_type"),
        "rs_ongoing": one("SELECT research_status_id FROM research_status WHERE status_code = 'ONGOING'"),
        "rs_draft": one("SELECT research_status_id FROM research_status WHERE status_code = 'DRAFT'"),
        "membership_type": one("SELECT min(membership_type_id) FROM membership_type"),
        "doc_type": one("SELECT min(document_type_id) FROM document_type"),
        "evidence_type": one("SELECT min(evidence_type_id) FROM evidence_type"),
        "confidentiality": one("SELECT min(confidentiality_level_id) FROM confidentiality_level"),
        "year": one("SELECT academic_year_id FROM academic_year ORDER BY academic_year_id LIMIT 1"),
        "campus": one("SELECT min(campus_id) FROM campus"),
    }


def _staff_record(c: _Ctx, m: dict, emp: int, dept: int | None, kind: str, title: str, state: str, i: int) -> None:
    db = c.db
    if db.execute(text("SELECT 1 FROM staff_activity WHERE employee_id = :e AND activity_title = :t"), {"e": emp, "t": title}).first():
        return
    code = {"journal": "JOURNAL_PUBLICATION", "award": "AWARD_RECOGNITION", "conference": "CONFERENCE_ACTIVITY",
            "funded": "FUNDED_RESEARCH_PROJECT", "proposal": "RESEARCH_PROPOSAL", "membership": "PROFESSIONAL_MEMBERSHIP",
            "evidence": "ACADEMIC_PROFESSIONAL_CONTRIBUTION", "consultancy": "CONSULTANCY_PROJECT"}[kind]
    vcode, acode = STAFF_STATES[state]
    verified = state in ("VERIFIED", "APPROVED")
    approved = state == "APPROVED"
    reviewer, approver = c.users.get("hod") or c.actor, c.users.get("dean") or c.actor
    owner_user = db.execute(text("SELECT user_id FROM person_account_link WHERE employee_id = :e LIMIT 1"), {"e": emp}).scalar() or c.actor
    start = (c.now - timedelta(days=40 + i * 17)).date()
    res = db.execute(text(
        "INSERT INTO staff_activity (employee_id, activity_type_id, academic_year_id, institution_id, campus_id, department_id, "
        "activity_title, start_date, description, verification_status_id, verified_by_user_id, verified_at, verification_remarks, "
        "approval_status_id, approved_by_user_id, approved_at, approval_remarks, rejection_reason, created_by_user_id, updated_by_user_id) "
        "SELECT :e, t.activity_type_id, :y, :inst, :campus, :d, :title, :sd, :desc, vs.verification_status_id, :vb, :va, :vr, "
        "a.approval_status_id, :ab, :aa, :ar, :rej, :cb, :cb FROM activity_type t, verification_status vs, approval_status a "
        "WHERE t.activity_type_code = :code AND vs.status_code = :vc AND a.status_code = :ac RETURNING staff_activity_id"),
        {"e": emp, "y": m["year"], "inst": c.inst, "campus": m["campus"], "d": dept, "title": title, "sd": start,
         "desc": f"{title}. Recorded for the annual faculty review.", "vb": reviewer if verified or state == "REJECTED" else None,
         "va": c.ago(days=10 + i) if verified or state == "REJECTED" else None,
         "vr": "Checked against the supporting documents." if verified else ("Does not meet the criteria." if state == "REJECTED" else
                                                                           "Please attach the supporting proof." if state == "RETURNED" else None),
         "ab": approver if approved else None, "aa": c.ago(days=5 + i) if approved else None, "ar": "Approved." if approved else None,
         "rej": "Insufficient evidence for the claim." if state == "REJECTED" else None, "cb": owner_user, "code": code,
         "vc": vcode, "ac": acode}).scalar()
    if res is None:
        return
    c.counts["staff_activity"] = c.counts.get("staff_activity", 0) + 1
    p = {"a": res, "e": emp, "d": dept, "t": title, "y": start.year, "sd": start, "i": i}

    def sub(table: str, sql: str, **extra):
        c.run(table, sql, **{**p, **extra})

    if kind == "journal" and m["pub_type"] and m["journal"]:
        sub("journal_publication", "INSERT INTO journal_publication (staff_activity_id, publication_type_id, journal_id, paper_title, "
            "publication_date, publication_year, doi, peer_reviewed, open_access, primary_author_position, keywords) "
            "VALUES (:a, :pt, :j, :t, :sd, :y, :doi, true, false, 1, 'education, analytics')",
            pt=m["pub_type"], j=m["journal"], doi=f"10.1109/demo.{emp}.{res}")
    elif kind == "award":
        sub("staff_award", "INSERT INTO staff_award (staff_activity_id, award_category_id, award_name, awarding_organization_id, award_date, "
            "cash_prize_amount, currency_code) VALUES (:a, :ac, :t, :o, :sd, 10000, 'INR')", ac=m["award_cat"], o=m["org"])
    elif kind == "conference" and m["conf"] and m["contrib"]:
        sub("conference_activity", "INSERT INTO conference_activity (staff_activity_id, conference_event_id, conference_contribution_type_id, "
            "paper_title, proceedings_title) VALUES (:a, :ce, :ct, :t, 'Proceedings of the conference')", ce=m["conf"], ct=m["contrib"])
    elif kind == "funded" and m["agency"] and m["funding_type"] and m["rs_ongoing"] and dept:
        sub("funded_research_project", "INSERT INTO funded_research_project (staff_activity_id, project_title, "
            "principal_investigator_employee_id, department_id, funding_agency_id, funding_type_id, requested_amount, sanctioned_amount, "
            "amount_received, amount_utilized, sanction_date, project_start_date, project_end_date, duration_months, research_status_id, "
            "research_domain) VALUES (:a, :t, :e, :d, :ag, :ft, 900000, 750000, 400000, 250000, :sd, :sd, :ed, 24, :rs, 'Computer science')",
            ag=m["agency"], ft=m["funding_type"], rs=m["rs_ongoing"], ed=start + timedelta(days=730))
    elif kind == "proposal" and m["rs_draft"] and dept:
        sub("research_proposal", "INSERT INTO research_proposal (staff_activity_id, proposal_title, principal_investigator_employee_id, "
            "department_id, proposal_submission_date, funding_agency_id, funding_type_id, requested_amount, research_status_id, "
            "research_domain) VALUES (:a, :t, :e, :d, :sd, :ag, :ft, 500000, :rs, 'Computer science')",
            ag=m["agency"], ft=m["funding_type"], rs=m["rs_draft"])
    elif kind == "membership" and m["org"] and m["membership_type"]:
        sub("staff_professional_membership", "INSERT INTO staff_professional_membership (staff_activity_id, organization_id, membership_type_id, "
            "membership_number, membership_start_date, membership_expiry_date, renewal_required, membership_status) "
            "VALUES (:a, :o, :mt, :num, :sd, :ex, true, 'ACTIVE')", o=m["org"], mt=m["membership_type"], num=f"DEMO-{emp}-{res}",
            ex=start + timedelta(days=1095))
    elif kind == "evidence" and m["doc_type"] and m["confidentiality"]:
        sub("evidence_document", "INSERT INTO evidence_document (staff_activity_id, document_type_id, evidence_type_id, confidentiality_level_id, "
            "document_title, description, academic_year_id, document_issue_date, issuing_authority, verification_status_id, "
            "approval_status_id, current_version_number, is_active, created_by_user_id) "
            "SELECT :a, :dt, :et, :cl, :t, 'Supporting document for the claim', :ay, :sd, 'Issuing authority', s.verification_status_id, "
            "ap.approval_status_id, 1, true, :cb FROM staff_activity sa JOIN verification_status s ON s.verification_status_id = "
            "sa.verification_status_id JOIN approval_status ap ON ap.approval_status_id = sa.approval_status_id "
            "WHERE sa.staff_activity_id = :a", dt=m["doc_type"], et=m["evidence_type"], cl=m["confidentiality"], ay=m["year"], cb=c.actor)
    elif kind == "consultancy" and m["client"]:
        sub("consultancy_project", "INSERT INTO consultancy_project (staff_activity_id, consultancy_title, client_organization_id, "
            "principal_consultant_employee_id, consultancy_type, project_start_date, consultancy_amount, amount_received, status, deliverables) "
            "VALUES (:a, :t, :cl, :e, 'CONSULTANCY', :sd, 150000, 75000, 'ONGOING', 'Audit report and recommendations')", cl=m["client"])


def _staff_research(c: _Ctx) -> None:
    db = c.db
    m = _research_masters(c)
    staff = dict.fromkeys(c.employee.values())  # persona staff first, then colleagues of the same department
    for (eid,) in db.execute(text("SELECT employee_id FROM employee ORDER BY employee_id")):
        if len(staff) >= 14:
            break
        staff.setdefault(eid)
    for n, emp in enumerate(staff):
        dept = db.execute(text("SELECT department_id FROM employee_assignment WHERE employee_id = :e AND end_date IS NULL "
                               "ORDER BY employee_assignment_id LIMIT 1"), {"e": emp}).scalar() or c.dept
        who = db.execute(text("SELECT coalesce(last_name, first_name) FROM employee WHERE employee_id = :e"), {"e": emp}).scalar() or str(emp)
        for k in range(7):
            kind = KIND_CYCLE[(n + k) % len(KIND_CYCLE)]
            state = STATE_CYCLE[(n + k * 2) % len(STATE_CYCLE)]
            variants = KIND_TITLES[kind]
            title = f"{variants[(n + k) % len(variants)]} [{who}]"
            _staff_record(c, m, emp, dept, kind, title, state, n * 7 + k)


# ------------------------------------------------------------------------------------------------ staff HR extras
QUALIFICATION_LEVELS = [("BE", "B.E. / B.Tech", 1, False), ("ME", "M.E. / M.Tech", 2, False), ("PHD", "Ph.D.", 3, True)]


def _staff_hr(c: _Ctx) -> None:
    for code, name, order, terminal in QUALIFICATION_LEVELS:
        c.run("qualification_level",
              "INSERT INTO qualification_level (level_code, level_name, display_order, is_terminal_degree, is_active) "
              "SELECT CAST(:c AS varchar), CAST(:n AS varchar), :o, CAST(:t AS boolean), true WHERE NOT EXISTS "
              "(SELECT 1 FROM qualification_level WHERE level_code = :c OR level_name = :n)", c=code, n=name, o=order, t=terminal)
    c.run("study_mode", "INSERT INTO study_mode (mode_code, mode_name, is_active) SELECT 'FULL_TIME', 'Full time', true "
          "WHERE NOT EXISTS (SELECT 1 FROM study_mode WHERE mode_code = 'FULL_TIME' OR mode_name = 'Full time')")
    c.run("awarding_body", "INSERT INTO awarding_body (awarding_body_name, university_type, city, country_id, is_active) "
          "SELECT 'Visvesvaraya Technological University', 'STATE', 'Belagavi', (SELECT min(country_id) FROM country), true "
          "WHERE NOT EXISTS (SELECT 1 FROM awarding_body WHERE awarding_body_name = 'Visvesvaraya Technological University')")
    c.run("education_institution", "INSERT INTO education_institution (institution_name, city, country_id, is_active) "
          "SELECT 'Karnataka Institute of Engineering', 'Dharwad', (SELECT min(country_id) FROM country), true "
          "WHERE NOT EXISTS (SELECT 1 FROM education_institution WHERE institution_name = 'Karnataka Institute of Engineering' "
          "AND city = 'Dharwad')")
    for code, degree, year_back, cgpa, highest_for in (("BE", "Bachelor of Engineering", 14, 8.1, "other"), ("ME", "Master of Technology", 10, 8.6, "mid"),
                                                       ("PHD", "Doctor of Philosophy", 4, None, "doctor")):
        c.run("employee_qualification",
              "INSERT INTO employee_qualification (qualification_level_id, study_mode_id, degree_certificate_name, specialization, "
              "passing_year, completion_year, result, cgpa, cgpa_scale, qualification_status, is_highest_qualification, awarding_body_id, "
              "education_institution_id, created_by_user_id, employee_id) "
              "SELECT ql.qualification_level_id, (SELECT min(study_mode_id) FROM study_mode), CAST(:dg AS varchar), 'Computer Science and Engineering', "
              "CAST(extract(year FROM now()) AS int) - :yb, CAST(extract(year FROM now()) AS int) - :yb, 'First class', CAST(:cg AS numeric), "
              "CASE WHEN CAST(:cg AS numeric) IS NULL THEN NULL ELSE 10 END, 'COMPLETED', "
              "(CASE :hf WHEN 'doctor' THEN e.display_name LIKE 'Dr.%' WHEN 'mid' THEN e.display_name NOT LIKE 'Dr.%' ELSE false END), "
              "(SELECT min(awarding_body_id) FROM awarding_body), (SELECT min(education_institution_id) FROM education_institution), "
              "CAST(:u AS bigint), e.employee_id FROM employee e JOIN qualification_level ql ON ql.level_code = :c "
              "WHERE (:c <> 'PHD' OR e.display_name LIKE 'Dr.%') AND NOT EXISTS (SELECT 1 FROM employee_qualification q "
              "WHERE q.employee_id = e.employee_id AND q.qualification_level_id = ql.qualification_level_id)",
              c=code, dg=degree, yb=year_back, cg=cgpa, hf=highest_for, u=c.actor)
    for atype, line, primary in (("PERMANENT", "21, Gokul Road", False), ("CURRENT", "Staff Quarters, University Campus", True)):
        c.run("employee_address",
              "INSERT INTO employee_address (address_type, address_line_1, city, postal_code, is_primary, country_id, state_id, employee_id) "
              "SELECT CAST(:t AS varchar), CAST(:l AS varchar), 'Hubballi', '580030', CAST(:p AS boolean), (SELECT min(country_id) FROM country), "
              "(SELECT min(state_id) FROM state WHERE state_name = 'Karnataka'), e.employee_id FROM employee e "
              "WHERE (SELECT min(country_id) FROM country) IS NOT NULL AND NOT EXISTS (SELECT 1 FROM employee_address a "
              "WHERE a.employee_id = e.employee_id AND (a.address_type = CAST(:t AS varchar) OR (CAST(:p AS boolean) AND a.is_primary)))", t=atype, l=line, p=primary)


SECTIONS = [_announcements, _notifications, _grievances, _certificates, _documents, _admissions, _family, _alumni_and_applicant, _feedback,
            _staff_research, _staff_hr]


def ensure_service_content(db: Session) -> dict[str, int]:
    """Insert whatever demo content is missing; returns the number of rows added per table (empty when nothing was missing)."""
    c = _Ctx(db)
    for section in SECTIONS:
        with db.begin_nested():
            section(c)
    db.flush()
    return {k: v for k, v in c.counts.items() if v}
