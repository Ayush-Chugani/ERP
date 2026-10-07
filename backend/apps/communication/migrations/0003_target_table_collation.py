from typing import ClassVar

from django.db import migrations


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("communication", "0002_institution_and_audience_targets")
    ]
    operations: ClassVar[list] = [
        migrations.RunSQL(
            "ALTER TABLE announcement_programme_target DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "ALTER TABLE announcement_user_target DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
