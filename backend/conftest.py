"""Keep tiny action IDs stable across rolled-back and reused MySQL test runs."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def stable_action_catalogue(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        from apps.identity_access.models import AccessAction
        from apps.identity_access.seeding import catalogue

        # Test database only, after django_db_setup has switched the connection.
        # MySQL AUTO_INCREMENT isn't rolled back; repeatedly reseeding 11 actions
        # in TestCase transactions otherwise exhausts the source TINYINT key.
        for index, row in enumerate(catalogue()["actions"], start=1):
            values = dict(row)
            code = values.pop("action_code")
            if not AccessAction.objects.filter(action_code=code).exists():
                if AccessAction.objects.filter(pk=index).exists():
                    raise RuntimeError(
                        "Unexpected test action catalogue; recreate the isolated test database."
                    )
                AccessAction.objects.create(pk=index, action_code=code, **values)
