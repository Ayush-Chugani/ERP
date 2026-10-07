from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import connection, transaction, IntegrityError
from django.test import TestCase
from django.utils import timezone
from apps.identity_access import models as m
from apps.identity_access.evaluator import Scope, has_permission, has_object_permission


class FoundationTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.user = get_user_model().objects.create_user(username='m15-principal', password='test-secret')
        self.module = m.AccessModule.objects.create(module_code='PROBE', module_name='Probe')
        resource = m.AccessResource.objects.create(access_module=self.module, resource_code='ALL', resource_name='All')
        action = m.AccessAction.objects.create(pk=254,action_code='PROBE', action_name='Probe')
        self.permission = m.Permission.objects.create(access_resource=resource, access_action=action,
            permission_code='PROBE.ALL.PROBE', permission_name='Probe')
        self.role = m.Role.objects.create(role_code='PROBE', role_name='Probe', role_category='SYSTEM', role_level='SELF')
        m.RolePermission.objects.create(role=self.role, permission=self.permission)
        self.assignment = m.UserRoleAssignment.objects.create(user=self.user, role=self.role,
            scope_type='SELF', valid_from=self.now-timedelta(days=1))

    def allowed(self, user=None):
        user = user or self.user
        return has_permission(user, 'PROBE.ALL.PROBE', 'SELF', user.pk, at=self.now)

    def test_self_override_deny_matches_role_in_orm_and_sql(self):
        self.assertTrue(self.allowed())
        m.UserPermissionOverride.objects.create(user=self.user, permission=self.permission,
            permission_effect='DENY', scope_type='SELF', valid_from=self.now-timedelta(hours=1), justification='Test denial')
        self.assertFalse(self.allowed())
        with connection.cursor() as cursor:
            cursor.execute('SELECT scope_entity_id, permission_effect FROM v_effective_user_permission WHERE user_id=%s AND permission_id=%s', [self.user.pk,self.permission.pk])
            self.assertEqual(cursor.fetchall(), ((self.user.pk, 'DENY'),))

    def test_ancestor_deny_does_not_change_exact_scope(self):
        m.UserPermissionOverride.objects.create(user=self.user, permission=self.permission,
            permission_effect='DENY', scope_type='GLOBAL', valid_from=self.now-timedelta(hours=1), justification='Test denial')
        self.assertTrue(self.allowed())
        self.assertFalse(has_object_permission(self.user,'PROBE.ALL.PROBE',scopes=[Scope('GLOBAL',0),Scope('SELF',self.user.pk)],at=self.now))

    def test_delegated_self_and_source_revocation(self):
        delegate = get_user_model().objects.create_user(username='m15-delegate')
        m.RoleDelegation.objects.create(delegator_user=self.user,delegate_user=delegate,
            source_assignment=self.assignment,valid_from=self.now-timedelta(hours=1),
            valid_to=self.now+timedelta(hours=1),delegation_status='ACTIVE',reason='Test')
        self.assertTrue(self.allowed(delegate))
        self.assignment.assignment_status='REVOKED'; self.assignment.save()
        self.assertFalse(self.allowed(delegate))

    def test_inactive_catalogue_and_stale_account_fail_closed(self):
        self.module.is_active=False; self.module.save()
        self.assertFalse(self.allowed())
        self.module.is_active=True; self.module.save()
        get_user_model().objects.filter(pk=self.user.pk).update(account_status='DISABLED')
        self.assertFalse(self.allowed())

    def test_invalid_scope_and_dates_rejected_by_database(self):
        for fields in [dict(scope_type='CAMPUS'), dict(scope_type='SELF',valid_to=self.assignment.valid_from)]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                m.UserRoleAssignment.objects.create(user=self.user,role=self.role,valid_from=self.assignment.valid_from,**fields)

    def test_exact_scope_uniqueness(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.UserRoleAssignment.objects.create(user=self.user,role=self.role,scope_type='SELF',valid_from=self.assignment.valid_from)

    def test_exclusive_end_and_no_superuser_bypass(self):
        self.assignment.valid_to=self.now; self.assignment.save()
        self.user.is_superuser=True; self.user.save()
        self.assertFalse(self.allowed())

    def test_existing_password_storage_and_identity_preserved(self):
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('test-secret'))
        self.assertEqual(self.user.account_status,'ACTIVE')
        self.assertFalse(self.user.must_change_password)

    def test_audit_is_append_only(self):
        from django.core.exceptions import ValidationError
        row=m.ActivityAudit.objects.create(user=self.user,module_code='IAM',action_code='READ')
        with self.assertRaises(ValidationError): row.delete()
        with self.assertRaises(ValidationError): m.ActivityAudit.objects.filter(pk=row.pk).update(details={})

    def test_delegation_cannot_escape_source_principal_denial(self):
        delegate=get_user_model().objects.create_user(username='source-denied-delegate')
        m.RoleDelegation.objects.create(delegator_user=self.user,delegate_user=delegate,
            source_assignment=self.assignment,valid_from=self.now-timedelta(hours=1),
            valid_to=self.now+timedelta(hours=1),delegation_status='ACTIVE',reason='Test')
        m.UserPermissionOverride.objects.create(user=self.user,permission=self.permission,
            permission_effect='DENY',scope_type='SELF',valid_from=self.now-timedelta(hours=1),justification='Source access restricted')
        self.assertFalse(self.allowed(delegate))
