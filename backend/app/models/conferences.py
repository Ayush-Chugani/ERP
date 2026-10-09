"""SQLAlchemy models for the conferences domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class ConferenceActivity(Base):
    __tablename__ = 'conference_activity'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    conference_event_id = mapped_column(BigInteger, ForeignKey('conference_event.conference_event_id'), nullable=False)
    conference_contribution_type_id = mapped_column(SmallInteger, ForeignKey('conference_contribution_type.conference_contribution_type_id'), nullable=False)
    publication_type_id = mapped_column(Integer, ForeignKey('publication_type.publication_type_id'))
    paper_title = mapped_column(String(500))
    abstract_text = mapped_column(Text)
    proceedings_title = mapped_column(String(500))
    proceedings_volume = mapped_column(String(100))
    proceedings_issue = mapped_column(String(100))
    page_from = mapped_column(String(30))
    page_to = mapped_column(String(30))
    isbn = mapped_column(String(30))
    issn = mapped_column(String(20))
    doi = mapped_column(String(255))
    proceedings_url = mapped_column(String(1000))
    presentation_title = mapped_column(String(500))
    award_name = mapped_column(String(250))
    award_details = mapped_column(Text)
    award_date = mapped_column(Date)
    __table_args__ = (
        UniqueConstraint('doi', name='uq_conference_activity_doi'),
        Index('ix_conference_activity_conference_contribution_type_id', 'conference_contribution_type_id'),
        Index('ix_conference_activity_conference_event_id', 'conference_event_id'),
        Index('ix_conference_activity_publication_type_id', 'publication_type_id'),
    )


class ConferenceActivityIndexing(Base):
    __tablename__ = 'conference_activity_indexing'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('conference_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    indexing_agency_id = mapped_column(Integer, ForeignKey('indexing_agency.indexing_agency_id'), primary_key=True, autoincrement=False)
    indexing_status = mapped_column(String(12), nullable=False, server_default=text("'CLAIMED'"))
    source_url = mapped_column(String(1000))
    remarks = mapped_column(String(500))
    __table_args__ = (
        Index('ix_conference_activity_indexing_indexing_agency_id', 'indexing_agency_id'),
        CheckConstraint("indexing_status IN ('CLAIMED', 'VERIFIED', 'DISCONTINUED', 'NOT_INDEXED')", name='ck_conference_activity_indexing_indexing_status_enum'),
    )


class ConferenceEvent(Base):
    __tablename__ = 'conference_event'
    conference_event_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conference_title = mapped_column(String(500), nullable=False)
    conference_edition = mapped_column(String(100))
    organizer_id = mapped_column(BigInteger, ForeignKey('organizer.organizer_id'))
    sponsoring_organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'))
    proceedings_publisher_id = mapped_column(BigInteger, ForeignKey('publisher.publisher_id'))
    participation_level_id = mapped_column(SmallInteger, ForeignKey('participation_level.participation_level_id'))
    event_mode_id = mapped_column(SmallInteger, ForeignKey('event_mode.event_mode_id'))
    venue_name = mapped_column(String(250))
    city = mapped_column(String(120))
    state_id = mapped_column(Integer, ForeignKey('state.state_id'))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    start_date = mapped_column(Date, nullable=False)
    end_date = mapped_column(Date, nullable=False)
    conference_website = mapped_column(String(1000))
    brochure_url = mapped_column(String(1000))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index('ix_conference_event_country_id', 'country_id'),
        Index('ix_conference_event_participation_level_id', 'participation_level_id'),
        Index('ix_conference_event_event_mode_id', 'event_mode_id'),
        Index('ix_conference_event_organizer_id', 'organizer_id'),
        Index('ix_conference_event_proceedings_publisher_id', 'proceedings_publisher_id'),
        Index('ix_conference_event_sponsoring_organization_id', 'sponsoring_organization_id'),
        Index('ix_conference_event_state_id', 'state_id'),
        CheckConstraint('(end_date >= start_date)', name='ck_conference_event_conference_event_dates'),
    )
