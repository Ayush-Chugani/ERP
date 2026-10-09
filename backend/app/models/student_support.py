"""SQLAlchemy models for the student_support domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class CounsellingSession(Base):
    __tablename__ = 'counselling_session'
    counselling_session_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mentor_assignment_id = mapped_column(BigInteger, ForeignKey('mentor_assignment.mentor_assignment_id'), nullable=False)
    session_date = mapped_column(DateTime(timezone=True), nullable=False)
    observations = mapped_column(Text)
    action_plan = mapped_column(Text)
    follow_up_date = mapped_column(Date)
    session_status = mapped_column(String(18), nullable=False, server_default=text("'COMPLETED'"))
    confidentiality_level = mapped_column(String(17), nullable=False, server_default=text("'RESTRICTED'"))
    __table_args__ = (
        Index('ix_counselling_session_mentor_assignment_id', 'mentor_assignment_id'),
        CheckConstraint("session_status IN ('SCHEDULED', 'COMPLETED', 'CANCELLED', 'FOLLOW_UP_REQUIRED')", name='ck_counselling_session_session_status_enum'),
        CheckConstraint("confidentiality_level IN ('NORMAL', 'RESTRICTED', 'HIGHLY_RESTRICTED')", name='ck_counselling_session_confidentiality_level_enum'),
    )


class Grievance(Base):
    __tablename__ = 'grievance'
    grievance_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    grievance_number = mapped_column(String(30), nullable=False)
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    grievance_category_id = mapped_column(Integer, ForeignKey('grievance_category.grievance_category_id'), nullable=False)
    department_id = mapped_column(Integer, ForeignKey('department.department_id'))
    submitted_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    subject = mapped_column(String(200), nullable=False)
    description = mapped_column(Text, nullable=False)
    priority = mapped_column(String(6), nullable=False, server_default=text("'NORMAL'"))
    status = mapped_column(String(12), nullable=False, server_default=text("'SUBMITTED'"))
    resolved_at = mapped_column(DateTime(timezone=True))
    resolution = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint('grievance_number', name='uq_grievance_grievance_number'),
        Index('ix_grievance_grievance_category_id', 'grievance_category_id'),
        Index('ix_grievance_department_id', 'department_id'),
        Index('ix_grievance_student_id', 'student_id'),
        CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH', 'URGENT')", name='ck_grievance_priority_enum'),
        CheckConstraint("status IN ('SUBMITTED', 'ASSIGNED', 'UNDER_REVIEW', 'RESOLVED', 'REJECTED', 'CLOSED')", name='ck_grievance_status_enum'),
    )


class GrievanceAction(Base):
    __tablename__ = 'grievance_action'
    grievance_action_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    grievance_id = mapped_column(BigInteger, ForeignKey('grievance.grievance_id'), nullable=False)
    action_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    action_type = mapped_column(String(50), nullable=False)
    action_notes = mapped_column(Text)
    new_status = mapped_column(String(30))
    __table_args__ = (
        Index('ix_grievance_action_grievance_id', 'grievance_id'),
    )


class GrievanceCategory(Base):
    __tablename__ = 'grievance_category'
    grievance_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(30), nullable=False)
    category_name = mapped_column(String(100), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_grievance_category_category_code'),
        UniqueConstraint('category_name', name='uq_grievance_category_category_name'),
    )


class MentorAssignment(Base):
    __tablename__ = 'mentor_assignment'
    mentor_assignment_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    start_date = mapped_column(Date, nullable=False)
    end_date = mapped_column(Date)
    assignment_status = mapped_column(String(9), nullable=False, server_default=text("'ACTIVE'"))
    __table_args__ = (
        Index('ix_mentor_assignment_employee_id', 'employee_id'),
        Index('ix_mentor_assignment_student_id', 'student_id'),
        CheckConstraint("assignment_status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')", name='ck_mentor_assignment_assignment_status_enum'),
    )
