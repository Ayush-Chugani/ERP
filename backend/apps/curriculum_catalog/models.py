from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F
from apps.core.fields import UnsignedAutoField, ReferenceTextField
from apps.core.models import AppendOnlyQuerySet
from .fields import UnsignedBigAutoField, YearField


def text(length, optional=False, code=False, **kwargs):
    return ReferenceTextField(
        max_length=length,
        null=optional,
        blank=optional,
        kind="code" if code else "name",
        db_collation="utf8mb4_unicode_ci",
        **kwargs,
    )


def parent(model, name, **kwargs):
    return models.ForeignKey(
        model, on_delete=models.PROTECT, db_column=name + "_id", **kwargs
    )


def decimal(digits, places, **kwargs):
    return models.DecimalField(max_digits=digits, decimal_places=places, **kwargs)


class CourseCategory(models.Model):
    course_category_id = UnsignedAutoField(bits=16, primary_key=True)
    category_code = text(30, code=True, unique=True)
    category_name = text(100, unique=True)
    is_graded = models.BooleanField(default=True, db_default=True)
    contributes_to_gpa = models.BooleanField(default=True, db_default=True)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "course_category"
        ordering = ["category_code", "pk"]
        permissions = [
            ("activate_coursecategory", "Activate category"),
            ("deactivate_coursecategory", "Deactivate category"),
            ("export_coursecategory", "Export categories"),
        ]

    def __str__(self):
        return self.category_name


class CourseCatalog(models.Model):
    class Type(models.TextChoices):
        THEORY = "THEORY"
        LAB = "LAB"
        THEORY_LAB = "THEORY_LAB"
        PROJECT = "PROJECT"
        SEMINAR = "SEMINAR"
        INTERNSHIP = "INTERNSHIP"
        OTHER = "OTHER"

    course_id = UnsignedAutoField(bits=32, primary_key=True)
    owning_department = parent(
        "organization.Department", "owning_department", related_name="owned_courses"
    )
    course_category = parent(CourseCategory, "course_category", related_name="courses")
    course_code = text(30, code=True, unique=True)
    course_title = text(200)
    short_title = text(80, optional=True)
    course_type = models.CharField(max_length=10, choices=Type.choices)
    lecture_hours = decimal(4, 1, default=0, db_default=0)
    tutorial_hours = decimal(4, 1, default=0, db_default=0)
    practical_hours = decimal(4, 1, default=0, db_default=0)
    self_study_hours = decimal(4, 1, default=0, db_default=0)
    credits = decimal(4, 1, default=0, db_default=0)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "course_catalog"
        ordering = ["course_code", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    lecture_hours__gte=0,
                    tutorial_hours__gte=0,
                    practical_hours__gte=0,
                    self_study_hours__gte=0,
                    credits__gte=0,
                ),
                name="chk_course_nonnegative_values",
            ),
            models.CheckConstraint(
                condition=Q(effective_from__isnull=True)
                | Q(effective_to__isnull=True)
                | Q(effective_to__gte=F("effective_from")),
                name="chk_course_effective_dates",
            ),
            models.CheckConstraint(
                condition=Q(
                    course_type__in=[
                        "THEORY",
                        "LAB",
                        "THEORY_LAB",
                        "PROJECT",
                        "SEMINAR",
                        "INTERNSHIP",
                        "OTHER",
                    ]
                ),
                name="chk_catalog_course_type",
            ),
        ]
        indexes = [
            models.Index(
                fields=["owning_department", "is_active", "course_code"],
                name="catalog_department_active",
            )
        ]
        permissions = [
            ("activate_coursecatalog", "Activate course"),
            ("deactivate_coursecatalog", "Deactivate course"),
            ("export_coursecatalog", "Export courses"),
        ]

    def clean(self):
        if (
            self.effective_from
            and self.effective_to
            and self.effective_to < self.effective_from
        ):
            raise ValidationError(
                {"effective_to": "Must be on or after effective_from."}
            )

    def __str__(self):
        return self.course_title


class CurriculumScheme(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT"
        ACTIVE = "ACTIVE"
        RETIRED = "RETIRED"

    curriculum_scheme_id = UnsignedAutoField(bits=32, primary_key=True)
    programme = parent(
        "organization.Programme", "programme", related_name="curriculum_schemes"
    )
    specialization = parent(
        "organization.ProgrammeSpecialization",
        "specialization",
        null=True,
        blank=True,
        db_constraint=False,
        related_name="curriculum_schemes",
    )
    scheme_code = text(30, code=True, unique=True)
    scheme_name = text(150)
    regulation_year = YearField()
    total_credits = decimal(6, 1, null=True, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=7, choices=Status.choices, default="DRAFT", db_default="DRAFT"
    )

    class Meta:
        db_table = "curriculum_scheme"
        ordering = ["scheme_code", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["curriculum_scheme_id", "programme"], name="uq_m6_scheme_programme"),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=F("effective_from")),
                name="chk_scheme_effective_dates",
            ),
            models.CheckConstraint(
                condition=Q(total_credits__isnull=True) | Q(total_credits__gte=0),
                name="chk_scheme_total_credits",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["DRAFT", "ACTIVE", "RETIRED"]),
                name="chk_scheme_status",
            ),
        ]
        indexes = [
            models.Index(
                fields=["programme", "specialization", "status", "effective_from"],
                name="scheme_effective_lookup",
            )
        ]
        permissions = [
            ("activate_curriculumscheme", "Activate scheme"),
            ("retire_curriculumscheme", "Retire scheme"),
            ("clone_curriculumscheme", "Clone scheme"),
            ("export_curriculumscheme", "Export schemes"),
        ]

    def clean(self):
        errors = {}
        if (
            self.effective_from
            and self.effective_to
            and self.effective_to < self.effective_from
        ):
            errors["effective_to"] = "Must be on or after effective_from."
        if (
            self.specialization_id
            and self.specialization.programme_id != self.programme_id
        ):
            errors["specialization_id"] = "Specialization must belong to the programme."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.scheme_name


class CurriculumCourse(models.Model):
    curriculum_course_id = UnsignedBigAutoField(primary_key=True)
    curriculum_scheme = parent(
        CurriculumScheme, "curriculum_scheme", related_name="composition"
    )
    semester = parent(
        "academic_calendar.Semester", "semester", related_name="curriculum_courses"
    )
    course = parent(CourseCatalog, "course", related_name="curriculum_mappings")
    course_category = parent(
        CourseCategory, "course_category", related_name="curriculum_mappings"
    )
    is_mandatory = models.BooleanField(default=True, db_default=True)
    elective_group_code = text(30, optional=True, code=True)
    display_order = models.PositiveSmallIntegerField(null=True, blank=True)
    internal_max_marks = decimal(6, 2, default=0, db_default=0)
    external_max_marks = decimal(6, 2, default=0, db_default=0)
    passing_marks = decimal(6, 2, null=True, blank=True)
    exam_duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "curriculum_course"
        ordering = ["semester__semester_number", "display_order", "pk"]
        constraints = [models.UniqueConstraint(fields=["curriculum_course_id", "course"], name="uq_m7_curriculum_course_identity"), 
            models.UniqueConstraint(
                fields=["curriculum_scheme", "semester", "course"],
                name="uq_curriculum_course",
            ),
            models.UniqueConstraint(
                fields=["curriculum_scheme", "semester", "display_order"],
                name="uq_curriculum_display_order",
            ),
            models.CheckConstraint(
                condition=Q(internal_max_marks__gte=0, external_max_marks__gte=0)
                & (
                    Q(passing_marks__isnull=True)
                    | (
                        Q(passing_marks__gte=0)
                        & Q(
                            passing_marks__lte=F("internal_max_marks")
                            + F("external_max_marks")
                        )
                    )
                ),
                name="chk_curriculum_marks",
            ),
            models.CheckConstraint(
                condition=Q(is_mandatory=True, elective_group_code__isnull=True)
                | (
                    Q(is_mandatory=False, elective_group_code__isnull=False)
                    & ~Q(elective_group_code="")
                ),
                name="chk_curriculum_elective",
            ),
        ]
        permissions = [
            ("compose_curriculumcourse", "Compose draft curriculum"),
            ("export_curriculumcourse", "Export composition"),
        ]

    def clean(self):
        if (
            self.is_mandatory
            and self.elective_group_code
            or not self.is_mandatory
            and not self.elective_group_code
        ):
            raise ValidationError(
                {
                    "elective_group_code": "Mandatory rows have no group; electives require a group."
                }
            )
        total = Decimal(self.internal_max_marks or 0) + Decimal(
            self.external_max_marks or 0
        )
        if self.passing_marks is not None and not 0 <= self.passing_marks <= total:
            raise ValidationError(
                {"passing_marks": "Must be between zero and total marks."}
            )


class CoursePrerequisite(models.Model):
    pk = models.CompositePrimaryKey("course_id", "prerequisite_course_id")
    course = parent(CourseCatalog, "course", related_name="prerequisite_edges")
    prerequisite_course = parent(
        CourseCatalog, "prerequisite_course", related_name="required_by_edges"
    )
    minimum_grade = text(5, optional=True, code=True)

    class Meta:
        db_table = "course_prerequisite"
        ordering = ["course_id", "prerequisite_course_id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(course=F("prerequisite_course")),
                name="chk_prerequisite_not_self",
            )
        ]
        permissions = [
            ("manage_courseprerequisite", "Manage prerequisites"),
            ("export_courseprerequisite", "Export prerequisites"),
        ]

    def clean(self):
        if self.course_id == self.prerequisite_course_id:
            raise ValidationError(
                {"prerequisite_course_id": "A course cannot require itself."}
            )


class CurriculumRevision(models.Model):
    resource = models.CharField(max_length=32)
    record_key = models.CharField(max_length=50)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "platform_curriculum_revision"
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "record_key"], name="uq_curriculum_revision"
            )
        ]


class CurriculumAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    institution = models.ForeignKey(
        "organization.Institution", null=True, on_delete=models.PROTECT
    )
    resource = models.CharField(max_length=32)
    record_key = models.CharField(max_length=50)
    action = models.CharField(max_length=24)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    reason = models.CharField(max_length=250, blank=True)
    correlation_id = models.CharField(max_length=64)
    timestamp = models.DateTimeField(auto_now_add=True)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        db_table = "platform_curriculum_audit"
        default_permissions = ("view",)
        ordering = ["-timestamp", "-pk"]
        indexes = [
            models.Index(
                fields=["resource", "record_key"], name="curriculum_audit_record"
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit is append-only.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit is append-only.")


class CurriculumEvent(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    audit = models.OneToOneField(CurriculumAudit, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=80)
    schema_version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        db_table = "platform_curriculum_event"
        default_permissions = ()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Events are append-only.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Events are append-only.")
