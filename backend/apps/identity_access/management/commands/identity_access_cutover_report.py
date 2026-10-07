from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.tenancy.models import Membership,ScopeGrant
from apps.identity_access.models import UserRoleAssignment

class Command(BaseCommand):
    help='Read-only aggregate cutover inventory. Similar role names are never treated as equivalent grants.'
    def handle(self,*args,**options):
        self.stdout.write(str({'users':get_user_model().objects.count(),'legacy_memberships':Membership.objects.count(),'legacy_scope_grants':ScopeGrant.objects.count(),'m15_assignments':UserRoleAssignment.objects.count(),'cutover_ready':False}))
        self.stdout.write('For each protected endpoint, map its old policy to explicit permission and owner-scope adapters; compare actual decisions before activation. This command does not infer mappings or enable access.')
