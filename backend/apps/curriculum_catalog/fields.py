from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.functional import cached_property


class UnsignedBigAutoField(models.BigAutoField):
    def get_internal_type(self):
        return "PositiveBigIntegerField"

    def db_type(self, connection):
        return (
            "bigint unsigned"
            if connection.vendor == "mysql"
            else super().db_type(connection)
        )

    def db_type_suffix(self, connection):
        return (
            "AUTO_INCREMENT"
            if connection.vendor == "mysql"
            else super().db_type_suffix(connection)
        )

    def rel_db_type(self, connection):
        return self.db_type(connection)

    def db_check(self, connection):
        return None

    @cached_property
    def validators(self):
        return [
            *self.default_validators,
            *self._validators,
            MinValueValidator(1),
            MaxValueValidator(2**64 - 1),
        ]


class YearField(models.PositiveSmallIntegerField):
    def db_type(self, connection):
        return "year" if connection.vendor == "mysql" else super().db_type(connection)

    @property
    def validators(self):
        return [*super().validators, MinValueValidator(1901), MaxValueValidator(2155)]
