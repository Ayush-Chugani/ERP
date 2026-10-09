"""SQLAlchemy models for the assessments_results domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class AssessmentComponent(Base):
    __tablename__ = 'assessment_component'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    assessment_component_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    component_code = mapped_column(String(30), nullable=False)
    component_name = mapped_column(String(100), nullable=False)
    component_type = mapped_column(String(20), nullable=False)
    maximum_marks = mapped_column(Numeric(7, 2), nullable=False)
    weightage_percent = mapped_column(Numeric(5, 2))
    is_mandatory = mapped_column(Boolean, nullable=False, server_default=text("false"))
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    course_offering_id = mapped_column(BigInteger, ForeignKey('course_offering.course_offering_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('course_offering_id', 'component_code', name='uq_assessment_component_course_offering_id_component_code'),
        UniqueConstraint('assessment_component_id', 'course_offering_id', name='uq_assessment_component_assessment_component_id_cours_7fd965'),
        Index('ix_assessment_component_actor_id', 'actor_id'),
        CheckConstraint('(version >= 0)', name='ck_assessment_component_assessment_component_chk_1'),
        CheckConstraint('(maximum_marks > 0)', name='ck_assessment_component_m10_component_max'),
        CheckConstraint('((weightage_percent is null) or ((weightage_percent >= 0) and (weightage_percent <= 100)))', name='ck_assessment_component_m10_component_weight'),
    )


class AssessmentEvent(Base):
    __tablename__ = 'assessment_event'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    assessment_event_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_number = mapped_column(Integer, nullable=False)
    event_number = mapped_column(Integer)
    event_title = mapped_column(String(150), nullable=False)
    assessment_date = mapped_column(Date, nullable=False)
    start_time = mapped_column(Time)
    end_time = mapped_column(Time)
    maximum_marks = mapped_column(Numeric(7, 2), nullable=False)
    reduced_maximum_marks = mapped_column(Numeric(7, 2))
    details = mapped_column(Text, nullable=False, server_default=text("''"))
    status = mapped_column(String(9), nullable=False, server_default=text("'PLANNED'"))
    roster = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    assessment_component_id = mapped_column(BigInteger, ForeignKey('assessment_component.assessment_component_id'), nullable=False)
    course_offering_id = mapped_column(BigInteger, ForeignKey('course_offering.course_offering_id'), nullable=False)
    policy_id = mapped_column(BigInteger, ForeignKey('assessment_policy.id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['assessment_component_id', 'course_offering_id'], ['assessment_component.assessment_component_id', 'assessment_component.course_offering_id']),
        UniqueConstraint('assessment_event_id', 'course_offering_id', name='uq_assessment_event_assessment_event_id_course_offering_id'),
        Index('ix_assessment_event_actor_id', 'actor_id'),
        Index('ix_assessment_event_policy_id', 'policy_id'),
        Index('ix_assessment_event_assessment_component_id_course_of_43f1d5', 'assessment_component_id', 'course_offering_id'),
        Index('ix_assessment_event_course_offering_id_assessment_dat_6c4af6', 'course_offering_id', 'assessment_date', 'status'),
        CheckConstraint('(version >= 0)', name='ck_assessment_event_assessment_event_chk_1'),
        CheckConstraint('(attempt_number >= 0)', name='ck_assessment_event_assessment_event_chk_2'),
        CheckConstraint('(event_number >= 0)', name='ck_assessment_event_assessment_event_chk_3'),
        CheckConstraint('((attempt_number >= 1) and (attempt_number <= 255))', name='ck_assessment_event_m10_event_attempt'),
        CheckConstraint('((maximum_marks > 0) and ((reduced_maximum_marks is null) or ((reduced_maximum_marks > 0) and (reduced_maximum_marks <= maximum_marks))))', name='ck_assessment_event_m10_event_marks'),
        CheckConstraint('((start_time is null) or (end_time is null) or (end_time > start_time))', name='ck_assessment_event_m10_event_time'),
        CheckConstraint("(status in ('PLANNED','CONDUCTED','CANCELLED','PUBLISHED'))", name='ck_assessment_event_m10_event_status'),
    )


class GradeRule(Base):
    __tablename__ = 'grade_rule'
    grade_rule_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    grade_letter = mapped_column(String(5), nullable=False)
    grade_point = mapped_column(Numeric(4, 2), nullable=False)
    minimum_percentage = mapped_column(Numeric(5, 2), nullable=False)
    maximum_percentage = mapped_column(Numeric(5, 2), nullable=False)
    result_status = mapped_column(String(8), nullable=False)
    grade_scale_id = mapped_column(Integer, ForeignKey('grade_scale.grade_scale_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('grade_scale_id', 'grade_letter', name='uq_grade_rule_grade_scale_id_grade_letter'),
        CheckConstraint('((grade_point >= 0) and (maximum_percentage > minimum_percentage) and (maximum_percentage <= 100) and (minimum_percentage >= 0))', name='ck_grade_rule_m10_grade_range'),
    )


class GradeScale(Base):
    __tablename__ = 'grade_scale'
    grade_scale_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    scale_name = mapped_column(String(100), nullable=False)
    effective_from = mapped_column(Date, nullable=False)
    effective_to = mapped_column(Date)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('scale_name', name='uq_grade_scale_scale_name'),
        Index('ix_grade_scale_actor_id', 'actor_id'),
        Index('ix_grade_scale_institution_id', 'institution_id'),
        CheckConstraint('((effective_to is null) or (effective_to >= effective_from))', name='ck_grade_scale_m10_scale_dates'),
    )


class AssessmentPolicy(Base):
    __tablename__ = 'assessment_policy'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    number = mapped_column(Integer, nullable=False)
    rules = mapped_column(JSONB, nullable=False)
    reason = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    course_offering_id = mapped_column(BigInteger, ForeignKey('course_offering.course_offering_id'), nullable=False)
    grade_scale_id = mapped_column(Integer, ForeignKey('grade_scale.grade_scale_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('course_offering_id', 'number', name='uq_assessment_policy_course_offering_id_number'),
        Index('ix_assessment_policy_actor_id', 'actor_id'),
        Index('ix_assessment_policy_grade_scale_id', 'grade_scale_id'),
        CheckConstraint('(number >= 0)', name='ck_assessment_policy_platform_m10_policy_chk_1'),
    )


class ResultPublication(Base):
    __tablename__ = 'result_publication'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource = mapped_column(String(30), nullable=False)
    record_id = mapped_column(BigInteger, nullable=False)
    number = mapped_column(Integer, nullable=False)
    data = mapped_column(JSONB, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('resource', 'record_id', 'number', name='uq_result_publication_resource_record_id_number'),
        Index('ix_result_publication_actor_id', 'actor_id'),
        Index('ix_result_publication_institution_id', 'institution_id'),
        CheckConstraint('(record_id >= 0)', name='ck_result_publication_platform_m10_publication_chk_1'),
        CheckConstraint('(number >= 0)', name='ck_result_publication_platform_m10_publication_chk_2'),
    )


class StudentAssessmentMark(Base):
    __tablename__ = 'student_assessment_mark'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    student_assessment_mark_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attendance_status = mapped_column(String(11), nullable=False)
    marks_obtained = mapped_column(Numeric(7, 2))
    reduced_marks = mapped_column(Numeric(7, 2))
    remarks = mapped_column(String(500), nullable=False, server_default=text("''"))
    evaluated_at = mapped_column(DateTime(timezone=True))
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    assessment_event_id = mapped_column(BigInteger, ForeignKey('assessment_event.assessment_event_id'), nullable=False)
    course_offering_id = mapped_column(BigInteger, ForeignKey('course_offering.course_offering_id'), nullable=False)
    course_registration_id = mapped_column(BigInteger, ForeignKey('student_course_registration.course_registration_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['assessment_event_id', 'course_offering_id'], ['assessment_event.assessment_event_id', 'assessment_event.course_offering_id']),
        ForeignKeyConstraint(['course_registration_id', 'course_offering_id'], ['student_course_registration.course_registration_id', 'student_course_registration.course_offering_id']),
        UniqueConstraint('assessment_event_id', 'course_registration_id', name='uq_student_assessment_mark_assessment_event_id_course_1fc3dd'),
        Index('ix_student_assessment_mark_assessment_event_id_course_33000a', 'assessment_event_id', 'course_offering_id'),
        Index('ix_student_assessment_mark_course_registration_id_cou_63de6c', 'course_registration_id', 'course_offering_id'),
        Index('ix_student_assessment_mark_actor_id', 'actor_id'),
        Index('ix_student_assessment_mark_course_offering_id', 'course_offering_id'),
        CheckConstraint('((marks_obtained is null) or (marks_obtained >= 0))', name='ck_student_assessment_mark_m10_mark_raw'),
        CheckConstraint('((reduced_marks is null) or (reduced_marks >= 0))', name='ck_student_assessment_mark_m10_mark_reduced'),
        CheckConstraint('(version >= 0)', name='ck_student_assessment_mark_student_assessment_mark_chk_1'),
        CheckConstraint("(attendance_status in ('PRESENT','ABSENT','EXEMPTED','MALPRACTICE'))", name='ck_student_assessment_mark_m10_mark_status'),
    )


class StudentCourseResult(Base):
    __tablename__ = 'student_course_result'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    student_course_result_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_number = mapped_column(SmallInteger, nullable=False)
    internal_marks = mapped_column(Numeric(7, 2))
    external_marks = mapped_column(Numeric(7, 2))
    total_marks = mapped_column(Numeric(7, 2))
    grade_letter = mapped_column(String(5), nullable=False, server_default=text("''"))
    grade_point = mapped_column(Numeric(4, 2))
    credits_earned = mapped_column(Numeric(4, 1), nullable=False, server_default=text("0"))
    result_status = mapped_column(String(10), nullable=False)
    result_date = mapped_column(Date)
    remarks = mapped_column(String(500), nullable=False, server_default=text("''"))
    evidence = mapped_column(JSONB, nullable=False)
    state = mapped_column(String(10), nullable=False, server_default=text("'CALCULATED'"))
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    course_registration_id = mapped_column(BigInteger, ForeignKey('student_course_registration.course_registration_id'), nullable=False)
    policy_id = mapped_column(BigInteger, ForeignKey('assessment_policy.id'), nullable=False)
    is_withheld = mapped_column(Boolean, nullable=False, server_default=text("false"))
    __table_args__ = (
        UniqueConstraint('course_registration_id', 'attempt_number', name='uq_student_course_result_course_registration_id_attem_3a9fb2'),
        Index('ix_student_course_result_policy_id', 'policy_id'),
        Index('ix_student_course_result_actor_id', 'actor_id'),
        CheckConstraint('((attempt_number >= 1) and (attempt_number <= 255) and (credits_earned >= 0))', name='ck_student_course_result_m10_course_result'),
        CheckConstraint("(result_status in ('PASS','FAIL','ABSENT','WITHHELD','EXEMPTED','INCOMPLETE'))", name='ck_student_course_result_m10_course_status'),
        CheckConstraint('(version >= 0)', name='ck_student_course_result_student_course_result_chk_1'),
        CheckConstraint('(attempt_number >= 0)', name='ck_student_course_result_student_course_result_chk_2'),
        CheckConstraint("(state in ('CALCULATED','PUBLISHED','WITHHELD'))", name='ck_student_course_result_m10_course_state'),
    )


class StudentTermResult(Base):
    __tablename__ = 'student_term_result'
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    student_term_result_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    credits_registered = mapped_column(Numeric(6, 1), nullable=False, server_default=text("0"))
    credits_earned = mapped_column(Numeric(6, 1), nullable=False, server_default=text("0"))
    sgpa = mapped_column(Numeric(4, 2))
    cgpa = mapped_column(Numeric(4, 2))
    result_status = mapped_column(String(10), nullable=False)
    published_at = mapped_column(DateTime(timezone=True))
    state = mapped_column(String(10), nullable=False, server_default=text("'CALCULATED'"))
    evidence = mapped_column(JSONB, nullable=False)
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    term_registration_id = mapped_column(BigInteger, ForeignKey('student_term_registration.term_registration_id'), nullable=False)
    is_withheld = mapped_column(Boolean, nullable=False, server_default=text("false"))
    __table_args__ = (
        UniqueConstraint('term_registration_id', name='uq_student_term_result_term_registration_id'),
        Index('ix_student_term_result_actor_id', 'actor_id'),
        CheckConstraint('((credits_earned >= 0) and (credits_earned <= credits_registered) and (credits_registered >= 0))', name='ck_student_term_result_m10_term_credits'),
        CheckConstraint("(result_status in ('PASS','FAIL','PROMOTED','WITHHELD','INCOMPLETE'))", name='ck_student_term_result_m10_term_status'),
        CheckConstraint('(version >= 0)', name='ck_student_term_result_student_term_result_chk_1'),
        CheckConstraint("(state in ('CALCULATED','PUBLISHED','WITHHELD'))", name='ck_student_term_result_m10_term_state'),
    )
