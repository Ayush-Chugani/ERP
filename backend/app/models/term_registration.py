"""SQLAlchemy models for the term_registration domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class ClassBatch(Base):
    __tablename__ = 'class_batch'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    class_batch_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_code = mapped_column(String(20), nullable=False)
    batch_name = mapped_column(String(100))
    capacity = mapped_column(Integer)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    class_section_id = mapped_column(BigInteger, ForeignKey('class_section.class_section_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('class_section_id', 'batch_code', name='uq_class_batch_class_section_id_batch_code'),
        UniqueConstraint('class_batch_id', 'class_section_id', name='uq_class_batch_class_batch_id_class_section_id'),
        Index('ix_class_batch_created_by_id', 'created_by_id'),
        Index('ix_class_batch_updated_by_id', 'updated_by_id'),
        CheckConstraint('((capacity is null) or (capacity > 0))', name='ck_class_batch_m7_batch_capacity'),
        CheckConstraint('(version >= 0)', name='ck_class_batch_class_batch_chk_1'),
        CheckConstraint('(capacity >= 0)', name='ck_class_batch_class_batch_chk_2'),
    )


class ClassSection(Base):
    __tablename__ = 'class_section'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    class_section_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    section_code = mapped_column(String(20), nullable=False)
    section_name = mapped_column(String(100))
    capacity = mapped_column(Integer)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    home_room_id = mapped_column(Integer, ForeignKey('room.room_id'))
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    programme_term_offering_id = mapped_column(BigInteger, ForeignKey('programme_term_offering.programme_term_offering_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('programme_term_offering_id', 'section_code', name='uq_class_section_programme_term_offering_id_section_code'),
        UniqueConstraint('class_section_id', 'programme_term_offering_id', name='uq_class_section_class_section_id_programme_term_offering_id'),
        Index('ix_class_section_created_by_id', 'created_by_id'),
        Index('ix_class_section_home_room_id', 'home_room_id'),
        Index('ix_class_section_updated_by_id', 'updated_by_id'),
        CheckConstraint('((capacity is null) or (capacity > 0))', name='ck_class_section_m7_section_capacity'),
        CheckConstraint('(version >= 0)', name='ck_class_section_class_section_chk_1'),
        CheckConstraint('(capacity >= 0)', name='ck_class_section_class_section_chk_2'),
    )


class CourseOffering(Base):
    __tablename__ = 'course_offering'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    course_offering_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    offering_code = mapped_column(String(50), nullable=False)
    registration_capacity = mapped_column(Integer)
    status = mapped_column(String(9), nullable=False)
    course_id = mapped_column(Integer, ForeignKey('course_catalog.course_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    curriculum_course_id = mapped_column(BigInteger, ForeignKey('curriculum_course.curriculum_course_id'))
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    programme_term_offering_id = mapped_column(BigInteger, ForeignKey('programme_term_offering.programme_term_offering_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['curriculum_course_id', 'course_id'], ['curriculum_course.curriculum_course_id', 'curriculum_course.course_id']),
        UniqueConstraint('offering_code', name='uq_course_offering_offering_code'),
        UniqueConstraint('programme_term_offering_id', 'course_id', name='uq_course_offering_programme_term_offering_id_course_id'),
        UniqueConstraint('course_offering_id', 'programme_term_offering_id', name='uq_course_offering_course_offering_id_programme_term__a32d4e'),
        Index('ix_course_offering_course_id', 'course_id'),
        Index('ix_course_offering_created_by_id', 'created_by_id'),
        Index('ix_course_offering_updated_by_id', 'updated_by_id'),
        Index('ix_course_offering_curriculum_course_id_course_id', 'curriculum_course_id', 'course_id'),
        CheckConstraint('((registration_capacity is null) or (registration_capacity > 0))', name='ck_course_offering_m7_course_capacity'),
        CheckConstraint("(status in ('PLANNED','OPEN','ACTIVE','COMPLETED','CANCELLED'))", name='ck_course_offering_m7_course_status'),
        CheckConstraint('(version >= 0)', name='ck_course_offering_course_offering_chk_1'),
        CheckConstraint('(registration_capacity >= 0)', name='ck_course_offering_course_offering_chk_2'),
    )


class CourseOfferingSection(Base):
    __tablename__ = 'course_offering_section'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    course_offering_section_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_type = mapped_column(String(9), nullable=False)
    class_batch_id = mapped_column(BigInteger, ForeignKey('class_batch.class_batch_id'))
    class_section_id = mapped_column(BigInteger, ForeignKey('class_section.class_section_id'), nullable=False)
    course_offering_id = mapped_column(BigInteger, ForeignKey('course_offering.course_offering_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    programme_term_offering_id = mapped_column(BigInteger, ForeignKey('programme_term_offering.programme_term_offering_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['class_batch_id', 'class_section_id'], ['class_batch.class_batch_id', 'class_batch.class_section_id']),
        ForeignKeyConstraint(['course_offering_id', 'programme_term_offering_id'], ['course_offering.course_offering_id', 'course_offering.programme_term_offering_id']),
        ForeignKeyConstraint(['class_section_id', 'programme_term_offering_id'], ['class_section.class_section_id', 'class_section.programme_term_offering_id']),
        UniqueConstraint('course_offering_section_id', 'course_offering_id', name='uq_course_offering_section_course_offering_section_id_c85ef0'),
        UniqueConstraint('course_offering_section_id', 'programme_term_offering_id', name='uq_course_offering_section_course_offering_section_id_dff116'),
        UniqueConstraint('course_offering_section_id', 'session_type', name='uq_course_offering_section_course_offering_section_id_8c77bf'),
        Index('ix_course_offering_section_created_by_id', 'created_by_id'),
        Index('ix_course_offering_section_programme_term_offering_id', 'programme_term_offering_id'),
        Index('ix_course_offering_section_updated_by_id', 'updated_by_id'),
        Index('ix_course_offering_section_class_batch_id_class_section_id', 'class_batch_id', 'class_section_id'),
        Index('ix_course_offering_section_course_offering_id_program_9bebb9', 'course_offering_id', 'programme_term_offering_id'),
        Index('ix_course_offering_section_class_section_id_programme_e6a839', 'class_section_id', 'programme_term_offering_id'),
        CheckConstraint("(session_type in ('LECTURE','TUTORIAL','PRACTICAL','PROJECT','SEMINAR','OTHER'))", name='ck_course_offering_section_m7_mapping_session'),
        CheckConstraint('(version >= 0)', name='ck_course_offering_section_course_offering_section_chk_1'),
    )


class CourseOfferingSectionStudent(Base):
    __tablename__ = 'course_offering_section_student'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    course_offering_section_student_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_type = mapped_column(String(9), nullable=False)
    roster_status = mapped_column(String(11), nullable=False)
    effective_from = mapped_column(Date, nullable=False)
    effective_to = mapped_column(Date)
    course_offering_id = mapped_column(BigInteger, ForeignKey('course_offering.course_offering_id'), nullable=False)
    course_offering_section_id = mapped_column(BigInteger, ForeignKey('course_offering_section.course_offering_section_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    course_registration_id = mapped_column(BigInteger, ForeignKey('student_course_registration.course_registration_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['course_offering_section_id', 'session_type'], ['course_offering_section.course_offering_section_id', 'course_offering_section.session_type']),
        ForeignKeyConstraint(['course_registration_id', 'course_offering_id'], ['student_course_registration.course_registration_id', 'student_course_registration.course_offering_id']),
        ForeignKeyConstraint(['course_offering_section_id', 'course_offering_id'], ['course_offering_section.course_offering_section_id', 'course_offering_section.course_offering_id']),
        UniqueConstraint('course_offering_section_id', 'course_registration_id', 'effective_from', name='uq_course_offering_section_student_course_offering_se_27d995'),
        UniqueConstraint('course_offering_section_student_id', 'course_offering_section_id', name='uq_course_offering_section_student_course_offering_se_15eded'),
        Index('ix_course_offering_section_student_course_offering_id', 'course_offering_id'),
        Index('ix_course_offering_section_student_created_by_id', 'created_by_id'),
        Index('ix_course_offering_section_student_updated_by_id', 'updated_by_id'),
        Index('ix_course_offering_section_student_course_offering_se_cb33fd', 'course_offering_section_id', 'session_type'),
        Index('ix_course_offering_section_student_course_registratio_1856ce', 'course_registration_id', 'course_offering_id'),
        Index('ix_course_offering_section_student_course_offering_se_d4603e', 'course_offering_section_id', 'course_offering_id'),
        Index('ix_course_offering_section_student_course_offering_se_675cb0', 'course_offering_section_id', 'roster_status', 'effective_from', 'effective_to'),
        CheckConstraint('((effective_to is null) or (effective_to > effective_from))', name='ck_course_offering_section_student_course_section_stu_3f6a45'),
        CheckConstraint("((roster_status <> 'ACTIVE') or (effective_to is null))", name='ck_course_offering_section_student_m7_roster_open'),
        CheckConstraint("(roster_status in ('ACTIVE','DROPPED','TRANSFERRED','COMPLETED'))", name='ck_course_offering_section_student_m7_roster_status'),
        CheckConstraint('(version >= 0)', name='ck_course_offering_section_student_course_offering_se_6fc5c7'),
    )


class RegistrationPolicy(Base):
    __tablename__ = 'registration_policy'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    maximum_credits = mapped_column(Numeric(6, 1), nullable=False)
    minimum_credits = mapped_column(Numeric(6, 1), nullable=False)
    version = mapped_column(BigInteger, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('programme_id', name='uq_registration_policy_programme_id'),
        Index('ix_registration_policy_updated_by_id', 'updated_by_id'),
        CheckConstraint('((maximum_credits > 0) and (minimum_credits >= 0) and (minimum_credits <= maximum_credits))', name='ck_registration_policy_m7_credit_policy'),
        CheckConstraint('(version >= 0)', name='ck_registration_policy_platform_registration_policy_chk_1'),
    )


class RegistrationProgression(Base):
    __tablename__ = 'registration_progression'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    enrolment_version = mapped_column(BigInteger, nullable=False)
    offering_version = mapped_column(BigInteger, nullable=False)
    reason = mapped_column(String(500), nullable=False)
    approved_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    enrolment_id = mapped_column(BigInteger, ForeignKey('student_programme_enrolment.enrolment_id'), nullable=False)
    offering_id = mapped_column(BigInteger, ForeignKey('programme_term_offering.programme_term_offering_id'), nullable=False)
    __table_args__ = (
        Index('ix_registration_progression_enrolment_id_offering_id__00579b', 'enrolment_id', 'offering_id', 'enrolment_version', 'offering_version'),
        Index('ix_registration_progression_actor_id', 'actor_id'),
        Index('ix_registration_progression_offering_id', 'offering_id'),
        CheckConstraint('(enrolment_version >= 0)', name='ck_registration_progression_platform_registration_pro_7f888d'),
        CheckConstraint('(offering_version >= 0)', name='ck_registration_progression_platform_registration_pro_fe9d51'),
    )


class ProgrammeTermOffering(Base):
    __tablename__ = 'programme_term_offering'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    programme_term_offering_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    status = mapped_column(String(17), nullable=False)
    academic_term_id = mapped_column(Integer, ForeignKey('academic_term.academic_term_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    curriculum_scheme_id = mapped_column(Integer, ForeignKey('curriculum_scheme.curriculum_scheme_id'), nullable=False)
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'), nullable=False)
    semester_id = mapped_column(SmallInteger, ForeignKey('semester.semester_id'), nullable=False)
    specialization_id = mapped_column(Integer, ForeignKey('programme_specialization.specialization_id'))
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['curriculum_scheme_id', 'programme_id'], ['curriculum_scheme.curriculum_scheme_id', 'curriculum_scheme.programme_id']),
        ForeignKeyConstraint(['specialization_id', 'programme_id'], ['programme_specialization.specialization_id', 'programme_specialization.programme_id']),
        UniqueConstraint('programme_term_offering_id', 'programme_id', name='uq_programme_term_offering_programme_term_offering_id_0bd199'),
        Index('ix_programme_term_offering_curriculum_scheme_id_programme_id', 'curriculum_scheme_id', 'programme_id'),
        Index('ix_programme_term_offering_specialization_id_programme_id', 'specialization_id', 'programme_id'),
        Index('ix_programme_term_offering_created_by_id', 'created_by_id'),
        Index('ix_programme_term_offering_programme_id', 'programme_id'),
        Index('ix_programme_term_offering_semester_id', 'semester_id'),
        Index('ix_programme_term_offering_updated_by_id', 'updated_by_id'),
        CheckConstraint("(status in ('PLANNED','REGISTRATION_OPEN','ACTIVE','COMPLETED','CANCELLED'))", name='ck_programme_term_offering_m7_offering_status'),
        CheckConstraint('(version >= 0)', name='ck_programme_term_offering_programme_term_offering_chk_1'),
    )


class StudentCourseRegistration(Base):
    __tablename__ = 'student_course_registration'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    course_registration_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    registration_type = mapped_column(String(15), nullable=False)
    registration_date = mapped_column(Date, nullable=False)
    registration_status = mapped_column(String(10), nullable=False)
    course_offering_id = mapped_column(BigInteger, ForeignKey('course_offering.course_offering_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    programme_term_offering_id = mapped_column(BigInteger, ForeignKey('programme_term_offering.programme_term_offering_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    term_registration_id = mapped_column(BigInteger, ForeignKey('student_term_registration.term_registration_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['course_offering_id', 'programme_term_offering_id'], ['course_offering.course_offering_id', 'course_offering.programme_term_offering_id']),
        ForeignKeyConstraint(['term_registration_id', 'programme_term_offering_id'], ['student_term_registration.term_registration_id', 'student_term_registration.programme_term_offering_id']),
        UniqueConstraint('course_registration_id', 'course_offering_id', name='uq_student_course_registration_course_registration_id_77162a'),
        UniqueConstraint('term_registration_id', 'course_offering_id', name='uq_student_course_registration_term_registration_id_c_8cf395'),
        Index('ix_student_course_registration_course_offering_id_pro_8ab528', 'course_offering_id', 'programme_term_offering_id'),
        Index('ix_student_course_registration_term_registration_id_p_fc0143', 'term_registration_id', 'programme_term_offering_id'),
        Index('ix_student_course_registration_course_offering_id_reg_26b05f', 'course_offering_id', 'registration_status'),
        Index('ix_student_course_registration_created_by_id', 'created_by_id'),
        Index('ix_student_course_registration_programme_term_offering_id', 'programme_term_offering_id'),
        Index('ix_student_course_registration_updated_by_id', 'updated_by_id'),
        CheckConstraint("(registration_status in ('REGISTERED','APPROVED','DROPPED','WITHDRAWN','COMPLETED'))", name='ck_student_course_registration_m7_registration_status'),
        CheckConstraint("(registration_type in ('REGULAR','ELECTIVE','BACKLOG','REPEAT','IMPROVEMENT','AUDIT','CREDIT_TRANSFER'))", name='ck_student_course_registration_m7_registration_type'),
        CheckConstraint('(version >= 0)', name='ck_student_course_registration_student_course_registr_823421'),
    )


class StudentTermRegistration(Base):
    __tablename__ = 'student_term_registration'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    term_registration_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    roll_number = mapped_column(String(30))
    registration_date = mapped_column(Date, nullable=False)
    registration_status = mapped_column(String(10), nullable=False)
    class_batch_id = mapped_column(BigInteger, ForeignKey('class_batch.class_batch_id'))
    class_section_id = mapped_column(BigInteger, ForeignKey('class_section.class_section_id'))
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    enrolment_id = mapped_column(BigInteger, ForeignKey('student_programme_enrolment.enrolment_id'), nullable=False)
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'), nullable=False)
    programme_term_offering_id = mapped_column(BigInteger, ForeignKey('programme_term_offering.programme_term_offering_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['enrolment_id', 'programme_id'], ['student_programme_enrolment.enrolment_id', 'student_programme_enrolment.programme_id']),
        ForeignKeyConstraint(['programme_term_offering_id', 'programme_id'], ['programme_term_offering.programme_term_offering_id', 'programme_term_offering.programme_id']),
        ForeignKeyConstraint(['class_batch_id', 'class_section_id'], ['class_batch.class_batch_id', 'class_batch.class_section_id']),
        ForeignKeyConstraint(['class_section_id', 'programme_term_offering_id'], ['class_section.class_section_id', 'class_section.programme_term_offering_id']),
        UniqueConstraint('term_registration_id', 'programme_term_offering_id', name='uq_student_term_registration_term_registration_id_pro_7880f6'),
        UniqueConstraint('enrolment_id', 'programme_term_offering_id', name='uq_student_term_registration_enrolment_id_programme_t_7d3e30'),
        UniqueConstraint('programme_term_offering_id', 'roll_number', name='uq_student_term_registration_programme_term_offering__a1187c'),
        Index('ix_student_term_registration_enrolment_id_programme_id', 'enrolment_id', 'programme_id'),
        Index('ix_student_term_registration_programme_term_offering__5786c8', 'programme_term_offering_id', 'programme_id'),
        Index('ix_student_term_registration_class_batch_id_class_section_id', 'class_batch_id', 'class_section_id'),
        Index('ix_student_term_registration_class_section_id_program_eb789c', 'class_section_id', 'programme_term_offering_id'),
        Index('ix_student_term_registration_class_batch_id_registrat_6577f5', 'class_batch_id', 'registration_status'),
        Index('ix_student_term_registration_class_section_id_registr_c855d5', 'class_section_id', 'registration_status'),
        Index('ix_student_term_registration_created_by_id', 'created_by_id'),
        Index('ix_student_term_registration_programme_id', 'programme_id'),
        Index('ix_student_term_registration_updated_by_id', 'updated_by_id'),
        CheckConstraint("(registration_status in ('DRAFT','REGISTERED','APPROVED','CANCELLED','COMPLETED'))", name='ck_student_term_registration_m7_term_status'),
        CheckConstraint('((class_batch_id is null) or (class_section_id is not null))', name='ck_student_term_registration_term_registration_batch_section'),
        CheckConstraint('(version >= 0)', name='ck_student_term_registration_student_term_registration_chk_1'),
    )
