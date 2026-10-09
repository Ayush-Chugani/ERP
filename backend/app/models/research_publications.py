"""SQLAlchemy models for the research_publications domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class Journal(Base):
    __tablename__ = 'journal'
    journal_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    journal_name = mapped_column(String(300), nullable=False)
    journal_type_id = mapped_column(SmallInteger, ForeignKey('journal_type.journal_type_id'), nullable=False)
    publisher_id = mapped_column(BigInteger, ForeignKey('publisher.publisher_id'))
    issn = mapped_column(String(20))
    eissn = mapped_column(String(20))
    website_url = mapped_column(String(500))
    country_id = mapped_column(Integer, ForeignKey('country.country_id'))
    is_peer_reviewed_default = mapped_column(Boolean)
    is_open_access_default = mapped_column(Boolean)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('eissn', name='uq_journal_eissn'),
        UniqueConstraint('issn', name='uq_journal_issn'),
        Index('ix_journal_country_id', 'country_id'),
        Index('ix_journal_publisher_id', 'publisher_id'),
        Index('ix_journal_journal_type_id', 'journal_type_id'),
    )


class JournalMetric(Base):
    __tablename__ = 'journal_metric'
    journal_metric_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    journal_id = mapped_column(BigInteger, ForeignKey('journal.journal_id'), nullable=False)
    metric_type_id = mapped_column(SmallInteger, ForeignKey('metric_type.metric_type_id'), nullable=False)
    metric_year = mapped_column(SmallInteger, nullable=False)
    metric_value = mapped_column(Numeric(12, 4), nullable=False)
    quartile = mapped_column(String(10))
    source_name = mapped_column(String(150))
    source_url = mapped_column(String(1000))
    verified_at = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('journal_id', 'metric_type_id', 'metric_year', name='uq_journal_metric_journal_id_metric_type_id_metric_year'),
        Index('ix_journal_metric_metric_type_id', 'metric_type_id'),
        CheckConstraint('(metric_value >= 0)', name='ck_journal_metric_journal_metric_value'),
    )


class JournalPublication(Base):
    __tablename__ = 'journal_publication'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    publication_type_id = mapped_column(Integer, ForeignKey('publication_type.publication_type_id'), nullable=False)
    journal_id = mapped_column(BigInteger, ForeignKey('journal.journal_id'), nullable=False)
    paper_title = mapped_column(String(500), nullable=False)
    volume_number = mapped_column(String(50))
    issue_number = mapped_column(String(50))
    edition = mapped_column(String(100))
    page_from = mapped_column(String(30))
    page_to = mapped_column(String(30))
    article_number = mapped_column(String(60))
    publication_date = mapped_column(Date)
    publication_year = mapped_column(SmallInteger, nullable=False)
    doi = mapped_column(String(255))
    url = mapped_column(String(1000))
    peer_reviewed = mapped_column(Boolean, nullable=False, server_default=text("false"))
    open_access = mapped_column(Boolean, nullable=False, server_default=text("false"))
    primary_author_position = mapped_column(Integer)
    primary_staff_corresponding_author = mapped_column(Boolean, nullable=False, server_default=text("false"))
    affiliation_text = mapped_column(String(500))
    abstract_text = mapped_column(Text)
    keywords = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint('doi', name='uq_journal_publication_doi'),
        Index('ix_journal_publication_journal_id', 'journal_id'),
        Index('ix_journal_publication_publication_type_id', 'publication_type_id'),
    )


class JournalPublicationIndexing(Base):
    __tablename__ = 'journal_publication_indexing'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('journal_publication.staff_activity_id'), primary_key=True, autoincrement=False)
    indexing_agency_id = mapped_column(Integer, ForeignKey('indexing_agency.indexing_agency_id'), primary_key=True, autoincrement=False)
    indexed_year = mapped_column(SmallInteger)
    indexing_status = mapped_column(String(12), nullable=False, server_default=text("'CLAIMED'"))
    source_url = mapped_column(String(1000))
    remarks = mapped_column(String(500))
    __table_args__ = (
        Index('ix_journal_publication_indexing_indexing_agency_id', 'indexing_agency_id'),
        CheckConstraint("indexing_status IN ('CLAIMED', 'VERIFIED', 'DISCONTINUED', 'NOT_INDEXED')", name='ck_journal_publication_indexing_indexing_status_enum'),
    )
