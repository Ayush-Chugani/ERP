"""SQLAlchemy models for the research_proposals domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class ResearchProposal(Base):
    __tablename__ = 'research_proposal'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    proposal_title = mapped_column(String(500), nullable=False)
    principal_investigator_employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    department_id = mapped_column(Integer, ForeignKey('department.department_id'), nullable=False)
    proposal_submission_date = mapped_column(Date)
    funding_agency_id = mapped_column(BigInteger, ForeignKey('funding_agency.funding_agency_id'))
    funding_type_id = mapped_column(SmallInteger, ForeignKey('funding_type.funding_type_id'))
    scheme_program_name = mapped_column(String(300))
    requested_amount = mapped_column(Numeric(16, 2))
    currency_code = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    research_status_id = mapped_column(SmallInteger, ForeignKey('research_status.research_status_id'), nullable=False)
    proposal_reference_number = mapped_column(String(150))
    project_objectives = mapped_column(Text)
    research_domain = mapped_column(String(300))
    expected_outcomes = mapped_column(Text)
    review_comments = mapped_column(Text)
    __table_args__ = (
        Index('ix_research_proposal_department_id', 'department_id'),
        Index('ix_research_proposal_funding_agency_id', 'funding_agency_id'),
        Index('ix_research_proposal_funding_type_id', 'funding_type_id'),
        Index('ix_research_proposal_principal_investigator_employee_id', 'principal_investigator_employee_id'),
        Index('ix_research_proposal_research_status_id', 'research_status_id'),
        CheckConstraint('((requested_amount is null) or (requested_amount >= 0))', name='ck_research_proposal_research_proposal_requested_amount'),
    )
