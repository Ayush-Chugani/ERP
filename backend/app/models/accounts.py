"""SQLAlchemy models for the accounts domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class UserAccount(Base):
    """Login identity. People (students/staff) link to it through ``person_account_link``."""

    __tablename__ = 'user_account'
    user_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username = mapped_column(String(150), nullable=False)
    email = mapped_column(String(254), nullable=False, server_default=text("''"))
    first_name = mapped_column(String(150), nullable=False, server_default=text("''"))
    last_name = mapped_column(String(150), nullable=False, server_default=text("''"))
    password_hash = mapped_column(String(255), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_superuser = mapped_column(Boolean, nullable=False, server_default=text("false"))
    account_status = mapped_column(String(8), nullable=False, server_default=text("'ACTIVE'"))
    failed_login_count = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_login_at = mapped_column(DateTime(timezone=True))
    locked_until = mapped_column(DateTime(timezone=True))
    multi_factor_enabled = mapped_column(Boolean, nullable=False, server_default=text("false"))
    mfa_secret = mapped_column(String(64))
    must_change_password = mapped_column(Boolean, nullable=False, server_default=text("false"))
    password_changed_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    security_version = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    institution_id = mapped_column(Integer, ForeignKey('institution.institution_id', ondelete='RESTRICT'),
                                   comment='Organisation that owns this login; NULL for platform-level accounts')
    __table_args__ = (
        Index('ix_user_account_institution_id', 'institution_id'),
        Index('uq_user_account_username_lower', func.lower(username), unique=True),
        CheckConstraint("account_status IN ('PENDING', 'ACTIVE', 'LOCKED', 'DISABLED', 'EXPIRED')", name='ck_user_account_status'),
        CheckConstraint('failed_login_count >= 0', name='ck_user_account_failed_login_count'),
        CheckConstraint('security_version >= 0', name='ck_user_account_security_version'),
    )
