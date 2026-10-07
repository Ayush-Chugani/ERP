from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.fields import UnsignedAutoField
from apps.documents_exit.fields import NativeTimestampField
from apps.identity_access.model_support import Evidence as AppendOnly
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import (
    CanonicalDateTimeField,
    CanonicalTextField,
    CurrentTimestamp,
    NativeEnumField,
)

from .fields import SourceIndex, VersionNumber

ACTIONS = (
    "CREATE",
    "UPLOAD",
    "REPLACE",
    "UPDATE_METADATA",
    "PREVIEW",
    "DOWNLOAD",
    "VERIFY",
    "REJECT_VERIFICATION",
    "APPROVE",
    "REJECT_APPROVAL",
    "SOFT_DELETE",
    "RESTORE",
    "ACCESS_DENIED",
)


class ActiveDocuments(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True, is_active=True)


class EvidenceDocument(models.Model):
    objects = ActiveDocuments()
    all_objects = models.Manager()
    evidence_document_id = UnsignedBigAutoField(primary_key=True)
    staff_activity = models.ForeignKey(
        "staff_activities.StaffActivity",
        on_delete=models.PROTECT,
        db_column="staff_activity_id",
        related_name="+",
    )
    document_type = models.ForeignKey(
        "common_reference.DocumentType",
        on_delete=models.PROTECT,
        db_column="document_type_id",
        related_name="+",
    )
    evidence_type = models.ForeignKey(
        "staff_profile.EvidenceType",
        on_delete=models.PROTECT,
        db_column="evidence_type_id",
        related_name="+",
        null=True,
        blank=True,
    )
    confidentiality_level = models.ForeignKey(
        "staff_profile.ConfidentialityLevel",
        on_delete=models.PROTECT,
        db_column="confidentiality_level_id",
        related_name="+",
    )
    academic_year = models.ForeignKey(
        "academic_calendar.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="+",
        null=True,
        blank=True,
    )
    issuing_organization = models.ForeignKey(
        "staff_profile.ExternalOrganization",
        on_delete=models.PROTECT,
        db_column="issuing_organization_id",
        related_name="+",
        null=True,
        blank=True,
    )
    verification_status = models.ForeignKey(
        "staff_profile.VerificationStatus",
        on_delete=models.PROTECT,
        db_column="verification_status_id",
        related_name="+",
    )
    verified_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        db_column="verified_by_user_id",
        related_name="+",
        null=True,
        blank=True,
    )
    approval_status = models.ForeignKey(
        "staff_profile.ApprovalStatus",
        on_delete=models.PROTECT,
        db_column="approval_status_id",
        related_name="+",
    )
    approved_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        db_column="approved_by_user_id",
        related_name="+",
        null=True,
        blank=True,
    )
    created_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        db_column="created_by_user_id",
        related_name="+",
    )
    updated_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        db_column="updated_by_user_id",
        related_name="+",
        null=True,
        blank=True,
    )
    deleted_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        db_column="deleted_by_user_id",
        related_name="+",
        null=True,
        blank=True,
    )
    document_title = models.CharField(max_length=500, db_collation="utf8mb4_unicode_ci")
    issuing_authority = models.CharField(
        max_length=300, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    certificate_document_number = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    verification_remarks = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    rejection_reason = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    deletion_reason = models.CharField(
        max_length=1000, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    description = CanonicalTextField(
        null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    document_issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    verified_at = CanonicalDateTimeField(null=True, blank=True)
    approved_at = CanonicalDateTimeField(null=True, blank=True)
    deleted_at = CanonicalDateTimeField(null=True, blank=True)
    current_version_number = VersionNumber(default=1, db_default=1)
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)

    class Meta:
        db_table = "evidence_document"
        indexes: ClassVar[list] = [
            SourceIndex(
                name="idx_evidence_activity",
                fields=[
                    "staff_activity",
                    "document_type",
                    "evidence_type",
                    "is_active",
                ],
            ),
            SourceIndex(
                name="idx_evidence_verification",
                fields=["verification_status", "approval_status", "created_at"],
            ),
            SourceIndex(
                name="idx_evidence_academic_year",
                fields=["academic_year", "document_type"],
            ),
            SourceIndex(
                name="idx_evidence_certificate_number",
                fields=["certificate_document_number"],
            ),
            SourceIndex(
                name="idx_evidence_expiry", fields=["expiry_date", "is_active"]
            ),
        ]
        base_manager_name = "all_objects"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(expiry_date__isnull=True)
                | models.Q(document_issue_date__isnull=True)
                | models.Q(expiry_date__gte=models.F("document_issue_date")),
                name="chk_evidence_document_dates",
            ),
            models.CheckConstraint(
                condition=models.Q(current_version_number__gte=1),
                name="chk_evidence_document_version",
            ),
        ]

    def clean(self):
        from .validators import validate_document

        validate_document(self)

    def __str__(self):
        return self.document_title

    @property
    def institution_id(self):
        return self.staff_activity.institution_id


class VersionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if kwargs != {"is_current": False}:
            raise ValidationError("Historical version content is immutable.")
        return super().update(**kwargs)

    def delete(self):
        raise ValidationError("Historical versions must be retained.")


class EvidenceDocumentVersion(models.Model):
    evidence_document_version_id = UnsignedBigAutoField(primary_key=True)
    evidence_document = models.ForeignKey(
        EvidenceDocument,
        on_delete=models.PROTECT,
        related_name="versions",
        db_column="evidence_document_id",
    )
    version_number = VersionNumber()
    file_object = models.ForeignKey(
        "documents_exit.FileObject",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="file_object_id",
    )
    change_reason = models.CharField(
        max_length=1000, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    uploaded_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="uploaded_by_user_id",
    )
    uploaded_at = NativeTimestampField(db_default=CurrentTimestamp())
    is_current = models.BooleanField(default=True, db_default=True)
    current_document_id = models.GeneratedField(
        expression=models.Case(
            models.When(is_current=True, then=models.F("evidence_document_id")),
            default=None,
        ),
        output_field=models.PositiveBigIntegerField(),
        db_persist=True,
        null=True,
    )
    objects = VersionQuerySet.as_manager()

    class Meta:
        db_table = "evidence_document_version"
        indexes: ClassVar[list] = [
            SourceIndex(
                name="idx_evidence_version_current",
                fields=["evidence_document", "is_current", "version_number"],
            ),
        ]
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["evidence_document", "version_number"],
                name="uq_evidence_document_version",
            ),
            models.UniqueConstraint(
                fields=["evidence_document", "file_object"],
                name="uq_evidence_document_file",
            ),
            models.CheckConstraint(
                condition=models.Q(version_number__gte=1),
                name="chk_evidence_version_number",
            ),
            models.UniqueConstraint(
                fields=["current_document_id"], name="uq_m33_current_document"
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "Use the replacement service; version content is immutable."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical versions must be retained.")


class EvidenceTag(models.Model):
    evidence_tag_id = UnsignedAutoField(primary_key=True)
    tag_code = models.CharField(
        max_length=60, unique=True, db_collation="utf8mb4_unicode_ci"
    )
    tag_name = models.CharField(
        max_length=120, unique=True, db_collation="utf8mb4_unicode_ci"
    )
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "evidence_tag"
        default_permissions = ()

    def __str__(self):
        return self.tag_name

    def clean(self):
        import re

        self.tag_code = self.tag_code.strip().upper()
        self.tag_name = " ".join(self.tag_name.split())
        if not re.fullmatch(r"[A-Z0-9_-]{1,60}", self.tag_code):
            raise ValidationError(
                {"tag_code": "Use letters, digits, underscore or hyphen."}
            )


class EvidenceDocumentTag(models.Model):
    pk = models.CompositePrimaryKey("evidence_document_id", "evidence_tag_id")
    evidence_document = models.ForeignKey(
        EvidenceDocument,
        on_delete=models.PROTECT,
        related_name="tag_links",
        db_column="evidence_document_id",
    )
    evidence_tag = models.ForeignKey(
        EvidenceTag,
        on_delete=models.PROTECT,
        related_name="+",
        db_column="evidence_tag_id",
    )

    class Meta:
        db_table = "evidence_document_tag"
        default_permissions = ()


class EvidenceDocumentAudit(AppendOnly):
    evidence_document_audit_id = UnsignedBigAutoField(primary_key=True)
    evidence_document = models.ForeignKey(
        EvidenceDocument,
        on_delete=models.PROTECT,
        related_name="audits",
        db_column="evidence_document_id",
    )
    evidence_document_version = models.ForeignKey(
        EvidenceDocumentVersion,
        on_delete=models.PROTECT,
        related_name="+",
        db_column="evidence_document_version_id",
        null=True,
        blank=True,
    )
    action_code = NativeEnumField(
        choices=[(a, a) for a in ACTIONS],
        max_length=19,
        db_collation="utf8mb4_unicode_ci",
    )
    performed_by_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="performed_by_user_id",
        null=True,
        blank=True,
    )
    performed_at = CanonicalDateTimeField(
        default=timezone.now, db_default=CurrentTimestamp()
    )
    ip_address = models.CharField(
        max_length=45, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    user_agent = models.CharField(
        max_length=500, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    before_values = models.JSONField(null=True, blank=True)
    after_values = models.JSONField(null=True, blank=True)
    remarks = models.CharField(
        max_length=1000, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )

    class Meta:
        db_table = "evidence_document_audit"
        indexes: ClassVar[list] = [
            SourceIndex(
                name="idx_evidence_audit_time",
                fields=["evidence_document", "performed_at"],
            ),
        ]
        default_permissions = ()


class EvidenceCommandReceipt(AppendOnly):
    actor = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    key = models.CharField(max_length=100)
    operation = models.CharField(max_length=40)
    digest = models.CharField(max_length=64)
    document = models.ForeignKey(EvidenceDocument, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    provenance = models.JSONField(default=dict)

    class Meta:
        db_table = "platform_evidence_command_receipt"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=["actor", "key"], name="uq_m33_actor_key")
        ]


class EvidenceExpiryNotice(models.Model):
    document = models.ForeignKey(EvidenceDocument, on_delete=models.PROTECT)
    expiry_date = models.DateField()
    threshold_days = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "platform_evidence_expiry_notice"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["document", "expiry_date", "threshold_days"],
                name="uq_m33_expiry_notice",
            )
        ]
