"""Explicit writable contract. Adding a model field never makes it writable."""

from . import models as m

RESOURCES = {
    "students": (
        m.Student,
        "student_number university_seat_number first_name middle_name last_name display_name date_of_birth gender_id blood_group_id primary_email primary_phone nationality_country_id religion_id social_category_id caste_id sub_caste_id photo_url admission_date notes institution_id campus_id department_id",
    ),
    "student-addresses": (
        m.StudentAddress,
        "student_id address_type address_line_1 address_line_2 city state_id country_id postal_code valid_from valid_to",
    ),
    "guardians": (
        m.StudentParentGuardian,
        "student_id relationship_type full_name occupation annual_income email phone address_line_1 address_line_2 city state_id country_id postal_code is_primary_contact",
    ),
    "residences": (
        m.StudentResidence,
        "student_id residence_type hostel_name room_number start_date end_date is_current",
    ),
    "previous-education": (
        m.StudentPreviousEducation,
        "student_id qualification_level examination_name institution_name board_university registration_number month_of_passing year_of_passing result_class marks_obtained maximum_marks percentage",
    ),
    "entrance-exams": (
        m.StudentEntranceExam,
        "student_id exam_name registration_number rank_number score exam_year allotment_date registration_fee",
    ),
    "staff-types": (m.StaffType, "type_code type_name description"),
    "staff-categories": (
        m.StaffCategory,
        "staff_type_id category_code category_name description",
    ),
    "employment-sources": (
        m.EmploymentSource,
        "source_code source_name is_external description",
    ),
    "agencies": (
        m.ExternalAgency,
        "institution_id agency_code agency_name service_type contact_person phone email contract_start_date contract_end_date address",
    ),
    "designations": (
        m.Designation,
        "staff_category_id designation_code designation_name description",
    ),
    "employees": (
        m.Employee,
        "institution_id employment_source_id external_agency_id employee_number agency_employee_number first_name middle_name last_name display_name date_of_birth gender_id blood_group_id primary_email primary_phone nationality_country_id religion_id social_category_id caste_id sub_caste_id photo_url joining_date employment_type",
    ),
    "employee-addresses": (
        m.EmployeeAddress,
        "employee_id address_type address_line_1 address_line_2 city state_id country_id postal_code valid_from valid_to",
    ),
    "assignments": (
        m.EmployeeAssignment,
        "employee_id campus_id department_id designation_id start_date end_date",
    ),
    "competencies": (
        m.EmployeeCompetency,
        "employee_id course_id competency_level valid_from valid_to",
    ),
}
FIELDS = {model: tuple(fields.split()) for model, fields in RESOURCES.values()}
PATHS = {model: path for path, (model, _) in RESOURCES.items()}
SHARED = (m.StaffType, m.StaffCategory, m.EmploymentSource, m.Designation)
RESTRICTED = {
    "religion_id",
    "social_category_id",
    "caste_id",
    "sub_caste_id",
    "notes",
    "annual_income",
}
CONFIDENTIAL = {
    "date_of_birth",
    "primary_email",
    "primary_phone",
    "email",
    "phone",
    "nationality_country_id",
    "gender_id",
    "blood_group_id",
    "photo_url",
    "university_seat_number",
    "address_line_1",
    "address_line_2",
    "city",
    "state_id",
    "country_id",
    "postal_code",
    "full_name",
    "occupation",
    "hostel_name",
    "room_number",
    "registration_number",
    "marks_obtained",
    "percentage",
    "score",
    "rank_number",
    "registration_fee",
    "contact_person",
    "address",
}
