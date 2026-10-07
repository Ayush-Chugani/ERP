from io import StringIO
from unittest.mock import patch
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from apps.core.models import ReferenceAuditEvent
from .models import Country, State, BloodGroup, DocumentType, Caste, Religion, SocialCategory, AdmissionCategory
from .resources import RESOURCES
from .services import write_reference


class AdministrationSeedAuditTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(username='platform', password='test')
        self.client.force_login(self.actor)

    def seed(self, **kwargs):
        output = StringIO()
        call_command('seed_reference_data', actor=self.actor.username, stdout=output, **kwargs)
        return output.getvalue()

    def test_karnataka_labels_are_opt_in_idempotent_and_preserve_edits(self):
        self.seed()
        self.assertFalse(Religion.objects.exists())
        self.assertIn('created=26', self.seed(karnataka=True))
        self.assertEqual(State.objects.get(state_code='KA').country.iso_code, 'IN')
        self.assertEqual(Religion.objects.count(), 7)
        self.assertEqual(SocialCategory.objects.count(), 7)
        self.assertEqual(AdmissionCategory.objects.count(), 11)
        self.assertFalse(SocialCategory.objects.filter(category_code='KA_GM').exists())
        self.assertFalse(Caste.objects.exists())
        label = AdmissionCategory.objects.get(category_code='KA_SCA')
        label.category_name = 'Administrator category label'
        label.is_active = False
        label.save()
        count = ReferenceAuditEvent.objects.count()
        self.assertIn('unchanged=36', self.seed(karnataka=True))
        label.refresh_from_db()
        self.assertEqual(label.category_name, 'Administrator category label')
        self.assertFalse(label.is_active)
        self.assertEqual(ReferenceAuditEvent.objects.count(), count)

    def test_seed_idempotency_preservation_update_and_demo(self):
        self.assertIn('created=10', self.seed())
        self.assertEqual(ReferenceAuditEvent.objects.count(), 10)
        self.assertEqual(BloodGroup.objects.count(), 8)
        self.assertEqual(DocumentType.objects.count(), 0)
        self.assertEqual(Caste.objects.count(), 0)
        original_ids = list(Country.objects.values_list('pk', flat=True))
        self.assertIn('unchanged=10', self.seed())
        self.assertEqual(ReferenceAuditEvent.objects.count(), 10)
        country = Country.objects.get(iso_code='IN')
        write_reference(Country, {'country_name': 'Administrator label', 'is_active': False}, country.pk, actor=self.actor)
        self.seed()
        country.refresh_from_db()
        self.assertEqual(country.country_name, 'Administrator label')
        self.assertFalse(country.is_active)
        self.seed(update=True)
        country.refresh_from_db()
        self.assertEqual(country.country_name, 'India')
        self.assertFalse(country.is_active)
        self.assertEqual(list(Country.objects.values_list('pk', flat=True)), original_ids)
        self.seed(demo=True)
        self.assertEqual(DocumentType.objects.get().document_code, 'DEMO_DOCUMENT')
        self.assertEqual(ReferenceAuditEvent.objects.filter(source='seed', action='update').count(), 1)

    def test_seed_uses_parent_natural_keys_and_rolls_back_invalid_parent(self):
        Country.objects.create(country_id=42, iso_code='IN', country_name='India')
        self.seed()
        self.assertEqual(State.objects.get(state_code='MH').country_id, 42)
        State.objects.all().delete()
        country = Country.objects.get(pk=42)
        country.is_active = False
        country.save()
        count = ReferenceAuditEvent.objects.count()
        with self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(State.objects.count(), 0)
        self.assertEqual(ReferenceAuditEvent.objects.count(), count)

    def test_seed_conflict_rolls_back_whole_batch_and_checks_actor(self):
        Country.objects.create(iso_code='XX', country_name='India')
        with self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(State.objects.count(), 0)
        self.assertEqual(ReferenceAuditEvent.objects.count(), 0)
        user = get_user_model().objects.create_user(username='ordinary')
        with self.assertRaises(CommandError):
            call_command('seed_reference_data', actor=user.username, stdout=StringIO())

    def test_api_audit_actions_and_failure_atomicity(self):
        client = APIClient()
        client.force_authenticate(self.actor)
        response = client.post('/api/v1/reference/countries/', {'iso_code': 'IN', 'country_name': 'India'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['country_id']
        url = f'/api/v1/reference/countries/{pk}/'
        for data in [{'country_name': 'New label'}, {'is_active': False}, {'is_active': True}]:
            self.assertEqual(client.patch(url, data, format='json').status_code, 200)
        events = list(ReferenceAuditEvent.objects.order_by('pk'))
        self.assertEqual([e.action for e in events], ['create', 'update', 'deactivate', 'reactivate'])
        self.assertEqual(events[0].before, {})
        self.assertEqual(events[0].actor, self.actor)
        self.assertEqual(events[0].source, 'api')
        self.assertEqual(events[1].before['country_name'], 'India')
        self.assertEqual(events[1].after['country_name'], 'New label')
        self.assertNotIn('password', str(events[0].after))
        # No-op writes produce no misleading change event.
        client.patch(url, {'is_active': True}, format='json')
        self.assertEqual(ReferenceAuditEvent.objects.count(), 4)
        with patch.object(ReferenceAuditEvent, 'save', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                write_reference(Country, {'country_name': 'Must rollback'}, pk, actor=self.actor)
        self.assertEqual(Country.objects.get(pk=pk).country_name, 'New label')
        self.assertEqual(ReferenceAuditEvent.objects.count(), 4)

    def test_admin_registration_create_update_lifecycle_and_no_bulk_delete(self):
        for model, *_ in RESOURCES:
            self.assertIn(model, admin.site._registry)
        add = reverse('admin:common_reference_country_add')
        response = self.client.post(add, {'iso_code': ' in ', 'country_name': ' India ', 'is_active': 'on', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        country = Country.objects.get(iso_code='IN')
        change = reverse('admin:common_reference_country_change', args=[country.pk])
        for active in (False, True):
            payload = {'iso_code': 'IN', 'country_name': 'India', '_save': 'Save'}
            if active:
                payload['is_active'] = 'on'
            self.assertEqual(self.client.post(change, payload).status_code, 302)
        self.assertEqual(list(ReferenceAuditEvent.objects.order_by('pk').values_list('action', flat=True)), ['create', 'deactivate', 'reactivate'])
        self.assertFalse(ReferenceAuditEvent.objects.exclude(source='admin').exists())
        delete = reverse('admin:common_reference_country_delete', args=[country.pk])
        self.assertEqual(self.client.post(delete, {'post': 'yes'}).status_code, 403)
        listing = reverse('admin:common_reference_country_changelist')
        self.client.post(listing, {'action': 'delete_selected', '_selected_action': [country.pk], 'post': 'yes'})
        self.assertTrue(Country.objects.filter(pk=country.pk).exists())
        self.assertEqual(ReferenceAuditEvent.objects.count(), 3)
        audit = ReferenceAuditEvent.objects.first()
        self.assertEqual(self.client.post(reverse('admin:core_referenceauditevent_change', args=[audit.pk]), {'action': 'update'}).status_code, 403)

    def test_admin_parent_validation_and_audit_rollback(self):
        country = Country.objects.create(iso_code='IN', country_name='India', is_active=False)
        add = reverse('admin:common_reference_state_add')
        payload = {'country': country.pk, 'state_code': 'MH', 'state_name': 'Maharashtra', 'is_active': 'on', '_save': 'Save'}
        response = self.client.post(add, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn('country', response.context['adminform'].form.errors)
        self.assertEqual(State.objects.count(), 0)
        state = State.objects.create(country=country, state_code='MH', state_name='Historical')
        response = self.client.post(reverse('admin:common_reference_state_change', args=[state.pk]), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReferenceAuditEvent.objects.get().after['state_name'], 'Maharashtra')
        with patch.object(ReferenceAuditEvent, 'save', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('admin:common_reference_country_add'), {'iso_code': 'US', 'country_name': 'United States', 'is_active': 'on'})
        self.assertFalse(Country.objects.filter(iso_code='US').exists())

    def test_admin_maintenance_gate_and_audit_access(self):
        user = get_user_model().objects.create_user(username='staff', password='test', is_staff=True)
        user.user_permissions.set(Permission.objects.filter(content_type__app_label='common_reference'))
        user.user_permissions.remove(Permission.objects.get(codename='maintain_reference'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('admin:common_reference_country_add')).status_code, 403)
        with self.assertRaises(Exception) as denied:
            write_reference(Country, {'iso_code': 'IN', 'country_name': 'India'}, actor=user)
        self.assertEqual(denied.exception.status_code, 403)
        audit_url = reverse('admin:core_referenceauditevent_changelist')
        self.assertEqual(self.client.get(audit_url).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename='view_referenceauditevent'))
        self.assertEqual(self.client.get(audit_url).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:core_referenceauditevent_add')).status_code, 403)

    def test_audit_append_only(self):
        obj = write_reference(Country, {'iso_code': 'IN', 'country_name': 'India'}, actor=self.actor)
        event = ReferenceAuditEvent.objects.get()
        for operation in [lambda: event.save(), lambda: event.delete(), lambda: ReferenceAuditEvent.objects.update(action='update'), lambda: ReferenceAuditEvent.objects.all().delete()]:
            with self.assertRaises(ValidationError):
                operation()
        self.assertEqual(ReferenceAuditEvent.objects.get().record_id, obj.pk)
        with self.assertRaises(ValidationError):
            ReferenceAuditEvent.objects.bulk_create([event], update_conflicts=True, update_fields=['action'])

    def test_late_seed_failure_rolls_back_prior_inserts(self):
        invalid = (
            ('countries', {'iso_code': 'IN'}, {'country_name': 'India'}),
            ('states', {'country_id': {'iso_code': 'IN'}, 'state_code': 'INVALID SPACE'}, {'state_name': 'Invalid'}),
        )
        with patch('apps.common_reference.management.commands.seed_reference_data.BASELINE', invalid):
            with self.assertRaises(CommandError):
                self.seed()
        self.assertEqual(Country.objects.count(), 0)
        self.assertEqual(ReferenceAuditEvent.objects.count(), 0)

