from rest_framework import serializers as d

from .. import policies


class Strict(d.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise d.ValidationError(
                {"non_field_errors": ["Unknown or unsupported fields."]}
            )
        return super().to_internal_value(data)


def make(name, **fields):
    return type(name, (Strict,), fields)


def pk(required=True):
    return d.IntegerField(min_value=1, required=required)


def text(required=False, allow_null=True):
    return d.CharField(
        required=required,
        allow_null=allow_null,
        allow_blank=not required,
        max_length=15000,
        trim_whitespace=True,
    )


def status(values):
    return d.ChoiceField(choices=values)


MentorCreate = make(
    "MentorCreate",
    student_id=pk(),
    employee_id=pk(),
    start_date=d.DateField(),
    end_date=d.DateField(required=False, allow_null=True),
)
MentorEnd = make(
    "MentorEnd", expected_status=status(policies.ASSIGNMENT), end_date=d.DateField()
)
MentorChange = make(
    "MentorChange",
    expected_status=status(policies.ASSIGNMENT),
    employee_id=pk(),
    start_date=d.DateField(),
)
SessionSchedule = make(
    "SessionSchedule",
    mentor_assignment_id=pk(),
    session_date=d.DateTimeField(),
    confidentiality_level=d.ChoiceField(choices=policies.LEVELS, default="RESTRICTED"),
)
SessionComplete = make(
    "SessionComplete",
    expected_status=status(policies.SESSION),
    observations=text(),
    action_plan=text(),
)
SessionFollowUp = make(
    "SessionFollowUp",
    expected_status=status(policies.SESSION),
    observations=text(),
    action_plan=text(),
    follow_up_date=d.DateField(),
)
SessionCancel = make("SessionCancel", expected_status=status(policies.SESSION))
SessionReschedule = make(
    "SessionReschedule",
    expected_status=status(policies.SESSION),
    session_date=d.DateTimeField(),
)
SessionConfidentiality = make(
    "SessionConfidentiality",
    expected_status=status(policies.SESSION),
    confidentiality_level=status(policies.LEVELS),
)
GrievanceSubmit = make(
    "GrievanceSubmit",
    grievance_category_id=pk(),
    department_id=pk(False),
    subject=d.CharField(max_length=200),
    description=text(True, False),
    priority=d.ChoiceField(choices=policies.PRIORITY, default="NORMAL"),
)
GrievanceAssign = make(
    "GrievanceAssign",
    expected_status=status(policies.STATUS),
    department_id=pk(),
    notes=text(True, False),
)
GrievanceReview = make(
    "GrievanceReview", expected_status=status(policies.STATUS), notes=text()
)
GrievanceResolve = make(
    "GrievanceResolve",
    expected_status=status(policies.STATUS),
    resolution=text(True, False),
    notes=text(),
)
GrievanceReject = make(
    "GrievanceReject", expected_status=status(policies.STATUS), notes=text(True, False)
)
GrievanceClose = make(
    "GrievanceClose", expected_status=status(policies.STATUS), notes=text()
)
CategoryWrite = make(
    "CategoryWrite",
    category_code=d.CharField(max_length=30),
    category_name=d.CharField(max_length=100),
    is_active=d.BooleanField(default=True),
)


class SessionDetailOutput(d.Serializer):
    id = d.CharField()
    mentor_assignment_id = d.CharField()
    session_date = d.DateTimeField()
    follow_up_date = d.DateField(allow_null=True)
    status = d.ChoiceField(choices=policies.SESSION)
    confidentiality_level = d.ChoiceField(choices=policies.LEVELS)
    observations = d.CharField(
        allow_null=True,
        help_text="Sensitive: authorized detail only. Do not cache, log or forward.",
    )
    action_plan = d.CharField(
        allow_null=True,
        help_text="Sensitive: authorized detail only. Do not cache, log or forward.",
    )


class GrievanceDetailOutput(d.Serializer):
    id = d.CharField()
    number = d.CharField()
    status = d.ChoiceField(choices=policies.STATUS)
    subject = d.CharField(help_text="Sensitive: protected detail only.")
    description = d.CharField(
        help_text="Sensitive: protected detail only. Do not cache, log or forward."
    )
    resolution = d.CharField(
        allow_null=True, help_text="Sensitive: protected detail only."
    )


class AssignmentOutput(d.Serializer):
    id = d.CharField()
    student_id = d.CharField()
    employee_id = d.CharField()
    status = d.ChoiceField(choices=policies.ASSIGNMENT)
    start_date = d.DateField()
    end_date = d.DateField(allow_null=True)
