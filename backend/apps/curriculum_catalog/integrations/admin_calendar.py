"""Declared admin-only adapter for Django relation widgets, not a public read API."""

from apps.academic_calendar.models import Semester
from apps.academic_calendar.policies import scoped


def semester_queryset(actor):
    return scoped(Semester, actor)
