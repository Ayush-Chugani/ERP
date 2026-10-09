"""SQLAlchemy models for the tenancy domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class UserInstitution(Base):
    __tablename__ = 'user_institution'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('user_id', 'institution_id', name='uq_user_institution_user_id_institution_id'),
        Index('ix_user_institution_institution_id', 'institution_id'),
    )


class InstitutionModule(Base):
    __tablename__ = 'institution_module'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_structure = mapped_column(Boolean, nullable=False, server_default=text("false"))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    academic_calendar = mapped_column(Boolean, nullable=False, server_default=text("false"))
    curriculum_catalog = mapped_column(Boolean, nullable=False, server_default=text("false"))
    people_master = mapped_column(Boolean, nullable=False, server_default=text("false"))
    admission_enrolment = mapped_column(Boolean, nullable=False, server_default=text("false"))
    term_registration = mapped_column(Boolean, nullable=False, server_default=text("false"))
    teaching_timetable = mapped_column(Boolean, nullable=False, server_default=text("false"))
    attendance_lesson_plan = mapped_column(Boolean, nullable=False, server_default=text("false"))
    assessments_results = mapped_column(Boolean, nullable=False, server_default=text("false"))
    feedback = mapped_column(Boolean, nullable=False, server_default=text("false"))
    __table_args__ = (
        UniqueConstraint('institution_id', name='uq_institution_module_institution_id'),
    )
