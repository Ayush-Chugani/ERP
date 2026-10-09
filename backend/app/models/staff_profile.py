"""SQLAlchemy models for the staff_profile domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class ActivityType(Base):
    __tablename__ = 'activity_type'
    activity_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_type_code = mapped_column(String(50), nullable=False)
    activity_type_name = mapped_column(String(150), nullable=False)
    activity_group = mapped_column(String(34), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('activity_type_code', name='uq_activity_type_activity_type_code'),
        UniqueConstraint('activity_type_name', name='uq_activity_type_activity_type_name'),
        CheckConstraint("activity_group IN ('PUBLICATION', 'CONFERENCE', 'PROFESSIONAL_DEVELOPMENT', 'INTERNSHIP', 'RESEARCH', 'CONSULTANCY', 'CO_CURRICULAR', 'EXTRA_CURRICULAR', 'AWARD', 'MEMBERSHIP', 'ACADEMIC_PROFESSIONAL_CONTRIBUTION', 'OTHER')", name='ck_activity_type_activity_group_enum'),
    )


class ApprovalStatus(Base):
    __tablename__ = 'approval_status'
    approval_status_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    status_code = mapped_column(String(30), nullable=False)
    status_name = mapped_column(String(80), nullable=False)
    is_terminal = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('status_code', name='uq_approval_status_status_code'),
        UniqueConstraint('status_name', name='uq_approval_status_status_name'),
    )


class AwardCategory(Base):
    __tablename__ = 'award_category'
    award_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(50), nullable=False)
    category_name = mapped_column(String(150), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_award_category_category_code'),
        UniqueConstraint('category_name', name='uq_award_category_category_name'),
    )


class CocurricularCategory(Base):
    __tablename__ = 'cocurricular_category'
    cocurricular_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(50), nullable=False)
    category_name = mapped_column(String(150), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_cocurricular_category_category_code'),
        UniqueConstraint('category_name', name='uq_cocurricular_category_category_name'),
    )


class ConferenceContributionType(Base):
    __tablename__ = 'conference_contribution_type'
    conference_contribution_type_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    type_code = mapped_column(String(40), nullable=False)
    type_name = mapped_column(String(120), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('type_code', name='uq_conference_contribution_type_type_code'),
        UniqueConstraint('type_name', name='uq_conference_contribution_type_type_name'),
    )


class ConfidentialityLevel(Base):
    __tablename__ = 'confidentiality_level'
    confidentiality_level_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    level_code = mapped_column(String(30), nullable=False)
    level_name = mapped_column(String(80), nullable=False)
    display_order = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('level_code', name='uq_confidentiality_level_level_code'),
        UniqueConstraint('level_name', name='uq_confidentiality_level_level_name'),
    )


class EventMode(Base):
    __tablename__ = 'event_mode'
    event_mode_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    mode_code = mapped_column(String(20), nullable=False)
    mode_name = mapped_column(String(60), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('mode_code', name='uq_event_mode_mode_code'),
        UniqueConstraint('mode_name', name='uq_event_mode_mode_name'),
    )


class EvidenceType(Base):
    __tablename__ = 'evidence_type'
    evidence_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_type_code = mapped_column(String(60), nullable=False)
    evidence_type_name = mapped_column(String(180), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('evidence_type_code', name='uq_evidence_type_evidence_type_code'),
        UniqueConstraint('evidence_type_name', name='uq_evidence_type_evidence_type_name'),
    )


class ExternalOrganization(Base):
    __tablename__ = 'external_organization'
    organization_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_code = mapped_column(String(60))
    organization_name = mapped_column(String(250), nullable=False)
    short_name = mapped_column(String(100))
    website_url = mapped_column(String(500))
    email = mapped_column(String(254))
    phone = mapped_column(String(30))
    address_line_1 = mapped_column(String(250))
    address_line_2 = mapped_column(String(250))
    city = mapped_column(String(120))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    postal_code = mapped_column(String(20))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('organization_code', name='uq_external_organization_organization_code'),
        UniqueConstraint('organization_name', 'city', 'country_id', name='uq_external_organization_organization_name_city_country_id'),
        Index('ix_external_organization_country_id', 'country_id'),
        Index('ix_external_organization_state_id', 'state_id'),
    )


class ExtracurricularCategory(Base):
    __tablename__ = 'extracurricular_category'
    extracurricular_category_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code = mapped_column(String(50), nullable=False)
    category_name = mapped_column(String(150), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('category_code', name='uq_extracurricular_category_category_code'),
        UniqueConstraint('category_name', name='uq_extracurricular_category_category_name'),
    )


class FundingAgency(Base):
    __tablename__ = 'funding_agency'
    funding_agency_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'), nullable=False)
    funding_type_id = mapped_column(SmallInteger, ForeignKey('funding_type.funding_type_id'), nullable=False)
    agency_category = mapped_column(String(100))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('organization_id', name='uq_funding_agency_organization_id'),
        Index('ix_funding_agency_funding_type_id', 'funding_type_id'),
    )


class FundingType(Base):
    __tablename__ = 'funding_type'
    funding_type_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    funding_type_code = mapped_column(String(30), nullable=False)
    funding_type_name = mapped_column(String(100), nullable=False)
    is_external = mapped_column(Boolean, nullable=False, server_default=text("false"))
    description = mapped_column(String(300))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('funding_type_code', name='uq_funding_type_funding_type_code'),
        UniqueConstraint('funding_type_name', name='uq_funding_type_funding_type_name'),
    )


class IndexingAgency(Base):
    __tablename__ = 'indexing_agency'
    indexing_agency_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_code = mapped_column(String(40), nullable=False)
    agency_name = mapped_column(String(150), nullable=False)
    website_url = mapped_column(String(500))
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('agency_code', name='uq_indexing_agency_agency_code'),
        UniqueConstraint('agency_name', name='uq_indexing_agency_agency_name'),
    )


class IndustrySector(Base):
    __tablename__ = 'industry_sector'
    industry_sector_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_code = mapped_column(String(50), nullable=False)
    sector_name = mapped_column(String(150), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('sector_code', name='uq_industry_sector_sector_code'),
        UniqueConstraint('sector_name', name='uq_industry_sector_sector_name'),
    )


class JournalType(Base):
    __tablename__ = 'journal_type'
    journal_type_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    journal_type_code = mapped_column(String(30), nullable=False)
    journal_type_name = mapped_column(String(80), nullable=False)
    description = mapped_column(String(300))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('journal_type_code', name='uq_journal_type_journal_type_code'),
        UniqueConstraint('journal_type_name', name='uq_journal_type_journal_type_name'),
    )


class MembershipType(Base):
    __tablename__ = 'membership_type'
    membership_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_code = mapped_column(String(50), nullable=False)
    type_name = mapped_column(String(150), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('type_code', name='uq_membership_type_type_code'),
        UniqueConstraint('type_name', name='uq_membership_type_type_name'),
    )


class MetricType(Base):
    __tablename__ = 'metric_type'
    metric_type_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    metric_code = mapped_column(String(30), nullable=False)
    metric_name = mapped_column(String(100), nullable=False)
    description = mapped_column(String(300))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('metric_code', name='uq_metric_type_metric_code'),
        UniqueConstraint('metric_name', name='uq_metric_type_metric_name'),
    )


class Organizer(Base):
    __tablename__ = 'organizer'
    organizer_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('organization_id', name='uq_organizer_organization_id'),
    )


class ParticipationLevel(Base):
    __tablename__ = 'participation_level'
    participation_level_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    level_code = mapped_column(String(30), nullable=False)
    level_name = mapped_column(String(100), nullable=False)
    display_order = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('level_code', name='uq_participation_level_level_code'),
        UniqueConstraint('level_name', name='uq_participation_level_level_name'),
    )


class ProfessionalContributionType(Base):
    __tablename__ = 'professional_contribution_type'
    professional_contribution_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    contribution_code = mapped_column(String(60), nullable=False)
    contribution_name = mapped_column(String(180), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('contribution_code', name='uq_professional_contribution_type_contribution_code'),
        UniqueConstraint('contribution_name', name='uq_professional_contribution_type_contribution_name'),
    )


class PublicationType(Base):
    __tablename__ = 'publication_type'
    publication_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    publication_type_code = mapped_column(String(40), nullable=False)
    publication_type_name = mapped_column(String(120), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('publication_type_code', name='uq_publication_type_publication_type_code'),
        UniqueConstraint('publication_type_name', name='uq_publication_type_publication_type_name'),
    )


class Publisher(Base):
    __tablename__ = 'publisher'
    publisher_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('organization_id', name='uq_publisher_organization_id'),
    )


class ResearchStatus(Base):
    __tablename__ = 'research_status'
    research_status_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    status_code = mapped_column(String(30), nullable=False)
    status_name = mapped_column(String(100), nullable=False)
    display_order = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    is_terminal = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('status_code', name='uq_research_status_status_code'),
        UniqueConstraint('status_name', name='uq_research_status_status_name'),
    )


class RoleType(Base):
    __tablename__ = 'role_type'
    role_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_code = mapped_column(String(50), nullable=False)
    role_name = mapped_column(String(150), nullable=False)
    description = mapped_column(String(500))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('role_code', name='uq_role_type_role_code'),
        UniqueConstraint('role_name', name='uq_role_type_role_name'),
    )


class VerificationStatus(Base):
    __tablename__ = 'verification_status'
    verification_status_id = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    status_code = mapped_column(String(30), nullable=False)
    status_name = mapped_column(String(80), nullable=False)
    is_terminal = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('status_code', name='uq_verification_status_status_code'),
        UniqueConstraint('status_name', name='uq_verification_status_status_name'),
    )
