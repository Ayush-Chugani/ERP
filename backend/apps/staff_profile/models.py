from typing import ClassVar

from django.db import models

from apps.core.fields import UnsignedAutoField
from apps.documents_exit.fields import NativeTimestampField
from apps.people_master.fields import (
    UnsignedBigAutoField,
    UnsignedTinyIntegerField,
)
from apps.student_support.fields import CurrentTimestamp, NativeEnumField


class PublicationType(models.Model):
    publication_type_id = UnsignedAutoField(primary_key=True, bits=16)
    publication_type_code = models.CharField(
        max_length=40, db_collation="utf8mb4_unicode_ci", unique=True
    )
    publication_type_name = models.CharField(
        max_length=120, db_collation="utf8mb4_unicode_ci", unique=True
    )
    description = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(db_default=True, default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)

    class Meta:
        db_table = "publication_type"
        default_permissions = ()
        constraints: ClassVar[list] = []


class JournalType(models.Model):
    journal_type_id = UnsignedAutoField(primary_key=True, bits=8)
    journal_type_code = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    journal_type_name = models.CharField(
        max_length=80, db_collation="utf8mb4_unicode_ci", unique=True
    )
    description = models.CharField(
        max_length=300, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "journal_type"
        default_permissions = ()
        constraints: ClassVar[list] = []


class IndexingAgency(models.Model):
    indexing_agency_id = UnsignedAutoField(primary_key=True, bits=16)
    agency_code = models.CharField(
        max_length=40, db_collation="utf8mb4_unicode_ci", unique=True
    )
    agency_name = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", unique=True
    )
    website_url = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    description = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "indexing_agency"
        default_permissions = ()
        constraints: ClassVar[list] = []


class MetricType(models.Model):
    metric_type_id = UnsignedAutoField(primary_key=True, bits=8)
    metric_code = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    metric_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", unique=True
    )
    description = models.CharField(
        max_length=300, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "metric_type"
        default_permissions = ()
        constraints: ClassVar[list] = []


class ExternalOrganization(models.Model):
    organization_id = UnsignedBigAutoField(primary_key=True)
    organization_code = models.CharField(
        max_length=60,
        db_collation="utf8mb4_unicode_ci",
        null=True,
        blank=True,
        unique=True,
    )
    organization_name = models.CharField(
        max_length=250, db_collation="utf8mb4_unicode_ci"
    )
    short_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    website_url = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    email = models.CharField(
        max_length=254, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    phone = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    address_line_1 = models.CharField(
        max_length=250, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    address_line_2 = models.CharField(
        max_length=250, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    city = models.CharField(
        max_length=120, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    state = models.ForeignKey(
        "common_reference.State",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="state_id",
        null=True,
        blank=True,
    )
    country = models.ForeignKey(
        "common_reference.Country",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="country_id",
        null=True,
        blank=True,
    )
    postal_code = models.CharField(
        max_length=20, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(db_default=True, default=True)
    created_at = NativeTimestampField(db_default=CurrentTimestamp())
    updated_at = NativeTimestampField(db_default=CurrentTimestamp(), auto_now=True)

    class Meta:
        db_table = "external_organization"
        default_permissions = ()
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization_name", "city", "country"],
                name="uq_external_organization_name",
            ),
        ]


class Publisher(models.Model):
    publisher_id = UnsignedBigAutoField(primary_key=True)
    organization = models.OneToOneField(
        "staff_profile.ExternalOrganization",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="organization_id",
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "publisher"
        default_permissions = ()
        constraints: ClassVar[list] = []


class ActivityType(models.Model):
    activity_type_id = UnsignedAutoField(primary_key=True, bits=16)
    activity_type_code = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", unique=True
    )
    activity_type_name = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", unique=True
    )
    activity_group = NativeEnumField(
        choices=[
            ("PUBLICATION", "PUBLICATION"),
            ("CONFERENCE", "CONFERENCE"),
            ("PROFESSIONAL_DEVELOPMENT", "PROFESSIONAL_DEVELOPMENT"),
            ("INTERNSHIP", "INTERNSHIP"),
            ("RESEARCH", "RESEARCH"),
            ("CONSULTANCY", "CONSULTANCY"),
            ("CO_CURRICULAR", "CO_CURRICULAR"),
            ("EXTRA_CURRICULAR", "EXTRA_CURRICULAR"),
            ("AWARD", "AWARD"),
            ("MEMBERSHIP", "MEMBERSHIP"),
            (
                "ACADEMIC_PROFESSIONAL_CONTRIBUTION",
                "ACADEMIC_PROFESSIONAL_CONTRIBUTION",
            ),
            ("OTHER", "OTHER"),
        ],
        max_length=34,
        db_collation="utf8mb4_unicode_ci",
    )
    description = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "activity_type"
        default_permissions = ()
        constraints: ClassVar[list] = []


class ParticipationLevel(models.Model):
    participation_level_id = UnsignedAutoField(primary_key=True, bits=8)
    level_code = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    level_name = models.CharField(
        max_length=100, db_collation="utf8mb4_unicode_ci", unique=True
    )
    display_order = UnsignedTinyIntegerField(db_default=0, default=0)
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "participation_level"
        default_permissions = ()
        constraints: ClassVar[list] = []


class RoleType(models.Model):
    role_type_id = UnsignedAutoField(primary_key=True, bits=16)
    role_code = models.CharField(
        max_length=50, db_collation="utf8mb4_unicode_ci", unique=True
    )
    role_name = models.CharField(
        max_length=150, db_collation="utf8mb4_unicode_ci", unique=True
    )
    description = models.CharField(
        max_length=500, db_collation="utf8mb4_unicode_ci", null=True, blank=True
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "role_type"
        default_permissions = ()
        constraints: ClassVar[list] = []


class VerificationStatus(models.Model):
    verification_status_id = UnsignedAutoField(primary_key=True, bits=8)
    status_code = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    status_name = models.CharField(
        max_length=80, db_collation="utf8mb4_unicode_ci", unique=True
    )
    is_terminal = models.BooleanField(db_default=False, default=False)
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "verification_status"
        default_permissions = ()
        constraints: ClassVar[list] = []


class ApprovalStatus(models.Model):
    approval_status_id = UnsignedAutoField(primary_key=True, bits=8)
    status_code = models.CharField(
        max_length=30, db_collation="utf8mb4_unicode_ci", unique=True
    )
    status_name = models.CharField(
        max_length=80, db_collation="utf8mb4_unicode_ci", unique=True
    )
    is_terminal = models.BooleanField(db_default=False, default=False)
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "approval_status"
        default_permissions = ()
        constraints: ClassVar[list] = []


class Organizer(models.Model):
    organizer_id = UnsignedBigAutoField(primary_key=True)
    organization = models.OneToOneField(
        "staff_profile.ExternalOrganization",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="organization_id",
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "organizer"
        default_permissions = ()
        constraints: ClassVar[list] = []


class EventMode(models.Model):
    event_mode_id = UnsignedAutoField(primary_key=True, bits=8)
    mode_code = models.CharField(
        max_length=20, db_collation="utf8mb4_unicode_ci", unique=True
    )
    mode_name = models.CharField(
        max_length=60, db_collation="utf8mb4_unicode_ci", unique=True
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "event_mode"
        default_permissions = ()
        constraints: ClassVar[list] = []


class ConferenceContributionType(models.Model):
    conference_contribution_type_id = UnsignedAutoField(primary_key=True, bits=8)
    type_code = models.CharField(
        max_length=40, db_collation="utf8mb4_unicode_ci", unique=True
    )
    type_name = models.CharField(
        max_length=120, db_collation="utf8mb4_unicode_ci", unique=True
    )
    is_active = models.BooleanField(db_default=True, default=True)

    class Meta:
        db_table = "conference_contribution_type"
        default_permissions = ()
        constraints: ClassVar[list] = []


class IndustrySector(models.Model):
    industry_sector_id = UnsignedAutoField(primary_key=True, bits=16)
    sector_code = models.CharField(
        max_length=50, unique=True, db_collation="utf8mb4_unicode_ci"
    )
    sector_name = models.CharField(
        max_length=150, unique=True, db_collation="utf8mb4_unicode_ci"
    )
    description = models.CharField(
        max_length=500, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "industry_sector"
        default_permissions = ()


class FundingType(models.Model):
    funding_type_id = UnsignedAutoField(primary_key=True, bits=8)
    funding_type_code = models.CharField(
        max_length=30, unique=True, db_collation="utf8mb4_unicode_ci"
    )
    funding_type_name = models.CharField(
        max_length=100, unique=True, db_collation="utf8mb4_unicode_ci"
    )
    is_external = models.BooleanField(default=False, db_default=False)
    description = models.CharField(
        max_length=300, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "funding_type"
        default_permissions = ()


class FundingAgency(models.Model):
    funding_agency_id = UnsignedBigAutoField(primary_key=True)
    organization = models.OneToOneField(
        ExternalOrganization,
        on_delete=models.PROTECT,
        db_column="organization_id",
        related_name="+",
    )
    funding_type = models.ForeignKey(
        FundingType,
        on_delete=models.PROTECT,
        db_column="funding_type_id",
        related_name="+",
    )
    agency_category = models.CharField(
        max_length=100, null=True, blank=True, db_collation="utf8mb4_unicode_ci"
    )
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "funding_agency"
        default_permissions = ()


class ResearchStatus(models.Model):
    research_status_id = UnsignedAutoField(primary_key=True, bits=8)
    status_code = models.CharField(
        max_length=30, unique=True, db_collation="utf8mb4_unicode_ci"
    )
    status_name = models.CharField(
        max_length=100, unique=True, db_collation="utf8mb4_unicode_ci"
    )
    display_order = UnsignedTinyIntegerField(default=0, db_default=0)
    is_terminal = models.BooleanField(default=False, db_default=False)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "research_status"
        default_permissions = ()


class CoCurricularCategory(models.Model):
    cocurricular_category_id = UnsignedAutoField(primary_key=True, bits=16)
    category_code = models.CharField(max_length=50, unique=True, db_collation="utf8mb4_unicode_ci")
    category_name = models.CharField(max_length=150, unique=True, db_collation="utf8mb4_unicode_ci")
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "cocurricular_category"
        default_permissions = ()


class ExtraCurricularCategory(models.Model):
    extracurricular_category_id = UnsignedAutoField(primary_key=True, bits=16)
    category_code = models.CharField(max_length=50, unique=True, db_collation="utf8mb4_unicode_ci")
    category_name = models.CharField(max_length=150, unique=True, db_collation="utf8mb4_unicode_ci")
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "extracurricular_category"
        default_permissions = ()


class AwardCategory(models.Model):
    award_category_id = UnsignedAutoField(primary_key=True, bits=16)
    category_code = models.CharField(max_length=50, unique=True, db_collation="utf8mb4_unicode_ci")
    category_name = models.CharField(max_length=150, unique=True, db_collation="utf8mb4_unicode_ci")
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "award_category"
        default_permissions = ()


class MembershipType(models.Model):
    membership_type_id = UnsignedAutoField(primary_key=True, bits=16)
    type_code = models.CharField(max_length=50, unique=True, db_collation="utf8mb4_unicode_ci")
    type_name = models.CharField(max_length=150, unique=True, db_collation="utf8mb4_unicode_ci")
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "membership_type"
        default_permissions = ()


class ProfessionalContributionType(models.Model):
    professional_contribution_type_id = UnsignedAutoField(bits=16, primary_key=True)
    contribution_code = models.CharField(max_length=60, unique=True, db_collation="utf8mb4_unicode_ci")
    contribution_name = models.CharField(max_length=180, unique=True, db_collation="utf8mb4_unicode_ci")
    description = models.CharField(max_length=500, null=True, blank=True, db_collation="utf8mb4_unicode_ci")
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "professional_contribution_type"
        default_permissions = ()

    def __str__(self):
        return self.contribution_name


class EvidenceType(models.Model):
    evidence_type_id = UnsignedAutoField(bits=16, primary_key=True)
    evidence_type_code = models.CharField(max_length=60, unique=True, db_collation="utf8mb4_unicode_ci")
    evidence_type_name = models.CharField(max_length=180, unique=True, db_collation="utf8mb4_unicode_ci")
    description = models.CharField(max_length=500, null=True, blank=True, db_collation="utf8mb4_unicode_ci")
    is_active = models.BooleanField(default=True, db_default=True)
    class Meta:
        db_table = "evidence_type"
        default_permissions = ()
    def __str__(self):
        return self.evidence_type_name


class ConfidentialityLevel(models.Model):
    confidentiality_level_id = UnsignedAutoField(bits=8, primary_key=True)
    level_code = models.CharField(max_length=30, unique=True, db_collation="utf8mb4_unicode_ci")
    level_name = models.CharField(max_length=80, unique=True, db_collation="utf8mb4_unicode_ci")
    display_order = UnsignedTinyIntegerField(default=0, db_default=0)
    is_active = models.BooleanField(default=True, db_default=True)
    class Meta:
        db_table = "confidentiality_level"
        default_permissions = ()
    def __str__(self):
        return self.level_name
