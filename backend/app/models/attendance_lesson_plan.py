"""SQLAlchemy models for the attendance_lesson_plan domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class AttendanceCorrectionRequest(Base):
    __tablename__ = 'attendance_correction_request'
    attendance_correction_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attendance_version = mapped_column(BigInteger, nullable=False)
    reason = mapped_column(String(1000), nullable=False)
    evidence_reference = mapped_column(String(200), nullable=False, server_default=text("''"))
    request_status = mapped_column(String(9), nullable=False, server_default=text("'PENDING'"))
    resolution_remarks = mapped_column(String(1000), nullable=False, server_default=text("''"))
    requested_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at = mapped_column(DateTime(timezone=True))
    version = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    old_status_id = mapped_column(SmallInteger, ForeignKey('attendance_status.attendance_status_id'), nullable=False)
    requested_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    requested_status_id = mapped_column(SmallInteger, ForeignKey('attendance_status.attendance_status_id'), nullable=False)
    resolved_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    attendance_id = mapped_column(BigInteger, ForeignKey('student_attendance.attendance_id'), nullable=False)
    __table_args__ = (
        Index('ix_attendance_correction_request_attendance_id', 'attendance_id'),
        Index('ix_attendance_correction_request_old_status_id', 'old_status_id'),
        Index('ix_attendance_correction_request_requested_by_id', 'requested_by_id'),
        Index('ix_attendance_correction_request_requested_status_id', 'requested_status_id'),
        Index('ix_attendance_correction_request_resolved_by_id', 'resolved_by_id'),
        Index('ix_attendance_correction_request_request_status_requested_at', 'request_status', 'requested_at'),
        CheckConstraint('(attendance_version >= 0)', name='ck_attendance_correction_request_attendance_correctio_56c777'),
        CheckConstraint('(version >= 0)', name='ck_attendance_correction_request_attendance_correctio_7b5687'),
        CheckConstraint("(request_status in ('PENDING','APPROVED','REJECTED','CANCELLED'))", name='ck_attendance_correction_request_m9_correction_state'),
    )


class AttendanceStatus(Base):
    __tablename__ = 'attendance_status'
    attendance_status_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    status_code = mapped_column(String(20), nullable=False)
    status_name = mapped_column(String(50), nullable=False)
    counts_as_present = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('status_code', name='uq_attendance_status_status_code'),
        UniqueConstraint('status_name', name='uq_attendance_status_status_name'),
    )


class ClassSession(Base):
    __tablename__ = 'class_session'
    class_session_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurrence_sequence = mapped_column(Integer, nullable=False, server_default=text("0"))
    session_date = mapped_column(Date, nullable=False)
    start_time = mapped_column(Time, nullable=False)
    end_time = mapped_column(Time, nullable=False)
    session_type = mapped_column(String(9), nullable=False)
    planned_topic = mapped_column(Text, nullable=False, server_default=text("''"))
    topic_covered = mapped_column(Text, nullable=False, server_default=text("''"))
    class_number = mapped_column(Integer, nullable=False)
    session_status = mapped_column(String(11), nullable=False, server_default=text("'PLANNED'"))
    register_status = mapped_column(String(9), nullable=False, server_default=text("'UNOPENED'"))
    version = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    finalized_at = mapped_column(DateTime(timezone=True))
    calendar_reference = mapped_column(String(200), nullable=False)
    course_offering_section_id = mapped_column(BigInteger, ForeignKey('course_offering_section.course_offering_section_id'), nullable=False)
    created_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    faculty_assignment_id = mapped_column(BigInteger, ForeignKey('faculty_course_assignment.faculty_assignment_id'), nullable=False)
    occurrence_id = mapped_column(BigInteger, ForeignKey('timetable_occurrence.id'))
    room_id = mapped_column(Integer, ForeignKey('room.room_id'), nullable=False)
    source_session_id = mapped_column(BigInteger, ForeignKey('class_session.class_session_id'))
    timetable_session_id = mapped_column(BigInteger, ForeignKey('timetable_session.timetable_session_id'))
    updated_by_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    policy_id = mapped_column(BigInteger, ForeignKey('attendance_policy.id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(['faculty_assignment_id', 'course_offering_section_id'], ['faculty_course_assignment.faculty_assignment_id', 'faculty_course_assignment.course_offering_section_id']),
        ForeignKeyConstraint(['occurrence_id', 'course_offering_section_id'], ['timetable_occurrence.id', 'timetable_occurrence.course_offering_section_id']),
        ForeignKeyConstraint(['course_offering_section_id', 'session_type'], ['course_offering_section.course_offering_section_id', 'course_offering_section.session_type']),
        ForeignKeyConstraint(['timetable_session_id', 'course_offering_section_id'], ['timetable_session.timetable_session_id', 'timetable_session.course_offering_section_id']),
        UniqueConstraint('occurrence_id', name='uq_class_session_occurrence_id'),
        UniqueConstraint('course_offering_section_id', 'session_date', 'start_time', name='uq_class_session_course_offering_section_id_session_d_c5ef5f'),
        UniqueConstraint('class_session_id', 'course_offering_section_id', name='uq_class_session_class_session_id_course_offering_section_id'),
        UniqueConstraint('course_offering_section_id', 'class_number', name='uq_class_session_course_offering_section_id_class_number'),
        Index('ix_class_session_created_by_id', 'created_by_id'),
        Index('ix_class_session_policy_id', 'policy_id'),
        Index('ix_class_session_room_id', 'room_id'),
        Index('ix_class_session_source_session_id', 'source_session_id'),
        Index('ix_class_session_updated_by_id', 'updated_by_id'),
        Index('ix_class_session_faculty_assignment_id_course_offerin_543b9e', 'faculty_assignment_id', 'course_offering_section_id'),
        Index('ix_class_session_occurrence_id_course_offering_section_id', 'occurrence_id', 'course_offering_section_id'),
        Index('ix_class_session_course_offering_section_id_session_type', 'course_offering_section_id', 'session_type'),
        Index('ix_class_session_timetable_session_id_course_offering_cda817', 'timetable_session_id', 'course_offering_section_id'),
        Index('ix_class_session_course_offering_section_id_session_d_24c32b', 'course_offering_section_id', 'session_date', 'register_status'),
        CheckConstraint('(end_time > start_time)', name='ck_class_session_class_session_time'),
        CheckConstraint("(register_status in ('UNOPENED','OPEN','FINALIZED','REOPENED'))", name='ck_class_session_m9_register_status'),
        CheckConstraint("(session_status in ('PLANNED','CONDUCTED','CANCELLED','RESCHEDULED'))", name='ck_class_session_m9_session_status'),
        CheckConstraint('(occurrence_sequence >= 0)', name='ck_class_session_class_session_chk_1'),
        CheckConstraint('(class_number >= 0)', name='ck_class_session_class_session_chk_2'),
        CheckConstraint('(version >= 0)', name='ck_class_session_class_session_chk_3'),
    )


class LessonCoverage(Base):
    __tablename__ = 'lesson_coverage'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    topic_key = mapped_column(String(50), nullable=False)
    percent = mapped_column(Numeric(5, 2), nullable=False)
    minutes = mapped_column(Integer, nullable=False)
    remarks = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    lesson_revision_id = mapped_column(BigInteger, ForeignKey('lesson_plan_revision.id'), nullable=False)
    session_id = mapped_column(BigInteger, ForeignKey('class_session.class_session_id'), nullable=False)
    __table_args__ = (
        Index('ix_lesson_coverage_actor_id', 'actor_id'),
        Index('ix_lesson_coverage_lesson_revision_id', 'lesson_revision_id'),
        Index('ix_lesson_coverage_session_id', 'session_id'),
        CheckConstraint('((minutes > 0) and (percent > 0) and (percent <= 100))', name='ck_lesson_coverage_m9_coverage'),
        CheckConstraint('(minutes >= 0)', name='ck_lesson_coverage_platform_m9_coverage_chk_1'),
    )


class LessonPlanRevision(Base):
    __tablename__ = 'lesson_plan_revision'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    number = mapped_column(Integer, nullable=False)
    topics = mapped_column(JSONB, nullable=False)
    reason = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    section_id = mapped_column(BigInteger, ForeignKey('course_offering_section.course_offering_section_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('section_id', 'number', name='uq_lesson_plan_revision_section_id_number'),
        Index('ix_lesson_plan_revision_actor_id', 'actor_id'),
        CheckConstraint('(number >= 0)', name='ck_lesson_plan_revision_platform_m9_lesson_revision_chk_1'),
    )


class AttendancePolicy(Base):
    __tablename__ = 'attendance_policy'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    number = mapped_column(Integer, nullable=False)
    basis = mapped_column(String(8), nullable=False)
    rules = mapped_column(JSONB, nullable=False)
    threshold = mapped_column(Numeric(5, 2), nullable=False)
    edit_days = mapped_column(Integer, nullable=False)
    correction_days = mapped_column(Integer, nullable=False)
    reason = mapped_column(String(500), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    section_id = mapped_column(BigInteger, ForeignKey('course_offering_section.course_offering_section_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('section_id', 'number', name='uq_attendance_policy_section_id_number'),
        Index('ix_attendance_policy_actor_id', 'actor_id'),
        CheckConstraint("(basis in ('SESSION','DURATION'))", name='ck_attendance_policy_m9_basis'),
        CheckConstraint('((threshold >= 0) and (threshold <= 100))', name='ck_attendance_policy_m9_threshold'),
        CheckConstraint('(number >= 0)', name='ck_attendance_policy_platform_m9_policy_chk_1'),
        CheckConstraint('(edit_days >= 0)', name='ck_attendance_policy_platform_m9_policy_chk_2'),
        CheckConstraint('(correction_days >= 0)', name='ck_attendance_policy_platform_m9_policy_chk_3'),
    )


class StudentAttendance(Base):
    __tablename__ = 'student_attendance'
    attendance_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    marked_at = mapped_column(DateTime(timezone=True))
    remarks = mapped_column(String(500), nullable=False, server_default=text("''"))
    version = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    credit = mapped_column(Numeric(12, 4))
    denominator = mapped_column(Numeric(12, 4))
    attendance_status_id = mapped_column(SmallInteger, ForeignKey('attendance_status.attendance_status_id'))
    class_session_id = mapped_column(BigInteger, ForeignKey('class_session.class_session_id'), nullable=False)
    course_offering_section_id = mapped_column(BigInteger, ForeignKey('course_offering_section.course_offering_section_id'), nullable=False)
    course_offering_section_student_id = mapped_column(BigInteger, ForeignKey('course_offering_section_student.course_offering_section_student_id'), nullable=False)
    marked_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    exclusion_reason = mapped_column(String(500), nullable=False, server_default=text("''"))
    is_eligible = mapped_column(Boolean, nullable=False, server_default=text("false"))
    __table_args__ = (
        ForeignKeyConstraint(['course_offering_section_student_id', 'course_offering_section_id'], ['course_offering_section_student.course_offering_section_student_id', 'course_offering_section_student.course_offering_section_id']),
        ForeignKeyConstraint(['class_session_id', 'course_offering_section_id'], ['class_session.class_session_id', 'class_session.course_offering_section_id']),
        UniqueConstraint('class_session_id', 'course_offering_section_student_id', name='uq_student_attendance_class_session_id_course_offerin_acc8d0'),
        UniqueConstraint('class_session_id', 'student_id', name='uq_student_attendance_class_session_id_student_id'),
        Index('ix_student_attendance_course_offering_section_student_d66301', 'course_offering_section_student_id', 'course_offering_section_id'),
        Index('ix_student_attendance_class_session_id_course_offerin_885226', 'class_session_id', 'course_offering_section_id'),
        Index('ix_student_attendance_student_id_class_session_id', 'student_id', 'class_session_id'),
        Index('ix_student_attendance_attendance_status_id', 'attendance_status_id'),
        Index('ix_student_attendance_course_offering_section_id', 'course_offering_section_id'),
        Index('ix_student_attendance_marked_by_user_id', 'marked_by_user_id'),
        CheckConstraint('(((credit is null) and (denominator is null)) or ((credit >= 0) and (denominator >= credit)))', name='ck_student_attendance_m9_contribution'),
        CheckConstraint('(version >= 0)', name='ck_student_attendance_student_attendance_chk_1'),
    )
