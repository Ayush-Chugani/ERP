"""SQLAlchemy models for the professional_memberships domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class StaffProfessionalMembership(Base):
    __tablename__ = 'staff_professional_membership'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'), nullable=False)
    membership_type_id = mapped_column(Integer, ForeignKey('membership_type.membership_type_id'), nullable=False)
    membership_number = mapped_column(String(150))
    membership_start_date = mapped_column(Date)
    membership_expiry_date = mapped_column(Date)
    is_lifetime_membership = mapped_column(Boolean, nullable=False, server_default=text("false"))
    role_type_id = mapped_column(Integer, ForeignKey('role_type.role_type_id'))
    participation_level_id = mapped_column(SmallInteger, ForeignKey('participation_level.participation_level_id'))
    renewal_required = mapped_column(Boolean, nullable=False, server_default=text("false"))
    membership_status = mapped_column(String(9), nullable=False, server_default=text("'ACTIVE'"))
    __table_args__ = (
        UniqueConstraint('organization_id', 'membership_number', name='uq_staff_professional_membership_organization_id_memb_849390'),
        Index('ix_staff_professional_membership_participation_level_id', 'participation_level_id'),
        Index('ix_staff_professional_membership_role_type_id', 'role_type_id'),
        Index('ix_staff_professional_membership_membership_type_id', 'membership_type_id'),
        CheckConstraint("membership_status IN ('ACTIVE', 'EXPIRED', 'SUSPENDED', 'CANCELLED', 'LIFETIME')", name='ck_staff_professional_membership_membership_status_enum'),
        CheckConstraint('((membership_expiry_date is null) or (membership_start_date is null) or (membership_expiry_date >= membership_start_date))', name='ck_staff_professional_membership_staff_membership_dates'),
    )
