from django.db import models

from apps.student_support.fields import CanonicalDateTimeField


class NativeTimestampField(CanonicalDateTimeField):
    def db_type(self, connection):
        return (
            "timestamp" if connection.vendor == "mysql" else super().db_type(connection)
        )


class FixedHashField(models.CharField):
    def db_type(self, connection):
        return (
            "char(64)" if connection.vendor == "mysql" else super().db_type(connection)
        )
