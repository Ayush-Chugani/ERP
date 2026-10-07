from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.db import transaction


class Command(BaseCommand):
    help='Create M6 permission bundles without assigning users or institution scopes.'

    def handle(self,*args,**options):
        bundles={
            'Admissions reviewer':['view_admissionapplicant','view_admissionapplication','review_admission'],
            'Admissions registrar':['view_admissionapplicant','add_admissionapplicant','change_admissionapplicant','view_admissionapplication','add_admissionapplication','change_admissionapplication','view_studentprogrammeenrolment','view_enrolmentstatushistory','review_admission','select_admission','admit_admission','reopen_admission','lifecycle_admission'],
            'Admissions fee clearance':['view_admissionapplication','record_fee_clearance'],
        }
        with transaction.atomic():
            for name,codes in bundles.items():
                group,created=Group.objects.get_or_create(name=name)
                if created:
                    group.permissions.add(*Permission.objects.filter(content_type__app_label='admission_enrolment',codename__in=codes))
                self.stdout.write(f'{name}: {"created" if created else "preserved"}')
        self.stdout.write('No users, institution module flags, sensitive-data grants or People permissions were changed.')
