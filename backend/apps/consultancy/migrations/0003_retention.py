from typing import ClassVar

from django.db import migrations

TABLES = (
    "platform_consultancy_receipt_void",
    "platform_consultancy_receipt",
    "platform_consultancy_status_history",
)


def install(apps, schema_editor):
    for i, table in enumerate(TABLES):
        for operation in ("UPDATE", "DELETE"):
            schema_editor.execute(
                f"CREATE TRIGGER m27_{i}_no_{operation.lower()} BEFORE {operation} ON {table} FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Consultancy evidence is append-only'"
            )


def reverse(apps, schema_editor):
    if apps.get_model("consultancy", "ConsultancyProject").objects.exists():
        raise RuntimeError(
            "Retain populated consultancy records; disable runtime instead."
        )
    for i, _ in enumerate(TABLES):
        for operation in ("update", "delete"):
            schema_editor.execute(f"DROP TRIGGER m27_{i}_no_{operation}")


class Migration(migrations.Migration):
    atomic = False
    dependencies: ClassVar[list] = [
        ("consultancy", "0002_projectreceipt_projectstatushistory_projectteam_and_more")
    ]
    operations: ClassVar[list] = [migrations.RunPython(install, reverse)]
