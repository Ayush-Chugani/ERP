from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create additive M8 permission bundles; membership and scope grants remain explicit.'

    def handle(self, *args, **options):
        bundles = {
            'Timetable Planner': ['manage_timetable', 'view_schedule', 'export_timetable'],
            'Timetable Approver': ['manage_timetable', 'approve_timetable', 'view_schedule'],
            'Timetable Publisher': ['manage_timetable', 'publish_timetable', 'change_occurrence', 'view_schedule', 'export_timetable'],
            'Timetable Reader': ['view_schedule'],
        }
        for name, codes in bundles.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.add(*Permission.objects.filter(content_type__app_label='teaching_timetable', codename__in=codes))
        self.stdout.write('M8 groups updated; no user memberships or institution flags changed.')
