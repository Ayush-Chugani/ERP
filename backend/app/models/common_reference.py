"""SQLAlchemy models for the common_reference domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class AdmissionCategory(Base):
    __tablename__ = 'admission_category'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    admission_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(30), nullable=False)
    category_name = mapped_column(String(100), nullable=False)
    description = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_admission_category_category_code'),
        UniqueConstraint('category_name', name='uq_admission_category_category_name'),
    )


class BloodGroup(Base):
    __tablename__ = 'blood_group'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    blood_group_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    blood_group_code = mapped_column(String(5), nullable=False)
    __table_args__ = (
        UniqueConstraint('blood_group_code', name='uq_blood_group_blood_group_code'),
    )


class Caste(Base):
    __tablename__ = 'caste'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    caste_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    caste_code = mapped_column(String(30))
    caste_name = mapped_column(String(150), nullable=False)
    social_category_id = mapped_column(Integer, ForeignKey('social_category.social_category_id'))
    __table_args__ = (
        UniqueConstraint('caste_code', name='uq_caste_caste_code'),
        UniqueConstraint('social_category_id', 'caste_name', name='uq_caste_social_category_id_caste_name'),
    )


class Country(Base):
    __tablename__ = 'country'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    country_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    iso_code = mapped_column(String(2), nullable=False)
    country_name = mapped_column(String(100), nullable=False)
    __table_args__ = (
        UniqueConstraint('country_name', name='uq_country_country_name'),
        UniqueConstraint('iso_code', name='uq_country_iso_code'),
    )


class DocumentType(Base):
    __tablename__ = 'document_type'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    document_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_code = mapped_column(String(30), nullable=False)
    document_name = mapped_column(String(100), nullable=False)
    requires_verification = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('document_code', name='uq_document_type_document_code'),
        UniqueConstraint('document_name', name='uq_document_type_document_name'),
    )


class Gender(Base):
    __tablename__ = 'gender'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    gender_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    gender_code = mapped_column(String(20), nullable=False)
    gender_name = mapped_column(String(50), nullable=False)
    __table_args__ = (
        UniqueConstraint('gender_code', name='uq_gender_gender_code'),
        UniqueConstraint('gender_name', name='uq_gender_gender_name'),
    )


class Religion(Base):
    __tablename__ = 'religion'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    religion_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    religion_code = mapped_column(String(20))
    religion_name = mapped_column(String(100), nullable=False)
    __table_args__ = (
        UniqueConstraint('religion_code', name='uq_religion_religion_code'),
        UniqueConstraint('religion_name', name='uq_religion_religion_name'),
    )


class SocialCategory(Base):
    __tablename__ = 'social_category'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    social_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(20), nullable=False)
    category_name = mapped_column(String(100), nullable=False)
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_social_category_category_code'),
        UniqueConstraint('category_name', name='uq_social_category_category_name'),
    )


class State(Base):
    __tablename__ = 'state'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    state_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_code = mapped_column(String(10), nullable=False)
    state_name = mapped_column(String(100), nullable=False)
    country_id = mapped_column(Integer, ForeignKey('country.country_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('country_id', 'state_code', name='uq_state_country_id_state_code'),
        UniqueConstraint('country_id', 'state_name', name='uq_state_country_id_state_name'),
    )


class SubCaste(Base):
    __tablename__ = 'sub_caste'
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sub_caste_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_caste_code = mapped_column(String(30))
    sub_caste_name = mapped_column(String(150), nullable=False)
    caste_id = mapped_column(Integer, ForeignKey('caste.caste_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('caste_id', 'sub_caste_name', name='uq_sub_caste_caste_id_sub_caste_name'),
    )
