from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, connection
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Country, State, Caste, SocialCategory, SubCaste
from .resources import RESOURCES


class ReferenceAPITests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'mysql')
        self.user = get_user_model().objects.create_superuser(username='maintainer', password='test')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.country = Country.objects.create(iso_code='IN', country_name='India')
        self.category = SocialCategory.objects.create(category_code='A', category_name='Alpha')
        self.caste = Caste.objects.create(caste_name='Parent', social_category=self.category)

    def url(self, path, pk=None):
        return '/api/v1/reference/' + path + '/' + (str(pk) + '/' if pk else '')

    def test_all_resources_lifecycle_and_contract(self):
        for model, path, writable, parent, label in RESOURCES:
            with self.subTest(path=path):
                payload = {}
                for name in writable:
                    if name == 'is_active' or name == 'requires_verification':
                        payload[name] = True
                    elif name.endswith('_id'):
                        payload[name] = {'country': self.country, 'social_category': self.category, 'caste': self.caste}[parent].pk
                    else:
                        payload[name] = 'ZZ' if name == 'iso_code' else ('AB+' if name == 'blood_group_code' else 'Example')
                response = self.client.post(self.url(path), payload, format='json')
                self.assertEqual(response.status_code, 201, response.data)
                pk = response.data[model._meta.pk.name]
                self.assertTrue(response.data['effective_active'])
                if parent:
                    self.assertIn(parent + '_label', response.data)
                    self.assertTrue(response.data[parent + '_is_active'])
                detail = self.url(path, pk)
                self.assertEqual(self.client.get(detail).status_code, 200)
                self.assertEqual(self.client.put(detail, payload, format='json').status_code, 200)
                for active in (False, True):
                    response = self.client.patch(detail, {'is_active': active}, format='json')
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data['is_active'], active)
                self.assertEqual(self.client.delete(detail).status_code, 405)
                self.assertEqual(self.client.options(self.url(path)).status_code, 200)
                response = self.client.get(self.url(path), {'search': 'Example', 'page_size': 1})
                self.assertEqual(response.status_code, 200)
                self.assertIn('count', response.data)
                self.assertLessEqual(len(response.data['results']), 1)

    def test_permission_combinations_for_every_resource(self):
        reader = get_user_model().objects.create_user(username='reader', is_staff=True)
        for model, path, writable, parent, label in RESOURCES:
            obj = model.objects.first()
            # Create an instance using the lifecycle test's independent contract is unnecessary:
            # mutation authorization happens before payload validation and object lookup.
            perms = Permission.objects.filter(content_type__app_label='common_reference', codename__in=[
                'view_' + model._meta.model_name, 'add_' + model._meta.model_name, 'change_' + model._meta.model_name])
            reader.user_permissions.set(perms)
            self.client.force_authenticate(get_user_model().objects.get(pk=reader.pk))
            self.assertEqual(self.client.get(self.url(path)).status_code, 200)
            self.assertEqual(self.client.post(self.url(path), {}, format='json').status_code, 403)
            self.assertEqual(self.client.patch(self.url(path, 1), {}, format='json').status_code, 403)
            reader.user_permissions.set(Permission.objects.filter(codename='maintain_reference'))
            self.client.force_authenticate(get_user_model().objects.get(pk=reader.pk))
            self.assertEqual(self.client.get(self.url(path)).status_code, 403)
            self.assertEqual(self.client.post(self.url(path), {}, format='json').status_code, 403)
            self.client.force_authenticate(None)
            self.assertEqual(self.client.get(self.url(path)).status_code, 401)

    def test_historical_parents_dropdown_and_new_assignment(self):
        state = State.objects.create(country=self.country, state_code='MH', state_name='Maharashtra')
        self.client.patch(self.url('countries', self.country.pk), {'is_active': False}, format='json')
        state.refresh_from_db()
        self.assertTrue(state.is_active)
        self.assertEqual(self.client.get(self.url('states')).data['count'], 0)
        detail = self.client.get(self.url('states', state.pk)).data
        self.assertFalse(detail['effective_active'])
        self.assertEqual(detail['country_label'], 'India')
        self.assertEqual(self.client.patch(self.url('states', state.pk), {'country_id': self.country.pk, 'state_name': 'Updated'}, format='json').status_code, 200)
        response = self.client.post(self.url('states'), {'country_id': self.country.pk, 'state_code': 'NEW', 'state_name': 'New'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(self.url('states'), {'is_active': 'all'}).data['count'], 1)
        self.assertEqual(self.client.get(self.url('states'), {'is_active': 'false'}).data['count'], 0)
        child = SubCaste.objects.create(caste=self.caste, sub_caste_name='Child')
        self.client.patch(self.url('social-categories', self.category.pk), {'is_active': False}, format='json')
        self.assertEqual(self.client.get(self.url('sub-castes')).data['count'], 0)
        self.assertFalse(self.client.get(self.url('sub-castes', child.pk)).data['effective_active'])
        reader = get_user_model().objects.create_user(username='history')
        reader.user_permissions.add(Permission.objects.get(codename='view_state'))
        self.client.force_authenticate(reader)
        self.assertEqual(self.client.get(self.url('states', state.pk)).status_code, 200)
        self.assertEqual(self.client.get(self.url('states'), {'is_active': 'all'}).status_code, 403)

    def test_filters_and_malformed_input(self):
        Caste.objects.create(caste_name='Uncategorized')
        for params, count in [({'uncategorized': 'true'}, 1), ({'uncategorized': 'false'}, 1), ({'social_category_id': self.category.pk}, 1)]:
            self.assertEqual(self.client.get(self.url('castes'), params).data['count'], count)
        for params in [{'ordering': '--caste_name'}, {'ordering': 'password'}, {'page_size': 'bad'}, {'page': '0'}, {'social_category_id': '9' * 5000}, {'uncategorized': 'true', 'social_category_id': 1}, {'is_active': 'yes'}, {'unknown': 'x'}]:
            response = self.client.get(self.url('castes'), params)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.client.get(self.url('castes') + '?search=a&search=b').status_code, 400)
        for value in ['false', 0, None]:
            self.assertEqual(self.client.patch(self.url('countries', self.country.pk), {'is_active': value}, format='json').status_code, 400)
        for value in [True, 1.5, '1', 65536]:
            self.assertEqual(self.client.post(self.url('states'), {'country_id': value, 'state_code': 'X', 'state_name': 'X'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url('countries', self.country.pk), {'country_id': 20}, format='json').status_code, 400)

    def test_collation_duplicates_and_optional_codes(self):
        for name, status in [('Café', 201), ('CAFE', 409)]:
            response = self.client.post(self.url('castes'), {'caste_name': name}, format='json')
            self.assertEqual(response.status_code, status, response.data)
            if status == 409:
                self.assertEqual(response.data['error']['code'], 'duplicate_reference')
        for name in ['One', 'Two']:
            response = self.client.post(self.url('religions'), {'religion_name': name, 'religion_code': '  '}, format='json')
            self.assertEqual(response.status_code, 201)
            self.assertIsNone(response.data['religion_code'])
        response = self.client.post(self.url('countries'), {'iso_code': ' us ', 'country_name': ' United   States '}, format='json')
        self.assertEqual(response.data['iso_code'], 'US')
        self.assertEqual(response.data['country_name'], 'United States')

    def test_expected_database_errors_roll_back_and_are_sanitized(self):
        for failure, code in [(IntegrityError(1062, 'secret SQL'), 'duplicate_reference'), (IntegrityError(1452, 'secret SQL'), 'protected_reference'), (ProtectedError('secret SQL', []), 'protected_reference')]:
            original = Country.save
            def fail_after_write(obj, *args, **kwargs):
                original(obj, *args, **kwargs)
                raise failure
            with patch.object(Country, 'save', fail_after_write):
                response = self.client.patch(self.url('countries', self.country.pk), {'country_name': 'Changed'}, format='json')
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data['error']['code'], code)
            self.assertNotIn('secret SQL', str(response.data))
            self.country.refresh_from_db()
            self.assertEqual(self.country.country_name, 'India')



    def test_explicit_maintainer_grants_and_revocation(self):
        user = get_user_model().objects.create_user(username='scoped-maintainer')
        user.user_permissions.set(Permission.objects.filter(content_type__app_label='common_reference', codename__in=['maintain_reference', 'add_country', 'change_country', 'view_country']))
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post(self.url('countries'), {'iso_code': 'US', 'country_name': 'United States'}, format='json').status_code, 201)
        self.assertEqual(self.client.patch(self.url('countries', self.country.pk), {'is_active': False}, format='json').status_code, 200)
        self.assertEqual(self.client.get(self.url('countries'), {'is_active': 'false'}).data['count'], 1)
        user.user_permissions.clear()
        self.client.force_authenticate(get_user_model().objects.get(pk=user.pk))
        self.assertEqual(self.client.get(self.url('countries', self.country.pk)).status_code, 403)

    def test_scoped_duplicates_and_parent_filters(self):
        state = State.objects.create(country=self.country, state_code='MH', state_name='Maharashtra')
        response = self.client.post(self.url('states'), {'country_id': self.country.pk, 'state_code': 'XX', 'state_name': 'MAHARASHTRA'}, format='json')
        self.assertEqual(response.status_code, 409, response.data)
        response = self.client.post(self.url('castes'), {'social_category_id': self.category.pk, 'caste_name': 'PARENT'}, format='json')
        self.assertEqual(response.status_code, 409, response.data)
        child = SubCaste.objects.create(caste=self.caste, sub_caste_name='Child')
        for path, params in [('states', {'country_id': self.country.pk}), ('sub-castes', {'caste_id': self.caste.pk})]:
            self.assertEqual(self.client.get(self.url(path), params).data['count'], 1)
        # The selector joins the full ancestor chain; serializing additional rows
        # must not issue a per-row parent query.
        from django.test.utils import CaptureQueriesContext
        from .selectors import related
        from .serializers import SERIALIZERS
        SubCaste.objects.create(caste=self.caste, sub_caste_name='Second')
        with CaptureQueriesContext(connection) as captured:
            data = SERIALIZERS[SubCaste](related(SubCaste.objects.all()), many=True).data
        self.assertEqual(len(data), 2)
        self.assertEqual(len(captured), 1)
