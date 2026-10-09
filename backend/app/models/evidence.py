"""SQLAlchemy models for the evidence domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class EvidenceDocument(Base):
    __tablename__ = 'evidence_document'
    evidence_document_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    staff_activity_id = mapped_column(BigInteger, ForeignKey('staff_activity.staff_activity_id'), nullable=False)
    document_type_id = mapped_column(Integer, ForeignKey('document_type.document_type_id'), nullable=False)
    evidence_type_id = mapped_column(Integer, ForeignKey('evidence_type.evidence_type_id'))
    confidentiality_level_id = mapped_column(SmallInteger, ForeignKey('confidentiality_level.confidentiality_level_id'), nullable=False)
    document_title = mapped_column(String(500), nullable=False)
    description = mapped_column(Text)
    academic_year_id = mapped_column(Integer, ForeignKey('academic_year.academic_year_id'))
    document_issue_date = mapped_column(Date)
    issuing_authority = mapped_column(String(300))
    issuing_organization_id = mapped_column(BigInteger, ForeignKey('external_organization.organization_id'))
    certificate_document_number = mapped_column(String(150))
    expiry_date = mapped_column(Date)
    verification_status_id = mapped_column(SmallInteger, ForeignKey('verification_status.verification_status_id'), nullable=False)
    verified_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    verified_at = mapped_column(DateTime(timezone=True))
    verification_remarks = mapped_column(String(1000))
    approval_status_id = mapped_column(SmallInteger, ForeignKey('approval_status.approval_status_id'), nullable=False)
    approved_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    approved_at = mapped_column(DateTime(timezone=True))
    rejection_reason = mapped_column(String(1000))
    current_version_number = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    updated_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = mapped_column(DateTime(timezone=True))
    deleted_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    deletion_reason = mapped_column(String(1000))
    __table_args__ = (
        Index('ix_evidence_document_approval_status_id', 'approval_status_id'),
        Index('ix_evidence_document_approved_by_user_id', 'approved_by_user_id'),
        Index('ix_evidence_document_confidentiality_level_id', 'confidentiality_level_id'),
        Index('ix_evidence_document_created_by_user_id', 'created_by_user_id'),
        Index('ix_evidence_document_deleted_by_user_id', 'deleted_by_user_id'),
        Index('ix_evidence_document_document_type_id', 'document_type_id'),
        Index('ix_evidence_document_evidence_type_id', 'evidence_type_id'),
        Index('ix_evidence_document_issuing_organization_id', 'issuing_organization_id'),
        Index('ix_evidence_document_updated_by_user_id', 'updated_by_user_id'),
        Index('ix_evidence_document_verified_by_user_id', 'verified_by_user_id'),
        Index('ix_evidence_document_academic_year_id_document_type_id', 'academic_year_id', 'document_type_id'),
        Index('ix_evidence_document_staff_activity_id_document_type__61641a', 'staff_activity_id', 'document_type_id', 'evidence_type_id', 'is_active'),
        Index('ix_evidence_document_certificate_document_number', 'certificate_document_number'),
        Index('ix_evidence_document_expiry_date_is_active', 'expiry_date', 'is_active'),
        Index('ix_evidence_document_verification_status_id_approval__26c490', 'verification_status_id', 'approval_status_id', 'created_at'),
        CheckConstraint('((expiry_date is null) or (document_issue_date is null) or (expiry_date >= document_issue_date))', name='ck_evidence_document_evidence_document_dates'),
        CheckConstraint('(current_version_number >= 1)', name='ck_evidence_document_evidence_document_version'),
    )


class EvidenceDocumentAudit(Base):
    __tablename__ = 'evidence_document_audit'
    evidence_document_audit_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evidence_document_id = mapped_column(BigInteger, ForeignKey('evidence_document.evidence_document_id'), nullable=False)
    evidence_document_version_id = mapped_column(BigInteger, ForeignKey('evidence_document_version.evidence_document_version_id'))
    action_code = mapped_column(String(19), nullable=False)
    performed_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    performed_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ip_address = mapped_column(String(45))
    user_agent = mapped_column(String(500))
    before_values = mapped_column(JSONB)
    after_values = mapped_column(JSONB)
    remarks = mapped_column(String(1000))
    __table_args__ = (
        Index('ix_evidence_document_audit_performed_by_user_id', 'performed_by_user_id'),
        Index('ix_evidence_document_audit_evidence_document_version_id', 'evidence_document_version_id'),
        Index('ix_evidence_document_audit_evidence_document_id_performed_at', 'evidence_document_id', 'performed_at'),
        CheckConstraint("action_code IN ('CREATE', 'UPLOAD', 'REPLACE', 'UPDATE_METADATA', 'PREVIEW', 'DOWNLOAD', 'VERIFY', 'REJECT_VERIFICATION', 'APPROVE', 'REJECT_APPROVAL', 'SOFT_DELETE', 'RESTORE', 'ACCESS_DENIED')", name='ck_evidence_document_audit_action_code_enum'),
    )


class EvidenceDocumentTag(Base):
    __tablename__ = 'evidence_document_tag'
    evidence_document_id = mapped_column(BigInteger, ForeignKey('evidence_document.evidence_document_id'), primary_key=True, autoincrement=False)
    evidence_tag_id = mapped_column(Integer, ForeignKey('evidence_tag.evidence_tag_id'), primary_key=True, autoincrement=False)
    __table_args__ = (
        Index('ix_evidence_document_tag_evidence_tag_id', 'evidence_tag_id'),
    )


class EvidenceDocumentVersion(Base):
    __tablename__ = 'evidence_document_version'
    evidence_document_version_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evidence_document_id = mapped_column(BigInteger, ForeignKey('evidence_document.evidence_document_id'), nullable=False)
    version_number = mapped_column(Integer, nullable=False)
    file_object_id = mapped_column(BigInteger, ForeignKey('file_object.file_object_id'), nullable=False)
    change_reason = mapped_column(String(1000))
    uploaded_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'), nullable=False)
    uploaded_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_current = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('evidence_document_id', 'file_object_id', name='uq_evidence_document_version_evidence_document_id_fil_b82a8e'),
        UniqueConstraint('evidence_document_id', 'version_number', name='uq_evidence_document_version_evidence_document_id_ver_df8a34'),
        Index('ix_evidence_document_version_file_object_id', 'file_object_id'),
        Index('ix_evidence_document_version_uploaded_by_user_id', 'uploaded_by_user_id'),
        Index('ix_evidence_document_version_evidence_document_id_is__74d199', 'evidence_document_id', 'is_current', 'version_number'),
        CheckConstraint('(version_number >= 1)', name='ck_evidence_document_version_evidence_version_number'),
    )


class EvidenceTag(Base):
    __tablename__ = 'evidence_tag'
    evidence_tag_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag_code = mapped_column(String(60), nullable=False)
    tag_name = mapped_column(String(120), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('tag_code', name='uq_evidence_tag_tag_code'),
        UniqueConstraint('tag_name', name='uq_evidence_tag_tag_name'),
    )


class EvidenceExpiryNotice(Base):
    __tablename__ = 'evidence_expiry_notice'
    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    expiry_date = mapped_column(Date, nullable=False)
    threshold_days = mapped_column(Integer, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    delivered_at = mapped_column(DateTime(timezone=True))
    attempts = mapped_column(Integer, nullable=False)
    document_id = mapped_column(BigInteger, ForeignKey('evidence_document.evidence_document_id'), nullable=False)
    __table_args__ = (
        UniqueConstraint('document_id', 'expiry_date', 'threshold_days', name='uq_evidence_expiry_notice_document_id_expiry_date_thr_262c34'),
        CheckConstraint('(threshold_days >= 0)', name='ck_evidence_expiry_notice_platform_evidence_expiry_no_a388c5'),
        CheckConstraint('(attempts >= 0)', name='ck_evidence_expiry_notice_platform_evidence_expiry_no_bf5184'),
    )
