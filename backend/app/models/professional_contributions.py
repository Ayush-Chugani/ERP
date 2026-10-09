"""SQLAlchemy models for the professional_contributions domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class StaffProfessionalContribution(Base):
    __tablename__ = 'staff_professional_contribution'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    professional_contribution_type_id = mapped_column(Integer, ForeignKey('professional_contribution_type.professional_contribution_type_id'), nullable=False)
    organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'))
    journal_id = mapped_column(BigInteger, ForeignKey('journal.journal_id'))
    conference_event_id = mapped_column(BigInteger, ForeignKey('conference_event.conference_event_id'))
    programme_id = mapped_column(Integer, ForeignKey('programme.programme_id'))
    course_id = mapped_column(Integer, ForeignKey('course_catalog.course_id'))
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'))
    title_topic = mapped_column(String(500))
    appointment_reference_number = mapped_column(String(150))
    contribution_date = mapped_column(Date)
    start_date = mapped_column(Date)
    end_date = mapped_column(Date)
    number_of_reviews = mapped_column(Integer)
    number_of_candidates = mapped_column(Integer)
    contribution_details = mapped_column(Text)
    outcome_details = mapped_column(Text)
    __table_args__ = (
        Index('ix_staff_professional_contribution_conference_event_id', 'conference_event_id'),
        Index('ix_staff_professional_contribution_course_id', 'course_id'),
        Index('ix_staff_professional_contribution_journal_id', 'journal_id'),
        Index('ix_staff_professional_contribution_organization_id', 'organization_id'),
        Index('ix_staff_professional_contribution_programme_id', 'programme_id'),
        Index('ix_staff_professional_contribution_student_id', 'student_id'),
        Index('ix_staff_professional_contribution_professional_contr_497487', 'professional_contribution_type_id'),
        CheckConstraint('((end_date is null) or (start_date is null) or (end_date >= start_date))', name='ck_staff_professional_contribution_prof_contribution_dates'),
    )
