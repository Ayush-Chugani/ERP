from typing import ClassVar

from django.db import models

from apps.core.fields import UnsignedAutoField
from apps.documents_exit.fields import NativeTimestampField
from apps.people_master.fields import UnsignedBigAutoField
from apps.student_support.fields import (
    CanonicalDateTimeField,
    CanonicalTextField,
    CurrentTimestamp,
    NativeEnumField,
)

CAPABILITIES = (
    "manage_types",
    "create_announcement",
    "edit_announcement",
    "submit_announcement",
    "review_announcement",
    "approve_announcement",
    "reject_announcement",
    "archive_announcement",
    "manage_attachments",
    "view_audit",
    "publish_institution",
)


class Status(models.TextChoices):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class Audience(models.TextChoices):
    ALL = "ALL"
    STUDENTS = "STUDENTS"
    STAFF = "STAFF"
    PROGRAMME = "PROGRAMME"
    DEPARTMENT = "DEPARTMENT"
    CUSTOM = "CUSTOM"


def fk(model, **kw):
    return models.ForeignKey(model, on_delete=models.PROTECT, db_index=False, **kw)


class AnnouncementType(models.Model):
    announcement_type_id = UnsignedAutoField(bits=16, primary_key=True)
    type_code = models.CharField(max_length=30, unique=True)
    type_name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "announcement_type"
        default_permissions = ()


class Announcement(models.Model):
    announcement_id = UnsignedBigAutoField(primary_key=True)
    institution = fk("organization.Institution", db_column="institution_id")
    announcement_type = fk(AnnouncementType, db_column="announcement_type_id")
    department = fk(
        "organization.Department", null=True, blank=True, db_column="department_id"
    )
    title = models.CharField(max_length=250)
    description = CanonicalTextField()
    publish_from = CanonicalDateTimeField()
    publish_to = CanonicalDateTimeField(null=True, blank=True)
    approval_status = NativeEnumField(
        max_length=8, choices=Status.choices, default="DRAFT", db_default="DRAFT"
    )
    audience_type = NativeEnumField(
        max_length=10, choices=Audience.choices, default="ALL", db_default="ALL"
    )
    created_at = NativeTimestampField(db_default=CurrentTimestamp(), editable=False)

    class Meta:
        db_table = "announcement"
        default_permissions = ()
        permissions: ClassVar[list] = [
            (x, x.replace("_", " ").title()) for x in CAPABILITIES
        ]


class AnnouncementAttachment(models.Model):
    pk = models.CompositePrimaryKey("announcement_id", "file_object_id")
    announcement = fk(
        Announcement, db_column="announcement_id", related_name="attachments"
    )
    file_object = fk("documents_exit.FileObject", db_column="file_object_id")
    display_order = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "announcement_attachment"
        default_permissions = ()


class ProgrammeTarget(models.Model):
    pk = models.CompositePrimaryKey("announcement_id", "programme_id")
    announcement = fk(Announcement, related_name="programme_targets")
    programme = fk("organization.Programme")

    class Meta:
        db_table = "announcement_programme_target"
        default_permissions = ()


class UserTarget(models.Model):
    pk = models.CompositePrimaryKey("announcement_id", "user_id")
    announcement = fk(Announcement, related_name="user_targets")
    user = fk("accounts.User")

    class Meta:
        db_table = "announcement_user_target"
        default_permissions = ()
