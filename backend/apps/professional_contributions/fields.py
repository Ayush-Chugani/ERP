from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.functional import cached_property


class UnsignedSmallCount(models.PositiveSmallIntegerField):
    """Native SMALLINT UNSIGNED, including the upper half of its storage range."""

    def to_python(self, value):
        from django.core.exceptions import ValidationError

        if isinstance(value, (float, bool)):
            raise ValidationError("Use a whole number from 0 to 65,535.")
        return super().to_python(value)

    @cached_property
    def validators(self):
        return [*self._validators, MinValueValidator(0), MaxValueValidator(65535)]
