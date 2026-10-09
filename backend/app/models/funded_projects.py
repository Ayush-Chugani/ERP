"""SQLAlchemy models for the funded_projects domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class FundedResearchProject(Base):
    __tablename__ = 'funded_research_project'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    source_proposal_activity_id = mapped_column(BigInteger, ForeignKey('research_proposal.staff_activity_id'))
    project_title = mapped_column(String(500), nullable=False)
    principal_investigator_employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    department_id = mapped_column(Integer, ForeignKey('department.department_id'), nullable=False)
    funding_agency_id = mapped_column(BigInteger, ForeignKey('funding_agency.funding_agency_id'), nullable=False)
    funding_type_id = mapped_column(SmallInteger, ForeignKey('funding_type.funding_type_id'), nullable=False)
    scheme_program_name = mapped_column(String(300))
    requested_amount = mapped_column(Numeric(16, 2))
    sanctioned_amount = mapped_column(Numeric(16, 2), nullable=False)
    amount_received = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0.00"))
    amount_utilized = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0.00"))
    currency_code = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    sanction_date = mapped_column(Date, nullable=False)
    sanction_order_number = mapped_column(String(150))
    project_start_date = mapped_column(Date, nullable=False)
    project_end_date = mapped_column(Date)
    duration_months = mapped_column(Integer)
    research_status_id = mapped_column(SmallInteger, ForeignKey('research_status.research_status_id'), nullable=False)
    project_objectives = mapped_column(Text)
    research_domain = mapped_column(String(300))
    project_outcomes = mapped_column(Text)
    publications_generated = mapped_column(Text)
    patents_generated = mapped_column(Text)
    products_generated = mapped_column(Text)
    other_outputs = mapped_column(Text)
    utilization_summary = mapped_column(Text)
    completion_date = mapped_column(Date)
    __table_args__ = (
        UniqueConstraint('source_proposal_activity_id', name='uq_funded_research_project_source_proposal_activity_id'),
        Index('ix_funded_research_project_department_id', 'department_id'),
        Index('ix_funded_research_project_funding_agency_id', 'funding_agency_id'),
        Index('ix_funded_research_project_funding_type_id', 'funding_type_id'),
        Index('ix_funded_research_project_principal_investigator_emp_937f35', 'principal_investigator_employee_id'),
        Index('ix_funded_research_project_research_status_id', 'research_status_id'),
        Index('ix_funded_research_project_project_end_date', 'project_end_date'),
        Index('ix_funded_research_project_sanction_date', 'sanction_date'),
        Index('ix_funded_research_project_project_start_date', 'project_start_date'),
        CheckConstraint('((sanctioned_amount >= 0) and (amount_received >= 0) and (amount_utilized >= 0) and ((requested_amount is null) or (requested_amount >= 0)))', name='ck_funded_research_project_funded_project_amounts'),
        CheckConstraint('((project_end_date is null) or (project_end_date >= project_start_date))', name='ck_funded_research_project_funded_project_dates'),
    )


class ResearchUtilizationVoid(Base):
    __tablename__ = 'research_utilization_void'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reason = mapped_column(Text, nullable=False)
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    utilization_id = mapped_column(BigInteger, ForeignKey('research_project_financial_utilization.utilization_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('utilization_id', name='uq_research_utilization_void_utilization_id'),
        Index('ix_research_utilization_void_actor_id', 'actor_id'),
    )


class ResearchProjectFinancialUtilization(Base):
    __tablename__ = 'research_project_financial_utilization'
    utilization_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    staff_activity_id = mapped_column(BigInteger, ForeignKey('funded_research_project.staff_activity_id'), nullable=False)
    financial_year = mapped_column(String(9))
    reporting_period_from = mapped_column(Date)
    reporting_period_to = mapped_column(Date)
    opening_balance = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0.00"))
    amount_received = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0.00"))
    expenditure_amount = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0.00"))
    closing_balance = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0.00"))
    utilization_certificate_number = mapped_column(String(150))
    statement_of_expenditure_number = mapped_column(String(150))
    remarks = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        Index('ix_research_project_financial_utilization_staff_activity_id', 'staff_activity_id'),
        CheckConstraint('((opening_balance >= 0) and (amount_received >= 0) and (expenditure_amount >= 0) and (closing_balance >= 0))', name='ck_research_project_financial_utilization_project_uti_13ed26'),
        CheckConstraint('((reporting_period_to is null) or (reporting_period_from is null) or (reporting_period_to >= reporting_period_from))', name='ck_research_project_financial_utilization_project_uti_60cb0b'),
    )
