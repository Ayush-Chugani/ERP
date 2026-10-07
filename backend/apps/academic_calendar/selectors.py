"""Read selectors require both an actor and an explicitly validated institution."""
from datetime import date
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from .models import AcademicYear, AcademicTerm, Semester, TimeSlot
from .policies import enabled, grants, scoped


def context(actor, institution_id):
    if type(institution_id) is not int or institution_id < 1 or not enabled(actor):
        raise PermissionDenied('A trusted institution context is required.')
    if actor.is_superuser:
        from apps.organization.models import Institution
        if not Institution.objects.filter(pk=institution_id, is_active=True).exists():
            raise PermissionDenied()
    elif not grants(actor, institution_id).exists():
        raise PermissionDenied()


def current_year(*, actor, institution_id):
    context(actor, institution_id)
    return scoped(AcademicYear, actor, institution_id=institution_id).filter(status='ACTIVE').first()


def active_terms(*, actor, institution_id):
    context(actor, institution_id)
    return scoped(AcademicTerm, actor, institution_id=institution_id).filter(status='ACTIVE', academic_year__status='ACTIVE').select_related('academic_year')


def registration_terms(*, actor, institution_id, on_date: date):
    context(actor, institution_id)
    return scoped(AcademicTerm, actor, institution_id=institution_id).filter(status='REGISTRATION_OPEN', academic_year__status='ACTIVE',
        academic_year__start_date__lte=on_date, academic_year__end_date__gte=on_date).filter(
        Q(registration_start_date__isnull=True) | Q(registration_start_date__lte=on_date)).filter(
        Q(registration_end_date__isnull=True) | Q(registration_end_date__gte=on_date)).select_related('academic_year')


def term_by_code(*, actor, institution_id, year_code, term_code):
    context(actor, institution_id)
    return scoped(AcademicTerm, actor, institution_id=institution_id).filter(academic_year__year_code=year_code, term_code=term_code).select_related('academic_year').first()


def semesters(*, actor, institution_id):
    context(actor, institution_id)
    return scoped(Semester, actor, institution_id=institution_id)


def campus_slots(*, actor, institution_id, campus_id):
    context(actor, institution_id)
    return scoped(TimeSlot, actor, institution_id=institution_id).filter(campus_id=campus_id, is_active=True, campus__is_active=True)
