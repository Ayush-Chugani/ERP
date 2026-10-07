from django.db.models import Q
from . import models as m
from .policies import scoped, allowed
from rest_framework.exceptions import PermissionDenied


def duplicate_candidates(*,actor,applicant_id):
    if not allowed(actor,'sensitive'):
        raise PermissionDenied()
    base=scoped(m.AdmissionApplicant,actor)
    applicant=base.get(pk=applicant_id)
    match=Q(pk__in=[])
    for field in ('primary_email','primary_phone'):
        value=getattr(applicant,field)
        if value:
            match |= Q(**{field:value})
    if applicant.date_of_birth:
        match |= Q(display_name=applicant.display_name,date_of_birth=applicant.date_of_birth)
    return base.filter(institution=applicant.institution).filter(match).exclude(pk=applicant.pk).order_by('pk')[:20]


def enrolment_history(*,actor,enrolment_id,as_of=None):
    rows=scoped(m.EnrolmentStatusHistory,actor).filter(enrolment_id=enrolment_id)
    if as_of:
        rows=rows.filter(effective_date__lte=as_of)
    return rows.order_by('effective_date','sequence_number')
