from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.identity_access.audit import record
from apps.professional_memberships import services as s
from apps.professional_memberships.models import StaffProfessionalMembership
from apps.professional_memberships.permissions import activity_scope, principal


class Command(BaseCommand):
    help = (
        "Scoped, audited membership expiry; no schedule or notification is installed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--as-of", type=date.fromisoformat)
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, **options):
        if not options["dry_run"] and not settings.MEMBERSHIPS_AUTO_EXPIRY_ENABLED:
            raise CommandError(
                "Applied expiry is disabled; enable its policy or use --dry-run."
            )
        if not 1 <= options["batch_size"] <= 1000:
            raise CommandError("Batch size must be 1-1000.")
        actor = get_user_model().objects.filter(pk=options["actor_id"]).first()
        try:
            principal(actor)
        except APIException as error:
            raise CommandError(
                "The expiry actor is not authorized for this runtime."
            ) from error
        as_of = options["as_of"] or timezone.localdate()
        rows = StaffProfessionalMembership.objects.filter(
            activity_scope(actor, "VERIFY"),
            staff_activity__deleted_at__isnull=True,
            membership_status="ACTIVE",
            is_lifetime_membership=False,
            membership_expiry_date__lt=as_of,
        ).filter(activity_scope(actor, "READ"))
        due = (
            StaffProfessionalMembership.objects.filter(
                activity_scope(actor, "VERIFY"),
                staff_activity__deleted_at__isnull=True,
                membership_status="ACTIVE",
                is_lifetime_membership=False,
                renewal_required=True,
                membership_expiry_date__gte=as_of,
                membership_expiry_date__lte=as_of
                + timedelta(days=max(0, settings.MEMBERSHIPS_RENEWAL_WINDOW_DAYS)),
            )
            .filter(activity_scope(actor, "READ"))
            .count()
        )
        last = 0
        changed = 0
        errors = 0
        while True:
            ids = list(
                rows.filter(pk__gt=last)
                .order_by("pk")
                .values_list("pk", flat=True)[: options["batch_size"]]
            )
            if not ids:
                break
            for pk in ids:
                try:
                    changed += int(s.expire_one(actor, pk, as_of, options["dry_run"]))
                except (APIException, ValidationError):
                    errors += 1
            last = ids[-1]
        record(
            actor=actor,
            module=s.MODULE,
            action="READ" if options["dry_run"] else "UPDATE",
            details={
                "source": "expiry_batch",
                "as_of": str(as_of),
                "dry_run": options["dry_run"],
                "eligible_or_changed": changed,
                "renewal_due": due,
                "errors": errors,
            },
        )
        self.stdout.write(
            f"dry_run={options['dry_run']} eligible_or_changed={changed} renewal_due={due} errors={errors}"
        )
        if errors:
            raise CommandError(
                "Some rows failed authorization or validation; review audit and retry safely."
            )
