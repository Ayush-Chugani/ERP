import hashlib
import json
import re
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as ModelError
from django.utils import timezone
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.documents_exit import services as files
from apps.documents_exit import sharing
from apps.people_master.models import AccountLink
from apps.staff_activities.models import StaffActivity
from apps.staff_profile.models import ApprovalStatus, VerificationStatus

from . import audit
from . import permissions as p
from .models import (
    EvidenceCommandReceipt,
    EvidenceDocument,
    EvidenceDocumentAudit,
    EvidenceDocumentTag,
    EvidenceDocumentVersion,
    EvidenceTag,
)

EDITABLE = {"DRAFT", "REJECTED"}
METADATA = (
    "document_type_id",
    "evidence_type_id",
    "confidentiality_level_id",
    "document_title",
    "description",
    "academic_year_id",
    "document_issue_date",
    "issuing_authority",
    "issuing_organization_id",
    "certificate_document_number",
    "expiry_date",
)
WORKFLOW = (
    "verification_status_id",
    "verified_by_user_id",
    "verified_at",
    "verification_remarks",
    "approval_status_id",
    "approved_by_user_id",
    "approved_at",
    "rejection_reason",
)


class Conflict(APIException):
    status_code = 409
    default_detail = (
        "Evidence changed or the request key was reused. Refresh and retry safely."
    )


def guarded(fn):
    managed = files.command(fn)

    @wraps(fn)
    def run(*, actor, **kwargs):
        try:
            return managed(actor=actor, **kwargs)
        except (PermissionDenied, NotFound):
            audit.denied(actor, kwargs.get("document_id"))
            raise NotFound("Evidence unavailable.") from None

    return run


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def version(row):
    pk = row.pk if hasattr(row, "pk") else row
    return digest(
        [
            EvidenceDocument.all_objects.values().get(pk=pk),
            list(
                EvidenceDocumentTag.objects.filter(evidence_document_id=pk)
                .order_by("evidence_tag_id")
                .values_list("evidence_tag_id", flat=True)
            ),
            EvidenceDocumentAudit.objects.filter(evidence_document_id=pk)
            .exclude(action_code__in=["PREVIEW", "DOWNLOAD", "ACCESS_DENIED"])
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first(),
        ]
    )


def locked(actor, document_id, resource="DOCUMENT", action="READ", deleted=False):
    actor = p.principal(actor)
    row = (
        EvidenceDocument.all_objects.select_for_update()
        .select_related(
            "staff_activity__employee",
            "confidentiality_level",
            "verification_status",
            "approval_status",
            "document_type",
        )
        .get(pk=document_id)
    )
    p.document(actor, row, resource, action, deleted=deleted)
    return actor, row


def check_version(row, expected):
    if not expected or expected != version(row):
        raise Conflict()


def status(model, code):
    row = model.objects.filter(status_code=code, is_active=True).first()
    if row is None:
        raise ValidationError("Configure the evidence workflow status catalogue.")
    return row


def reset_workflow(row):
    row.verification_status = status(VerificationStatus, "PENDING")
    row.approval_status = status(ApprovalStatus, "DRAFT")
    for name in WORKFLOW:
        if name not in ("verification_status_id", "approval_status_id"):
            setattr(row, name, None)


def snapshot(row):
    return {name: getattr(row, name) for name in (*METADATA, *WORKFLOW)} | {
        "tags": list(
            EvidenceDocumentTag.objects.filter(evidence_document=row)
            .order_by("evidence_tag_id")
            .values_list("evidence_tag_id", flat=True)
        )
    }


def normalize(row):
    for name in METADATA:
        value = getattr(row, name)
        if isinstance(value, str):
            value = value.strip()
            if name == "document_title":
                value = " ".join(value.split())
            setattr(row, name, value or None)
    try:
        row.full_clean(
            exclude=["current_version_number", "created_at", "updated_at"],
            validate_unique=False,
            validate_constraints=False,
        )
    except ModelError as error:
        raise ValidationError(
            error.message_dict if hasattr(error, "message_dict") else error.messages
        ) from None
    for name in (
        "document_type",
        "evidence_type",
        "confidentiality_level",
        "issuing_organization",
    ):
        value = getattr(row, name)
        if value and not value.is_active:
            raise ValidationError({name + "_id": "Select an active reference."})


def apply(row, values):
    if set(values) - set(METADATA):
        raise ValidationError("Unknown or protected metadata field.")
    for name, value in values.items():
        setattr(row, name, value)


def tags(row, values):
    if (
        not isinstance(values, list)
        or len(values) > 30
        or any(type(pk) is not int or pk < 1 for pk in values)
    ):
        raise ValidationError({"tags": "Use at most 30 tag identifiers."})
    unique = set(values)
    if EvidenceTag.objects.filter(pk__in=unique, is_active=True).count() != len(unique):
        raise ValidationError({"tags": "Select active tags."})
    EvidenceDocumentTag.objects.filter(evidence_document=row).delete()
    EvidenceDocumentTag.objects.bulk_create(
        [
            EvidenceDocumentTag(evidence_document=row, evidence_tag_id=pk)
            for pk in sorted(unique)
        ]
    )


def current(row):
    found = list(
        EvidenceDocumentVersion.objects.select_for_update()
        .select_related("file_object")
        .filter(evidence_document=row, is_current=True)
    )
    if len(found) != 1 or found[0].version_number != row.current_version_number:
        raise Conflict("Current-version integrity requires administrator review.")
    return found[0]


def file_digest(upload):
    total = 0
    checksum = hashlib.sha256()
    for chunk in upload.chunks():
        total += len(chunk)
        if total > settings.DOCUMENTS_MAX_BYTES:
            raise ValidationError("File exceeds the upload limit.")
        checksum.update(chunk)
    upload.seek(0)
    return {"name": upload.name, "size": total, "sha256": checksum.hexdigest()}


def receipt(actor, key, operation, payload, authorize, execute, provenance=None):
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", key):
        raise ValidationError("Supply an Idempotency-Key of 1?100 safe characters.")
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    hashed = digest(payload)
    previous = EvidenceCommandReceipt.objects.filter(actor=actor, key=key).first()
    if previous:
        if previous.operation != operation or previous.digest != hashed:
            raise Conflict()
        _, row = locked(
            actor,
            previous.document_id,
            *authorize,
            deleted=operation in {"soft-delete", "restore"},
        )
        return row
    row = execute()
    EvidenceCommandReceipt.objects.create(
        actor=actor,
        key=key,
        operation=operation,
        digest=hashed,
        document=row,
        provenance=provenance or {},
    )
    return row


def file_rights(actor, parent, level, action):
    p.require(actor, "FILE", action, parent)
    sharing.authorized_institution(actor, parent.institution_id)
    from apps.documents_exit import permissions as fp

    if not fp.department_allowed(actor, None, "share_file", parent.institution_id):
        raise PermissionDenied()
    if level == "CONFIDENTIAL" and not fp.can(actor, "access_confidential_shared_file"):
        raise PermissionDenied()


@guarded
def create_evidence_with_file(*, actor, values, upload, key, provenance=None):
    actor = p.principal(actor)
    values = dict(values)
    parent = StaffActivity.objects.select_for_update().get(
        pk=values.pop("staff_activity_id", None), deleted_at__isnull=True
    )
    p.require(actor, "DOCUMENT", "CREATE", parent)
    p.require(actor, "DOCUMENT", "READ", parent)
    chosen_tags = values.pop("tags", [])
    payload = {
        "staff_activity": parent.pk,
        "metadata": values,
        "tags": chosen_tags,
        "file": file_digest(upload),
        "provenance": provenance or {},
    }

    def execute():
        row = EvidenceDocument(
            staff_activity=parent, created_by_user=actor, updated_by_user=actor
        )
        apply(row, values)
        reset_workflow(row)
        normalize(row)
        level = p.classification(actor, row.confidentiality_level, parent)
        file_rights(actor, parent, level, "CREATE")
        file = files.create_file(actor, upload, level)
        from apps.documents_exit.permissions import file_level

        file_level(actor, file)
        row.save()
        content = EvidenceDocumentVersion.objects.create(
            evidence_document=row,
            version_number=1,
            file_object=file,
            uploaded_by_user=actor,
            is_current=True,
        )
        tags(row, chosen_tags)
        audit.write(
            actor,
            row,
            "CREATE",
            version=content,
            after=snapshot(row),
            remarks="Imported evidence" if provenance else None,
        )
        audit.write(actor, row, "UPLOAD", version=content, after={"version_number": 1})
        current(row)
        return row

    return receipt(
        actor, key, "create", payload, ("DOCUMENT", "CREATE"), execute, provenance
    )


@guarded
def replace_evidence_file(
    *, actor, document_id, upload, change_reason, expected_version, key
):
    actor, row = locked(actor, document_id, "FILE", "UPDATE")
    if (
        not isinstance(change_reason, str)
        or not 1 <= len(change_reason.strip()) <= 1000
    ):
        raise ValidationError(
            {"change_reason": "Supply a reason of at most 1,000 characters."}
        )
    payload = {
        "id": str(document_id),
        "file": file_digest(upload),
        "reason": change_reason,
        "version": expected_version,
    }

    def execute():
        check_version(row, expected_version)
        previous = current(row)
        if row.current_version_number >= 65535:
            raise Conflict(
                "Maximum version number reached; retain this document and create a new aggregate."
            )
        level = p.classification(actor, row.confidentiality_level, row.staff_activity)
        file_rights(actor, row.staff_activity, level, "UPDATE")
        file = files.create_file(actor, upload, level)
        from apps.documents_exit.permissions import file_level

        file_level(actor, file)
        EvidenceDocumentVersion.objects.filter(pk=previous.pk, is_current=True).update(
            is_current=False
        )
        number = row.current_version_number + 1
        new = EvidenceDocumentVersion.objects.create(
            evidence_document=row,
            version_number=number,
            file_object=file,
            uploaded_by_user=actor,
            change_reason=change_reason.strip(),
        )
        before = {name: getattr(row, name) for name in WORKFLOW} | {
            "current_version_number": row.current_version_number
        }
        row.current_version_number = number
        reset_workflow(row)
        row.updated_by_user = actor
        row.save()
        audit.write(
            actor,
            row,
            "REPLACE",
            version=new,
            before=before,
            after={name: getattr(row, name) for name in WORKFLOW}
            | {"current_version_number": number},
            remarks=change_reason.strip(),
        )
        audit.write(actor, row, "UPLOAD", version=new, after={"version_number": number})
        current(row)
        return row

    return receipt(actor, key, "replace", payload, ("FILE", "UPDATE"), execute)


@guarded
def update_evidence_metadata(*, actor, document_id, values, expected_version):
    actor, row = locked(actor, document_id, "DOCUMENT", "UPDATE")
    check_version(row, expected_version)
    if row.approval_status.status_code not in EDITABLE:
        raise ValidationError("Only draft or rejected evidence metadata can be edited.")
    before = snapshot(row)
    values = dict(values)
    chosen_tags = values.pop("tags", None)
    if (
        "confidentiality_level_id" in values
        and values["confidentiality_level_id"] != row.confidentiality_level_id
    ):
        p.require(actor, "CLASSIFICATION", "UPDATE", row.staff_activity)
    apply(row, values)
    reset_workflow(row)
    normalize(row)
    p.classification(actor, row.confidentiality_level, row.staff_activity)
    row.updated_by_user = actor
    row.save()
    if chosen_tags is not None:
        tags(row, chosen_tags)
    after = snapshot(row)
    changed = {k for k in before if before[k] != after[k]}
    audit.write(
        actor,
        row,
        "UPDATE_METADATA",
        before={k: before[k] for k in changed},
        after={k: after[k] for k in changed},
    )
    return row


def independent(actor, row, allow_self=False):
    if allow_self:
        return
    if (
        actor.pk in {row.created_by_user_id, current(row).uploaded_by_user_id}
        or AccountLink.objects.filter(
            user=actor, employee_id=row.staff_activity.employee_id
        ).exists()
    ):
        raise PermissionDenied("Independent verification or approval is required.")


@guarded
def workflow(*, actor, document_id, action, remarks, expected_version, key):
    if action not in {"verify", "reject-verification", "approve", "reject-approval"}:
        raise ValidationError("Unsupported evidence workflow action.")
    permission = "VERIFY" if action in {"verify", "reject-verification"} else "APPROVE"
    actor, row = locked(actor, document_id, "DOCUMENT", permission)
    if not isinstance(remarks, str) or not 1 <= len(remarks.strip()) <= 1000:
        raise ValidationError(
            {"remarks": "Supply remarks of at most 1,000 characters."}
        )

    def execute():
        check_version(row, expected_version)
        current(row)
        independent(
            actor,
            row,
            allow_self=permission == "VERIFY" and settings.EVIDENCE_ALLOW_SELF_VERIFY,
        )
        before = {name: getattr(row, name) for name in WORKFLOW}
        if permission == "VERIFY":
            if (
                row.verification_status.status_code not in {"PENDING", "REJECTED"}
                or row.approval_status.status_code not in EDITABLE
            ):
                raise Conflict("Evidence is not awaiting verification.")
            row.verification_status = status(
                VerificationStatus, "VERIFIED" if action == "verify" else "REJECTED"
            )
            row.verified_by_user = actor if action == "verify" else None
            row.verified_at = timezone.now() if action == "verify" else None
            row.verification_remarks = remarks.strip()
        else:
            if row.approval_status.status_code not in EDITABLE:
                raise Conflict("Evidence is not awaiting approval.")
            if (
                settings.EVIDENCE_REQUIRE_VERIFIED_APPROVAL
                and row.verification_status.status_code != "VERIFIED"
            ):
                raise ValidationError(
                    "Verify the current evidence before approval or approval rejection."
                )
            row.approval_status = status(
                ApprovalStatus, "APPROVED" if action == "approve" else "REJECTED"
            )
            row.approved_by_user = actor if action == "approve" else None
            row.approved_at = timezone.now() if action == "approve" else None
            row.rejection_reason = (
                remarks.strip() if action == "reject-approval" else None
            )
        row.updated_by_user = actor
        row.save()
        audit.write(
            actor,
            row,
            action.upper().replace("-", "_"),
            version=current(row),
            before=before,
            after={name: getattr(row, name) for name in WORKFLOW},
            remarks=remarks.strip(),
        )
        return row

    return receipt(
        actor,
        key,
        action,
        {"id": str(document_id), "remarks": remarks, "version": expected_version},
        ("DOCUMENT", permission),
        execute,
    )


@guarded
def deletion(*, actor, document_id, restore, reason, expected_version, key):
    resource, action = ("TRASH", "UPDATE") if restore else ("DOCUMENT", "DELETE")
    actor, row = locked(actor, document_id, resource, action, deleted=True)
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
        raise ValidationError(
            {"reason": "Supply a reason of at most 1,000 characters."}
        )

    def execute():
        check_version(row, expected_version)
        if bool(row.deleted_at) != restore:
            return row
        if restore:
            row.deleted_at = None
            row.deleted_by_user = None
            row.deletion_reason = None
            row.is_active = True
        else:
            row.deleted_at = timezone.now()
            row.deleted_by_user = actor
            row.deletion_reason = reason.strip()
            row.is_active = False
        row.updated_by_user = actor
        row.save()
        audit.write(
            actor, row, "RESTORE" if restore else "SOFT_DELETE", remarks=reason.strip()
        )
        return row

    return receipt(
        actor,
        key,
        "restore" if restore else "soft-delete",
        {"id": str(document_id), "reason": reason, "version": expected_version},
        (resource, action),
        execute,
    )


@guarded
def access_file(*, actor, document_id, version_number=None, preview=False):
    actor, row = locked(actor, document_id, "FILE", "READ")
    active = current(row)
    if version_number is not None and int(version_number) != active.version_number:
        p.require(actor, "HISTORY", "READ", row.staff_activity)
    content = EvidenceDocumentVersion.objects.select_related("file_object").get(
        evidence_document=row, version_number=version_number or active.version_number
    )
    file = content.file_object
    sharing.authorized_institution(actor, row.institution_id)
    from apps.documents_exit import permissions as fp
    from apps.documents_exit import storage

    fp.file_level(actor, file)
    if file.confidentiality_level == "CONFIDENTIAL" and not fp.can(
        actor, "access_confidential_shared_file"
    ):
        raise PermissionDenied()
    if (
        file.mime_type not in settings.DOCUMENTS_ALLOWED_MIMES
        or file.file_size_bytes > settings.DOCUMENTS_MAX_BYTES
    ):
        raise NotFound()
    backend = storage.backend()
    if backend.provider != file.storage_provider:
        raise NotFound()
    try:
        stream = backend.open(file.storage_key)
    except Exception:  # noqa: BLE001 - provider failures must not expose private metadata.
        raise NotFound("File unavailable.") from None
    files.opened_streams.get().append(stream)
    checksum = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(65536), b""):
        size += len(chunk)
        if size > file.file_size_bytes:
            raise Conflict("File integrity check failed.")
        checksum.update(chunk)
    if (
        size != file.file_size_bytes
        or not file.checksum_sha256
        or checksum.hexdigest().lower() != file.checksum_sha256.lower()
    ):
        raise Conflict("File integrity check failed.")
    stream.seek(0)
    audit.write(actor, row, "PREVIEW" if preview else "DOWNLOAD", version=content)
    return stream, file
