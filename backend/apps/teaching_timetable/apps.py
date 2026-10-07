from django.apps import AppConfig


class TeachingTimetableConfig(AppConfig):
    name = 'apps.teaching_timetable'
    verbose_name = 'Teaching allocation and timetable'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import checks  # noqa: F401
