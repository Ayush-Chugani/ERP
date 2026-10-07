"""Keep these import paths stable: historical migrations depend on them."""
import re
import unicodedata
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.functional import cached_property

class UnsignedAutoField(models.AutoField):
    def __init__(self, *args, bits=32, **kwargs):
        if bits not in (8, 16, 32):
            raise ValueError("Unsigned auto field supports 8, 16 or 32 bits")
        self.bits = bits
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["bits"] = self.bits
        return name, path, args, kwargs

    def get_internal_type(self):
        # Integer lookups consult backend ranges; signed AutoField would turn
        # valid unsigned INT lookups above 2**31-1 into an empty result.
        return "PositiveIntegerField"

    def db_check(self, connection):
        return None  # MySQL UNSIGNED already enforces the storage range.

    def db_type(self, connection):
        if connection.vendor == "mysql":
            return {8: "tinyint unsigned", 16: "smallint unsigned", 32: "integer unsigned"}[self.bits]
        return super().db_type(connection)

    def db_type_suffix(self, connection):
        if connection.vendor == "mysql":
            return "AUTO_INCREMENT"
        return super().db_type_suffix(connection)

    def rel_db_type(self, connection):
        return self.db_type(connection)

    @cached_property
    def validators(self):
        # AutoField's signed backend range must not cap unsigned INT at 2**31-1.
        return [*self.default_validators, *self._validators,
                MinValueValidator(1), MaxValueValidator(2**self.bits - 1)]

class ReferenceTextField(models.CharField):
    def __init__(self, *args, kind="name", fixed=False, **kwargs):
        self.kind, self.fixed = kind, fixed
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.update(kind=self.kind, fixed=self.fixed)
        return name, path, args, kwargs

    def db_type(self, connection):
        if self.fixed and connection.vendor == "mysql":
            return f"char({self.max_length})"
        return super().db_type(connection)

    def to_python(self, value):
        value = super().to_python(value)
        if value is None:
            return None
        value = unicodedata.normalize("NFC", value).strip()
        if self.kind == "code":
            value = value.upper()
        elif self.kind == "name":
            value = " ".join(value.split())
        if not value and self.null:
            return None
        return value

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        if value and self.kind == "code" and not re.fullmatch(r"[A-Z0-9_+\-]+", value):
            raise ValidationError("Codes use ASCII letters, digits, underscore, plus or hyphen.")
        if value and self.fixed and not re.fullmatch(r"[A-Z]{2}", value):
            raise ValidationError("Country ISO code must contain exactly two ASCII letters.")
