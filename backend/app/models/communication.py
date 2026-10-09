"""SQLAlchemy models for the communication domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class Announcement(Base):
    __tablename__ = 'announcement'
    announcement_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    announcement_type_id = mapped_column(Integer, ForeignKey('announcement_type.announcement_type_id'), nullable=False)
    department_id = mapped_column(Integer, ForeignKey('department.department_id'))
    title = mapped_column(String(250), nullable=False)
    description = mapped_column(Text, nullable=False)
    publish_from = mapped_column(DateTime(timezone=True), nullable=False)
    publish_to = mapped_column(DateTime(timezone=True))
    approval_status = mapped_column(String(8), nullable=False, server_default=text("'DRAFT'"))
    audience_type = mapped_column(String(10), nullable=False, server_default=text("'ALL'"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    __table_args__ = (
        Index('ix_announcement_institution_id', 'institution_id'),
        Index('ix_announcement_department_id', 'department_id'),
        Index('ix_announcement_announcement_type_id', 'announcement_type_id'),
        CheckConstraint("approval_status IN ('DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'ARCHIVED')", name='ck_announcement_approval_status_enum'),
        CheckConstraint("audience_type IN ('ALL', 'STUDENTS', 'STAFF', 'PROGRAMME', 'DEPARTMENT', 'CUSTOM')", name='ck_announcement_audience_type_enum'),
    )


class AnnouncementAttachment(Base):
    __tablename__ = 'announcement_attachment'
    announcement_id = mapped_column(BigInteger, ForeignKey('announcement.announcement_id'), primary_key=True, autoincrement=False)
    file_object_id = mapped_column(BigInteger, ForeignKey('file_object.file_object_id'), primary_key=True, autoincrement=False)
    display_order = mapped_column(Integer)
    __table_args__ = (
        Index('ix_announcement_attachment_file_object_id', 'file_object_id'),
    )


class AnnouncementProgrammeTarget(Base):
    __tablename__ = 'announcement_programme_target'
    announcement_id = mapped_column(BigInteger, ForeignKey('announcement.announcement_id'), primary_key=True, autoincrement=False)
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'), primary_key=True, autoincrement=False)
    __table_args__ = (
        Index('ix_announcement_programme_target_programme_id', 'programme_id'),
    )


class AnnouncementType(Base):
    __tablename__ = 'announcement_type'
    announcement_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_code = mapped_column(String(30), nullable=False)
    type_name = mapped_column(String(100), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('type_code', name='uq_announcement_type_type_code'),
        UniqueConstraint('type_name', name='uq_announcement_type_type_name'),
    )


class AnnouncementUserTarget(Base):
    __tablename__ = 'announcement_user_target'
    announcement_id = mapped_column(BigInteger, ForeignKey('announcement.announcement_id'), primary_key=True, autoincrement=False)
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), primary_key=True, autoincrement=False)
    __table_args__ = (
        Index('ix_announcement_user_target_user_id', 'user_id'),
    )
