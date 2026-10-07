"""Run every sample-data seeder in dependency order (development only)."""

from django.core.management import call_command
from django.core.management.base import BaseCommand

STEPS = ("seed_sample_data", "seed_sample_academics", "seed_sample_staff", "seed_sample_services", "seed_sample_users")


class Command(BaseCommand):
    help = "Load all sample data: people, academics, staff activities, services and role-based demo users."

    def handle(self, *args, **opts):
        for step in STEPS:
            self.stdout.write(self.style.MIGRATE_HEADING(step))
            call_command(step, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("All sample data loaded. See Manuals/DEMO_DATA.md for accounts and roles."))
