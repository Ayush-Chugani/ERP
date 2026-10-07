from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import University, Institution, Campus, Department, OrganizationAudit
from .services import save_record
from .selectors import scoped
from apps.tenancy.models import Membership,ScopeGrant,InstitutionModule

class OrganizationServiceTests(TestCase):
    def setUp(self):
        self.root=get_user_model().objects.create_superuser(username='root',password='test')
        self.user=get_user_model().objects.create_user(username='tenant',password='test')
        self.uni=save_record(University,{'university_code':'U','university_name':'University'},actor=self.root)
        self.a=save_record(Institution,{'university':self.uni,'institution_code':'A','institution_name':'Alpha'},actor=self.root)
        self.b=save_record(Institution,{'university':self.uni,'institution_code':'B','institution_name':'Beta'},actor=self.root)
        self.module=InstitutionModule.objects.create(institution=self.a,organization_structure=True)
        self.member=Membership.objects.create(user=self.user,institution=self.a)
        self.grant=ScopeGrant.objects.create(membership=self.member,role='INSTITUTION_ADMIN')

    def test_scope_and_atomic_audit(self):
        self.assertEqual(list(scoped(Institution,self.user)),[self.a])
        with self.assertRaises(NotFound): save_record(Institution,{'institution_name':'Attack'},actor=self.user,pk=self.b.pk)
        with self.assertRaises(PermissionDenied): save_record(Campus,{'institution':self.b,'campus_code':'X','campus_name':'Wrong'},actor=self.user)
        with patch.object(OrganizationAudit,'save',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError): save_record(Campus,{'institution':self.a,'campus_code':'X','campus_name':'Test'},actor=self.user)
        self.assertFalse(Campus.objects.exists())
        self.module.organization_structure=False;self.module.save()
        self.assertFalse(scoped(Institution,self.user).exists())

    def test_parent_history_and_record_limits(self):
        campus=save_record(Campus,{'institution':self.a,'campus_code':'X','campus_name':'Test'},actor=self.user)
        save_record(Institution,{'is_active':False},actor=self.root,pk=self.a.pk)
        with self.assertRaises(ValidationError): save_record(Department,{'campus':campus,'department_code':'D','department_name':'Dept'},actor=self.root)
        save_record(Campus,{'campus_name':'Historical'},actor=self.root,pk=campus.pk)
        self.grant.record_limits={'institutions':[]};self.grant.save()
        self.assertFalse(scoped(Institution,self.user).exists())
