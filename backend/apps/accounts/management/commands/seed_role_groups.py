from django.contrib.auth.models import Group, Permission
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = "Create global starter groups; grants reference read permissions, no institution scope."
    @transaction.atomic
    def handle(self, *args, **options):
        for name in ("Admin", "Teacher", "Student"):
            group, _ = Group.objects.get_or_create(name=name)
            for model in apps.get_app_config("common_reference").get_models():
                group.permissions.add(Permission.objects.get(content_type__app_label="common_reference", codename="view_" + model._meta.model_name))
        self.stdout.write("Global starter groups ready; reference reads granted; existing permissions and memberships preserved.")
