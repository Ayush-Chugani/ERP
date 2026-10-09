"""SQLAlchemy models for the academic_calendar domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class AcademicTerm(Base):
    __tablename__ = 'academic_term'
    academic_term_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    term_code = mapped_column(String(20), nullable=False)
    term_name = mapped_column(String(100), nullable=False)
    term_type = mapped_column(String(6), nullable=False)
    start_date = mapped_column(Date, nullable=False)
    end_date = mapped_column(Date, nullable=False)
    registration_start_date = mapped_column(Date)
    registration_end_date = mapped_column(Date)
    status = mapped_column(String(17), nullable=False, server_default=text("'PLANNED'"))
    academic_year_id = mapped_column(Integer, ForeignKey('academic_year.academic_year_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('academic_year_id', 'term_code', name='uq_academic_term_academic_year_id_term_code'),
        Index('ix_academic_term_status_start_date', 'status', 'start_date'),
        CheckConstraint("(status in ('PLANNED','REGISTRATION_OPEN','ACTIVE','CLOSED'))", name='ck_academic_term_academic_term_status'),
        CheckConstraint("(term_type in ('ODD','EVEN','SUMMER','ANNUAL','OTHER'))", name='ck_academic_term_academic_term_type'),
        CheckConstraint('(end_date >= start_date)', name='ck_academic_term_term_dates'),
        CheckConstraint('((registration_start_date is null) or (registration_end_date is null) or (registration_end_date >= registration_start_date))', name='ck_academic_term_term_registration_dates'),
    )


class AcademicYear(Base):
    __tablename__ = 'academic_year'
    academic_year_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    year_code = mapped_column(String(9), nullable=False)
    start_date = mapped_column(Date, nullable=False)
    end_date = mapped_column(Date, nullable=False)
    status = mapped_column(String(7), nullable=False, server_default=text("'PLANNED'"))
    __table_args__ = (
        UniqueConstraint('year_code', name='uq_academic_year_year_code'),
        Index('ix_academic_year_status_start_date', 'status', 'start_date'),
        CheckConstraint('(end_date > start_date)', name='ck_academic_year_academic_year_dates'),
        CheckConstraint("(status in ('PLANNED','ACTIVE','CLOSED'))", name='ck_academic_year_academic_year_status'),
    )


class Semester(Base):
    __tablename__ = 'semester'
    semester_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    semester_number = mapped_column(SmallInteger, nullable=False)
    semester_name = mapped_column(String(50), nullable=False)
    __table_args__ = (
        UniqueConstraint('semester_name', name='uq_semester_semester_name'),
        UniqueConstraint('semester_number', name='uq_semester_semester_number'),
        CheckConstraint('(semester_number >= 0)', name='ck_semester_semester_chk_1'),
        CheckConstraint('(semester_number > 0)', name='ck_semester_semester_number'),
    )


class TimeSlot(Base):
    __tablename__ = 'time_slot'
    time_slot_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_code = mapped_column(String(20), nullable=False)
    start_time = mapped_column(Time, nullable=False)
    end_time = mapped_column(Time, nullable=False)
    is_break = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    campus_id = mapped_column(Integer, ForeignKey('campus.campus_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('campus_id', 'slot_code', name='uq_time_slot_campus_id_slot_code'),
        Index('ix_time_slot_campus_id_is_active_start_time', 'campus_id', 'is_active', 'start_time'),
        CheckConstraint('(end_time > start_time)', name='ck_time_slot_time_slot'),
    )
