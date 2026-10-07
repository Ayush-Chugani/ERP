"""Public managed-file sharing boundary. Only explicit shared uploads are eligible.

Trusted domain callbacks establish the owner before upload and attach inside the
same durable transaction. Never expose callbacks or scope assertions as API input.
"""

import hashlib

from django.conf import settings
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.core.models import ReferenceAuditEvent

from . import models as m
from . import permissions as p
from . import services as s
from . import storage


def authorized_institution(actor, institution_id):
    if (
        not settings.DOCUMENTS_EXIT_ENABLED
        or institution_id not in settings.DOCUMENTS_EXIT_INSTITUTIONS
        or not actor.is_active
    ):
        raise NotFound()
    if (
        not actor.is_superuser
        and not p.memberships(actor).filter(institution_id=institution_id).exists()
    ):
        raise NotFound()


def inspect_shared(*, actor, file_id, institution_id, manage=False):
    authorized_institution(actor, institution_id)
    if manage and not p.department_allowed(actor, None, "share_file", institution_id):
        raise NotFound()
    provenance = ReferenceAuditEvent.objects.filter(
        resource="m13_shared_file",
        record_id=file_id,
        after__institution_id=institution_id,
        after__event="shared_created",
    )
    if not provenance.exists():
        raise NotFound("Shared attachment unavailable.")
    file = p.get(m.FileObject.objects.all(), file_id)
    p.file_level(actor, file)
    if file.confidentiality_level == "CONFIDENTIAL" and not p.can(
        actor, "access_confidential_shared_file"
    ):
        raise NotFound()
    if (
        file.file_size_bytes > settings.DOCUMENTS_MAX_BYTES
        or file.mime_type not in settings.DOCUMENTS_ALLOWED_MIMES
    ):
        raise NotFound()
    return file


@s.command
def upload_shared(*, actor, upload, level, authorize, attach):
    owner = authorize(actor)
    institution_id = owner.institution_id
    authorized_institution(actor, institution_id)
    if not p.department_allowed(actor, None, "share_file", institution_id):
        raise PermissionDenied()
    if level not in m.Level.values:
        raise ValidationError("Invalid confidentiality level.")
    if level == "CONFIDENTIAL" and not p.can(actor, "access_confidential_shared_file"):
        raise PermissionDenied()
    file = s.create_file(actor, upload, level)
    p.file_level(actor, file)
    ReferenceAuditEvent.objects.create(
        actor=actor,
        action="create",
        resource="m13_shared_file",
        record_id=file.pk,
        source="api",
        before={},
        after={"event": "shared_created", "institution_id": institution_id},
    )
    return attach(actor, owner, file)


@s.command
def download_shared(*, actor, file_id, authorize):
    owner = authorize(actor)
    file = inspect_shared(
        actor=actor, file_id=file_id, institution_id=owner.institution_id
    )
    backend = storage.backend()
    if file.storage_provider != backend.provider:
        raise NotFound()
    try:
        stream = backend.open(file.storage_key)
    except Exception:  # noqa: BLE001 - storage errors must not expose private paths.
        raise NotFound("File unavailable.") from None
    s.opened_streams.get().append(stream)
    try:
        digest = hashlib.sha256()
        count = 0
        for chunk in iter(lambda: stream.read(65536), b""):
            count += len(chunk)
            if count > file.file_size_bytes:
                raise s.Conflict("File integrity check failed.")
            digest.update(chunk)
        if (
            count != file.file_size_bytes
            or file.checksum_sha256
            and digest.hexdigest().lower() != file.checksum_sha256.lower()
        ):
            raise s.Conflict("File integrity check failed.")
        stream.seek(0)
        s.audit(actor, file, "shared_downloaded")
        return stream, file
    except BaseException:
        stream.close()
        raise
