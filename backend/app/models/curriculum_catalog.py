"""SQLAlchemy models for the curriculum_catalog domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class CourseCatalog(Base):
    __tablename__ = 'course_catalog'
    course_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_code = mapped_column(String(30), nullable=False)
    course_title = mapped_column(String(200), nullable=False)
    short_title = mapped_column(String(80))
    course_type = mapped_column(String(10), nullable=False)
    lecture_hours = mapped_column(Numeric(4, 1), nullable=False, server_default=text("0.0"))
    tutorial_hours = mapped_column(Numeric(4, 1), nullable=False, server_default=text("0.0"))
    practical_hours = mapped_column(Numeric(4, 1), nullable=False, server_default=text("0.0"))
    self_study_hours = mapped_column(Numeric(4, 1), nullable=False, server_default=text("0.0"))
    credits = mapped_column(Numeric(4, 1), nullable=False, server_default=text("0.0"))
    effective_from = mapped_column(Date)
    effective_to = mapped_column(Date)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    owning_department_id = mapped_column(Integer, ForeignKey('department.department_id'), nullable=False)
    course_category_id = mapped_column(Integer, ForeignKey('course_category.course_category_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('course_code', name='uq_course_catalog_course_code'),
        Index('ix_course_catalog_owning_department_id_is_active_course_code', 'owning_department_id', 'is_active', 'course_code'),
        Index('ix_course_catalog_course_category_id', 'course_category_id'),
        CheckConstraint("(course_type in ('THEORY','LAB','THEORY_LAB','PROJECT','SEMINAR','INTERNSHIP','OTHER'))", name='ck_course_catalog_catalog_course_type'),
        CheckConstraint('((effective_from is null) or (effective_to is null) or (effective_to >= effective_from))', name='ck_course_catalog_course_effective_dates'),
        CheckConstraint('((credits >= 0) and (lecture_hours >= 0) and (practical_hours >= 0) and (self_study_hours >= 0) and (tutorial_hours >= 0))', name='ck_course_catalog_course_nonnegative_values'),
    )


class CourseCategory(Base):
    __tablename__ = 'course_category'
    course_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(30), nullable=False)
    category_name = mapped_column(String(100), nullable=False)
    is_graded = mapped_column(Boolean, nullable=False, server_default=text("true"))
    contributes_to_gpa = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_course_category_category_code'),
        UniqueConstraint('category_name', name='uq_course_category_category_name'),
    )


class CoursePrerequisite(Base):
    __tablename__ = 'course_prerequisite'
    minimum_grade = mapped_column(String(5))
    course_id = mapped_column(Integer, ForeignKey('course_catalog.course_id'), primary_key=True, autoincrement=False)
    prerequisite_course_id = mapped_column(Integer, ForeignKey('course_catalog.course_id'), primary_key=True, autoincrement=False)
    __table_args__ = (
        Index('ix_course_prerequisite_prerequisite_course_id', 'prerequisite_course_id'),
        CheckConstraint('(course_id <> prerequisite_course_id)', name='ck_course_prerequisite_prerequisite_not_self'),
    )


class CurriculumCourse(Base):
    __tablename__ = 'curriculum_course'
    curriculum_course_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    is_mandatory = mapped_column(Boolean, nullable=False, server_default=text("true"))
    elective_group_code = mapped_column(String(30))
    display_order = mapped_column(Integer)
    internal_max_marks = mapped_column(Numeric(6, 2), nullable=False, server_default=text("0.00"))
    external_max_marks = mapped_column(Numeric(6, 2), nullable=False, server_default=text("0.00"))
    passing_marks = mapped_column(Numeric(6, 2))
    exam_duration_minutes = mapped_column(Integer)
    course_id = mapped_column(Integer, ForeignKey('course_catalog.course_id'), nullable=False)
    course_category_id = mapped_column(Integer, ForeignKey('course_category.course_category_id'), nullable=False)
    semester_id = mapped_column(SmallInteger, ForeignKey('semester.semester_id'), nullable=False)
    curriculum_scheme_id = mapped_column(Integer, ForeignKey('curriculum_scheme.curriculum_scheme_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('curriculum_scheme_id', 'semester_id', 'course_id', name='uq_curriculum_course_curriculum_scheme_id_semester_id_f8ca50'),
        UniqueConstraint('curriculum_scheme_id', 'semester_id', 'display_order', name='uq_curriculum_course_curriculum_scheme_id_semester_id_05520d'),
        UniqueConstraint('curriculum_course_id', 'course_id', name='uq_curriculum_course_curriculum_course_id_course_id'),
        Index('ix_curriculum_course_course_category_id', 'course_category_id'),
        Index('ix_curriculum_course_course_id', 'course_id'),
        Index('ix_curriculum_course_semester_id', 'semester_id'),
        CheckConstraint('(((elective_group_code is null) and (is_mandatory = true)) or ((elective_group_code is not null) and (is_mandatory = false) and (elective_group_code is not null)))', name='ck_curriculum_course_curriculum_elective'),
        CheckConstraint('((external_max_marks >= 0) and (internal_max_marks >= 0) and ((passing_marks is null) or ((passing_marks >= 0) and (passing_marks <= (internal_max_marks + external_max_marks)))))', name='ck_curriculum_course_curriculum_marks'),
        CheckConstraint('(display_order >= 0)', name='ck_curriculum_course_curriculum_course_chk_1'),
        CheckConstraint('(exam_duration_minutes >= 0)', name='ck_curriculum_course_curriculum_course_chk_2'),
    )


class CurriculumScheme(Base):
    __tablename__ = 'curriculum_scheme'
    curriculum_scheme_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_code = mapped_column(String(30), nullable=False)
    scheme_name = mapped_column(String(150), nullable=False)
    regulation_year = mapped_column(SmallInteger, nullable=False)
    total_credits = mapped_column(Numeric(6, 1))
    effective_from = mapped_column(Date, nullable=False)
    effective_to = mapped_column(Date)
    status = mapped_column(String(7), nullable=False, server_default=text("'DRAFT'"))
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'), nullable=False)
    specialization_id = mapped_column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(['specialization_id', 'programme_id'], ['programme_specialization.specialization_id', 'programme_specialization.programme_id']),
        UniqueConstraint('scheme_code', name='uq_curriculum_scheme_scheme_code'),
        UniqueConstraint('curriculum_scheme_id', 'programme_id', name='uq_curriculum_scheme_curriculum_scheme_id_programme_id'),
        Index('ix_curriculum_scheme_specialization_id', 'specialization_id'),
        Index('ix_curriculum_scheme_specialization_id_programme_id', 'specialization_id', 'programme_id'),
        Index('ix_curriculum_scheme_programme_id_specialization_id_s_f1e0e5', 'programme_id', 'specialization_id', 'status', 'effective_from'),
        CheckConstraint('((effective_to is null) or (effective_to >= effective_from))', name='ck_curriculum_scheme_scheme_effective_dates'),
        CheckConstraint("(status in ('DRAFT','ACTIVE','RETIRED'))", name='ck_curriculum_scheme_scheme_status'),
        CheckConstraint('((total_credits is null) or (total_credits >= 0))', name='ck_curriculum_scheme_scheme_total_credits'),
        CheckConstraint('(regulation_year >= 0)', name='ck_curriculum_scheme_curriculum_scheme_chk_1'),
    )
