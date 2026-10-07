from django.db import models


class YearStatus(models.TextChoices):
    PLANNED = 'PLANNED'
    ACTIVE = 'ACTIVE'
    CLOSED = 'CLOSED'


class TermStatus(models.TextChoices):
    PLANNED = 'PLANNED'
    REGISTRATION_OPEN = 'REGISTRATION_OPEN'
    ACTIVE = 'ACTIVE'
    CLOSED = 'CLOSED'


class TermType(models.TextChoices):
    ODD = 'ODD'
    EVEN = 'EVEN'
    SUMMER = 'SUMMER'
    ANNUAL = 'ANNUAL'
    OTHER = 'OTHER'
