"""SQLAlchemy models for the people_master domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class Designation(Base):
    __tablename__ = 'designation'
    designation_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    designation_code = mapped_column(String(30), nullable=False)
    designation_name = mapped_column(String(100), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    staff_category_id = mapped_column(Integer, ForeignKey('staff_category.staff_category_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('designation_code', name='uq_designation_designation_code'),
        UniqueConstraint('staff_category_id', 'designation_name', name='uq_designation_staff_category_id_designation_name'),
    )


class Employee(Base):
    __tablename__ = 'employee'
    employee_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_number = mapped_column(String(30), nullable=False)
    agency_employee_number = mapped_column(String(50))
    first_name = mapped_column(String(100), nullable=False)
    middle_name = mapped_column(String(100))
    last_name = mapped_column(String(100))
    display_name = mapped_column(String(250), nullable=False)
    date_of_birth = mapped_column(Date)
    primary_email = mapped_column(String(254))
    primary_phone = mapped_column(String(25))
    photo_url = mapped_column(String(500))
    joining_date = mapped_column(Date, nullable=False)
    employment_type = mapped_column(String(9), nullable=False)
    employment_status = mapped_column(String(10), nullable=False, server_default=text("'DRAFT'"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    blood_group_id = mapped_column(SmallInteger, ForeignKey('blood_group.blood_group_id'))
    caste_id = mapped_column(Integer, ForeignKey('caste.caste_id'))
    gender_id = mapped_column(SmallInteger, ForeignKey('gender.gender_id'))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    nationality_country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    religion_id = mapped_column(Integer, ForeignKey('religion.religion_id'))
    social_category_id = mapped_column(Integer, ForeignKey('social_category.social_category_id'))
    sub_caste_id = mapped_column(Integer, ForeignKey('sub_caste.sub_caste_id'))
    employment_source_id = mapped_column(SmallInteger, ForeignKey('employment_source.employment_source_id'), nullable=False)
    external_agency_id = mapped_column(BigInteger, ForeignKey('external_agency.external_agency_id'))
    __table_args__ = (
        UniqueConstraint('employee_number', name='uq_employee_employee_number'),
        UniqueConstraint('external_agency_id', 'agency_employee_number', name='uq_employee_external_agency_id_agency_employee_number'),
        UniqueConstraint('primary_email', name='uq_employee_primary_email'),
        Index('ix_employee_blood_group_id', 'blood_group_id'),
        Index('ix_employee_caste_id', 'caste_id'),
        Index('ix_employee_employment_source_id', 'employment_source_id'),
        Index('ix_employee_gender_id', 'gender_id'),
        Index('ix_employee_nationality_country_id', 'nationality_country_id'),
        Index('ix_employee_religion_id', 'religion_id'),
        Index('ix_employee_social_category_id', 'social_category_id'),
        Index('ix_employee_sub_caste_id', 'sub_caste_id'),
        Index('ix_employee_institution_id_employment_status_employee_number', 'institution_id', 'employment_status', 'employee_number'),
        CheckConstraint("(employment_status in ('DRAFT','ACTIVE','ON_LEAVE','SUSPENDED','RESIGNED','RETIRED','TERMINATED'))", name='ck_employee_m5_employee_employment_st'),
        CheckConstraint("(employment_type in ('REGULAR','CONTRACT','VISITING','ADJUNCT','TEMPORARY','OTHER'))", name='ck_employee_m5_employee_employment_ty'),
    )


class EmployeeAddress(Base):
    __tablename__ = 'employee_address'
    employee_address_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    address_type = mapped_column(String(14), nullable=False)
    address_line_1 = mapped_column(String(200), nullable=False)
    address_line_2 = mapped_column(String(200))
    city = mapped_column(String(100), nullable=False)
    postal_code = mapped_column(String(12))
    valid_from = mapped_column(Date)
    valid_to = mapped_column(Date)
    is_primary = mapped_column(Boolean, nullable=False, server_default=text("false"))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'), nullable=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    __table_args__ = (
        Index('ix_employee_address_country_id', 'country_id'),
        Index('ix_employee_address_employee_id', 'employee_id'),
        Index('ix_employee_address_state_id', 'state_id'),
        CheckConstraint("(address_type in ('PERMANENT','CURRENT','CORRESPONDENCE','OTHER'))", name='ck_employee_address_m5_employee_address_address_type'),
        CheckConstraint('((valid_from is null) or (valid_to is null) or (valid_to >= valid_from))', name='ck_employee_address_m5_employee_address_dates'),
    )


class EmployeeAssignment(Base):
    __tablename__ = 'employee_assignment'
    employee_assignment_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    start_date = mapped_column(Date, nullable=False)
    end_date = mapped_column(Date)
    is_primary = mapped_column(Boolean, nullable=False, server_default=text("true"))
    campus_id = mapped_column(Integer, ForeignKey('campus.campus_id'), nullable=False)
    department_id = mapped_column(Integer)
    designation_id = mapped_column(Integer, ForeignKey('designation.designation_id'), nullable=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['department_id', 'campus_id'], ['department.department_id', 'department.campus_id']),
        Index('ix_employee_assignment_campus_id', 'campus_id'),
        Index('ix_employee_assignment_department_id', 'department_id'),
        Index('ix_employee_assignment_designation_id', 'designation_id'),
        Index('ix_employee_assignment_employee_id', 'employee_id'),
        Index('ix_employee_assignment_department_id_campus_id', 'department_id', 'campus_id'),
        CheckConstraint('((start_date is null) or (end_date is null) or (end_date >= start_date))', name='ck_employee_assignment_m5_employee_assignment_dates'),
    )


class EmployeeCompetency(Base):
    __tablename__ = 'employee_competency'
    competency_level = mapped_column(String(12))
    valid_from = mapped_column(Date)
    valid_to = mapped_column(Date)
    course_id = mapped_column(Integer, ForeignKey('course_catalog.course_id'), primary_key=True, autoincrement=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), primary_key=True, autoincrement=False)
    __table_args__ = (
        Index('ix_employee_competency_employee_id', 'employee_id'),
        Index('ix_employee_competency_course_id', 'course_id'),
        CheckConstraint("(competency_level in ('BEGINNER','INTERMEDIATE','ADVANCED','EXPERT'))", name='ck_employee_competency_m5_employee_competen_competency_le'),
        CheckConstraint('((valid_from is null) or (valid_to is null) or (valid_to >= valid_from))', name='ck_employee_competency_m5_employee_competency_dates'),
    )


class EmploymentSource(Base):
    __tablename__ = 'employment_source'
    employment_source_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    source_code = mapped_column(String(30), nullable=False)
    source_name = mapped_column(String(100), nullable=False)
    is_external = mapped_column(Boolean, nullable=False, server_default=text("false"))
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    __table_args__ = (
        UniqueConstraint('source_code', name='uq_employment_source_source_code'),
        UniqueConstraint('source_name', name='uq_employment_source_source_name'),
    )


class ExternalAgency(Base):
    __tablename__ = 'external_agency'
    external_agency_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agency_code = mapped_column(String(50), nullable=False)
    agency_name = mapped_column(String(200), nullable=False)
    service_type = mapped_column(String(100))
    contact_person = mapped_column(String(150))
    phone = mapped_column(String(25))
    email = mapped_column(String(254))
    contract_start_date = mapped_column(Date)
    contract_end_date = mapped_column(Date)
    address = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('institution_id', 'agency_code', name='uq_external_agency_institution_id_agency_code'),
        CheckConstraint('((contract_start_date is null) or (contract_end_date is null) or (contract_end_date >= contract_start_date))', name='ck_external_agency_m5_external_agency_dates'),
    )


class PersonAccountLink(Base):
    __tablename__ = 'person_account_link'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'))
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('employee_id', name='uq_person_account_link_employee_id'),
        UniqueConstraint('student_id', name='uq_person_account_link_student_id'),
        UniqueConstraint('user_id', 'employee_id', name='uq_person_account_link_user_id_employee_id'),
        UniqueConstraint('user_id', 'student_id', name='uq_person_account_link_user_id_student_id'),
        CheckConstraint('(((employee_id is null) and (student_id is not null)) or ((employee_id is not null) and (student_id is null)))', name='ck_person_account_link_people_link_root'),
    )


class AccountInvitation(Base):
    __tablename__ = 'account_invitation'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash = mapped_column(String(64), nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    used_at = mapped_column(DateTime(timezone=True))
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'))
    intended_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'))
    __table_args__ = (
        UniqueConstraint('token_hash', name='uq_account_invitation_token_hash'),
        Index('ix_account_invitation_created_by_id', 'created_by_id'),
        Index('ix_account_invitation_employee_id', 'employee_id'),
        Index('ix_account_invitation_intended_user_id', 'intended_user_id'),
        Index('ix_account_invitation_student_id', 'student_id'),
        CheckConstraint('(((employee_id is null) and (student_id is not null)) or ((employee_id is not null) and (student_id is null)))', name='ck_account_invitation_people_invite_root'),
    )


class StaffCategory(Base):
    __tablename__ = 'staff_category'
    staff_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(50), nullable=False)
    category_name = mapped_column(String(150), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    staff_type_id = mapped_column(SmallInteger, ForeignKey('staff_type.staff_type_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_staff_category_category_code'),
        Index('ix_staff_category_staff_type_id', 'staff_type_id'),
    )


class StaffType(Base):
    __tablename__ = 'staff_type'
    staff_type_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    type_code = mapped_column(String(30), nullable=False)
    type_name = mapped_column(String(100), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    __table_args__ = (
        UniqueConstraint('type_code', name='uq_staff_type_type_code'),
        UniqueConstraint('type_name', name='uq_staff_type_type_name'),
    )


class Student(Base):
    __tablename__ = 'student'
    student_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_number = mapped_column(String(30), nullable=False)
    university_seat_number = mapped_column(String(30))
    first_name = mapped_column(String(100), nullable=False)
    middle_name = mapped_column(String(100))
    last_name = mapped_column(String(100))
    display_name = mapped_column(String(250), nullable=False)
    date_of_birth = mapped_column(Date)
    primary_email = mapped_column(String(254))
    primary_phone = mapped_column(String(25))
    photo_url = mapped_column(String(500))
    admission_date = mapped_column(Date)
    student_status = mapped_column(String(9), nullable=False, server_default=text("'APPLICANT'"))
    notes = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    blood_group_id = mapped_column(SmallInteger, ForeignKey('blood_group.blood_group_id'))
    campus_id = mapped_column(Integer, ForeignKey('campus.campus_id'))
    caste_id = mapped_column(Integer, ForeignKey('caste.caste_id'))
    department_id = mapped_column(Integer, ForeignKey('department.department_id'))
    gender_id = mapped_column(SmallInteger, ForeignKey('gender.gender_id'))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    nationality_country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    religion_id = mapped_column(Integer, ForeignKey('religion.religion_id'))
    social_category_id = mapped_column(Integer, ForeignKey('social_category.social_category_id'))
    sub_caste_id = mapped_column(Integer, ForeignKey('sub_caste.sub_caste_id'))
    __table_args__ = (
        UniqueConstraint('student_number', name='uq_student_student_number'),
        UniqueConstraint('university_seat_number', name='uq_student_university_seat_number'),
        UniqueConstraint('primary_email', name='uq_student_primary_email'),
        Index('ix_student_institution_id_student_status_student_number', 'institution_id', 'student_status', 'student_number'),
        Index('ix_student_blood_group_id', 'blood_group_id'),
        Index('ix_student_campus_id', 'campus_id'),
        Index('ix_student_caste_id', 'caste_id'),
        Index('ix_student_department_id', 'department_id'),
        Index('ix_student_gender_id', 'gender_id'),
        Index('ix_student_nationality_country_id', 'nationality_country_id'),
        Index('ix_student_religion_id', 'religion_id'),
        Index('ix_student_social_category_id', 'social_category_id'),
        Index('ix_student_sub_caste_id', 'sub_caste_id'),
        CheckConstraint("(student_status in ('APPLICANT','ACTIVE','SUSPENDED','WITHDRAWN','COMPLETED','ALUMNUS','DECEASED'))", name='ck_student_m5_student_student_statu'),
    )


class StudentAddress(Base):
    __tablename__ = 'student_address'
    student_address_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    address_type = mapped_column(String(14), nullable=False)
    address_line_1 = mapped_column(String(200), nullable=False)
    address_line_2 = mapped_column(String(200))
    city = mapped_column(String(100), nullable=False)
    postal_code = mapped_column(String(12))
    valid_from = mapped_column(Date)
    valid_to = mapped_column(Date)
    is_primary = mapped_column(Boolean, nullable=False, server_default=text("false"))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'), nullable=False)
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    __table_args__ = (
        Index('ix_student_address_country_id', 'country_id'),
        Index('ix_student_address_state_id', 'state_id'),
        Index('ix_student_address_student_id', 'student_id'),
        CheckConstraint("(address_type in ('PERMANENT','CURRENT','CORRESPONDENCE','OTHER'))", name='ck_student_address_m5_student_address_address_type'),
        CheckConstraint('((valid_from is null) or (valid_to is null) or (valid_to >= valid_from))', name='ck_student_address_m5_student_address_dates'),
    )


class StudentEntranceExam(Base):
    __tablename__ = 'student_entrance_exam'
    student_entrance_exam_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_name = mapped_column(String(100), nullable=False)
    registration_number = mapped_column(String(50))
    rank_number = mapped_column(Integer)
    score = mapped_column(Numeric(8, 2))
    exam_year = mapped_column(SmallInteger)
    allotment_date = mapped_column(Date)
    registration_fee = mapped_column(Numeric(12, 2))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('student_id', 'exam_name', 'exam_year', name='uq_student_entrance_exam_student_id_exam_name_exam_year'),
        CheckConstraint('((registration_fee is null) or (registration_fee >= 0))', name='ck_student_entrance_exam_m5_student_entranc_registration'),
        CheckConstraint('(rank_number >= 0)', name='ck_student_entrance_exam_student_entrance_exam_chk_1'),
        CheckConstraint('(exam_year >= 0)', name='ck_student_entrance_exam_student_entrance_exam_chk_2'),
    )


class StudentParentGuardian(Base):
    __tablename__ = 'student_parent_guardian'
    student_parent_guardian_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    relationship_type = mapped_column(String(8), nullable=False)
    full_name = mapped_column(String(200), nullable=False)
    occupation = mapped_column(String(150))
    annual_income = mapped_column(Numeric(14, 2))
    email = mapped_column(String(254))
    phone = mapped_column(String(25))
    address_line_1 = mapped_column(String(200))
    address_line_2 = mapped_column(String(200))
    city = mapped_column(String(100))
    postal_code = mapped_column(String(12))
    is_primary_contact = mapped_column(Boolean, nullable=False, server_default=text("false"))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    __table_args__ = (
        Index('ix_student_parent_guardian_country_id', 'country_id'),
        Index('ix_student_parent_guardian_student_id', 'student_id'),
        Index('ix_student_parent_guardian_state_id', 'state_id'),
        CheckConstraint('((annual_income is null) or (annual_income >= 0))', name='ck_student_parent_guardian_m5_student_parent__annual_incom'),
        CheckConstraint("(relationship_type in ('FATHER','MOTHER','GUARDIAN','OTHER'))", name='ck_student_parent_guardian_m5_student_parent_gu_relat_8c0187'),
    )


class StudentPreviousEducation(Base):
    __tablename__ = 'student_previous_education'
    previous_education_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    qualification_level = mapped_column(String(7), nullable=False)
    examination_name = mapped_column(String(150))
    institution_name = mapped_column(String(250), nullable=False)
    board_university = mapped_column(String(200))
    registration_number = mapped_column(String(50))
    month_of_passing = mapped_column(SmallInteger)
    year_of_passing = mapped_column(SmallInteger)
    result_class = mapped_column(String(50))
    marks_obtained = mapped_column(Numeric(8, 2))
    maximum_marks = mapped_column(Numeric(8, 2))
    percentage = mapped_column(Numeric(5, 2))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('student_id', 'qualification_level', 'registration_number', name='uq_student_previous_education_student_id_qualificatio_06b803'),
        CheckConstraint('((marks_obtained is null) or (maximum_marks is null) or (marks_obtained <= maximum_marks))', name='ck_student_previous_education_m5_education_marks'),
        CheckConstraint('((month_of_passing is null) or ((month_of_passing >= 1) and (month_of_passing <= 12)))', name='ck_student_previous_education_m5_education_month'),
        CheckConstraint('((percentage is null) or ((percentage >= 0) and (percentage <= 100)))', name='ck_student_previous_education_m5_education_percent'),
        CheckConstraint('((marks_obtained is null) or (marks_obtained >= 0))', name='ck_student_previous_education_m5_student_previou_mark_3e54b6'),
        CheckConstraint('((maximum_marks is null) or (maximum_marks >= 0))', name='ck_student_previous_education_m5_student_previou_maxi_bd269b'),
        CheckConstraint("(qualification_level in ('SSLC','PUC_I','PUC_II','DIPLOMA','UG','PG','OTHER'))", name='ck_student_previous_education_m5_student_previous__qu_ca2c59'),
        CheckConstraint('(month_of_passing >= 0)', name='ck_student_previous_education_student_previous_educat_083098'),
        CheckConstraint('(year_of_passing >= 0)', name='ck_student_previous_education_student_previous_educat_9722cc'),
    )


class StudentResidence(Base):
    __tablename__ = 'student_residence'
    student_residence_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    residence_type = mapped_column(String(11), nullable=False)
    hostel_name = mapped_column(String(150))
    room_number = mapped_column(String(30))
    start_date = mapped_column(Date, nullable=False)
    end_date = mapped_column(Date)
    is_current = mapped_column(Boolean, nullable=False, server_default=text("true"))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    __table_args__ = (
        Index('ix_student_residence_student_id', 'student_id'),
        CheckConstraint('((start_date is null) or (end_date is null) or (end_date >= start_date))', name='ck_student_residence_m5_student_residence_dates'),
        CheckConstraint("(residence_type in ('HOSTEL','DAY_SCHOLAR','PG','RENTED','RELATIVE','OTHER'))", name='ck_student_residence_m5_student_residence_residence_typ'),
    )
