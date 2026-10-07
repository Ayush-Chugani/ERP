from django.core.management.base import BaseCommand
from apps.identity_access.seeding import seed

class Command(BaseCommand):
    help = 'Install the exact M15 reference catalogue without assigning users or replacing existing edits.'
    def handle(self, *args, **options):
        self.stdout.write(str(seed()))
