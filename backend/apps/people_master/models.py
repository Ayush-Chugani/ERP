from django.db import models
from django.db.models import Q, F, Case, When
from django.core.exceptions import ValidationError
from apps.core.fields import UnsignedAutoField
from .enums import StudentStatus, EmploymentStatus
from .fields import UnsignedBigAutoField, YearField, UnsignedTinyIntegerField


class LocalValidation(models.Model):
    class Meta:
        abstract = True

    def clean(self):
        from .validation import clean_local

        clean_local(self)


class Student(LocalValidation):
    student_id = UnsignedBigAutoField(primary_key=True)
    student_number = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    university_seat_number = models.CharField(
        max_length=30,
        db_collation="utf8mb4_unicode_ci",
        null=True,
        blank=True,
        unique=True,
    )
    first_name = models.CharField(
        max_length=100,
        db_collation="utf8mb4_unicode_ci",
    )
    middle_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    last_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    display_name = models.CharField(
        max_length=250,
        db_collation="utf8mb4_unicode_ci",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.ForeignKey(
        "common_reference.Gender",
        on_delete=models.PROTECT,
        db_column="gender_id",
        null=True,
        blank=True,
    )
    blood_group = models.ForeignKey(
        "common_reference.BloodGroup",
        on_delete=models.PROTECT,
        db_column="blood_group_id",
        null=True,
        blank=True,
    )
    primary_email = models.EmailField(
        max_length=254, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    primary_phone = models.CharField(
        max_length=25, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    nationality_country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        db_column="nationality_country_id",
        null=True,
        blank=True,
    )
    religion = models.ForeignKey(
        "common_reference.Religion",
        on_delete=models.PROTECT,
        db_column="religion_id",
        null=True,
        blank=True,
    )
    social_category = models.ForeignKey(
        "common_reference.SocialCategory",
        on_delete=models.PROTECT,
        db_column="social_category_id",
        null=True,
        blank=True,
    )
    caste = models.ForeignKey(
        "common_reference.Caste",
        on_delete=models.PROTECT,
        db_column="caste_id",
        null=True,
        blank=True,
    )
    sub_caste = models.ForeignKey(
        "common_reference.SubCaste",
        on_delete=models.PROTECT,
        db_column="sub_caste_id",
        null=True,
        blank=True,
    )
    photo_url = models.URLField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    admission_date = models.DateField(null=True, blank=True)

    StudentStatus = StudentStatus

    student_status = models.CharField(
        max_length=9,
        choices=StudentStatus.choices,
        default="APPLICANT",
        db_default="APPLICANT",
    )
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    institution = models.ForeignKey(
        "organization.Institution", on_delete=models.PROTECT
    )
    campus = models.ForeignKey(
        "organization.Campus", on_delete=models.PROTECT, null=True, blank=True
    )
    department = models.ForeignKey(
        "organization.Department", on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["institution", "student_status", "student_number"],
                name="m5_student_scope",
            )
        ]
        db_table = "student"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_student", "Change lifecycle"),
            ("confidential_student", "Read confidential fields"),
            ("restricted_student", "Read restricted fields"),
            ("export_student", "Export scoped records"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    student_status__in=[
                        "APPLICANT",
                        "ACTIVE",
                        "SUSPENDED",
                        "WITHDRAWN",
                        "COMPLETED",
                        "ALUMNUS",
                        "DECEASED",
                    ]
                ),
                name="chk_m5_student_student_statu",
            ),
            models.UniqueConstraint(
                fields=["primary_email"], name="uq_student_primary_email"
            ),
        ]


class StudentAddress(LocalValidation):
    student_address_id = UnsignedBigAutoField(primary_key=True)
    student = models.ForeignKey(
        "people_master.Student",
        on_delete=models.PROTECT,
        db_column="student_id",
    )

    class AddressType(models.TextChoices):
        PERMANENT = "PERMANENT"
        CURRENT = "CURRENT"
        CORRESPONDENCE = "CORRESPONDENCE"
        OTHER = "OTHER"

    address_type = models.CharField(
        max_length=14,
        choices=AddressType.choices,
    )
    address_line_1 = models.CharField(
        max_length=200,
        db_collation="utf8mb4_unicode_ci",
    )
    address_line_2 = models.CharField(
        max_length=200, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    city = models.CharField(
        max_length=100,
        db_collation="utf8mb4_unicode_ci",
    )
    state = models.ForeignKey(
        "common_reference.State",
        on_delete=models.PROTECT,
        db_column="state_id",
        null=True,
        blank=True,
    )
    country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        db_column="country_id",
    )
    postal_code = models.CharField(
        max_length=12, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=False, db_default=False)
    current_primary_student_id = models.GeneratedField(
        expression=Case(
            When(is_primary=True, valid_to__isnull=True, then=F("student")),
            default=None,
        ),
        output_field=models.PositiveBigIntegerField(),
        db_persist=True,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "student_address"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_studentaddress", "Change lifecycle"),
            ("confidential_studentaddress", "Read confidential fields"),
            ("restricted_studentaddress", "Read restricted fields"),
            ("export_studentaddress", "Export scoped records"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    address_type__in=["PERMANENT", "CURRENT", "CORRESPONDENCE", "OTHER"]
                ),
                name="chk_m5_student_address_address_type",
            ),
            models.UniqueConstraint(
                fields=["current_primary_student_id"],
                name="uq_student_current_primary_address",
            ),
            models.CheckConstraint(
                condition=Q(valid_from__isnull=True)
                | Q(valid_to__isnull=True)
                | Q(valid_to__gte=F("valid_from")),
                name="chk_m5_student_address_dates",
            ),
        ]


class StudentParentGuardian(LocalValidation):
    student_parent_guardian_id = UnsignedBigAutoField(primary_key=True)
    student = models.ForeignKey(
        "people_master.Student",
        on_delete=models.PROTECT,
        db_column="student_id",
    )

    class RelationshipType(models.TextChoices):
        FATHER = "FATHER"
        MOTHER = "MOTHER"
        GUARDIAN = "GUARDIAN"
        OTHER = "OTHER"

    relationship_type = models.CharField(
        max_length=8,
        choices=RelationshipType.choices,
    )
    full_name = models.CharField(
        max_length=200,
        db_collation="utf8mb4_unicode_ci",
    )
    occupation = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    annual_income = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    email = models.EmailField(
        max_length=254, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    phone = models.CharField(
        max_length=25, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    address_line_1 = models.CharField(
        max_length=200, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    address_line_2 = models.CharField(
        max_length=200, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    city = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    state = models.ForeignKey(
        "common_reference.State",
        on_delete=models.PROTECT,
        db_column="state_id",
        null=True,
        blank=True,
    )
    country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        db_column="country_id",
        null=True,
        blank=True,
    )
    postal_code = models.CharField(
        max_length=12, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_primary_contact = models.BooleanField(default=False, db_default=False)

    class Meta:
        db_table = "student_parent_guardian"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_studentparentguardian", "Change lifecycle"),
            ("confidential_studentparentguardian", "Read confidential fields"),
            ("restricted_studentparentguardian", "Read restricted fields"),
            ("export_studentparentguardian", "Export scoped records"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    relationship_type__in=["FATHER", "MOTHER", "GUARDIAN", "OTHER"]
                ),
                name="chk_m5_student_parent_gu_relationship_",
            ),
            models.CheckConstraint(
                condition=Q(annual_income__isnull=True) | Q(annual_income__gte=0),
                name="chk_m5_student_parent__annual_incom",
            ),
        ]


class StudentResidence(LocalValidation):
    student_residence_id = UnsignedBigAutoField(primary_key=True)
    student = models.ForeignKey(
        "people_master.Student",
        on_delete=models.PROTECT,
        db_column="student_id",
    )

    class ResidenceType(models.TextChoices):
        HOSTEL = "HOSTEL"
        DAY_SCHOLAR = "DAY_SCHOLAR"
        PG = "PG"
        RENTED = "RENTED"
        RELATIVE = "RELATIVE"
        OTHER = "OTHER"

    residence_type = models.CharField(
        max_length=11,
        choices=ResidenceType.choices,
    )
    hostel_name = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    room_number = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "student_residence"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_studentresidence", "Change lifecycle"),
            ("confidential_studentresidence", "Read confidential fields"),
            ("restricted_studentresidence", "Read restricted fields"),
            ("export_studentresidence", "Export scoped records"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    residence_type__in=[
                        "HOSTEL",
                        "DAY_SCHOLAR",
                        "PG",
                        "RENTED",
                        "RELATIVE",
                        "OTHER",
                    ]
                ),
                name="chk_m5_student_residence_residence_typ",
            ),
            models.CheckConstraint(
                condition=Q(start_date__isnull=True)
                | Q(end_date__isnull=True)
                | Q(end_date__gte=F("start_date")),
                name="chk_m5_student_residence_dates",
            ),
        ]


class StudentPreviousEducation(LocalValidation):
    previous_education_id = UnsignedBigAutoField(primary_key=True)
    student = models.ForeignKey(
        "people_master.Student",
        on_delete=models.PROTECT,
        db_column="student_id",
    )

    class QualificationLevel(models.TextChoices):
        SSLC = "SSLC"
        PUC_I = "PUC_I"
        PUC_II = "PUC_II"
        DIPLOMA = "DIPLOMA"
        UG = "UG"
        PG = "PG"
        OTHER = "OTHER"

    qualification_level = models.CharField(
        max_length=7,
        choices=QualificationLevel.choices,
    )
    examination_name = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    institution_name = models.CharField(
        max_length=250,
        db_collation="utf8mb4_unicode_ci",
    )
    board_university = models.CharField(
        max_length=200, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    registration_number = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    month_of_passing = UnsignedTinyIntegerField(null=True, blank=True)
    year_of_passing = YearField(null=True, blank=True)
    result_class = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    marks_obtained = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    maximum_marks = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    class Meta:
        db_table = "student_previous_education"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_studentpreviouseducation", "Change lifecycle"),
            ("confidential_studentpreviouseducation", "Read confidential fields"),
            ("restricted_studentpreviouseducation", "Read restricted fields"),
            ("export_studentpreviouseducation", "Export scoped records"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    qualification_level__in=[
                        "SSLC",
                        "PUC_I",
                        "PUC_II",
                        "DIPLOMA",
                        "UG",
                        "PG",
                        "OTHER",
                    ]
                ),
                name="chk_m5_student_previous__qualification",
            ),
            models.UniqueConstraint(
                fields=["student", "qualification_level", "registration_number"],
                name="uq_previous_education",
            ),
            models.CheckConstraint(
                condition=Q(marks_obtained__isnull=True) | Q(marks_obtained__gte=0),
                name="chk_m5_student_previou_marks_obtain",
            ),
            models.CheckConstraint(
                condition=Q(maximum_marks__isnull=True) | Q(maximum_marks__gte=0),
                name="chk_m5_student_previou_maximum_mark",
            ),
            models.CheckConstraint(
                condition=Q(percentage__isnull=True)
                | Q(percentage__gte=0, percentage__lte=100),
                name="chk_m5_education_percent",
            ),
            models.CheckConstraint(
                condition=Q(month_of_passing__isnull=True)
                | Q(month_of_passing__gte=1, month_of_passing__lte=12),
                name="chk_m5_education_month",
            ),
            models.CheckConstraint(
                condition=Q(marks_obtained__isnull=True)
                | Q(maximum_marks__isnull=True)
                | Q(marks_obtained__lte=F("maximum_marks")),
                name="chk_m5_education_marks",
            ),
        ]


class StudentEntranceExam(LocalValidation):
    student_entrance_exam_id = UnsignedBigAutoField(primary_key=True)
    student = models.ForeignKey(
        "people_master.Student",
        on_delete=models.PROTECT,
        db_column="student_id",
    )
    exam_name = models.CharField(
        max_length=100,
        db_collation="utf8mb4_unicode_ci",
    )
    registration_number = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    rank_number = models.PositiveIntegerField(null=True, blank=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    exam_year = YearField(null=True, blank=True)
    allotment_date = models.DateField(null=True, blank=True)
    registration_fee = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        db_table = "student_entrance_exam"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_studententranceexam", "Change lifecycle"),
            ("confidential_studententranceexam", "Read confidential fields"),
            ("restricted_studententranceexam", "Read restricted fields"),
            ("export_studententranceexam", "Export scoped records"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "exam_name", "exam_year"], name="uq_student_exam"
            ),
            models.CheckConstraint(
                condition=Q(registration_fee__isnull=True) | Q(registration_fee__gte=0),
                name="chk_m5_student_entranc_registration",
            ),
        ]


class StaffType(LocalValidation):
    staff_type_id = UnsignedAutoField(bits=8, primary_key=True)
    type_code = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    type_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", unique=True
    )
    description = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "staff_type"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_stafftype", "Change lifecycle"),
            ("confidential_stafftype", "Read confidential fields"),
            ("restricted_stafftype", "Read restricted fields"),
            ("export_stafftype", "Export scoped records"),
        ]
        constraints = []


class StaffCategory(LocalValidation):
    staff_category_id = UnsignedAutoField(bits=16, primary_key=True)
    staff_type = models.ForeignKey(
        "people_master.StaffType",
        on_delete=models.PROTECT,
        db_column="staff_type_id",
    )
    category_code = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", unique=True
    )
    category_name = models.CharField(
        max_length=150,
        db_collation="utf8mb4_unicode_ci",
    )
    description = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "staff_category"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_staffcategory", "Change lifecycle"),
            ("confidential_staffcategory", "Read confidential fields"),
            ("restricted_staffcategory", "Read restricted fields"),
            ("export_staffcategory", "Export scoped records"),
        ]
        constraints = []


class EmploymentSource(LocalValidation):
    employment_source_id = UnsignedAutoField(bits=8, primary_key=True)
    source_code = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    source_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", unique=True
    )
    is_external = models.BooleanField(default=False, db_default=False)
    description = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employment_source"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_employmentsource", "Change lifecycle"),
            ("confidential_employmentsource", "Read confidential fields"),
            ("restricted_employmentsource", "Read restricted fields"),
            ("export_employmentsource", "Export scoped records"),
        ]
        constraints = []


class ExternalAgency(LocalValidation):
    external_agency_id = UnsignedBigAutoField(primary_key=True)
    institution = models.ForeignKey(
        "organization.Institution",
        on_delete=models.PROTECT,
        db_column="institution_id",
    )
    agency_code = models.CharField(
        max_length=50,
        db_collation="utf8mb4_unicode_ci",
    )
    agency_name = models.CharField(
        max_length=200,
        db_collation="utf8mb4_unicode_ci",
    )
    service_type = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    contact_person = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    phone = models.CharField(
        max_length=25, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    email = models.EmailField(
        max_length=254, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    address = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_agency"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_externalagency", "Change lifecycle"),
            ("confidential_externalagency", "Read confidential fields"),
            ("restricted_externalagency", "Read restricted fields"),
            ("export_externalagency", "Export scoped records"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "agency_code"], name="uq_external_agency"
            ),
            models.CheckConstraint(
                condition=Q(contract_start_date__isnull=True)
                | Q(contract_end_date__isnull=True)
                | Q(contract_end_date__gte=F("contract_start_date")),
                name="chk_m5_external_agency_dates",
            ),
        ]


class Designation(LocalValidation):
    designation_id = UnsignedAutoField(bits=16, primary_key=True)
    staff_category = models.ForeignKey(
        "people_master.StaffCategory",
        on_delete=models.PROTECT,
        db_column="staff_category_id",
    )
    designation_code = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    designation_name = models.CharField(
        max_length=100,
        db_collation="utf8mb4_unicode_ci",
    )
    description = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "designation"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_designation", "Change lifecycle"),
            ("confidential_designation", "Read confidential fields"),
            ("restricted_designation", "Read restricted fields"),
            ("export_designation", "Export scoped records"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["staff_category", "designation_name"],
                name="uq_designation_category_name",
            ),
        ]


class Employee(LocalValidation):
    employee_id = UnsignedBigAutoField(primary_key=True)
    institution = models.ForeignKey(
        "organization.Institution",
        on_delete=models.PROTECT,
        db_column="institution_id",
    )
    employment_source = models.ForeignKey(
        "people_master.EmploymentSource",
        on_delete=models.PROTECT,
        db_column="employment_source_id",
    )
    external_agency = models.ForeignKey(
        "people_master.ExternalAgency",
        on_delete=models.PROTECT,
        db_column="external_agency_id",
        null=True,
        blank=True,
    )
    employee_number = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    agency_employee_number = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    first_name = models.CharField(
        max_length=100,
        db_collation="utf8mb4_unicode_ci",
    )
    middle_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    last_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    display_name = models.CharField(
        max_length=250,
        db_collation="utf8mb4_unicode_ci",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.ForeignKey(
        "common_reference.Gender",
        on_delete=models.PROTECT,
        db_column="gender_id",
        null=True,
        blank=True,
    )
    blood_group = models.ForeignKey(
        "common_reference.BloodGroup",
        on_delete=models.PROTECT,
        db_column="blood_group_id",
        null=True,
        blank=True,
    )
    primary_email = models.EmailField(
        max_length=254, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    primary_phone = models.CharField(
        max_length=25, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    nationality_country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        db_column="nationality_country_id",
        null=True,
        blank=True,
    )
    religion = models.ForeignKey(
        "common_reference.Religion",
        on_delete=models.PROTECT,
        db_column="religion_id",
        null=True,
        blank=True,
    )
    social_category = models.ForeignKey(
        "common_reference.SocialCategory",
        on_delete=models.PROTECT,
        db_column="social_category_id",
        null=True,
        blank=True,
    )
    caste = models.ForeignKey(
        "common_reference.Caste",
        on_delete=models.PROTECT,
        db_column="caste_id",
        null=True,
        blank=True,
    )
    sub_caste = models.ForeignKey(
        "common_reference.SubCaste",
        on_delete=models.PROTECT,
        db_column="sub_caste_id",
        null=True,
        blank=True,
    )
    photo_url = models.URLField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    joining_date = models.DateField()

    class EmploymentType(models.TextChoices):
        REGULAR = "REGULAR"
        CONTRACT = "CONTRACT"
        VISITING = "VISITING"
        ADJUNCT = "ADJUNCT"
        TEMPORARY = "TEMPORARY"
        OTHER = "OTHER"

    employment_type = models.CharField(
        max_length=9,
        choices=EmploymentType.choices,
    )

    EmploymentStatus = EmploymentStatus

    employment_status = models.CharField(
        max_length=10,
        choices=EmploymentStatus.choices,
        default="DRAFT",
        db_default="DRAFT",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["institution", "employment_status", "employee_number"],
                name="m5_employee_scope",
            )
        ]
        db_table = "employee"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_employee", "Change lifecycle"),
            ("confidential_employee", "Read confidential fields"),
            ("restricted_employee", "Read restricted fields"),
            ("export_employee", "Export scoped records"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    employment_type__in=[
                        "REGULAR",
                        "CONTRACT",
                        "VISITING",
                        "ADJUNCT",
                        "TEMPORARY",
                        "OTHER",
                    ]
                ),
                name="chk_m5_employee_employment_ty",
            ),
            models.CheckConstraint(
                condition=Q(
                    employment_status__in=[
                        "DRAFT",
                        "ACTIVE",
                        "ON_LEAVE",
                        "SUSPENDED",
                        "RESIGNED",
                        "RETIRED",
                        "TERMINATED",
                    ]
                ),
                name="chk_m5_employee_employment_st",
            ),
            models.UniqueConstraint(
                fields=["external_agency", "agency_employee_number"],
                name="uq_employee_agency_number",
            ),
            models.UniqueConstraint(
                fields=["primary_email"], name="uq_employee_primary_email"
            ),
        ]


class EmployeeAddress(LocalValidation):
    employee_address_id = UnsignedBigAutoField(primary_key=True)
    employee = models.ForeignKey(
        "people_master.Employee",
        on_delete=models.PROTECT,
        db_column="employee_id",
    )

    class AddressType(models.TextChoices):
        PERMANENT = "PERMANENT"
        CURRENT = "CURRENT"
        CORRESPONDENCE = "CORRESPONDENCE"
        OTHER = "OTHER"

    address_type = models.CharField(
        max_length=14,
        choices=AddressType.choices,
    )
    address_line_1 = models.CharField(
        max_length=200,
        db_collation="utf8mb4_unicode_ci",
    )
    address_line_2 = models.CharField(
        max_length=200, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    city = models.CharField(
        max_length=100,
        db_collation="utf8mb4_unicode_ci",
    )
    state = models.ForeignKey(
        "common_reference.State",
        on_delete=models.PROTECT,
        db_column="state_id",
        null=True,
        blank=True,
    )
    country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        db_column="country_id",
    )
    postal_code = models.CharField(
        max_length=12, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=False, db_default=False)
    current_primary_employee_id = models.GeneratedField(
        expression=Case(
            When(is_primary=True, valid_to__isnull=True, then=F("employee")),
            default=None,
        ),
        output_field=models.PositiveBigIntegerField(),
        db_persist=True,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "employee_address"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_employeeaddress", "Change lifecycle"),
            ("confidential_employeeaddress", "Read confidential fields"),
            ("restricted_employeeaddress", "Read restricted fields"),
            ("export_employeeaddress", "Export scoped records"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    address_type__in=["PERMANENT", "CURRENT", "CORRESPONDENCE", "OTHER"]
                ),
                name="chk_m5_employee_address_address_type",
            ),
            models.UniqueConstraint(
                fields=["current_primary_employee_id"],
                name="uq_employee_current_primary_address",
            ),
            models.CheckConstraint(
                condition=Q(valid_from__isnull=True)
                | Q(valid_to__isnull=True)
                | Q(valid_to__gte=F("valid_from")),
                name="chk_m5_employee_address_dates",
            ),
        ]


class EmployeeAssignment(LocalValidation):
    employee_assignment_id = UnsignedBigAutoField(primary_key=True)
    employee = models.ForeignKey(
        "people_master.Employee",
        on_delete=models.PROTECT,
        db_column="employee_id",
    )
    campus = models.ForeignKey(
        "organization.Campus",
        on_delete=models.PROTECT,
        db_column="campus_id",
    )
    department = models.ForeignKey(
        "organization.Department",
        on_delete=models.PROTECT,
        db_column="department_id",
        null=True,
        blank=True,
        db_constraint=False,
    )
    designation = models.ForeignKey(
        "people_master.Designation",
        on_delete=models.PROTECT,
        db_column="designation_id",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=True, db_default=True)
    current_primary_employee_id = models.GeneratedField(
        expression=Case(
            When(is_primary=True, end_date__isnull=True, then=F("employee")),
            default=None,
        ),
        output_field=models.PositiveBigIntegerField(),
        db_persist=True,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "employee_assignment"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_employeeassignment", "Change lifecycle"),
            ("confidential_employeeassignment", "Read confidential fields"),
            ("restricted_employeeassignment", "Read restricted fields"),
            ("export_employeeassignment", "Export scoped records"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["current_primary_employee_id"],
                name="uq_employee_current_primary",
            ),
            models.CheckConstraint(
                condition=Q(start_date__isnull=True)
                | Q(end_date__isnull=True)
                | Q(end_date__gte=F("start_date")),
                name="chk_m5_employee_assignment_dates",
            ),
        ]


class EmployeeCompetency(LocalValidation):
    employee = models.ForeignKey(
        "people_master.Employee",
        on_delete=models.PROTECT,
        db_column="employee_id",
    )
    course = models.ForeignKey(
        "curriculum_catalog.CourseCatalog",
        on_delete=models.PROTECT,
        db_column="course_id",
    )

    class CompetencyLevel(models.TextChoices):
        BEGINNER = "BEGINNER"
        INTERMEDIATE = "INTERMEDIATE"
        ADVANCED = "ADVANCED"
        EXPERT = "EXPERT"

    competency_level = models.CharField(
        max_length=12, choices=CompetencyLevel.choices, null=True, blank=True
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    pk = models.CompositePrimaryKey("employee_id", "course_id")

    class Meta:
        db_table = "employee_competency"
        ordering = ["pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("transition_employeecompetency", "Change lifecycle"),
            ("confidential_employeecompetency", "Read confidential fields"),
            ("restricted_employeecompetency", "Read restricted fields"),
            ("export_employeecompetency", "Export scoped records"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    competency_level__in=[
                        "BEGINNER",
                        "INTERMEDIATE",
                        "ADVANCED",
                        "EXPERT",
                    ]
                ),
                name="chk_m5_employee_competen_competency_le",
            ),
            models.CheckConstraint(
                condition=Q(valid_from__isnull=True)
                | Q(valid_to__isnull=True)
                | Q(valid_to__gte=F("valid_from")),
                name="chk_m5_employee_competency_dates",
            ),
        ]


# Platform support, separate from independent domain roots.
from django.conf import settings
from apps.core.models import AppendOnlyQuerySet
import uuid


class PeopleRevision(models.Model):
    resource = models.CharField(max_length=45)
    record_key = models.CharField(max_length=50)
    version = models.PositiveBigIntegerField(default=0)

    class Meta:
        db_table = "platform_people_revision"
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "record_key"], name="uq_people_revision"
            )
        ]


class PeopleAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    institution = models.ForeignKey(
        "organization.Institution", on_delete=models.PROTECT, null=True
    )
    resource = models.CharField(max_length=45)
    record_key = models.CharField(max_length=50)
    action = models.CharField(max_length=30)
    timestamp = models.DateTimeField(auto_now_add=True)
    correlation_id = models.UUIDField(default=uuid.uuid4)
    source = models.CharField(max_length=12, default="api")
    reason = models.CharField(max_length=250, blank=True)
    outcome = models.CharField(max_length=12, default="success")
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        db_table = "platform_people_audit"
        default_permissions = ("view",)
        ordering = ["-pk"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit is append-only.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit is append-only.")


class PeopleEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit = models.OneToOneField(PeopleAudit, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=100)
    schema_version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField(default=dict)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        db_table = "platform_people_event"
        default_permissions = ()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Events are append-only.")
        kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Events are append-only.")


class AccountLink(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    student = models.OneToOneField(
        Student, on_delete=models.PROTECT, null=True, blank=True
    )
    employee = models.OneToOneField(
        Employee, on_delete=models.PROTECT, null=True, blank=True
    )
    student_user_key = models.GeneratedField(
        expression=Case(When(student__isnull=False, then=F("user")), default=None),
        output_field=models.BigIntegerField(),
        db_persist=True,
        null=True,
        unique=True,
    )
    employee_user_key = models.GeneratedField(
        expression=Case(When(employee__isnull=False, then=F("user")), default=None),
        output_field=models.BigIntegerField(),
        db_persist=True,
        null=True,
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platform_people_account_link"
        constraints = [
            models.CheckConstraint(
                condition=Q(student__isnull=False, employee__isnull=True)
                | Q(student__isnull=True, employee__isnull=False),
                name="chk_people_link_root",
            ),
            models.UniqueConstraint(
                fields=["user", "student"], name="uq_people_user_student"
            ),
            models.UniqueConstraint(
                fields=["user", "employee"], name="uq_people_user_employee"
            ),
        ]
        permissions = [("manage_accountlink", "Manage explicit person account links")]


class AccountInvitation(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, null=True, blank=True
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, null=True, blank=True
    )
    intended_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "platform_people_invitation"
        constraints = [
            models.CheckConstraint(
                condition=Q(student__isnull=False, employee__isnull=True)
                | Q(student__isnull=True, employee__isnull=False),
                name="chk_people_invite_root",
            )
        ]
        default_permissions = ()
