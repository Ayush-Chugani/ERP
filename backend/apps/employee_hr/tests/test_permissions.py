from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from apps.people_master.tests.test_services import fixture
from apps.people_master.models import Employee, EmployeeAssignment, AccountLink
from apps.organization.models import Institution, Campus, Department
from apps.identity_access import models as iam
from apps.employee_hr.permissions import require_employee_permission


@override_settings(EMPLOYEE_HR_ENABLED=True, IDENTITY_ACCESS_ENABLED=True,
                   IDENTITY_ACCESS_SECURITY_ENABLED=True)
class EmployeeScopeTests(TestCase):
    def setUp(self):
        fixture(self)
        self.actor = get_user_model().objects.create_user(username='synthetic-hr-reader')
        self.employee = Employee.objects.create(
            institution=self.institution, employment_source=self.source,
            employee_number='SYNTHETIC-HR-SCOPE', first_name='Synthetic',
            display_name='Synthetic', joining_date=date(2020, 1, 1), employment_type='REGULAR')
        self.today = timezone.localdate()
        self.assignment = EmployeeAssignment.objects.create(
            employee=self.employee, campus=self.campus, department=self.department,
            designation=self.designation, start_date=self.today)
        module = iam.AccessModule.objects.create(module_code='HRPROBE', module_name='Synthetic probe')
        resource = iam.AccessResource.objects.create(
            access_module=module, resource_code='ROW', resource_name='Synthetic row')
        action = iam.AccessAction.objects.get(action_code='READ')
        self.permission = iam.Permission.objects.create(
            access_resource=resource, access_action=action,
            permission_code='HRPROBE.ROW.READ', permission_name='Synthetic read')
        self.role = iam.Role.objects.create(role_code='HRPROBE', role_name='Synthetic',
                                           role_category='SYSTEM', role_level='INSTITUTION')
        iam.RolePermission.objects.create(role=self.role, permission=self.permission)

    def grant(self, kind, entity=None):
        scope_fields = {kind.lower() + '_id': entity} if kind not in ('GLOBAL', 'SELF') else {}
        return iam.UserRoleAssignment.objects.create(
            user=self.actor, role=self.role, scope_type=kind,
            valid_from=timezone.now() - timedelta(days=1), **scope_fields)

    def check(self, actor=None, employee_id=None):
        return require_employee_permission(actor or self.actor, 'HRPROBE.ROW.READ',
                                           employee_id=employee_id or self.employee.pk)

    def test_department_grant_requires_current_assignment(self):
        self.grant('DEPARTMENT', self.department.pk)
        self.assertEqual(self.check().pk, self.employee.pk)
        self.assignment.start_date = self.today + timedelta(days=1)
        self.assignment.save()
        with self.assertRaises(PermissionDenied):
            self.check()
        self.assignment.start_date = self.today - timedelta(days=2)
        self.assignment.end_date = self.today - timedelta(days=1)
        self.assignment.save()
        with self.assertRaises(PermissionDenied):
            self.check()
        self.assignment.end_date = self.today
        self.assignment.save()
        self.assertEqual(self.check().pk, self.employee.pk)

    def test_self_requires_explicit_login_link(self):
        self.grant('SELF')
        with self.assertRaises(PermissionDenied):
            self.check()
        AccountLink.objects.create(user=self.actor, employee=self.employee)
        self.assertEqual(self.check().pk, self.employee.pk)
        other = Employee.objects.create(
            institution=self.institution, employment_source=self.source,
            employee_number='SYNTHETIC-HR-OTHER', first_name='Other', display_name='Other',
            joining_date=date(2020, 1, 1), employment_type='REGULAR')
        with self.assertRaises(PermissionDenied):
            self.check(employee_id=other.pk)

    def test_institution_deny_overrides_department_grant(self):
        self.grant('DEPARTMENT', self.department.pk)
        iam.UserPermissionOverride.objects.create(
            user=self.actor, permission=self.permission, permission_effect='DENY',
            scope_type='INSTITUTION', scope_entity_id=self.institution.pk,
            valid_from=timezone.now() - timedelta(days=1), justification='Synthetic denial')
        with self.assertRaises(PermissionDenied):
            self.check()

    def test_cross_institution_assignment_fails_closed(self):
        self.grant('INSTITUTION', self.institution.pk)
        other = Institution.objects.create(university=self.institution.university,
                                           institution_code='SYNTHETIC-OTHER', institution_name='Other')
        campus = Campus.objects.create(institution=other, campus_code='OTHER', campus_name='Other')
        # QuerySet update deliberately bypasses service validation to model damaged legacy data.
        EmployeeAssignment.objects.filter(pk=self.assignment.pk).update(campus=campus, department=None)
        with self.assertRaises(PermissionDenied):
            self.check()

    def test_unrelated_department_grant_cannot_gain_ancestry(self):
        campus = Campus.objects.create(institution=self.institution, campus_code='OTHER', campus_name='Other')
        department = Department.objects.create(campus=campus, department_code='OTHER', department_name='Other')
        self.grant('DEPARTMENT', department.pk)
        with self.assertRaises(PermissionDenied):
            self.check()
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeAssignment.objects.filter(pk=self.assignment.pk).update(department=department)

    def test_stale_actor_reset_and_disable_are_denied(self):
        self.grant('INSTITUTION', self.institution.pk)
        self.assertEqual(self.check().pk, self.employee.pk)
        get_user_model().objects.filter(pk=self.actor.pk).update(must_change_password=True)
        with self.assertRaises(PermissionDenied):
            self.check()
        get_user_model().objects.filter(pk=self.actor.pk).update(must_change_password=False, account_status='DISABLED')
        with self.assertRaises(PermissionDenied):
            self.check()

    def test_missing_employee_and_superuser_without_grants_are_denied(self):
        with self.assertRaises(PermissionDenied):
            self.check(employee_id=999999999)
        with self.assertRaises(PermissionDenied):
            self.check(actor=self.root)
