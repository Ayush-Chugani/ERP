"""SQLAlchemy models for the teaching_timetable domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class FacultyCourseAssignment(Base):
    __tablename__ = 'faculty_course_assignment'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    faculty_assignment_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_role = mapped_column(String(18), nullable=False)
    workload_hours = mapped_column(Numeric(6, 2))
    start_date = mapped_column(Date, nullable=False)
    end_date = mapped_column(Date)
    assignment_status = mapped_column(String(9), nullable=False, server_default=text("'PLANNED'"))
    course_offering_section_id = mapped_column(BigInteger, ForeignKey('course_offering_section.course_offering_section_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    cross_department_authorized = mapped_column(Boolean, nullable=False, server_default=text("false"))
    __table_args__ = (
        UniqueConstraint('course_offering_section_id', 'employee_id', 'assignment_role', 'start_date', name='uq_faculty_course_assignment_course_offering_section__7c1221'),
        UniqueConstraint('faculty_assignment_id', 'course_offering_section_id', name='uq_faculty_course_assignment_faculty_assignment_id_co_88d3ba'),
        Index('ix_faculty_course_assignment_created_by_id', 'created_by_id'),
        Index('ix_faculty_course_assignment_updated_by_id', 'updated_by_id'),
        Index('ix_faculty_course_assignment_employee_id_assignment_s_f3f7f9', 'employee_id', 'assignment_status', 'start_date', 'end_date'),
        CheckConstraint('((end_date is null) or (end_date >= start_date))', name='ck_faculty_course_assignment_m8_assignment_dates'),
        CheckConstraint("(assignment_role in ('PRIMARY_INSTRUCTOR','CO_INSTRUCTOR','LAB_INSTRUCTOR','TUTOR','COORDINATOR','OTHER'))", name='ck_faculty_course_assignment_m8_assignment_role'),
        CheckConstraint("(assignment_status in ('PLANNED','ACTIVE','COMPLETED','CANCELLED'))", name='ck_faculty_course_assignment_m8_assignment_status'),
        CheckConstraint('((workload_hours is null) or (workload_hours > 0))', name='ck_faculty_course_assignment_m8_workload'),
        CheckConstraint('(version >= 0)', name='ck_faculty_course_assignment_faculty_course_assignment_chk_1'),
    )


class TimetableAvailability(Base):
    __tablename__ = 'timetable_availability'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    effective_from = mapped_column(Date, nullable=False)
    effective_to = mapped_column(Date, nullable=False)
    day_of_week = mapped_column(Integer, nullable=False)
    start_time = mapped_column(Time, nullable=False)
    end_time = mapped_column(Time, nullable=False)
    reason = mapped_column(String(500), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    room_id = mapped_column(Integer, ForeignKey('room.room_id'))
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        Index('ix_timetable_availability_created_by_id', 'created_by_id'),
        Index('ix_timetable_availability_employee_id', 'employee_id'),
        Index('ix_timetable_availability_institution_id', 'institution_id'),
        Index('ix_timetable_availability_updated_by_id', 'updated_by_id'),
        Index('ix_timetable_availability_room_id', 'room_id'),
        CheckConstraint('(end_time > start_time)', name='ck_timetable_availability_m8_availability_clock'),
        CheckConstraint('(effective_to >= effective_from)', name='ck_timetable_availability_m8_availability_dates'),
        CheckConstraint('((day_of_week >= 1) and (day_of_week <= 7))', name='ck_timetable_availability_m8_availability_day'),
        CheckConstraint('(((employee_id is null) and (room_id is not null)) or ((employee_id is not null) and (room_id is null)))', name='ck_timetable_availability_m8_availability_resource'),
        CheckConstraint('(version >= 0)', name='ck_timetable_availability_platform_m8_availability_chk_1'),
        CheckConstraint('(day_of_week >= 0)', name='ck_timetable_availability_platform_m8_availability_chk_2'),
    )


class TimetableException(Base):
    __tablename__ = 'timetable_exception'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sequence = mapped_column(Integer, nullable=False)
    kind = mapped_column(String(10), nullable=False)
    date = mapped_column(Date, nullable=False)
    start_time = mapped_column(Time, nullable=False)
    end_time = mapped_column(Time, nullable=False)
    reason = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    faculty_assignment_id = mapped_column(BigInteger, ForeignKey('faculty_course_assignment.faculty_assignment_id'), nullable=False)
    room_id = mapped_column(Integer, ForeignKey('room.room_id'), nullable=False)
    occurrence_id = mapped_column(BigInteger, ForeignKey('timetable_occurrence.id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('occurrence_id', 'sequence', name='uq_timetable_exception_occurrence_id_sequence'),
        Index('ix_timetable_exception_faculty_assignment_id', 'faculty_assignment_id'),
        Index('ix_timetable_exception_actor_id', 'actor_id'),
        Index('ix_timetable_exception_room_id', 'room_id'),
        CheckConstraint('(end_time > start_time)', name='ck_timetable_exception_m8_exception_clock'),
        CheckConstraint("(kind in ('CANCEL','MOVE','SUBSTITUTE'))", name='ck_timetable_exception_m8_exception_kind'),
        CheckConstraint('(sequence >= 0)', name='ck_timetable_exception_platform_m8_exception_chk_1'),
    )


class TimetableOccurrence(Base):
    __tablename__ = 'timetable_occurrence'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date = mapped_column(Date, nullable=False)
    start_time = mapped_column(Time, nullable=False)
    end_time = mapped_column(Time, nullable=False)
    student_ids = mapped_column(JSONB, nullable=False)
    course_offering_section_id = mapped_column(BigInteger, ForeignKey('course_offering_section.course_offering_section_id'), nullable=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    room_id = mapped_column(Integer, ForeignKey('room.room_id'), nullable=False)
    revision_id = mapped_column(BigInteger, ForeignKey('timetable_revision.id'), nullable=False)
    session_id = mapped_column(BigInteger, ForeignKey('timetable_session.timetable_session_id'), nullable=False)
    class_section_id = mapped_column(BigInteger, ForeignKey('class_section.class_section_id'), nullable=False)
    class_batch_id = mapped_column(BigInteger, ForeignKey('class_batch.class_batch_id'))
    __table_args__ = (
        UniqueConstraint('session_id', 'date', name='uq_timetable_occurrence_session_id_date'),
        UniqueConstraint('id', 'course_offering_section_id', name='uq_timetable_occurrence_id_course_offering_section_id'),
        Index('ix_timetable_occurrence_date_employee_id_start_time', 'date', 'employee_id', 'start_time'),
        Index('ix_timetable_occurrence_date_room_id_start_time', 'date', 'room_id', 'start_time'),
        Index('ix_timetable_occurrence_class_batch_id', 'class_batch_id'),
        Index('ix_timetable_occurrence_class_section_id', 'class_section_id'),
        Index('ix_timetable_occurrence_course_offering_section_id', 'course_offering_section_id'),
        Index('ix_timetable_occurrence_employee_id', 'employee_id'),
        Index('ix_timetable_occurrence_revision_id', 'revision_id'),
        Index('ix_timetable_occurrence_room_id', 'room_id'),
        CheckConstraint('(end_time > start_time)', name='ck_timetable_occurrence_m8_occurrence_clock'),
    )


class TimetablePlan(Base):
    __tablename__ = 'timetable_plan'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    name = mapped_column(String(150), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    programme_term_offering_id = mapped_column(BigInteger, ForeignKey('programme_term_offering.programme_term_offering_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('programme_term_offering_id', name='uq_timetable_plan_programme_term_offering_id'),
        Index('ix_timetable_plan_created_by_id', 'created_by_id'),
        Index('ix_timetable_plan_updated_by_id', 'updated_by_id'),
        CheckConstraint('(version >= 0)', name='ck_timetable_plan_platform_m8_plan_chk_1'),
    )


class TimetablePolicy(Base):
    __tablename__ = 'timetable_policy'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    weekly_limit = mapped_column(Numeric(6, 2), nullable=False)
    require_competency = mapped_column(Boolean, nullable=False, server_default=text("false"))
    max_sessions = mapped_column(Integer, nullable=False)
    max_solver_jobs = mapped_column(Integer, nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('institution_id', name='uq_timetable_policy_institution_id'),
        Index('ix_timetable_policy_created_by_id', 'created_by_id'),
        Index('ix_timetable_policy_updated_by_id', 'updated_by_id'),
        CheckConstraint('((max_solver_jobs >= 1) and (max_solver_jobs <= 10))', name='ck_timetable_policy_m8_job_limit'),
        CheckConstraint('((max_sessions >= 1) and (max_sessions <= 500))', name='ck_timetable_policy_m8_session_limit'),
        CheckConstraint('(weekly_limit > 0)', name='ck_timetable_policy_m8_weekly_limit'),
        CheckConstraint('(version >= 0)', name='ck_timetable_policy_platform_m8_policy_chk_1'),
        CheckConstraint('(max_sessions >= 0)', name='ck_timetable_policy_platform_m8_policy_chk_2'),
        CheckConstraint('(max_solver_jobs >= 0)', name='ck_timetable_policy_platform_m8_policy_chk_3'),
    )


class TimetableRevision(Base):
    __tablename__ = 'timetable_revision'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    number = mapped_column(Integer, nullable=False)
    status = mapped_column(String(10), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    plan_id = mapped_column(BigInteger, ForeignKey('timetable_plan.id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('plan_id', 'number', name='uq_timetable_revision_plan_id_number'),
        Index('ix_timetable_revision_created_by_id', 'created_by_id'),
        Index('ix_timetable_revision_updated_by_id', 'updated_by_id'),
        CheckConstraint("(status in ('DRAFT','REVIEW','APPROVED','PUBLISHED','SUPERSEDED','WITHDRAWN','ARCHIVED'))", name='ck_timetable_revision_m8_revision_status'),
        CheckConstraint('(version >= 0)', name='ck_timetable_revision_platform_m8_revision_chk_1'),
        CheckConstraint('(number >= 0)', name='ck_timetable_revision_platform_m8_revision_chk_2'),
    )


class TimetableSolverJob(Base):
    __tablename__ = 'timetable_solver_job'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    status = mapped_column(String(10), nullable=False)
    seed = mapped_column(Integer, nullable=False)
    input_snapshot = mapped_column(JSONB, nullable=False)
    input_digest = mapped_column(String(64), nullable=False)
    result = mapped_column(JSONB, nullable=False)
    started_at = mapped_column(DateTime(timezone=True))
    finished_at = mapped_column(DateTime(timezone=True))
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    revision_id = mapped_column(BigInteger, ForeignKey('timetable_revision.id'), nullable=False)
    __table_args__ = (
        Index('ix_timetable_solver_job_status_created_at', 'status', 'created_at'),
        Index('ix_timetable_solver_job_created_by_id', 'created_by_id'),
        Index('ix_timetable_solver_job_revision_id', 'revision_id'),
        Index('ix_timetable_solver_job_updated_by_id', 'updated_by_id'),
        CheckConstraint("(status in ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED','ACCEPTED'))", name='ck_timetable_solver_job_m8_solver_status'),
        CheckConstraint('(version >= 0)', name='ck_timetable_solver_job_platform_m8_solver_job_chk_1'),
        CheckConstraint('(seed >= 0)', name='ck_timetable_solver_job_platform_m8_solver_job_chk_2'),
    )


class TimetableWorkloadOverride(Base):
    __tablename__ = 'timetable_workload_override'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    effective_from = mapped_column(Date, nullable=False)
    effective_to = mapped_column(Date, nullable=False)
    weekly_limit = mapped_column(Numeric(6, 2), nullable=False)
    reason = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    __table_args__ = (
        Index('ix_timetable_workload_override_actor_id', 'actor_id'),
        Index('ix_timetable_workload_override_employee_id', 'employee_id'),
        CheckConstraint('(effective_to >= effective_from)', name='ck_timetable_workload_override_m8_override_dates'),
        CheckConstraint('(weekly_limit > 0)', name='ck_timetable_workload_override_m8_override_limit'),
    )


class TimetableSession(Base):
    __tablename__ = 'timetable_session'
    version = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    timetable_session_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    day_of_week = mapped_column(Integer, nullable=False)
    effective_from = mapped_column(Date, nullable=False)
    effective_to = mapped_column(Date, nullable=False)
    course_offering_section_id = mapped_column(BigInteger, ForeignKey('course_offering_section.course_offering_section_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    faculty_assignment_id = mapped_column(BigInteger, ForeignKey('faculty_course_assignment.faculty_assignment_id'))
    revision_id = mapped_column(BigInteger, ForeignKey('timetable_revision.id'), nullable=False)
    room_id = mapped_column(Integer, ForeignKey('room.room_id'))
    time_slot_id = mapped_column(Integer, ForeignKey('time_slot.time_slot_id'), nullable=False)
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['faculty_assignment_id', 'course_offering_section_id'], ['faculty_course_assignment.faculty_assignment_id', 'faculty_course_assignment.course_offering_section_id']),
        UniqueConstraint('timetable_session_id', 'course_offering_section_id', name='uq_timetable_session_timetable_session_id_course_offe_82fb86'),
        Index('ix_timetable_session_faculty_assignment_id_course_off_63ec68', 'faculty_assignment_id', 'course_offering_section_id'),
        Index('ix_timetable_session_faculty_assignment_id_day_of_wee_897662', 'faculty_assignment_id', 'day_of_week', 'effective_from'),
        Index('ix_timetable_session_revision_id_course_offering_section_id', 'revision_id', 'course_offering_section_id'),
        Index('ix_timetable_session_room_id_day_of_week_effective_fr_cc52ff', 'room_id', 'day_of_week', 'effective_from', 'effective_to'),
        Index('ix_timetable_session_course_offering_section_id', 'course_offering_section_id'),
        Index('ix_timetable_session_created_by_id', 'created_by_id'),
        Index('ix_timetable_session_time_slot_id', 'time_slot_id'),
        Index('ix_timetable_session_updated_by_id', 'updated_by_id'),
        CheckConstraint('((day_of_week >= 1) and (day_of_week <= 7))', name='ck_timetable_session_day_of_week'),
        CheckConstraint('(effective_to >= effective_from)', name='ck_timetable_session_m8_session_dates'),
        CheckConstraint('(version >= 0)', name='ck_timetable_session_timetable_session_chk_1'),
        CheckConstraint('(day_of_week >= 0)', name='ck_timetable_session_timetable_session_chk_2'),
    )
