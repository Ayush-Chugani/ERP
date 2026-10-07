from typing import ClassVar

from django.db import migrations


def install(apps, schema_editor):
    for operation in ("UPDATE", "DELETE"):
        schema_editor.execute(
            f"CREATE TRIGGER m33_audit_no_{operation.lower()} BEFORE {operation} ON evidence_document_audit FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Evidence audit is append-only'"
        )
    schema_editor.execute(
        "CREATE TRIGGER m33_version_no_delete BEFORE DELETE ON evidence_document_version FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Evidence versions must be retained'"
    )
    fields = (
        "evidence_document_version_id",
        "evidence_document_id",
        "version_number",
        "file_object_id",
        "change_reason",
        "uploaded_by_user_id",
        "uploaded_at",
    )
    unchanged = " AND ".join(f"(OLD.{field} <=> NEW.{field})" for field in fields)
    schema_editor.execute(
        f"CREATE TRIGGER m33_version_immutable BEFORE UPDATE ON evidence_document_version FOR EACH ROW BEGIN IF NOT ({unchanged}) OR NOT (OLD.is_current = 1 AND NEW.is_current = 0) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Version content is immutable; only current demotion is permitted'; END IF; END"
    )


def reverse(apps, schema_editor):
    if (
        apps.get_model("evidence", "EvidenceDocument")._base_manager.exists()
        or apps.get_model("evidence", "EvidenceDocumentAudit")._base_manager.exists()
    ):
        raise RuntimeError("Retain populated evidence and audit.")
    for trigger in (
        "m33_audit_no_update",
        "m33_audit_no_delete",
        "m33_version_no_delete",
        "m33_version_immutable",
    ):
        schema_editor.execute("DROP TRIGGER " + trigger)


class Migration(migrations.Migration):
    atomic = False
    dependencies: ClassVar[list] = [("evidence", "0001_initial")]
    operations: ClassVar[list] = [migrations.RunPython(install, reverse)]
