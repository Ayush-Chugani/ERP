"""Keep empty TINYINT status masters reusable after rolled-back native tests."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def reusable_status_masters(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        from django.db import connection

        from apps.staff_profile.models import ApprovalStatus, VerificationStatus

        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            raise RuntimeError(
                "Status fixture is restricted to the isolated test database."
            )
        if connection.vendor == "mysql":
            with connection.cursor() as cursor:
                for model in (ApprovalStatus, VerificationStatus):
                    if not model.objects.exists():
                        cursor.execute(
                            "ALTER TABLE "
                            + connection.ops.quote_name(model._meta.db_table)
                            + " AUTO_INCREMENT=1"
                        )
