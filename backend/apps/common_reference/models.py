from django.db import models
from apps.core.fields import ReferenceTextField, UnsignedAutoField

COLLATION = "utf8mb4_0900_ai_ci"

class ReferenceMaster(models.Model):
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        abstract = True

    def full_clean(self, *args, **kwargs):
        for field in self._meta.fields:
            if isinstance(field, ReferenceTextField):
                setattr(self, field.attname, field.to_python(getattr(self, field.attname)))
        return super().full_clean(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Validate/normalize normal ORM, admin and command writes. Database unique
        # constraints still arbitrate races. Bulk expressions bypass model validation.
        self.full_clean(exclude=[f.name for f in self._meta.fields if f.generated])
        return super().save(*args, **kwargs)

class Country(ReferenceMaster):
    country_id = UnsignedAutoField(bits=16, primary_key=True, db_column="country_id")
    iso_code = ReferenceTextField(max_length=2, kind="code", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=True)
    country_name = ReferenceTextField(max_length=100, kind="name", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)

    class Meta:
        db_table = "country"
        ordering = ["country_id"]
        permissions = [("view_reference", "Read global references"), ("maintain_reference", "Maintain global references")]

class State(ReferenceMaster):
    state_id = UnsignedAutoField(bits=16, primary_key=True, db_column="state_id")
    country = models.ForeignKey("Country", on_delete=models.PROTECT, db_column="country_id", null=False, blank=False, db_index=False)
    state_code = ReferenceTextField(max_length=10, kind="code", null=False, blank=False, unique=False, db_collation=COLLATION, fixed=False)
    state_name = ReferenceTextField(max_length=100, kind="name", null=False, blank=False, unique=False, db_collation=COLLATION, fixed=False)

    class Meta:
        db_table = "state"
        ordering = ["state_id"]
        constraints = [
            models.UniqueConstraint(fields=['country', 'state_code'], name="uq_state_country_code"),
            models.UniqueConstraint(fields=['country', 'state_name'], name="uq_state_country_name"),
        ]

class Gender(ReferenceMaster):
    gender_id = UnsignedAutoField(bits=8, primary_key=True, db_column="gender_id")
    gender_code = ReferenceTextField(max_length=20, kind="code", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)
    gender_name = ReferenceTextField(max_length=50, kind="name", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)

    class Meta:
        db_table = "gender"
        ordering = ["gender_id"]

class BloodGroup(ReferenceMaster):
    blood_group_id = UnsignedAutoField(bits=8, primary_key=True, db_column="blood_group_id")
    blood_group_code = ReferenceTextField(max_length=5, kind="code", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)

    class Meta:
        db_table = "blood_group"
        ordering = ["blood_group_id"]

class Religion(ReferenceMaster):
    religion_id = UnsignedAutoField(bits=16, primary_key=True, db_column="religion_id")
    religion_code = ReferenceTextField(max_length=20, kind="code", null=True, blank=True, unique=True, db_collation=COLLATION, fixed=False)
    religion_name = ReferenceTextField(max_length=100, kind="name", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)

    class Meta:
        db_table = "religion"
        ordering = ["religion_id"]

class SocialCategory(ReferenceMaster):
    social_category_id = UnsignedAutoField(bits=16, primary_key=True, db_column="social_category_id")
    category_code = ReferenceTextField(max_length=20, kind="code", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)
    category_name = ReferenceTextField(max_length=100, kind="name", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)

    class Meta:
        db_table = "social_category"
        ordering = ["social_category_id"]

class Caste(ReferenceMaster):
    caste_id = UnsignedAutoField(bits=32, primary_key=True, db_column="caste_id")
    social_category = models.ForeignKey("SocialCategory", on_delete=models.PROTECT, db_column="social_category_id", null=True, blank=True, db_index=False)
    caste_code = ReferenceTextField(max_length=30, kind="code", null=True, blank=True, unique=True, db_collation=COLLATION, fixed=False)
    caste_name = ReferenceTextField(max_length=150, kind="name", null=False, blank=False, unique=False, db_collation=COLLATION, fixed=False)
    uncategorized_caste_name = models.GeneratedField(
        expression=models.Case(models.When(social_category__isnull=True, then=models.F("caste_name")),
                               default=models.Value(None)),
        output_field=models.CharField(max_length=150, null=True, db_collation=COLLATION),
        db_persist=True, null=True, blank=True,
    )

    class Meta:
        db_table = "caste"
        ordering = ["caste_id"]
        constraints = [
            models.UniqueConstraint(fields=['social_category', 'caste_name'], name="uq_caste_name_category"),
            models.UniqueConstraint(fields=['uncategorized_caste_name'], name="uq_caste_uncategorized_name"),
        ]

class SubCaste(ReferenceMaster):
    sub_caste_id = UnsignedAutoField(bits=32, primary_key=True, db_column="sub_caste_id")
    caste = models.ForeignKey("Caste", on_delete=models.PROTECT, db_column="caste_id", null=False, blank=False, db_index=False)
    sub_caste_code = ReferenceTextField(max_length=30, kind="code", null=True, blank=True, unique=False, db_collation=COLLATION, fixed=False)
    sub_caste_name = ReferenceTextField(max_length=150, kind="name", null=False, blank=False, unique=False, db_collation=COLLATION, fixed=False)

    class Meta:
        db_table = "sub_caste"
        ordering = ["sub_caste_id"]
        constraints = [
            models.UniqueConstraint(fields=['caste', 'sub_caste_name'], name="uq_sub_caste"),
        ]

class AdmissionCategory(ReferenceMaster):
    admission_category_id = UnsignedAutoField(bits=16, primary_key=True, db_column="admission_category_id")
    category_code = ReferenceTextField(max_length=30, kind="code", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)
    category_name = ReferenceTextField(max_length=100, kind="name", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)
    description = ReferenceTextField(max_length=500, kind="description", null=True, blank=True, unique=False, db_collation=COLLATION, fixed=False)

    class Meta:
        db_table = "admission_category"
        ordering = ["admission_category_id"]

class DocumentType(ReferenceMaster):
    document_type_id = UnsignedAutoField(bits=16, primary_key=True, db_column="document_type_id")
    document_code = ReferenceTextField(max_length=30, kind="code", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)
    document_name = ReferenceTextField(max_length=100, kind="name", null=False, blank=False, unique=True, db_collation=COLLATION, fixed=False)
    requires_verification = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "document_type"
        ordering = ["document_type_id"]

