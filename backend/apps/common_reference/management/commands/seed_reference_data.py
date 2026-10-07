from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from rest_framework.exceptions import APIException
from apps.common_reference.resources import RESOURCES
from apps.common_reference.seed_data import BASELINE, DEMONSTRATION, KARNATAKA
from apps.common_reference.serializers import SERIALIZERS
from apps.common_reference.services import write_reference


class Command(BaseCommand):
    help = 'Seed minimal references using an explicitly authorized actor; preserve existing values by default.'

    def add_arguments(self, parser):
        parser.add_argument('--actor', required=True, help='Existing active platform maintainer username')
        parser.add_argument('--update', action='store_true', help='Update existing non-key baseline fields; never reactivate')
        parser.add_argument('--karnataka', action='store_true', help='Add Karnataka state, religion and education category labels; no caste eligibility mappings or postal directory')
        parser.add_argument('--demo', action='store_true', help='Also load explicitly synthetic demonstration data')

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(username=options['actor'], is_active=True)
        except get_user_model().DoesNotExist:
            raise CommandError('Actor must be an existing active user.')
        if not actor.has_perm('common_reference.maintain_reference'):
            raise CommandError('Actor requires global maintenance permission.')
        registry = {row[1]: row for row in RESOURCES}
        counts = {'created': 0, 'updated': 0, 'unchanged': 0}
        try:
            with transaction.atomic():
                ContentType.objects.select_for_update().get(app_label='common_reference', model='country')
                for path, natural, defaults in BASELINE + (KARNATAKA if options['karnataka'] else ()) + (DEMONSTRATION if options['demo'] else ()):
                    model, _, _, parent, _ = registry[path]
                    key = dict(natural)
                    if parent:
                        field = model._meta.get_field(parent)
                        try:
                            key[parent + '_id'] = field.related_model.objects.get(**key[parent + '_id']).pk
                        except field.related_model.DoesNotExist:
                            raise CommandError(f'Missing seed parent for {path}.')
                    obj = model.objects.filter(**key).first()
                    operation = 'change' if obj else 'add'
                    if not actor.has_perm(f'common_reference.{operation}_{model._meta.model_name}'):
                        raise CommandError(f'Actor lacks {operation} permission for {path}.')
                    if obj and not options['update']:
                        counts['unchanged'] += 1
                        continue
                    payload = {**key, **defaults} if obj is None else dict(defaults)
                    serializer = SERIALIZERS[model](obj, data=payload, partial=obj is not None)
                    serializer.is_valid(raise_exception=True)
                    before = {name: getattr(obj, name) for name in payload} if obj else None
                    saved = write_reference(model, dict(serializer.validated_data), obj.pk if obj else None,
                                            actor=actor, source='seed')
                    if obj is None:
                        counts['created'] += 1
                    elif before != {name: getattr(saved, name) for name in payload}:
                        counts['updated'] += 1
                    else:
                        counts['unchanged'] += 1
        except APIException as exc:
            raise CommandError(str(exc.detail)) from exc
        self.stdout.write(self.style.SUCCESS(', '.join(f'{key}={value}' for key, value in counts.items())))
