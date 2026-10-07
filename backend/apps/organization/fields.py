from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class UnsignedTinyIntegerField(models.PositiveSmallIntegerField):
    def db_type(self, connection):
        return 'tinyint unsigned' if connection.vendor == 'mysql' else super().db_type(connection)

    @property
    def validators(self):
        return [*super().validators, MinValueValidator(0), MaxValueValidator(255)]
