from django.db import models
class ResponseType(models.TextChoices):
    SINGLE_CHOICE='SINGLE_CHOICE';MULTIPLE_CHOICE='MULTIPLE_CHOICE';RATING='RATING';TEXT='TEXT'
class QuestionnaireType(models.TextChoices):
    COURSE='COURSE';FACULTY='FACULTY';PROGRAMME='PROGRAMME';INSTITUTION='INSTITUTION';EXIT='EXIT';OTHER='OTHER'
class QuestionnaireStatus(models.TextChoices):
    DRAFT='DRAFT';ACTIVE='ACTIVE';RETIRED='RETIRED'
class CycleStatus(models.TextChoices):
    SCHEDULED='SCHEDULED';OPEN='OPEN';CLOSED='CLOSED';CANCELLED='CANCELLED'
class Visibility(models.TextChoices):
    HIDDEN='HIDDEN';ADMIN_ONLY='ADMIN_ONLY';FACULTY='FACULTY';PUBLIC='PUBLIC'
