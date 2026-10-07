"""Bounded, restartable legacy import. No implicit workflow certification."""

from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from apps.documents_exit import storage
from apps.documents_exit.models import FileObject
from apps.documents_exit.permissions import file_level
from apps.staff_activities.models import StaffActivity

from . import permissions as p
from . import services as s
from .models import EvidenceCommandReceipt, EvidenceDocument, EvidenceTag


def legacy_import(*, actor, entries, root, namespace, dry_run=True):
    actor = p.principal(actor)
    root = Path(root).resolve()
    if (
        not isinstance(namespace, str)
        or not 1 <= len(namespace) <= 100
        or not isinstance(entries, list)
        or len(entries) > 200
    ):
        raise ValidationError("Use a namespace and at most 200 manifest rows.")
    results = []
    for number, entry in enumerate(entries, start=1):
        try:
            if not isinstance(entry, dict) or set(entry) - {
                "source_id",
                "path",
                "metadata",
                "original_timestamps",
                "original_status",
            }:
                raise ValidationError("Unknown manifest fields.")
            if (
                not isinstance(entry.get("source_id"), str)
                or not 1 <= len(entry["source_id"]) <= 200
            ):
                raise ValidationError("Supply a stable source_id.")
            path = (root / entry["path"]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValidationError(
                    "Source file is missing or outside the import root."
                )
            from django.conf import settings

            if path.stat().st_size > settings.DOCUMENTS_MAX_BYTES:
                raise ValidationError("Source file exceeds the upload limit.")
            upload = SimpleUploadedFile(
                path.name, path.read_bytes(), content_type="application/octet-stream"
            )
            from .api import CreateMetadata

            serializer = CreateMetadata(data=entry["metadata"])
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
            parent = StaffActivity.objects.get(
                pk=values["staff_activity_id"], deleted_at__isnull=True
            )
            p.require(actor, "DOCUMENT", "CREATE", parent)
            p.require(actor, "DOCUMENT", "READ", parent)
            metadata = {
                k: v
                for k, v in values.items()
                if k not in {"staff_activity_id", "tags"}
            }
            row = EvidenceDocument(
                staff_activity=parent, created_by_user=actor, updated_by_user=actor
            )
            s.apply(row, metadata)
            s.reset_workflow(row)
            s.normalize(row)
            level = p.classification(actor, row.confidentiality_level, parent)
            s.file_rights(actor, parent, level, "CREATE")
            file_level(actor, FileObject(confidentiality_level=level))
            chosen = values.get("tags", [])
            if EvidenceTag.objects.filter(
                pk__in=set(chosen), is_active=True
            ).count() != len(set(chosen)):
                raise ValidationError("Tag mapping requires review.")
            checked = storage.validate_upload(upload)
            upload.seek(0)
            provenance = {
                "namespace": namespace,
                "source_id": entry["source_id"],
                "original_timestamps": entry.get("original_timestamps", {}),
                "original_status": entry.get("original_status"),
                "sha256": checked["checksum"],
            }
            key = "legacy:" + s.digest([namespace, entry["source_id"]])
            payload = {
                "staff_activity": parent.pk,
                "metadata": metadata,
                "tags": chosen,
                "file": s.file_digest(upload),
                "provenance": provenance,
            }
            previous = EvidenceCommandReceipt.objects.filter(
                actor=actor, key=key
            ).first()
            if previous and (
                previous.operation != "create" or previous.digest != s.digest(payload)
            ):
                raise s.Conflict()
            if previous:
                p.document(actor, previous.document)
            if dry_run:
                results.append(
                    {
                        "row": number,
                        "source_id": entry["source_id"],
                        "status": "already_imported" if previous else "valid",
                    }
                )
            else:
                saved = s.create_evidence_with_file(
                    actor=actor,
                    values=values,
                    upload=upload,
                    key=key,
                    provenance=provenance,
                )
                results.append(
                    {
                        "row": number,
                        "source_id": entry["source_id"],
                        "status": "replayed" if previous else "created",
                        "document_id": str(saved.pk),
                    }
                )
        except Exception as error:  # noqa: BLE001 - bounded reconciliation redacts provider errors.
            # No paths, confidential metadata or provider exception text enter reconciliation output.
            results.append(
                {
                    "row": number,
                    "status": "error",
                    "code": getattr(error, "default_code", "invalid_mapping_or_file"),
                    "fields": sorted(error.detail)
                    if isinstance(getattr(error, "detail", None), dict)
                    else [],
                }
            )
    return {
        "dry_run": dry_run,
        "rows": results,
        "succeeded": sum(r["status"] != "error" for r in results),
        "failed": sum(r["status"] == "error" for r in results),
    }
