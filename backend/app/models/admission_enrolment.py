"""SQLAlchemy models for the admission_enrolment domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class AdmissionApplicant(Base):
    __tablename__ = 'admission_applicant'
    version = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    admission_applicant_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    first_name = mapped_column(String(100), nullable=False)
    middle_name = mapped_column(String(100))
    last_name = mapped_column(String(100))
    display_name = mapped_column(String(250), nullable=False)
    date_of_birth = mapped_column(Date)
    primary_email = mapped_column(String(254))
    primary_phone = mapped_column(String(25))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    canonical_student_id = mapped_column(BigInteger, ForeignKey('student.student_id'))
    caste_id = mapped_column(Integer, ForeignKey('caste.caste_id'))
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    gender_id = mapped_column(SmallInteger, ForeignKey('gender.gender_id'))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    nationality_country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    social_category_id = mapped_column(Integer, ForeignKey('social_category.social_category_id'))
    sub_caste_id = mapped_column(Integer, ForeignKey('sub_caste.sub_caste_id'))
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        Index('ix_admission_applicant_canonical_student_id', 'canonical_student_id'),
        Index('ix_admission_applicant_caste_id', 'caste_id'),
        Index('ix_admission_applicant_created_by_id', 'created_by_id'),
        Index('ix_admission_applicant_gender_id', 'gender_id'),
        Index('ix_admission_applicant_nationality_country_id', 'nationality_country_id'),
        Index('ix_admission_applicant_social_category_id', 'social_category_id'),
        Index('ix_admission_applicant_sub_caste_id', 'sub_caste_id'),
        Index('ix_admission_applicant_updated_by_id', 'updated_by_id'),
        Index('ix_admission_applicant_institution_id_primary_email', 'institution_id', 'primary_email'),
        Index('ix_admission_applicant_institution_id_display_name', 'institution_id', 'display_name'),
        Index('ix_admission_applicant_institution_id_primary_phone', 'institution_id', 'primary_phone'),
        CheckConstraint('(version >= 0)', name='ck_admission_applicant_admission_applicant_chk_1'),
    )


class AdmissionApplication(Base):
    __tablename__ = 'admission_application'
    version = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    application_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_number = mapped_column(String(30), nullable=False)
    application_date = mapped_column(Date, nullable=False)
    application_status = mapped_column(String(12), nullable=False, server_default=text("'DRAFT'"))
    eligibility_status = mapped_column(String(10), nullable=False, server_default=text("'PENDING'"))
    remarks = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    academic_year_id = mapped_column(Integer, ForeignKey('academic_year.academic_year_id'), nullable=False)
    admission_applicant_id = mapped_column(BigInteger, ForeignKey('admission_applicant.admission_applicant_id'), nullable=False)
    admission_category_id = mapped_column(Integer, ForeignKey('admission_category.admission_category_id'))
    admitted_student_id = mapped_column(BigInteger, ForeignKey('student.student_id'))
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'), nullable=False)
    reviewer_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    specialization_id = mapped_column(Integer, ForeignKey('programme_specialization.specialization_id'))
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['specialization_id', 'programme_id'], ['programme_specialization.specialization_id', 'programme_specialization.programme_id']),
        UniqueConstraint('application_number', name='uq_admission_application_application_number'),
        UniqueConstraint('application_id', 'admitted_student_id', name='uq_admission_application_application_id_admitted_student_id'),
        Index('ix_admission_application_academic_year_id', 'academic_year_id'),
        Index('ix_admission_application_admission_applicant_id', 'admission_applicant_id'),
        Index('ix_admission_application_admission_category_id', 'admission_category_id'),
        Index('ix_admission_application_admitted_student_id', 'admitted_student_id'),
        Index('ix_admission_application_created_by_id', 'created_by_id'),
        Index('ix_admission_application_reviewer_id', 'reviewer_id'),
        Index('ix_admission_application_updated_by_id', 'updated_by_id'),
        Index('ix_admission_application_specialization_id_programme_id', 'specialization_id', 'programme_id'),
        Index('ix_admission_application_programme_id_academic_year_i_567347', 'programme_id', 'academic_year_id', 'application_status', 'application_id'),
        CheckConstraint('(version >= 0)', name='ck_admission_application_admission_application_chk_1'),
        CheckConstraint("(((admitted_student_id is not null) and (application_status = 'ADMITTED')) or ((application_status <> 'ADMITTED') and (admitted_student_id is null)))", name='ck_admission_application_m6_application_conversion'),
        CheckConstraint("((application_status not in ('ELIGIBLE','SELECTED','ADMITTED')) or (eligibility_status = 'ELIGIBLE'))", name='ck_admission_application_m6_application_eligible'),
    )


class EnrolmentStatusHistory(Base):
    __tablename__ = 'enrolment_status_history'
    occurred_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source = mapped_column(String(30), nullable=False)
    request_id = mapped_column(String(36), nullable=False)
    sequence_number = mapped_column(BigInteger, nullable=False)
    enrolment_status_history_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    old_status = mapped_column(String(11))
    new_status = mapped_column(String(11), nullable=False)
    effective_date = mapped_column(Date, nullable=False)
    reason = mapped_column(String(500), nullable=False)
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    correction_of_id = mapped_column(BigInteger, ForeignKey('enrolment_status_history.enrolment_status_history_id'))
    enrolment_id = mapped_column(BigInteger, ForeignKey('student_programme_enrolment.enrolment_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('enrolment_id', 'sequence_number', name='uq_enrolment_status_history_enrolment_id_sequence_number'),
        Index('ix_enrolment_status_history_actor_id', 'actor_id'),
        Index('ix_enrolment_status_history_correction_of_id', 'correction_of_id'),
        Index('ix_enrolment_status_history_enrolment_id_effective_da_d7c544', 'enrolment_id', 'effective_date', 'sequence_number'),
        CheckConstraint("(reason <> '')", name='ck_enrolment_status_history_m6_history_reason'),
        CheckConstraint('(sequence_number > 0)', name='ck_enrolment_status_history_m6_history_sequence'),
        CheckConstraint('(sequence_number >= 0)', name='ck_enrolment_status_history_enrolment_status_history_chk_1'),
    )


class AdmissionFeeClearance(Base):
    __tablename__ = 'admission_fee_clearance'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reference = mapped_column(String(150), nullable=False)
    recorded_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    application_version = mapped_column(BigInteger, nullable=False)
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    application_id = mapped_column(BigInteger, ForeignKey('admission_application.application_id'), nullable=False)
    __table_args__ = (
        Index('ix_admission_fee_clearance_actor_id', 'actor_id'),
        Index('ix_admission_fee_clearance_application_id', 'application_id'),
        CheckConstraint('(application_version >= 0)', name='ck_admission_fee_clearance_platform_admission_fee_cle_9face4'),
    )


class StudentProgrammeEnrolment(Base):
    __tablename__ = 'student_programme_enrolment'
    version = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    enrolment_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admission_date = mapped_column(Date, nullable=False)
    expected_completion_date = mapped_column(Date)
    enrolment_status = mapped_column(String(11), nullable=False, server_default=text("'ACTIVE'"))
    admission_academic_year_id = mapped_column(Integer, ForeignKey('academic_year.academic_year_id'), nullable=False)
    admission_category_id = mapped_column(Integer, ForeignKey('admission_category.admission_category_id'))
    admission_semester_id = mapped_column(SmallInteger, ForeignKey('semester.semester_id'), nullable=False)
    application_id = mapped_column(BigInteger, ForeignKey('admission_application.application_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    curriculum_scheme_id = mapped_column(Integer, ForeignKey('curriculum_scheme.curriculum_scheme_id'), nullable=False)
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'), nullable=False)
    specialization_id = mapped_column(Integer, ForeignKey('programme_specialization.specialization_id'))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    transfer_from_id = mapped_column(BigInteger, ForeignKey('student_programme_enrolment.enrolment_id'))
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['application_id', 'student_id'], ['admission_application.application_id', 'admission_application.admitted_student_id']),
        ForeignKeyConstraint(['curriculum_scheme_id', 'programme_id'], ['curriculum_scheme.curriculum_scheme_id', 'curriculum_scheme.programme_id']),
        ForeignKeyConstraint(['specialization_id', 'programme_id'], ['programme_specialization.specialization_id', 'programme_specialization.programme_id']),
        UniqueConstraint('application_id', name='uq_student_programme_enrolment_application_id'),
        UniqueConstraint('transfer_from_id', name='uq_student_programme_enrolment_transfer_from_id'),
        UniqueConstraint('enrolment_id', 'programme_id', name='uq_student_programme_enrolment_enrolment_id_programme_id'),
        UniqueConstraint('student_id', 'programme_id', 'admission_academic_year_id', name='uq_student_programme_enrolment_student_id_programme_i_90543a'),
        Index('ix_student_programme_enrolment_application_id_student_id', 'application_id', 'student_id'),
        Index('ix_student_programme_enrolment_curriculum_scheme_id_p_31928e', 'curriculum_scheme_id', 'programme_id'),
        Index('ix_student_programme_enrolment_specialization_id_prog_56eecf', 'specialization_id', 'programme_id'),
        Index('ix_student_programme_enrolment_programme_id_enrolment_95a214', 'programme_id', 'enrolment_status', 'admission_academic_year_id'),
        Index('ix_student_programme_enrolment_admission_academic_year_id', 'admission_academic_year_id'),
        Index('ix_student_programme_enrolment_admission_category_id', 'admission_category_id'),
        Index('ix_student_programme_enrolment_admission_semester_id', 'admission_semester_id'),
        Index('ix_student_programme_enrolment_created_by_id', 'created_by_id'),
        Index('ix_student_programme_enrolment_updated_by_id', 'updated_by_id'),
        CheckConstraint('((expected_completion_date is null) or (expected_completion_date >= admission_date))', name='ck_student_programme_enrolment_m6_enrolment_completion'),
        CheckConstraint('(version >= 0)', name='ck_student_programme_enrolment_student_programme_enro_a88376'),
    )
