from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.communication.models import AnnouncementType
from apps.communication.services import write_type


class Command(BaseCommand):
    help = (
        "Idempotently seed one explicitly selected type through the authorized service."
    )

    def add_arguments(self, parser):
        parser.add_argument("--actor", type=int, required=True)
        parser.add_argument("--code", required=True)
        parser.add_argument("--name", required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.get(pk=options["actor"])
        row = AnnouncementType.objects.filter(
            type_code=options["code"].strip().upper()
        ).first()
        write_type(
            actor=actor,
            pk=row.pk if row else None,
            type_code=options["code"],
            type_name=options["name"],
        )
        self.stdout.write("Selected announcement type reconciled.")
