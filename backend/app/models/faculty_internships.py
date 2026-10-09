"""SQLAlchemy models for the faculty_internships domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class FacultyInternship(Base):
    __tablename__ = 'faculty_internship'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'), nullable=False)
    internship_title = mapped_column(String(500), nullable=False)
    internship_domain = mapped_column(String(250))
    industry_sector_id = mapped_column(Integer, ForeignKey('industry_sector.industry_sector_id'))
    location_text = mapped_column(String(300))
    mentor_name = mapped_column(String(200))
    mentor_designation = mapped_column(String(150))
    mentor_email = mapped_column(String(254))
    work_undertaken = mapped_column(Text)
    technologies_tools = mapped_column(Text)
    outcomes = mapped_column(Text)
    stipend_incentive_type = mapped_column(String(10), nullable=False, server_default=text("'NONE'"))
    stipend_incentive_amount = mapped_column(Numeric(14, 2))
    currency_code = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    funding_source = mapped_column(String(250))
    mou_reference = mapped_column(String(150))
    collaboration_reference = mapped_column(String(250))
    __table_args__ = (
        Index('ix_faculty_internship_organization_id', 'organization_id'),
        Index('ix_faculty_internship_industry_sector_id', 'industry_sector_id'),
        CheckConstraint("stipend_incentive_type IN ('NONE', 'STIPEND', 'INCENTIVE', 'HONORARIUM', 'OTHER')", name='ck_faculty_internship_stipend_incentive_type_enum'),
        CheckConstraint('((stipend_incentive_amount is null) or (stipend_incentive_amount >= 0))', name='ck_faculty_internship_faculty_internship_amount'),
    )
