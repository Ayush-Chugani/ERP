"""SQLAlchemy models for the staff_activities domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class StaffActivityAttachment(Base):
    __tablename__ = 'staff_activity_attachment'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category = mapped_column(String(40), nullable=False)
    title = mapped_column(String(200), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    file_object_id = mapped_column(BigInteger, ForeignKey('file_object.file_object_id'), nullable=False)
    replaces_id = mapped_column(BigInteger, ForeignKey('staff_activity_attachment.id'))
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('replaces_id', name='uq_staff_activity_attachment_replaces_id'),
        Index('ix_staff_activity_attachment_file_object_id', 'file_object_id'),
        Index('ix_staff_activity_attachment_staff_activity_id', 'staff_activity_id'),
    )


class StaffActivity(Base):
    __tablename__ = 'staff_activity'
    staff_activity_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    activity_type_id = mapped_column(Integer, ForeignKey('activity_type.activity_type_id'), nullable=False)
    academic_year_id = mapped_column(Integer, ForeignKey('academic_year.academic_year_id'))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    campus_id = mapped_column(Integer, ForeignKey('campus.campus_id'))
    department_id = mapped_column(Integer, ForeignKey('department.department_id'))
    participation_level_id = mapped_column(SmallInteger, ForeignKey('participation_level.participation_level_id'))
    primary_role_type_id = mapped_column(Integer, ForeignKey('role_type.role_type_id'))
    activity_title = mapped_column(String(500), nullable=False)
    start_date = mapped_column(Date)
    end_date = mapped_column(Date)
    description = mapped_column(Text)
    outcomes = mapped_column(Text)
    remarks = mapped_column(Text)
    verification_status_id = mapped_column(SmallInteger, ForeignKey('verification_status.verification_status_id'), nullable=False)
    verified_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    verified_at = mapped_column(DateTime(timezone=True))
    verification_remarks = mapped_column(String(1000))
    approval_status_id = mapped_column(SmallInteger, ForeignKey('approval_status.approval_status_id'), nullable=False)
    approved_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    approved_at = mapped_column(DateTime(timezone=True))
    approval_remarks = mapped_column(String(1000))
    rejection_reason = mapped_column(String(1000))
    created_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    updated_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = mapped_column(DateTime(timezone=True))
    deleted_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    deletion_reason = mapped_column(String(1000))
    __table_args__ = (
        Index('ix_staff_activity_approval_status_id', 'approval_status_id'),
        Index('ix_staff_activity_approved_by_user_id', 'approved_by_user_id'),
        Index('ix_staff_activity_campus_id', 'campus_id'),
        Index('ix_staff_activity_created_by_user_id', 'created_by_user_id'),
        Index('ix_staff_activity_deleted_by_user_id', 'deleted_by_user_id'),
        Index('ix_staff_activity_department_id', 'department_id'),
        Index('ix_staff_activity_employee_id', 'employee_id'),
        Index('ix_staff_activity_institution_id', 'institution_id'),
        Index('ix_staff_activity_participation_level_id', 'participation_level_id'),
        Index('ix_staff_activity_primary_role_type_id', 'primary_role_type_id'),
        Index('ix_staff_activity_activity_type_id', 'activity_type_id'),
        Index('ix_staff_activity_updated_by_user_id', 'updated_by_user_id'),
        Index('ix_staff_activity_verification_status_id', 'verification_status_id'),
        Index('ix_staff_activity_verified_by_user_id', 'verified_by_user_id'),
        Index('ix_staff_activity_academic_year_id', 'academic_year_id'),
        CheckConstraint('((end_date is null) or (start_date is null) or (end_date >= start_date))', name='ck_staff_activity_staff_activity_dates'),
    )
