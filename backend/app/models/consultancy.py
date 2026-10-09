"""SQLAlchemy models for the consultancy domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class ConsultancyProject(Base):
    __tablename__ = 'consultancy_project'
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), primary_key=True, autoincrement=False)
    consultancy_title = mapped_column(String(500), nullable=False)
    client_organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'), nullable=False)
    principal_consultant_employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    consultancy_type = mapped_column(String(26), nullable=False, server_default=text("'CONSULTANCY'"))
    work_order_number = mapped_column(String(150))
    agreement_number = mapped_column(String(150))
    purchase_order_number = mapped_column(String(150))
    project_start_date = mapped_column(Date, nullable=False)
    completion_date = mapped_column(Date)
    consultancy_amount = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0.00"))
    amount_received = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0.00"))
    faculty_incentive_share = mapped_column(Numeric(16, 2))
    currency_code = mapped_column(String(3), nullable=False, server_default=text("'INR'"))
    deliverables = mapped_column(Text)
    status = mapped_column(String(9), nullable=False, server_default=text("'PROPOSED'"))
    client_feedback = mapped_column(Text)
    __table_args__ = (
        Index('ix_consultancy_project_client_organization_id', 'client_organization_id'),
        Index('ix_consultancy_project_principal_consultant_employee_id', 'principal_consultant_employee_id'),
        CheckConstraint("consultancy_type IN ('CONSULTANCY', 'INDUSTRY_SPONSORED_PROJECT', 'TESTING_SERVICE', 'TRAINING_SERVICE', 'OTHER')", name='ck_consultancy_project_consultancy_type_enum'),
        CheckConstraint("status IN ('PROPOSED', 'APPROVED', 'ONGOING', 'COMPLETED', 'CANCELLED', 'CLOSED')", name='ck_consultancy_project_status_enum'),
        CheckConstraint('((completion_date is null) or (completion_date >= project_start_date))', name='ck_consultancy_project_consultancy_dates'),
        CheckConstraint('((consultancy_amount >= 0) and (amount_received >= 0) and ((faculty_incentive_share is null) or (faculty_incentive_share >= 0)))', name='ck_consultancy_project_consultancy_amounts'),
    )


class ConsultancyMilestone(Base):
    __tablename__ = 'consultancy_milestone'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sequence = mapped_column(Integer, nullable=False)
    title = mapped_column(String(200), nullable=False)
    description = mapped_column(Text)
    due_date = mapped_column(Date, nullable=False)
    completion_date = mapped_column(Date)
    acceptance_date = mapped_column(Date)
    status = mapped_column(String(9), nullable=False)
    client_remarks = mapped_column(Text)
    project_id = mapped_column(BigInteger, ForeignKey('consultancy_project.staff_activity_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('project_id', 'sequence', name='uq_consultancy_milestone_project_id_sequence'),
        CheckConstraint("status IN ('PLANNED', 'COMPLETED', 'ACCEPTED', 'CANCELLED')", name='ck_consultancy_milestone_status_enum'),
        CheckConstraint('((acceptance_date is null) or ((acceptance_date >= completion_date) and (completion_date is not null)))', name='ck_consultancy_milestone_consultancy_acceptance'),
        CheckConstraint('(sequence > 0)', name='ck_consultancy_milestone_consultancy_milestone_seq'),
        CheckConstraint('(sequence >= 0)', name='ck_consultancy_milestone_platform_consultancy_milesto_2b0c57'),
    )


class ConsultancyReceipt(Base):
    __tablename__ = 'consultancy_receipt'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    receipt_date = mapped_column(Date, nullable=False)
    amount = mapped_column(Numeric(16, 2), nullable=False)
    currency_code = mapped_column(String(3), nullable=False)
    reference_number = mapped_column(String(150), nullable=False)
    invoice_number = mapped_column(String(150))
    payment_mode = mapped_column(String(80))
    remarks = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    document_attachment_id = mapped_column(BigInteger, ForeignKey('staff_activity_attachment.id'))
    project_id = mapped_column(BigInteger, ForeignKey('consultancy_project.staff_activity_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('project_id', 'reference_number', name='uq_consultancy_receipt_project_id_reference_number'),
        Index('ix_consultancy_receipt_actor_id', 'actor_id'),
        Index('ix_consultancy_receipt_document_attachment_id', 'document_attachment_id'),
        CheckConstraint('(amount >= 0)', name='ck_consultancy_receipt_consultancy_receipt_amount'),
    )


class ConsultancyReceiptVoid(Base):
    __tablename__ = 'consultancy_receipt_void'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reason = mapped_column(Text, nullable=False)
    actor_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    receipt_id = mapped_column(BigInteger, ForeignKey('consultancy_receipt.id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('receipt_id', name='uq_consultancy_receipt_void_receipt_id'),
        Index('ix_consultancy_receipt_void_actor_id', 'actor_id'),
    )


class ConsultancyTeamMember(Base):
    __tablename__ = 'consultancy_team_member'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_role = mapped_column(String(80), nullable=False)
    contribution_description = mapped_column(Text)
    start_date = mapped_column(Date, nullable=False)
    end_date = mapped_column(Date)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    employee_id = mapped_column(BigInteger, ForeignKey('employee.employee_id'), nullable=False)
    project_id = mapped_column(BigInteger, ForeignKey('consultancy_project.staff_activity_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('project_id', 'employee_id', name='uq_consultancy_team_member_project_id_employee_id'),
        Index('ix_consultancy_team_member_employee_id', 'employee_id'),
        CheckConstraint('((end_date is null) or (end_date >= start_date))', name='ck_consultancy_team_member_consultancy_team_dates'),
    )
