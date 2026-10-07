from django.db import models


class StudentStatus(models.TextChoices):
    APPLICANT = "APPLICANT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    WITHDRAWN = "WITHDRAWN"
    COMPLETED = "COMPLETED"
    ALUMNUS = "ALUMNUS"
    DECEASED = "DECEASED"


class EmploymentStatus(models.TextChoices):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    SUSPENDED = "SUSPENDED"
    RESIGNED = "RESIGNED"
    RETIRED = "RETIRED"
    TERMINATED = "TERMINATED"
