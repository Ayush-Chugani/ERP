from collections.abc import Mapping

from rest_framework import serializers as d

from .. import models as m


class Strict(d.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise d.ValidationError({"non_field_errors": ["Expected an object."]})
        if set(data) - set(self.fields):
            raise d.ValidationError(
                {"non_field_errors": ["Unknown or protected fields."]}
            )
        return super().to_internal_value(data)


def make(name, **fields):
    return type(name, (Strict,), fields)


def pk(required=True):
    return d.IntegerField(min_value=1, required=required)


def text(limit, required=False):
    return d.CharField(
        max_length=limit,
        required=required,
        allow_null=not required,
        allow_blank=not required,
    )


def reason():
    return text(500, True)


def fields():
    return {
        "document_number": text(100),
        "issue_date": d.DateField(required=False, allow_null=True),
        "expiry_date": d.DateField(required=False, allow_null=True),
        "remarks": text(500),
    }


Upload = make(
    "DocumentUpload",
    upload=d.FileField(),
    document_type_id=pk(),
    student_id=pk(False),
    **fields(),
)
Update = make(
    "DocumentUpdate",
    expected_status=d.ChoiceField(choices=m.Verification.choices),
    upload=d.FileField(required=False),
    **fields(),
)
Verify = make(
    "DocumentVerification",
    expected_status=d.ChoiceField(choices=m.Verification.choices),
    target=d.ChoiceField(choices=m.Verification.choices),
    reason=reason(),
)
TypeWrite = make(
    "CertificateTypeWrite",
    certificate_code=text(30, True),
    certificate_name=text(100, True),
    is_active=d.BooleanField(default=True),
)
RequestCertificate = make(
    "CertificateSubmit", certificate_type_id=pk(), purpose=text(500)
)
CertificateAction = make(
    "CertificateAction",
    expected_status=d.ChoiceField(choices=m.RequestStatus.choices),
    reason=reason(),
)
Issue = make("CertificateIssue", reason=reason())
Exit = make(
    "ExitFinalize",
    enrolment_id=pk(),
    exit_type=d.ChoiceField(choices=m.ExitType.choices),
    exit_date=d.DateField(),
    reason=reason(),
    confirmed=d.BooleanField(),
    destination_institution=text(250),
    old_registration_number=text(50),
    remarks=text(15000),
)
Delete = make("FileSoftDelete", reason=reason())
