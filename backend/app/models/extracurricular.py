"""SQLAlchemy models for the extracurricular domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class ExtracurricularActivity(Base):
    __tablename__ = 'extracurricular_activity'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    extracurricular_category_id = mapped_column(Integer, ForeignKey('extracurricular_category.extracurricular_category_id'), nullable=False)
    event_name = mapped_column(String(500), nullable=False)
    organizer_id = mapped_column(BigInteger, ForeignKey('organizer.organizer_id'))
    institution_organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'))
    event_date = mapped_column(Date)
    venue_name = mapped_column(String(250))
    city = mapped_column(String(120))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    award_recognition = mapped_column(String(500))
    activity_details = mapped_column(Text)
    __table_args__ = (
        Index('ix_extracurricular_activity_extracurricular_category_id', 'extracurricular_category_id'),
        Index('ix_extracurricular_activity_country_id', 'country_id'),
        Index('ix_extracurricular_activity_institution_organization_id', 'institution_organization_id'),
        Index('ix_extracurricular_activity_organizer_id', 'organizer_id'),
        Index('ix_extracurricular_activity_state_id', 'state_id'),
    )
