from collections.abc import Mapping

from rest_framework import serializers as z

from ..models import Audience


class Strict(z.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) - set(self.fields):
            raise z.ValidationError(
                {
                    "non_field_errors": [
                        "Expected an object containing only allowed fields."
                    ]
                }
            )
        return super().to_internal_value(data)


class Write(Strict):
    institution_id = z.IntegerField(min_value=1)
    department_id = z.IntegerField(
        min_value=1, allow_null=True, required=False, default=None
    )
    announcement_type_id = z.IntegerField(min_value=1)
    title = z.CharField(max_length=250)
    description = z.CharField(max_length=50000)
    publish_from = z.DateTimeField()
    publish_to = z.DateTimeField(allow_null=True, required=False, default=None)
    audience_type = z.ChoiceField(choices=Audience.choices)
    programme_ids = z.ListField(
        child=z.IntegerField(min_value=1), max_length=500, default=list
    )
    user_ids = z.ListField(
        child=z.IntegerField(min_value=1), max_length=500, default=list
    )
    expected_version = z.CharField(max_length=30, required=False)


class Workflow(Strict):
    expected_version = z.CharField(max_length=30)
    reason = z.CharField(max_length=500)


class TypeWrite(Strict):
    type_code = z.RegexField(r"^[A-Za-z0-9_]+$", max_length=30)
    type_name = z.CharField(max_length=100)
    is_active = z.BooleanField(default=True)


class Attachment(Strict):
    expected_version = z.CharField(max_length=30)
    file_id = z.IntegerField(min_value=1)
    display_order = z.IntegerField(
        min_value=0, max_value=65535, allow_null=True, required=False, default=None
    )


class Upload(Strict):
    expected_version = z.CharField(max_length=30)
    upload = z.FileField()
    level = z.ChoiceField(
        choices=[
            "PUBLIC",
            "INTERNAL",
            "CONFIDENTIAL",
            "RESTRICTED",
            "HIGHLY_RESTRICTED",
        ],
        default="INTERNAL",
    )
    display_order = z.IntegerField(
        min_value=0, max_value=65535, allow_null=True, required=False, default=None
    )
