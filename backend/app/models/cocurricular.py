"""SQLAlchemy models for the cocurricular domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class CocurricularActivity(Base):
    __tablename__ = 'cocurricular_activity'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    cocurricular_category_id = mapped_column(Integer, ForeignKey('cocurricular_category.cocurricular_category_id'), nullable=False)
    event_name = mapped_column(String(500), nullable=False)
    organizer_id = mapped_column(BigInteger, ForeignKey('organizer.organizer_id'))
    institution_organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'))
    event_date = mapped_column(Date)
    venue_name = mapped_column(String(250))
    city = mapped_column(String(120))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    achievement_award = mapped_column(String(500))
    contribution_details = mapped_column(Text)
    __table_args__ = (
        Index('ix_cocurricular_activity_cocurricular_category_id', 'cocurricular_category_id'),
        Index('ix_cocurricular_activity_country_id', 'country_id'),
        Index('ix_cocurricular_activity_institution_organization_id', 'institution_organization_id'),
        Index('ix_cocurricular_activity_organizer_id', 'organizer_id'),
        Index('ix_cocurricular_activity_state_id', 'state_id'),
    )
