from django.apps import AppConfig


class AcademicCalendarConfig(AppConfig):
    name = 'apps.academic_calendar'
    verbose_name = 'Academic Calendar'
    # Activation is evaluated by policies at runtime; no queries or signals here.
