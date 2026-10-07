from typing import ClassVar

from django.db import migrations


def install(apps, schema_editor):
    for operation in ("UPDATE", "DELETE"):
        schema_editor.execute(
            f"CREATE TRIGGER m31_history_no_{operation.lower()} BEFORE {operation} ON platform_professional_memberships_status_history FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Proposal status history is append-only'"
        )


def reverse(apps, schema_editor):
    if (
        apps.get_model(
            "professional_memberships", "MembershipStatusHistory"
        ).objects.exists()
        or apps.get_model(
            "professional_memberships", "StaffProfessionalMembership"
        ).objects.exists()
    ):
        raise RuntimeError(
            "Retain populated membership records and status history; disable the runtime module instead."
        )
    for operation in ("update", "delete"):
        schema_editor.execute(f"DROP TRIGGER m31_history_no_{operation}")


class Migration(migrations.Migration):
    atomic = False
    dependencies: ClassVar[list] = [("professional_memberships", "0001_initial")]
    operations: ClassVar[list] = [migrations.RunPython(install, reverse)]
