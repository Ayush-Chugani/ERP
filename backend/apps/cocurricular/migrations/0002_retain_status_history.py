from typing import ClassVar

from django.db import migrations


def install(apps, schema_editor):
    for operation in ("UPDATE", "DELETE"):
        schema_editor.execute(
            f"CREATE TRIGGER m28_history_no_{operation.lower()} BEFORE {operation} ON platform_cocurricular_status_history FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Proposal status history is append-only'"
        )


def reverse(apps, schema_editor):
    if (
        apps.get_model("cocurricular", "CocurricularStatusHistory").objects.exists()
        or apps.get_model("cocurricular", "CocurricularActivity").objects.exists()
    ):
        raise RuntimeError(
            "Retain populated co-curricular records and status history; disable the runtime module instead."
        )
    for operation in ("update", "delete"):
        schema_editor.execute(f"DROP TRIGGER m28_history_no_{operation}")


class Migration(migrations.Migration):
    atomic = False
    dependencies: ClassVar[list] = [("cocurricular", "0001_initial")]
    operations: ClassVar[list] = [migrations.RunPython(install, reverse)]
