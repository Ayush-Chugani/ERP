"""SQLAlchemy models for the organization domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class Building(Base):
    __tablename__ = 'building'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    building_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_code = mapped_column(String(20), nullable=False)
    building_name = mapped_column(String(100), nullable=False)
    campus_id = mapped_column(Integer, ForeignKey('campus.campus_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('campus_id', 'building_code', name='uq_building_campus_id_building_code'),
    )


class Campus(Base):
    __tablename__ = 'campus'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    campus_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    campus_code = mapped_column(String(20), nullable=False)
    campus_name = mapped_column(String(150), nullable=False)
    address_line_1 = mapped_column(String(200))
    address_line_2 = mapped_column(String(200))
    city = mapped_column(String(100))
    postal_code = mapped_column(String(12))
    phone = mapped_column(String(25))
    email = mapped_column(String(254))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('institution_id', 'campus_code', name='uq_campus_institution_id_campus_code'),
        Index('ix_campus_state_id', 'state_id'),
    )


class Department(Base):
    __tablename__ = 'department'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    department_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    department_code = mapped_column(String(20), nullable=False)
    department_name = mapped_column(String(150), nullable=False)
    department_type = mapped_column(String(30))
    campus_id = mapped_column(Integer, ForeignKey('campus.campus_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('campus_id', 'department_code', name='uq_department_campus_id_department_code'),
        UniqueConstraint('department_id', 'campus_id', name='uq_department_department_id_campus_id'),
    )


class Institution(Base):
    __tablename__ = 'institution'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    institution_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    institution_code = mapped_column(String(20), nullable=False)
    institution_name = mapped_column(String(200), nullable=False)
    legal_name = mapped_column(String(250))
    website_url = mapped_column(String(255))
    email = mapped_column(String(254))
    phone = mapped_column(String(25))
    university_id = mapped_column(Integer, ForeignKey('university.university_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('institution_code', name='uq_institution_institution_code'),
        Index('ix_institution_university_id', 'university_id'),
    )


class Programme(Base):
    __tablename__ = 'programme'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    programme_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    programme_code = mapped_column(String(30), nullable=False)
    programme_name = mapped_column(String(150), nullable=False)
    award_name = mapped_column(String(150))
    programme_level = mapped_column(String(12), nullable=False)
    duration_semesters = mapped_column(SmallInteger, nullable=False)
    maximum_duration_semesters = mapped_column(SmallInteger)
    department_id = mapped_column(Integer, ForeignKey('department.department_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('programme_code', name='uq_programme_programme_code'),
        Index('ix_programme_department_id', 'department_id'),
        CheckConstraint('((duration_semesters > 0) and ((maximum_duration_semesters is null) or (maximum_duration_semesters >= duration_semesters)))', name='ck_programme_programme_duration'),
        CheckConstraint("(programme_level in ('UG','PG','DIPLOMA','CERTIFICATE','DOCTORAL','OTHER'))", name='ck_programme_programme_level'),
        CheckConstraint('(duration_semesters >= 0)', name='ck_programme_programme_chk_1'),
        CheckConstraint('(maximum_duration_semesters >= 0)', name='ck_programme_programme_chk_2'),
    )


class ProgrammeSpecialization(Base):
    __tablename__ = 'programme_specialization'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    specialization_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialization_code = mapped_column(String(30), nullable=False)
    specialization_name = mapped_column(String(150), nullable=False)
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('programme_id', 'specialization_code', name='uq_programme_specialization_programme_id_specialization_code'),
        UniqueConstraint('specialization_id', 'programme_id', name='uq_programme_specialization_specialization_id_programme_id'),
    )


class Room(Base):
    __tablename__ = 'room'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    room_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code = mapped_column(String(20), nullable=False)
    room_name = mapped_column(String(100))
    room_type = mapped_column(String(15), nullable=False)
    capacity = mapped_column(Integer)
    building_id = mapped_column(Integer, ForeignKey('building.building_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('building_id', 'room_code', name='uq_room_building_id_room_code'),
        CheckConstraint('((capacity is null) or (capacity > 0))', name='ck_room_room_capacity'),
        CheckConstraint("(room_type in ('CLASSROOM','LAB','SEMINAR_HALL','AUDITORIUM','OFFICE','OTHER'))", name='ck_room_room_type'),
        CheckConstraint('(capacity >= 0)', name='ck_room_room_chk_1'),
    )


class University(Base):
    __tablename__ = 'university'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
    university_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    university_code = mapped_column(String(30), nullable=False)
    university_name = mapped_column(String(200), nullable=False)
    legal_name = mapped_column(String(250))
    university_type = mapped_column(String(10), nullable=False)
    website_url = mapped_column(String(255))
    email = mapped_column(String(254))
    phone = mapped_column(String(25))
    address_line_1 = mapped_column(String(200))
    address_line_2 = mapped_column(String(200))
    city = mapped_column(String(100))
    postal_code = mapped_column(String(12))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    __table_args__ = (
        UniqueConstraint('university_code', name='uq_university_university_code'),
        Index('ix_university_state_id', 'state_id'),
        CheckConstraint("(university_type in ('CENTRAL','STATE','PRIVATE','DEEMED','OTHER'))", name='ck_university_university_type'),
    )
