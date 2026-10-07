from typing import ClassVar

from django.db import migrations


def install(apps, schema_editor):
    for prefix, table in [
        ("m26_history", "platform_funded_project_status_history"),
        ("m26_void", "platform_research_utilization_void"),
    ]:
        for operation in ("UPDATE", "DELETE"):
            schema_editor.execute(
                f"CREATE TRIGGER {prefix}_no_{operation.lower()} BEFORE {operation} ON {table} FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Retained project evidence is append-only'"
            )


def reverse(apps, schema_editor):
    if apps.get_model("funded_projects", "FundedResearchProject").objects.exists():
        raise RuntimeError("Retain populated projects; disable the module instead.")
    for prefix in ("m26_history", "m26_void"):
        for operation in ("update", "delete"):
            schema_editor.execute(f"DROP TRIGGER {prefix}_no_{operation}")


class Migration(migrations.Migration):
    atomic = False
    dependencies: ClassVar[list] = [
        ("funded_projects", "0002_fundedresearchproject_ix_project_sanction_and_more")
    ]
    operations: ClassVar[list] = [migrations.RunPython(install, reverse)]
