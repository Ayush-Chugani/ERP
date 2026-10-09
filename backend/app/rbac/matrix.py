"""The authoritative role matrix (least privilege).

Each system role is defined here and ``catalogue.sync`` makes the database match it exactly: missing grants are added and
grants not listed here are removed. To customise access, create a new role instead of editing a system role (edits to a
system role are reverted the next time ``python -m app.cli bootstrap`` runs).

Letters: R read, C create, U update, D delete, A approve, V verify, P publish, S assign, X export.
``m(MODULE, letters)`` grants a whole module; ``r(MODULE, RESOURCE, letters)`` grants a single resource
(resource-level grants cannot carry S, which only exists module-wide).
"""
from collections.abc import Iterable

LETTERS = {"R": "READ", "C": "CREATE", "U": "UPDATE", "D": "DELETE", "A": "APPROVE", "V": "VERIFY", "P": "PUBLISH",
           "S": "ASSIGN", "F": "CONFIGURE", "X": "EXPORT"}
RESOURCE_LETTERS = set("RCUDAVPX")

Entry = tuple[str, str | None, str]


def m(module: str, letters: str) -> Entry:
    return (module, None, letters)


def r(module: str, resource: str, letters: str) -> Entry:
    assert set(letters) <= RESOURCE_LETTERS, f"{module}.{resource}: resource-level grants cannot use {set(letters) - RESOURCE_LETTERS}"
    return (module, resource, letters)


# Staff research / professional-record modules (reviewed through the V/A chain).
STAFF = ("STAFF_ACTIVITIES", "RESEARCH_PUBLICATIONS", "AWARDS", "CONFERENCES", "CONSULTANCY", "FUNDED_PROJECTS",
         "RESEARCH_PROPOSALS", "FACULTY_INTERNSHIPS", "PROFESSIONAL_CONTRIBUTIONS", "PROFESSIONAL_MEMBERSHIPS",
         "COCURRICULAR", "EXTRACURRICULAR", "EVIDENCE")
# Everything an institution runs (read access for oversight roles). Sensitive staff identifiers are never covered by
# module-wide grants (they need the specific EMPLOYEE_AADHAAR / EMPLOYEE_PAN / EMPLOYEE_BANK_ACCOUNT permission).
OPERATIONS = ("ACADEMIC_CALENDAR", "ADMISSION", "ASSESSMENT", "ATTENDANCE", "COMMUNICATION", "CURRICULUM", "DOCUMENT",
              "EMPLOYEE", "FEEDBACK", "GRIEVANCE", "INSTITUTION", "MENTORING", "REGISTRATION", "RESULT", "STUDENT",
              "TEACHING", "TIMETABLE", "REPORTING")


def reads(modules: Iterable[str], letters: str = "R") -> list[Entry]:
    return [m(mod, letters) for mod in modules]


def staff(letters: str) -> list[Entry]:
    return reads(STAFF, letters)


# Attendance resources a teacher works with (policy and status lists are read-only reference for them).
ATTENDANCE_WORK = ("CLASS_SESSION", "STUDENT_ATTENDANCE", "LESSON_COVERAGE", "LESSON_PLAN_REVISION", "ATTENDANCE_CORRECTION_REQUEST")

# Teachers read the feedback set-up (cycles, questions) but not raw responses, which are about colleagues.
_FEEDBACK_SETUP = ("FEEDBACK_CYCLE", "FEEDBACK_QUESTIONNAIRE", "FEEDBACK_QUESTIONNAIRE_ITEM", "FEEDBACK_QUESTION",
                   "FEEDBACK_QUESTION_CATEGORY", "FEEDBACK_CHOICE")

_FACULTY: list[Entry] = [
    m("REFERENCE", "R"), m("ACADEMIC_CALENDAR", "R"), m("CURRICULUM", "R"), m("TIMETABLE", "R"), m("TEACHING", "R"),
    r("STUDENT", "STUDENT", "R"), m("REGISTRATION", "R"), m("COMMUNICATION", "R"),
    m("ATTENDANCE", "R"), *[r("ATTENDANCE", res, "RCU") for res in ATTENDANCE_WORK],
    m("ASSESSMENT", "R"), r("ASSESSMENT", "STUDENT_ASSESSMENT_MARK", "RCU"), r("ASSESSMENT", "ASSESSMENT_EVENT", "RCU"),
    m("MENTORING", "R"), r("MENTORING", "COUNSELLING_SESSION", "RCU"),
    *[r("FEEDBACK", res, "R") for res in _FEEDBACK_SETUP],
]

MATRIX: dict[str, list[Entry]] = {
    # ----------------------------------------------------------------------------------- platform
    "SYSTEM_ADMIN": [m("IAM", "RCUSFX"), m("REFERENCE", "RCUDX"), m("ACADEMIC_CALENDAR", "RCUDPX"), m("COMMUNICATION", "RCUPX"),
                     m("INSTITUTION", "RCUX"), m("AUDIT", "RX"), m("REPORTING", "RX")],
    "SECURITY_ADMIN": [m("IAM", "RCUSFX"), m("AUDIT", "RX")],
    # ----------------------------------------------------------------------------------- leadership
    "VICE_CHANCELLOR": [*reads(OPERATIONS, "RX"), m("REFERENCE", "R"), m("AUDIT", "RX"), *staff("RAX")],
    "DEAN_ACADEMICS": [
        m("REFERENCE", "R"), m("AUDIT", "RX"), m("CURRICULUM", "RCUAPX"), m("ACADEMIC_CALENDAR", "RCUAPX"),
        m("REGISTRATION", "RAX"), m("STUDENT", "RAX"), m("RESULT", "RX"), *staff("RAVX"),
        *reads(("ADMISSION", "ASSESSMENT", "ATTENDANCE", "COMMUNICATION", "DOCUMENT", "EMPLOYEE", "FEEDBACK", "GRIEVANCE",
                "INSTITUTION", "MENTORING", "TEACHING", "TIMETABLE", "REPORTING"), "RX")],
    "CAMPUS_DIRECTOR": [
        m("REFERENCE", "R"), m("AUDIT", "RX"), m("STUDENT", "RAX"), m("EMPLOYEE", "RAX"), m("GRIEVANCE", "RASX"),
        m("TIMETABLE", "RAPX"), m("RESULT", "RAX"), m("ADMISSION", "RX"), m("INSTITUTION", "RUX"), m("COMMUNICATION", "RCUPX"),
        *staff("RAVX"),
        *reads(("ACADEMIC_CALENDAR", "ASSESSMENT", "ATTENDANCE", "CURRICULUM", "DOCUMENT", "FEEDBACK", "MENTORING",
                "REGISTRATION", "TEACHING", "REPORTING"), "RX")],
    "HEAD_DEPARTMENT": [
        m("REFERENCE", "R"), m("TEACHING", "RCUSX"), m("TIMETABLE", "RCUASX"), m("ATTENDANCE", "RAX"), m("RESULT", "RVX"),
        m("MENTORING", "RCUSX"), m("CURRICULUM", "RCUX"), m("REGISTRATION", "RAX"), m("COMMUNICATION", "RCU"), *staff("RAVX"),
        *reads(("ACADEMIC_CALENDAR", "ADMISSION", "ASSESSMENT", "DOCUMENT", "EMPLOYEE", "FEEDBACK", "INSTITUTION", "STUDENT",
                "REPORTING"), "RX"), m("GRIEVANCE", "R")],
    # ----------------------------------------------------------------------------------- registrar and admissions
    "REGISTRAR": [
        m("REFERENCE", "RCUX"), m("AUDIT", "RX"), m("STUDENT", "RCUAX"), m("ADMISSION", "RCUAVX"), m("REGISTRATION", "RCUAX"),
        m("ACADEMIC_CALENDAR", "RCUAPX"), m("CURRICULUM", "RCUAPX"), m("DOCUMENT", "RCUAVPX"), m("COMMUNICATION", "RCUAP"),
        *reads(("ASSESSMENT", "RESULT", "ATTENDANCE", "EMPLOYEE", "TIMETABLE", "INSTITUTION", "TEACHING", "REPORTING"), "RX"),
        *reads(("FEEDBACK", "MENTORING", "GRIEVANCE"), "R"), *staff("R")],
    "ADMISSION_OFFICER": [m("REFERENCE", "R"), m("ADMISSION", "RCUAVX"), r("STUDENT", "STUDENT", "R"), m("DOCUMENT", "R"), m("COMMUNICATION", "R")],
    "DOCUMENT_VERIFIER": [m("REFERENCE", "R"), m("DOCUMENT", "RV"), r("STUDENT", "STUDENT", "R"), m("ADMISSION", "R")],
    "STUDENT_SECTION_OFFICER": [m("REFERENCE", "R"), m("STUDENT", "RCUX"), m("REGISTRATION", "RCUAX"), m("DOCUMENT", "RV"),
                                m("ADMISSION", "R"), m("COMMUNICATION", "R")],
    # ----------------------------------------------------------------------------------- examination cell
    "CONTROLLER_EXAMINATIONS": [
        m("REFERENCE", "R"), m("ASSESSMENT", "RCUAPX"), m("RESULT", "RCUAVPX"), m("REGISTRATION", "RUX"), m("DOCUMENT", "RCUAVPX"),
        r("STUDENT", "STUDENT", "R"), m("ATTENDANCE", "R"), m("COMMUNICATION", "RCUP"), m("REPORTING", "RX")],
    "EXAMINATION_OFFICER": [m("REFERENCE", "R"), m("ASSESSMENT", "RCUX"), m("RESULT", "RX"), r("RESULT", "STUDENT_COURSE_RESULT", "CU"),
                            r("RESULT", "STUDENT_TERM_RESULT", "CU"), m("REGISTRATION", "R"),
                            r("STUDENT", "STUDENT", "R"), m("DOCUMENT", "R"), m("COMMUNICATION", "R")],
    "EVALUATOR": [m("REFERENCE", "R"), m("ASSESSMENT", "R"), r("ASSESSMENT", "STUDENT_ASSESSMENT_MARK", "RCU"),
                  m("REGISTRATION", "R"), r("STUDENT", "STUDENT", "R")],
    "RESULT_APPROVER": [m("REFERENCE", "R"), m("RESULT", "RAVX"), m("ASSESSMENT", "R"), r("STUDENT", "STUDENT", "R"), m("REGISTRATION", "R"),
                        m("DOCUMENT", "R")],
    # ----------------------------------------------------------------------------------- faculty
    "FACULTY": list(_FACULTY),
    "LAB_INSTRUCTOR": list(_FACULTY),
    "COURSE_COORDINATOR": [*_FACULTY, m("ASSESSMENT", "RCU"), r("ATTENDANCE", "LESSON_PLAN_REVISION", "A"),
                           r("ATTENDANCE", "LESSON_COVERAGE", "A")],
    "TIMETABLE_COORDINATOR": [m("REFERENCE", "R"), m("TIMETABLE", "RCUSA"), m("TEACHING", "RCUS"), m("ATTENDANCE", "R"),
                              m("ACADEMIC_CALENDAR", "R"), m("REGISTRATION", "R"), m("CURRICULUM", "R"), m("INSTITUTION", "R"),
                              m("EMPLOYEE", "R")],
    "PROGRAMME_COORDINATOR": [m("REFERENCE", "R"), m("CURRICULUM", "RCU"), m("REGISTRATION", "RAX"), m("STUDENT", "R"),
                              m("ACADEMIC_CALENDAR", "R"), m("TEACHING", "R"), m("TIMETABLE", "R")],
    "SEMESTER_COORDINATOR": [m("REFERENCE", "R"), m("CURRICULUM", "RCU"), m("REGISTRATION", "RAX"), m("STUDENT", "R"),
                             m("ACADEMIC_CALENDAR", "R"), m("TEACHING", "R"), m("TIMETABLE", "R")],
    "FACULTY_ADVISOR": [m("REFERENCE", "R"), m("MENTORING", "RX"), r("MENTORING", "COUNSELLING_SESSION", "RCU"), m("STUDENT", "R"), m("ATTENDANCE", "R"), m("RESULT", "R"),
                        m("COMMUNICATION", "R")],
    "MENTOR": [m("REFERENCE", "R"), m("MENTORING", "RX"), r("MENTORING", "COUNSELLING_SESSION", "RCU"), m("STUDENT", "R"), m("ATTENDANCE", "R"), m("RESULT", "R"),
               m("COMMUNICATION", "R")],
    "STAFF_SELF": [(mod, None, "CRUD") for mod in STAFF],
    # ----------------------------------------------------------------------------------- support, finance, audit
    "GRIEVANCE_OFFICER": [m("REFERENCE", "R"), m("GRIEVANCE", "RUSAX"), r("STUDENT", "STUDENT", "R"), m("MENTORING", "R"), m("COMMUNICATION", "R")],
    "FINANCE_OFFICER": [m("REFERENCE", "R"), m("ADMISSION", "R"), r("ADMISSION", "ADMISSION_FEE_CLEARANCE", "RVX"),
                        m("FUNDED_PROJECTS", "R"), m("CONSULTANCY", "R"), m("REPORTING", "R")],
    "INTERNAL_AUDITOR": [m("REFERENCE", "R"), m("AUDIT", "RX"), *reads(OPERATIONS, "RX"), *staff("RX")],
    "EXTERNAL_AUDITOR": [m("REFERENCE", "R"), m("AUDIT", "RX"), *reads(OPERATIONS, "RX"), *staff("RX")],
    # ----------------------------------------------------------------------------------- self-service
    "STUDENT": [
        m("REFERENCE", "R"), m("TIMETABLE", "R"), m("MENTORING", "R"), m("COMMUNICATION", "R"), m("ATTENDANCE", "R"),
        m("RESULT", "R"), m("ADMISSION", "R"), m("FEEDBACK", "R"), m("DOCUMENT", "R"), m("REGISTRATION", "R"),
        m("STUDENT", "R"), r("STUDENT", "STUDENT", "RU"), r("STUDENT", "STUDENT_ADDRESS", "RCU"),
        m("GRIEVANCE", "RC"),
        r("DOCUMENT", "CERTIFICATE_REQUEST", "RCU"), r("DOCUMENT", "STUDENT_DOCUMENT", "RCU"),
        r("ATTENDANCE", "ATTENDANCE_CORRECTION_REQUEST", "RCU"),
        r("REGISTRATION", "STUDENT_TERM_REGISTRATION", "RCU"), r("REGISTRATION", "STUDENT_COURSE_REGISTRATION", "RCU"),
        r("FEEDBACK", "FEEDBACK_RESPONSE", "RC"), r("FEEDBACK", "FEEDBACK_RESPONSE_ITEM", "RC"),
        r("FEEDBACK", "FEEDBACK_RESPONSE_ITEM_CHOICE", "RC"),
    ],
    "APPLICANT": [m("REFERENCE", "R"), m("COMMUNICATION", "R"), r("ADMISSION", "ADMISSION_APPLICANT", "RCU"),
                  r("ADMISSION", "ADMISSION_APPLICATION", "RCU"), r("DOCUMENT", "STUDENT_DOCUMENT", "RCU")],
    "PARENT_GUARDIAN": [m("REFERENCE", "R"), m("ATTENDANCE", "R"), m("RESULT", "R"), m("COMMUNICATION", "R"), r("STUDENT", "STUDENT", "R")],
    "ALUMNI": [m("REFERENCE", "R"), m("COMMUNICATION", "R"), r("STUDENT", "STUDENT", "R"), m("RESULT", "R"),
               r("DOCUMENT", "CERTIFICATE_REQUEST", "RCU"), m("DOCUMENT", "R"), r("FEEDBACK", "FEEDBACK_RESPONSE", "RC"),
               r("FEEDBACK", "FEEDBACK_RESPONSE_ITEM", "RC"), r("FEEDBACK", "FEEDBACK_RESPONSE_ITEM_CHOICE", "RC")],
}


def desired_codes(entries: list[Entry]) -> set[str]:
    out: set[str] = set()
    for module, resource, letters in entries:
        for ch in letters:
            out.add(f"{module}.{resource or 'ALL'}.{LETTERS[ch]}")
    return out


# ------------------------------------------------------------------------------- row-level restrictions for teaching roles
# These roles work only on the classes / papers / mentees they are assigned to, even though their role is scoped to a
# whole department or programme. A person who also holds a wider role (e.g. head of department) is not restricted.
CLASS_ROLES = frozenset({"FACULTY", "LAB_INSTRUCTOR", "EVALUATOR", "COURSE_COORDINATOR"})
MENTOR_ROLES = frozenset({"MENTOR", "FACULTY_ADVISOR"})
TEACHING_ROLES = CLASS_ROLES | MENTOR_ROLES
# Tables whose rows belong to a class section / course offering (visible and editable only for assigned sections).
CLASS_SCOPED = frozenset({"class_session", "student_attendance", "lesson_coverage", "lesson_plan_revision",
                          "attendance_correction_request", "assessment_event", "student_assessment_mark",
                          "course_offering_section_student"})
# Tables whose rows belong to one student; mentors and advisors see only their mentees.
MENTEE_SCOPED = frozenset({"student", "student_address", "student_attendance", "student_course_result", "student_term_result",
                           "attendance_correction_request", "student_parent_guardian", "student_residence",
                           "student_previous_education", "student_entrance_exam", "student_term_registration",
                           "student_course_registration"})
# Tables that are the mentoring relationship itself (any teaching role sees only its own).
MENTORING_OWN = frozenset({"counselling_session", "mentor_assignment"})
