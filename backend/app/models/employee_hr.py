"""SQLAlchemy models for the employee_hr domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class AwardingBody(Base):
    __tablename__ = 'awarding_body'
    awarding_body_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    awarding_body_type_id = mapped_column(SmallInteger, ForeignKey('awarding_body_type.awarding_body_type_id'))
    awarding_body_name = mapped_column(String(250), nullable=False)
    university_type = mapped_column(String(10))
    city = mapped_column(String(100))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    website_url = mapped_column(String(255))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('awarding_body_name', 'country_id', name='uq_awarding_body_awarding_body_name_country_id'),
        Index('ix_awarding_body_country_id', 'country_id'),
        Index('ix_awarding_body_state_id', 'state_id'),
        Index('ix_awarding_body_awarding_body_type_id', 'awarding_body_type_id'),
        CheckConstraint("university_type IN ('CENTRAL', 'STATE', 'PRIVATE', 'DEEMED', 'FOREIGN', 'AUTONOMOUS', 'OTHER')", name='ck_awarding_body_university_type_enum'),
    )


class AwardingBodyType(Base):
    __tablename__ = 'awarding_body_type'
    awarding_body_type_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    type_code = mapped_column(String(30), nullable=False)
    type_name = mapped_column(String(100), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('type_code', name='uq_awarding_body_type_type_code'),
        UniqueConstraint('type_name', name='uq_awarding_body_type_type_name'),
    )


class EducationInstitution(Base):
    __tablename__ = 'education_institution'
    education_institution_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    education_institution_type_id = mapped_column(SmallInteger, ForeignKey('education_institution_type.education_institution_type_id'))
    institution_name = mapped_column(String(250), nullable=False)
    city = mapped_column(String(100))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    website_url = mapped_column(String(255))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('institution_name', 'city', 'country_id', name='uq_education_institution_institution_name_city_country_id'),
        Index('ix_education_institution_country_id', 'country_id'),
        Index('ix_education_institution_state_id', 'state_id'),
        Index('ix_education_institution_education_institution_type_id', 'education_institution_type_id'),
    )


class EducationInstitutionType(Base):
    __tablename__ = 'education_institution_type'
    education_institution_type_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    type_code = mapped_column(String(30), nullable=False)
    type_name = mapped_column(String(100), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('type_code', name='uq_education_institution_type_type_code'),
        UniqueConstraint('type_name', name='uq_education_institution_type_type_name'),
    )


class EmployeeAadhaar(Base):
    __tablename__ = 'employee_aadhaar'
    employee_aadhaar_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    aadhaar_number_ciphertext = mapped_column(LargeBinary, nullable=False)
    aadhaar_number_fingerprint = mapped_column(String(64), nullable=False)
    aadhaar_number_last4 = mapped_column(String(4), nullable=False)
    aadhaar_number_masked = mapped_column(String(30), nullable=False)
    name_as_per_aadhaar = mapped_column(String(200), nullable=False)
    format_validated = mapped_column(Boolean, nullable=False, server_default=text("false"))
    verification_status = mapped_column(String(8), nullable=False, server_default=text("'PENDING'"))
    verified_at = mapped_column(DateTime(timezone=True))
    verification_remarks = mapped_column(String(1000))
    collection_purpose = mapped_column(String(500))
    remarks = mapped_column(String(1000))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = mapped_column(DateTime(timezone=True))
    created_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    updated_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    verified_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    __table_args__ = (
        UniqueConstraint('aadhaar_number_fingerprint', name='uq_employee_aadhaar_aadhaar_number_fingerprint'),
        UniqueConstraint('employee_id', name='uq_employee_aadhaar_employee_id'),
        UniqueConstraint('employee_aadhaar_id', 'employee_id', name='uq_employee_aadhaar_employee_aadhaar_id_employee_id'),
        Index('ix_employee_aadhaar_created_by_user_id', 'created_by_user_id'),
        Index('ix_employee_aadhaar_updated_by_user_id', 'updated_by_user_id'),
        Index('ix_employee_aadhaar_verified_by_user_id', 'verified_by_user_id'),
        CheckConstraint("verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED')", name='ck_employee_aadhaar_verification_status_enum'),
        CheckConstraint("regexp_like(aadhaar_number_last4,'^[0-9]{4}$','c')", name='ck_employee_aadhaar_employee_aadhaar_last4'),
    )


class EmployeeBankAccount(Base):
    __tablename__ = 'employee_bank_account'
    employee_bank_account_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_holder_name = mapped_column(String(200), nullable=False)
    bank_name = mapped_column(String(200), nullable=False)
    branch_name = mapped_column(String(200))
    account_number_ciphertext = mapped_column(LargeBinary, nullable=False)
    account_number_fingerprint = mapped_column(String(64), nullable=False)
    account_number_last4 = mapped_column(String(4), nullable=False)
    account_number_confirmed = mapped_column(Boolean, nullable=False, server_default=text("false"))
    account_type = mapped_column(String(7), nullable=False, server_default=text("'SAVINGS'"))
    ifsc_code = mapped_column(String(11), nullable=False)
    micr_code = mapped_column(String(20))
    branch_code = mapped_column(String(30))
    bank_address = mapped_column(String(500))
    city = mapped_column(String(100))
    upi_id = mapped_column(String(150))
    is_salary_account = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_primary = mapped_column(Boolean, nullable=False, server_default=text("false"))
    account_status = mapped_column(String(20), nullable=False, server_default=text("'PENDING_VERIFICATION'"))
    verification_status = mapped_column(String(8), nullable=False, server_default=text("'PENDING'"))
    verified_at = mapped_column(DateTime(timezone=True))
    verification_remarks = mapped_column(String(1000))
    effective_from = mapped_column(Date)
    effective_to = mapped_column(Date)
    remarks = mapped_column(String(1000))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = mapped_column(DateTime(timezone=True))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    created_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    updated_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    verified_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    __table_args__ = (
        UniqueConstraint('account_number_fingerprint', name='uq_employee_bank_account_account_number_fingerprint'),
        UniqueConstraint('employee_bank_account_id', 'employee_id', name='uq_employee_bank_account_employee_bank_account_id_emp_ba7ceb'),
        Index('ix_employee_bank_account_country_id', 'country_id'),
        Index('ix_employee_bank_account_created_by_user_id', 'created_by_user_id'),
        Index('ix_employee_bank_account_employee_id', 'employee_id'),
        Index('ix_employee_bank_account_state_id', 'state_id'),
        Index('ix_employee_bank_account_updated_by_user_id', 'updated_by_user_id'),
        Index('ix_employee_bank_account_verified_by_user_id', 'verified_by_user_id'),
        CheckConstraint("account_type IN ('SAVINGS', 'CURRENT', 'SALARY', 'NRE', 'NRO', 'OTHER')", name='ck_employee_bank_account_account_type_enum'),
        CheckConstraint("account_status IN ('PENDING_VERIFICATION', 'ACTIVE', 'INACTIVE', 'CLOSED', 'REJECTED')", name='ck_employee_bank_account_account_status_enum'),
        CheckConstraint("verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED')", name='ck_employee_bank_account_verification_status_enum'),
        CheckConstraint('((effective_to is null) or (effective_from is null) or (effective_to >= effective_from))', name='ck_employee_bank_account_employee_bank_dates'),
        CheckConstraint("regexp_like(ifsc_code,'^[A-Za-z]{4}0[A-Za-z0-9]{6}$','c')", name='ck_employee_bank_account_employee_bank_ifsc'),
        CheckConstraint("regexp_like(account_number_last4,'^[0-9]{4}$','c')", name='ck_employee_bank_account_employee_bank_last4'),
    )


class EmployeePan(Base):
    __tablename__ = 'employee_pan'
    employee_pan_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pan_number_ciphertext = mapped_column(LargeBinary, nullable=False)
    pan_number_fingerprint = mapped_column(String(64), nullable=False)
    pan_number_masked = mapped_column(String(15), nullable=False)
    name_as_per_pan = mapped_column(String(200), nullable=False)
    pan_issue_date = mapped_column(Date)
    pan_issue_details = mapped_column(String(500))
    format_validated = mapped_column(Boolean, nullable=False, server_default=text("false"))
    verification_status = mapped_column(String(8), nullable=False, server_default=text("'PENDING'"))
    verified_at = mapped_column(DateTime(timezone=True))
    verification_remarks = mapped_column(String(1000))
    remarks = mapped_column(String(1000))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = mapped_column(DateTime(timezone=True))
    created_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    updated_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    verified_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    __table_args__ = (
        UniqueConstraint('employee_id', name='uq_employee_pan_employee_id'),
        UniqueConstraint('pan_number_fingerprint', name='uq_employee_pan_pan_number_fingerprint'),
        UniqueConstraint('employee_pan_id', 'employee_id', name='uq_employee_pan_employee_pan_id_employee_id'),
        Index('ix_employee_pan_created_by_user_id', 'created_by_user_id'),
        Index('ix_employee_pan_updated_by_user_id', 'updated_by_user_id'),
        Index('ix_employee_pan_verified_by_user_id', 'verified_by_user_id'),
        CheckConstraint("verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED')", name='ck_employee_pan_verification_status_enum'),
        CheckConstraint('((char_length(pan_number_masked) >= 6) and (char_length(pan_number_masked) <= 15))', name='ck_employee_pan_employee_pan_masked'),
    )


class EmployeePreviousEmployment(Base):
    __tablename__ = 'employee_previous_employment'
    employee_previous_employment_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    department_division = mapped_column(String(200))
    designation = mapped_column(String(150), nullable=False)
    employment_type = mapped_column(String(13), nullable=False)
    nature_of_work = mapped_column(String(1000))
    employment_start_date = mapped_column(Date, nullable=False)
    employment_end_date = mapped_column(Date)
    experience_days = mapped_column(Integer)
    last_drawn_salary = mapped_column(Numeric(14, 2))
    salary_currency_code = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    reason_for_leaving = mapped_column(String(1000))
    reporting_authority_name = mapped_column(String(200))
    reporting_authority_designation = mapped_column(String(150))
    reporting_authority_phone = mapped_column(String(25))
    reporting_authority_email = mapped_column(String(254))
    remarks = mapped_column(String(1000))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = mapped_column(DateTime(timezone=True))
    created_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    previous_organization_id = mapped_column(BigInteger, ForeignKey('previous_organization.previous_organization_id'), nullable=False)
    updated_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    __table_args__ = (
        UniqueConstraint('employee_previous_employment_id', 'employee_id', name='uq_employee_previous_employment_employee_previous_emp_a55970'),
        Index('ix_employee_previous_employment_created_by_user_id', 'created_by_user_id'),
        Index('ix_employee_previous_employment_employee_id', 'employee_id'),
        Index('ix_employee_previous_employment_previous_organization_id', 'previous_organization_id'),
        Index('ix_employee_previous_employment_updated_by_user_id', 'updated_by_user_id'),
        CheckConstraint("employment_type IN ('FULL_TIME', 'PART_TIME', 'CONTRACT', 'TEMPORARY', 'VISITING', 'CONSULTANT', 'TRAINEE', 'SELF_EMPLOYED', 'OTHER')", name='ck_employee_previous_employment_employment_type_enum'),
        CheckConstraint('((employment_end_date is null) or (employment_end_date >= employment_start_date))', name='ck_employee_previous_employment_previous_employment_dates'),
        CheckConstraint('((last_drawn_salary is null) or (last_drawn_salary >= 0))', name='ck_employee_previous_employment_previous_employment_salary'),
        CheckConstraint('(experience_days >= 0)', name='ck_employee_previous_employment_employee_previous_emp_db02c3'),
    )


class EmployeeQualification(Base):
    __tablename__ = 'employee_qualification'
    qualification_level_id = mapped_column(Integer, ForeignKey('qualification_level.qualification_level_id'), nullable=False)
    study_mode_id = mapped_column(SmallInteger, ForeignKey('study_mode.study_mode_id'))
    employee_qualification_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    degree_certificate_name = mapped_column(String(250), nullable=False)
    specialization = mapped_column(String(200))
    course_program_name = mapped_column(String(250))
    start_date = mapped_column(Date)
    start_year = mapped_column(SmallInteger)
    completion_date = mapped_column(Date)
    completion_year = mapped_column(SmallInteger)
    passing_year = mapped_column(SmallInteger)
    registration_roll_number = mapped_column(String(100))
    result = mapped_column(String(100))
    class_grade = mapped_column(String(100))
    cgpa = mapped_column(Numeric(6, 3))
    cgpa_scale = mapped_column(Numeric(6, 3))
    percentage = mapped_column(Numeric(5, 2))
    maximum_marks = mapped_column(Numeric(10, 2))
    marks_obtained = mapped_column(Numeric(10, 2))
    qualification_status = mapped_column(String(15), nullable=False, server_default=text("'COMPLETED'"))
    is_highest_qualification = mapped_column(Boolean, nullable=False, server_default=text("false"))
    remarks = mapped_column(String(1000))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = mapped_column(DateTime(timezone=True))
    awarding_body_id = mapped_column(BigInteger, ForeignKey('awarding_body.awarding_body_id'))
    created_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    education_institution_id = mapped_column(BigInteger, ForeignKey('education_institution.education_institution_id'))
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    updated_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    __table_args__ = (
        UniqueConstraint('employee_qualification_id', 'employee_id', name='uq_employee_qualification_employee_qualification_id_e_d4b7c4'),
        Index('ix_employee_qualification_awarding_body_id', 'awarding_body_id'),
        Index('ix_employee_qualification_created_by_user_id', 'created_by_user_id'),
        Index('ix_employee_qualification_employee_id', 'employee_id'),
        Index('ix_employee_qualification_education_institution_id', 'education_institution_id'),
        Index('ix_employee_qualification_qualification_level_id', 'qualification_level_id'),
        Index('ix_employee_qualification_study_mode_id', 'study_mode_id'),
        Index('ix_employee_qualification_updated_by_user_id', 'updated_by_user_id'),
        CheckConstraint("qualification_status IN ('COMPLETED', 'PURSUING', 'AWAITING_RESULT', 'DISCONTINUED', 'OTHER')", name='ck_employee_qualification_qualification_status_enum'),
        CheckConstraint('((cgpa is null) or (cgpa >= 0))', name='ck_employee_qualification_employee_qualification_cgpa'),
        CheckConstraint('((cgpa is null) or (cgpa_scale is null) or (cgpa <= cgpa_scale))', name='ck_employee_qualification_employee_qualification_cgpa_range'),
        CheckConstraint('((cgpa_scale is null) or (cgpa_scale > 0))', name='ck_employee_qualification_employee_qualification_cgpa_scale'),
        CheckConstraint('((completion_date is null) or (start_date is null) or (completion_date >= start_date))', name='ck_employee_qualification_employee_qualification_dates'),
        CheckConstraint('((marks_obtained is null) or (maximum_marks is null) or ((marks_obtained >= 0) and (marks_obtained <= maximum_marks) and (maximum_marks >= 0)))', name='ck_employee_qualification_employee_qualification_marks'),
        CheckConstraint('((percentage is null) or ((percentage >= 0) and (percentage <= 100)))', name='ck_employee_qualification_employee_qualification_percentage'),
        CheckConstraint('(start_year >= 0)', name='ck_employee_qualification_employee_qualification_chk_1'),
        CheckConstraint('(completion_year >= 0)', name='ck_employee_qualification_employee_qualification_chk_2'),
        CheckConstraint('(passing_year >= 0)', name='ck_employee_qualification_employee_qualification_chk_3'),
    )


class PreviousOrganization(Base):
    __tablename__ = 'previous_organization'
    previous_organization_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    previous_organization_type_id = mapped_column(SmallInteger, ForeignKey('previous_organization_type.previous_organization_type_id'))
    organization_name = mapped_column(String(250), nullable=False)
    address_line_1 = mapped_column(String(200))
    address_line_2 = mapped_column(String(200))
    city = mapped_column(String(100))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    postal_code = mapped_column(String(12))
    phone = mapped_column(String(25))
    email = mapped_column(String(254))
    website_url = mapped_column(String(255))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('organization_name', 'city', 'country_id', name='uq_previous_organization_organization_name_city_country_id'),
        Index('ix_previous_organization_country_id', 'country_id'),
        Index('ix_previous_organization_state_id', 'state_id'),
        Index('ix_previous_organization_previous_organization_type_id', 'previous_organization_type_id'),
    )


class PreviousOrganizationType(Base):
    __tablename__ = 'previous_organization_type'
    previous_organization_type_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    type_code = mapped_column(String(40), nullable=False)
    type_name = mapped_column(String(120), nullable=False)
    classification = mapped_column(String(13), nullable=False, server_default=text("'OTHER'"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('type_code', name='uq_previous_organization_type_type_code'),
        UniqueConstraint('type_name', name='uq_previous_organization_type_type_name'),
        CheckConstraint("classification IN ('INDUSTRY', 'ACADEMIC', 'GOVERNMENT', 'PRIVATE', 'PUBLIC_SECTOR', 'NGO', 'SELF_EMPLOYED', 'OTHER')", name='ck_previous_organization_type_classification_enum'),
    )


class QualificationLevel(Base):
    __tablename__ = 'qualification_level'
    qualification_level_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    level_code = mapped_column(String(40), nullable=False)
    level_name = mapped_column(String(120), nullable=False)
    display_order = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_terminal_degree = mapped_column(Boolean, nullable=False, server_default=text("false"))
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('level_code', name='uq_qualification_level_level_code'),
        UniqueConstraint('level_name', name='uq_qualification_level_level_name'),
    )


class StudyMode(Base):
    __tablename__ = 'study_mode'
    study_mode_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    mode_code = mapped_column(String(30), nullable=False)
    mode_name = mapped_column(String(100), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('mode_code', name='uq_study_mode_mode_code'),
        UniqueConstraint('mode_name', name='uq_study_mode_mode_name'),
    )
