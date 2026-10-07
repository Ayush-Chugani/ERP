import hashlib
import logging
import re
from contextvars import ContextVar
from functools import wraps
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as ModelError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.admission_enrolment.models import StudentProgrammeEnrolment
from apps.common_reference.models import DocumentType
from apps.core.models import ReferenceAuditEvent

from . import integrations, storage
from . import models as m
from . import permissions as p

logger = logging.getLogger(__name__)
files_written = ContextVar("m13_files", default=None)
correlation = ContextVar("m13_correlation", default="")
opened_streams = ContextVar("m13_streams", default=None)


class Conflict(APIException):
    status_code = 409
    default_code = "documents_conflict"
    default_detail = (
        "Document workflow conflicts with current state. Refresh and retry."
    )


def command(fn):
    @wraps(fn)
    @sensitive_variables()
    def run(*, actor, **values):
        written = []
        token = files_written.set(written)
        opened = []
        stream_token = opened_streams.set(opened)
        try:
            # Durable boundary ensures a caller cannot later roll back metadata after storage cleanup scope ends.
            with transaction.atomic(durable=True):
                ContentType.objects.select_for_update().get(
                    app_label="organization", model="university"
                )
                actor = get_user_model().objects.get(pk=actor.pk)
                if not settings.DOCUMENTS_EXIT_ENABLED or not actor.is_active:
                    raise PermissionDenied()
                return fn(actor=actor, **values)
        except BaseException as error:
            for stream in opened:
                stream.close()
            for backend, key in reversed(written):
                try:
                    backend.delete(key)
                except Exception:  # noqa: BLE001 - redact provider/parser exceptions at the security boundary.
                    logger.critical("m13_storage_cleanup_failed")
            if isinstance(error, (ModelError, ValueError, TypeError)):
                raise ValidationError(
                    "Invalid document input. Check dates, lengths and allowed fields."
                ) from None
            if isinstance(error, ObjectDoesNotExist):
                raise NotFound("Document record unavailable.") from None
            if (
                isinstance(error, (IntegrityError, OperationalError))
                and error.args
                and error.args[0] in [1062, 1451, 1452, 3819, 4025, 1205, 1213]
            ):
                raise Conflict() from None
            raise
        finally:
            files_written.reset(token)
            opened_streams.reset(stream_token)

    return run


def audit(actor, obj, event, reason=None, **metadata):
    allowed = {
        "status",
        "previous_status",
        "file_id",
        "previous_file_id",
        "enrolment_status",
    }
    if set(metadata) - allowed:
        raise ValueError("Unsupported audit metadata")
    data = {"event": event, "correlation": correlation.get(), **metadata}
    # Required approval/rejection/exit rationale is protected audit content, never operational log content.
    if reason is not None:
        data["reason"] = reason
    ReferenceAuditEvent.objects.create(
        actor=actor,
        action="create" if event.endswith("created") else "update",
        resource="m13_" + obj._meta.model_name,
        record_id=obj.pk,
        source="api",
        before={},
        after=data,
    )


def reason_required(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValidationError("A reason of at most 500 characters is required.")
    return reason.strip()


def save(obj):
    obj.full_clean()
    obj.save()
    return obj


def number(kind, limit):
    prefix = settings.DOCUMENTS_NUMBER_PREFIX
    if not re.fullmatch(r"[A-Z0-9]{1,4}", prefix):
        raise integrations.ProviderUnavailable()
    return (prefix + kind + uuid4().hex.upper())[:limit]


def create_file(actor, upload, level="RESTRICTED"):
    if files_written.get() is None:
        raise RuntimeError("File creation requires a document command boundary.")
    checked = storage.validate_upload(upload)
    backend = storage.backend()
    key = uuid4().hex + "." + checked["extension"]
    try:
        backend.put(key, checked["data"])
    except FileExistsError:
        raise Conflict("Storage key collision; retry.") from None
    except Exception:  # noqa: BLE001 - redact provider/parser exceptions at the security boundary.
        try:
            backend.delete(key)
        except Exception:  # noqa: BLE001 - preserve the original failure without logging sensitive provider paths.
            logger.critical("m13_storage_cleanup_failed")
        raise integrations.ProviderUnavailable() from None
    files_written.get().append((backend, key))
    obj = m.FileObject(
        storage_provider=backend.provider,
        storage_key=key,
        original_file_name=checked["name"],
        mime_type=checked["mime"],
        file_size_bytes=len(checked["data"]),
        checksum_sha256=checked["checksum"],
        stored_file_name=key,
        file_extension=checked["extension"],
        confidentiality_level=level,
        is_encrypted=backend.encrypted,
        uploaded_by_user_id=actor.pk,
    )
    save(obj)
    audit(actor, obj, "file_created")
    return obj


def document_dates(obj):
    if obj.issue_date and obj.expiry_date and obj.expiry_date < obj.issue_date:
        raise ValidationError("Expiry date cannot precede issue date.")


@command
def upload_document(
    *,
    actor,
    upload,
    document_type_id,
    student_id=None,
    document_number=None,
    issue_date=None,
    expiry_date=None,
    remarks=None,
):
    student = (
        p.get(p.students(actor, "upload_documents"), student_id, True)
        if student_id
        else p.own_student(actor, "upload_own_document")
    )
    if student.student_status != "ACTIVE":
        raise Conflict("An active student is required.")
    kind = p.get(DocumentType.objects.filter(is_active=True), document_type_id)
    obj = m.StudentDocument(
        student=student,
        document_type=kind,
        document_number=document_number or None,
        issue_date=issue_date,
        expiry_date=expiry_date,
        remarks=remarks,
    )
    document_dates(obj)
    obj.file_object = create_file(actor, upload)
    save(obj)
    audit(
        actor,
        obj,
        "document_created",
        file_id=obj.file_object_id,
        status=obj.verification_status,
    )
    return obj


@command
def update_document(
    *,
    actor,
    pk,
    expected_status,
    upload=None,
    document_number=None,
    issue_date=None,
    expiry_date=None,
    remarks=None,
):
    obj = p.get(
        p.scoped(m.StudentDocument, actor, "upload_documents", "upload_own_document"),
        pk,
        True,
    )
    if obj.verification_status != expected_status or obj.verification_status not in [
        "PENDING",
        "REJECTED",
        "EXPIRED",
    ]:
        raise Conflict(
            "Verified documents must be returned to pending before replacement."
        )
    if obj.student.student_status != "ACTIVE":
        raise Conflict("An active student is required for resubmission.")
    previous = obj.file_object_id
    if upload:
        obj.file_object = create_file(actor, upload)
    obj.document_number = document_number or None
    obj.issue_date = issue_date
    obj.expiry_date = expiry_date
    obj.remarks = remarks
    obj.verification_status = "PENDING"
    obj.verified_at = None
    document_dates(obj)
    save(obj)
    audit(
        actor,
        obj,
        "document_replaced" if upload else "document_updated",
        previous_file_id=previous,
        file_id=obj.file_object_id,
        status=obj.verification_status,
    )
    return obj


@command
def verify_document(*, actor, pk, expected_status, target, reason):
    obj = p.get(p.scoped(m.StudentDocument, actor, "verify_document"), pk, True)
    p.reject_self_approval(actor, obj.student_id)
    reason = reason_required(reason)
    transitions = {
        "PENDING": {"VERIFIED", "REJECTED", "EXPIRED"},
        "VERIFIED": {"PENDING", "EXPIRED"},
        "REJECTED": {"PENDING", "EXPIRED"},
        "EXPIRED": {"PENDING"},
    }
    if (
        obj.verification_status != expected_status
        or target not in transitions[obj.verification_status]
    ):
        raise Conflict()
    if target == "VERIFIED" and (
        obj.file_object.deleted_at
        or obj.expiry_date
        and obj.expiry_date < timezone.localdate()
    ):
        raise Conflict("Expired or deleted content cannot be verified.")
    if target == "EXPIRED" and (
        not obj.expiry_date or obj.expiry_date >= timezone.localdate()
    ):
        raise Conflict("Document is not past its expiry date.")
    before = obj.verification_status
    obj.verification_status = target
    obj.verified_at = timezone.now() if target == "VERIFIED" else None
    save(obj)
    audit(
        actor,
        obj,
        "document_verification",
        reason,
        previous_status=before,
        status=target,
    )
    return obj


@command
def certificate_type(
    *, actor, certificate_code, certificate_name, is_active=True, pk=None
):
    p.type_admin(actor)
    obj = (
        p.get(m.CertificateType.objects.all(), pk, True) if pk else m.CertificateType()
    )
    obj.certificate_code = certificate_code.strip().upper()
    obj.certificate_name = " ".join(certificate_name.split())
    obj.is_active = is_active
    save(obj)
    audit(actor, obj, "type_updated" if pk else "type_created")
    return obj


@command
def request_certificate(*, actor, certificate_type_id, purpose=None):
    student = p.own_student(actor, "request_certificate")
    kind = p.get(m.CertificateType.objects.filter(is_active=True), certificate_type_id)
    if (
        not integrations.policy(
            student.institution_id, "allow_concurrent_requests", False
        )
        and m.CertificateRequest.objects.filter(
            student=student,
            certificate_type=kind,
            request_status__in=["SUBMITTED", "UNDER_REVIEW", "APPROVED"],
        ).exists()
    ):
        raise Conflict("An active request already exists for this certificate type.")
    for _ in range(5):
        try:
            with transaction.atomic():
                obj = m.CertificateRequest(
                    student=student,
                    certificate_type=kind,
                    purpose=purpose,
                    request_number=number("R", 30),
                    requested_at=timezone.now(),
                )
                obj.full_clean(validate_unique=False)
                obj.save(force_insert=True)
            audit(actor, obj, "certificate_request_created", status=obj.request_status)
            return obj
        except IntegrityError as error:
            if not error.args or error.args[0] != 1062:
                raise
    raise Conflict("Number allocation failed; retry.")


@command
def certificate_action(*, actor, pk, expected_status, action, reason):
    cap = {
        "review": "review_certificate",
        "approve": "approve_certificate",
        "reject": "approve_certificate",
        "cancel": "review_certificate",
    }.get(action)
    if not cap:
        raise ValidationError("Unsupported certificate action.")
    obj = p.get(
        p.scoped(
            m.CertificateRequest,
            actor,
            cap,
            "request_certificate" if action == "cancel" else None,
        ),
        pk,
        True,
    )
    reason = reason_required(reason)
    if action != "cancel":
        p.reject_self_approval(actor, obj.student_id)
    elif (not p.scoped(m.CertificateRequest, actor, cap).filter(pk=pk).exists()) and (
        not integrations.policy(
            obj.student.institution_id, "student_cancel_before_approval", True
        )
        or obj.request_status not in ["SUBMITTED", "UNDER_REVIEW"]
    ):
        raise Conflict()
    target = {
        "review": "UNDER_REVIEW",
        "approve": "APPROVED",
        "reject": "REJECTED",
        "cancel": "CANCELLED",
    }[action]
    allowed = {
        "SUBMITTED": {"UNDER_REVIEW", "CANCELLED"},
        "UNDER_REVIEW": {"APPROVED", "REJECTED", "CANCELLED"},
        "APPROVED": {"CANCELLED"},
    }
    if obj.request_status != expected_status or target not in allowed.get(
        obj.request_status, set()
    ):
        raise Conflict()
    before = obj.request_status
    obj.request_status = target
    save(obj)
    audit(
        actor,
        obj,
        "certificate_" + action,
        reason,
        previous_status=before,
        status=target,
    )
    return obj


@command
def issue_certificate(*, actor, pk, reason):
    obj = p.get(p.scoped(m.CertificateRequest, actor, "issue_certificate"), pk, True)
    p.reject_self_approval(actor, obj.student_id)
    reason = reason_required(reason)
    if obj.request_status == "ISSUED":
        return obj
    if obj.request_status != "APPROVED":
        raise Conflict("Only approved requests can be issued.")
    for _ in range(5):
        value = number("C", 50)
        if not m.CertificateRequest.objects.filter(certificate_number=value).exists():
            break
    else:
        raise Conflict("Number allocation failed; retry.")
    result = integrations.invoke(
        "DOCUMENTS_CERTIFICATE_RENDERER", request=obj, certificate_number=value
    )
    if not isinstance(result, bytes):
        raise integrations.ProviderUnavailable()
    obj.file_object = create_file(
        actor,
        SimpleUploadedFile("certificate.pdf", result, content_type="application/pdf"),
    )
    obj.certificate_number = value
    obj.issued_at = timezone.now()
    obj.request_status = "ISSUED"
    save(obj)
    audit(
        actor,
        obj,
        "certificate_issued",
        reason,
        status="ISSUED",
        file_id=obj.file_object_id,
    )
    return obj


@command
def finalize_exit(
    *,
    actor,
    enrolment_id,
    exit_type,
    exit_date,
    reason,
    confirmed,
    destination_institution=None,
    old_registration_number=None,
    remarks=None,
):
    reason = reason_required(reason)
    if confirmed is not True:
        raise ValidationError("Explicit confirmation is required.")
    cap = "terminate_enrolment" if exit_type == "TERMINATION" else "finalize_exit"
    if not p.can(actor, cap):
        raise NotFound()
    enrolment = p.get(
        StudentProgrammeEnrolment.objects.filter(student__in=p.students(actor, cap)),
        enrolment_id,
        True,
    )
    p.reject_self_approval(actor, enrolment.student_id)
    values = {
        "exit_type": exit_type,
        "exit_date": exit_date,
        "destination_institution": destination_institution,
        "old_registration_number": old_registration_number,
        "remarks": remarks,
    }
    existing = m.StudentExit.objects.filter(enrolment=enrolment).first()
    if existing:
        if all(getattr(existing, key) == value for key, value in values.items()):
            return existing
        raise Conflict("This enrolment already has a different finalized exit.")
    if exit_date < enrolment.admission_date or exit_date > timezone.localdate():
        raise ValidationError("Exit date must be between admission and today.")
    if exit_type == "TRANSFER" and not destination_institution:
        raise ValidationError("Transfer destination is required.")
    if exit_type != "TRANSFER" and destination_institution:
        raise ValidationError("Destination applies only to transfer.")
    if exit_type in ["TERMINATION", "OTHER"] and not remarks:
        raise ValidationError("Remarks are required for this exit type.")
    decision = integrations.invoke(
        "DOCUMENTS_EXIT_CLEARANCE",
        actor=actor,
        enrolment=enrolment,
        exit_type=exit_type,
        exit_date=exit_date,
    )
    if not isinstance(decision, dict) or decision.get("allowed") is not True:
        raise Conflict("Required exit clearances or results are incomplete.")
    target = {
        "COMPLETION": "COMPLETED",
        "TRANSFER": "TRANSFERRED",
        "WITHDRAWAL": "WITHDRAWN",
        "TERMINATION": "TERMINATED",
    }.get(exit_type, decision.get("enrolment_status"))
    if target not in ["COMPLETED", "TRANSFERRED", "WITHDRAWN", "TERMINATED"]:
        raise Conflict("Exit policy must specify a terminal enrolment status.")
    from apps.admission_enrolment.models import EnrolmentStatusHistory

    latest = (
        EnrolmentStatusHistory.objects.filter(enrolment=enrolment)
        .order_by("-sequence_number")
        .first()
    )
    if latest and exit_date < latest.effective_date:
        raise ValidationError("Exit date must follow existing enrolment history.")
    from apps.admission_enrolment.services import finalize_exit_enrolment

    if enrolment.enrolment_status != target:
        finalize_exit_enrolment(
            actor=actor,
            pk=enrolment.pk,
            version=enrolment.version,
            target=target,
            reason=reason,
            effective_date=exit_date,
        )
    obj = save(m.StudentExit(enrolment=enrolment, **values))
    audit(actor, obj, "exit_created", reason, enrolment_status=target)
    return obj


@command
def access_file(*, actor, resource, pk, delete=False, reason=None):
    if resource == "documents":
        obj = p.get(
            p.scoped(
                m.StudentDocument,
                actor,
                "delete_file" if delete else "view_documents",
                None if delete else "view_own_document",
            ),
            pk,
            True,
        )
    elif resource == "certificates":
        obj = p.get(
            p.scoped(
                m.CertificateRequest,
                actor,
                "delete_file" if delete else "view_certificates",
                None if delete else "view_own_document",
            ),
            pk,
            True,
        )
        if obj.request_status != "ISSUED":
            raise NotFound()
        if delete:
            raise Conflict("Issued certificates are retained immutable records.")
    else:
        raise NotFound()
    file = p.get(m.FileObject.objects.all(), obj.file_object_id, True)
    p.file_level(actor, file)
    if delete:
        reason = reason_required(reason)
        file.deleted_at = timezone.now()
        save(file)
        audit(actor, file, "file_deleted", reason)
        return file
    backend = storage.backend()
    if backend.provider != file.storage_provider:
        raise integrations.ProviderUnavailable()
    try:
        stream = backend.open(file.storage_key)
    except Exception:  # noqa: BLE001 - redact provider/parser exceptions at the security boundary.
        raise NotFound("File unavailable.") from None
    opened_streams.get().append(stream)
    try:
        digest = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: stream.read(65536), b""):
            size += len(chunk)
            if size > file.file_size_bytes:
                raise Conflict("Stored file integrity check failed.")
            digest.update(chunk)
        if (
            size != file.file_size_bytes
            or file.checksum_sha256
            and digest.hexdigest().lower() != file.checksum_sha256.lower()
        ):
            raise Conflict("Stored file integrity check failed.")
        stream.seek(0)
        audit(actor, file, "file_downloaded")
    except BaseException:
        stream.close()
        raise
    return stream, file
