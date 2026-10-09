"""SQLAlchemy models for the documents_exit domain (generated from the SIMS schema, then maintained by hand)."""
from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index,
                        Integer, LargeBinary, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class CertificateRequest(Base):
    __tablename__ = 'certificate_request'
    certificate_request_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_number = mapped_column(String(30), nullable=False)
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    certificate_type_id = mapped_column(Integer, ForeignKey('certificate_type.certificate_type_id'), nullable=False)
    requested_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    purpose = mapped_column(String(500))
    request_status = mapped_column(String(12), nullable=False, server_default=text("'SUBMITTED'"))
    issued_at = mapped_column(DateTime(timezone=True))
    certificate_number = mapped_column(String(50))
    file_object_id = mapped_column(BigInteger, ForeignKey('file_object.file_object_id'))
    __table_args__ = (
        UniqueConstraint('certificate_number', name='uq_certificate_request_certificate_number'),
        UniqueConstraint('request_number', name='uq_certificate_request_request_number'),
        Index('ix_certificate_request_file_object_id', 'file_object_id'),
        Index('ix_certificate_request_student_id', 'student_id'),
        Index('ix_certificate_request_certificate_type_id', 'certificate_type_id'),
        CheckConstraint("request_status IN ('SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'ISSUED', 'CANCELLED')", name='ck_certificate_request_request_status_enum'),
    )


class CertificateType(Base):
    __tablename__ = 'certificate_type'
    certificate_type_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    certificate_code = mapped_column(String(30), nullable=False)
    certificate_name = mapped_column(String(100), nullable=False)
    is_active = mapped_column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint('certificate_code', name='uq_certificate_type_certificate_code'),
        UniqueConstraint('certificate_name', name='uq_certificate_type_certificate_name'),
    )


class FileObject(Base):
    __tablename__ = 'file_object'
    file_object_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    storage_provider = mapped_column(String(30), nullable=False)
    storage_key = mapped_column(String(500), nullable=False)
    original_file_name = mapped_column(String(255), nullable=False)
    mime_type = mapped_column(String(100), nullable=False)
    file_size_bytes = mapped_column(BigInteger, nullable=False)
    checksum_sha256 = mapped_column(String(64))
    stored_file_name = mapped_column(String(255))
    storage_url = mapped_column(String(1000))
    file_extension = mapped_column(String(20))
    confidentiality_level = mapped_column(String(17), nullable=False, server_default=text("'INTERNAL'"))
    is_encrypted = mapped_column(Boolean, nullable=False, server_default=text("false"))
    uploaded_by_user_id = mapped_column(BigInteger, ForeignKey('user_account.user_id'))
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('storage_key', name='uq_file_object_storage_key'),
        Index('ix_file_object_uploaded_by_user_id', 'uploaded_by_user_id'),
        CheckConstraint("confidentiality_level IN ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED', 'HIGHLY_RESTRICTED')", name='ck_file_object_confidentiality_level_enum'),
        CheckConstraint("((checksum_sha256 is null) or regexp_like(checksum_sha256,'^[0-9A-Fa-f]{64}$'))", name='ck_file_object_file_object_checksum'),
        CheckConstraint('(file_size_bytes > 0)', name='ck_file_object_file_object_size'),
    )


class StudentDocument(Base):
    __tablename__ = 'student_document'
    student_document_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id = mapped_column(BigInteger, ForeignKey('student.student_id'), nullable=False)
    document_type_id = mapped_column(Integer, ForeignKey('document_type.document_type_id'), nullable=False)
    file_object_id = mapped_column(BigInteger, ForeignKey('file_object.file_object_id'), nullable=False)
    document_number = mapped_column(String(100))
    issue_date = mapped_column(Date)
    expiry_date = mapped_column(Date)
    verification_status = mapped_column(String(8), nullable=False, server_default=text("'PENDING'"))
    verified_at = mapped_column(DateTime(timezone=True))
    remarks = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint('student_id', 'document_type_id', 'document_number', name='uq_student_document_student_id_document_type_id_docum_ad854f'),
        Index('ix_student_document_file_object_id', 'file_object_id'),
        Index('ix_student_document_document_type_id', 'document_type_id'),
        CheckConstraint("verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED')", name='ck_student_document_verification_status_enum'),
    )


class StudentExit(Base):
    __tablename__ = 'student_exit'
    student_exit_id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    enrolment_id = mapped_column(BigInteger, ForeignKey('student_programme_enrolment.enrolment_id'), nullable=False)
    exit_type = mapped_column(String(11), nullable=False)
    exit_date = mapped_column(Date, nullable=False)
    destination_institution = mapped_column(String(250))
    old_registration_number = mapped_column(String(50))
    remarks = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint('enrolment_id', name='uq_student_exit_enrolment_id'),
        CheckConstraint("exit_type IN ('COMPLETION', 'TRANSFER', 'WITHDRAWAL', 'TERMINATION', 'OTHER')", name='ck_student_exit_exit_type_enum'),
    )
