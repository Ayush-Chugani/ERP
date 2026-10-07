from typing import ClassVar

from django.db import models

from apps.core.fields import UnsignedAutoField
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import (
    CanonicalDateTimeField,
    CanonicalTextField,
    CurrentTimestamp,
    NativeEnumField,
)

from .fields import FixedHashField, NativeTimestampField


class Level(models.TextChoices):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"
    HIGHLY_RESTRICTED = "HIGHLY_RESTRICTED"


class Verification(models.TextChoices):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class RequestStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ISSUED = "ISSUED"
    CANCELLED = "CANCELLED"


class ExitType(models.TextChoices):
    COMPLETION = "COMPLETION"
    TRANSFER = "TRANSFER"
    WITHDRAWAL = "WITHDRAWAL"
    TERMINATION = "TERMINATION"
    OTHER = "OTHER"


CAPABILITIES = (
    "share_file",
    "access_confidential_shared_file",
    "view_own_document",
    "upload_own_document",
    "view_documents",
    "upload_documents",
    "verify_document",
    "access_restricted_file",
    "access_highly_restricted_file",
    "delete_file",
    "manage_certificate_type",
    "request_certificate",
    "view_certificates",
    "review_certificate",
    "approve_certificate",
    "issue_certificate",
    "view_exit",
    "finalize_exit",
    "terminate_enrolment",
    "view_document_audit",
)


def enum(choices, default=None):
    opts = {"choices": choices.choices, "max_length": max(map(len, choices.values))}
    if default:
        opts.update(default=default, db_default=default)
    return NativeEnumField(**opts)


def fk(model, **kw):
    return models.ForeignKey(model, on_delete=models.PROTECT, db_index=False, **kw)


class FileObject(models.Model):
    file_object_id = UnsignedBigAutoField(primary_key=True)
    storage_provider = models.CharField(max_length=30)
    storage_key = models.CharField(max_length=500, unique=True)
    original_file_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file_size_bytes = models.PositiveBigIntegerField()
    checksum_sha256 = FixedHashField(max_length=64, null=True, blank=True)
    stored_file_name = models.CharField(max_length=255, null=True, blank=True)
    storage_url = models.CharField(max_length=1000, null=True, blank=True)
    file_extension = models.CharField(max_length=20, null=True, blank=True)
    confidentiality_level = enum(Level, "INTERNAL")
    is_encrypted = models.BooleanField(default=False, db_default=False)
    uploaded_by_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, null=True, blank=True, related_name='+', db_column='uploaded_by_user_id')
    updated_at = NativeTimestampField(db_default=CurrentTimestamp())
    deleted_at = NativeTimestampField(null=True, blank=True)

    class Meta:
        db_table = "file_object"
        default_permissions = ()
        permissions = tuple((cap, cap.replace("_", " ")) for cap in CAPABILITIES)
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(file_size_bytes__gt=0), name="chk_file_object_size"
            ),
            models.CheckConstraint(
                condition=models.Q(checksum_sha256__isnull=True)
                | models.Q(checksum_sha256__regex=r"^[0-9A-Fa-f]{64}$"),
                name="chk_file_object_checksum",
            ),
        ]

    def save(self, *args, **kwargs):
        # Omit the database-owned ON UPDATE column from UPDATE statements.
        updating = not self._state.adding
        if updating:
            fields = kwargs.get("update_fields")
            if fields is None:
                fields = [
                    field.name
                    for field in self._meta.concrete_fields
                    if not field.primary_key
                ]
            kwargs["update_fields"] = [name for name in fields if name != "updated_at"]
        result = super().save(*args, **kwargs)
        if updating:
            self.refresh_from_db(fields=["updated_at"])
        return result

    def __str__(self):
        return f"File {self.pk}"


class StudentDocument(models.Model):
    student_document_id = UnsignedBigAutoField(primary_key=True)
    student = fk("people_master.Student")
    document_type = fk("common_reference.DocumentType")
    file_object = fk(FileObject)
    document_number = models.CharField(max_length=100, null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    verification_status = enum(Verification, "PENDING")
    verified_at = CanonicalDateTimeField(null=True, blank=True)
    remarks = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = "student_document"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["student", "document_type", "document_number"],
                name="uq_student_document",
            )
        ]

    def __str__(self):
        return f"Student document {self.pk}"


class CertificateType(models.Model):
    certificate_type_id = UnsignedAutoField(bits=16, primary_key=True)
    certificate_code = models.CharField(max_length=30, unique=True)
    certificate_name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "certificate_type"
        default_permissions = ()

    def __str__(self):
        return self.certificate_name


class CertificateRequest(models.Model):
    certificate_request_id = UnsignedBigAutoField(primary_key=True)
    request_number = models.CharField(max_length=30, unique=True)
    student = fk("people_master.Student")
    certificate_type = fk(CertificateType)
    requested_at = CanonicalDateTimeField(db_default=CurrentTimestamp())
    purpose = models.CharField(max_length=500, null=True, blank=True)
    request_status = enum(RequestStatus, "SUBMITTED")
    issued_at = CanonicalDateTimeField(null=True, blank=True)
    certificate_number = models.CharField(
        max_length=50, null=True, blank=True, unique=True
    )
    file_object = fk(FileObject, null=True, blank=True)

    class Meta:
        db_table = "certificate_request"
        default_permissions = ()

    def __str__(self):
        return self.request_number


class StudentExit(models.Model):
    student_exit_id = UnsignedBigAutoField(primary_key=True)
    enrolment = fk("admission_enrolment.StudentProgrammeEnrolment")
    exit_type = enum(ExitType)
    exit_date = models.DateField()
    destination_institution = models.CharField(max_length=250, null=True, blank=True)
    old_registration_number = models.CharField(max_length=50, null=True, blank=True)
    remarks = CanonicalTextField(null=True, blank=True)

    class Meta:
        db_table = "student_exit"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["enrolment"], name="uq_student_exit_enrolment"
            )
        ]

    def __str__(self):
        return f"Student exit {self.pk}"
