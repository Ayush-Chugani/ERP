from django.db import models


class NativeEnumField(models.CharField):
    def db_type(self, connection):
        if connection.vendor == "mysql":
            return (
                "enum("
                + ",".join(
                    "'" + str(value).replace("'", "''") + "'"
                    for value, _ in self.choices
                )
                + ")"
            )
        return super().db_type(connection)


class CanonicalDateTimeField(models.DateTimeField):
    def db_type(self, connection):
        return (
            "datetime" if connection.vendor == "mysql" else super().db_type(connection)
        )


class CanonicalTextField(models.TextField):
    def db_type(self, connection):
        return "text" if connection.vendor == "mysql" else super().db_type(connection)


class CurrentTimestamp(models.Func):
    template = "CURRENT_TIMESTAMP"
    output_field = models.DateTimeField()
    arity = 0
