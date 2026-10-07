from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.functional import cached_property


class VersionNumber(models.PositiveSmallIntegerField):
    @cached_property
    def validators(self):
        return [*self._validators, MinValueValidator(1), MaxValueValidator(65535)]


class SourceIndex(models.Index):
    """Preserve the source MySQL/MariaDB index identifiers (64-character limit)."""

    max_name_length = 64
