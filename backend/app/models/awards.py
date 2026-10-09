"""SQLAlchemy models for the awards domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class StaffAward(Base):
    __tablename__ = 'staff_award'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    award_category_id = mapped_column(Integer, ForeignKey('award_category.award_category_id'))
    award_name = mapped_column(String(500), nullable=False)
    awarding_organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'))
    award_date = mapped_column(Date, nullable=False)
    citation_details = mapped_column(Text)
    cash_prize_amount = mapped_column(Numeric(14, 2))
    incentive_amount = mapped_column(Numeric(14, 2))
    currency_code = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    award_reference_number = mapped_column(String(150))
    __table_args__ = (
        Index('ix_staff_award_award_category_id', 'award_category_id'),
        Index('ix_staff_award_awarding_organization_id', 'awarding_organization_id'),
        CheckConstraint('(((cash_prize_amount is null) or (cash_prize_amount >= 0)) and ((incentive_amount is null) or (incentive_amount >= 0)))', name='ck_staff_award_staff_award_amounts'),
    )
