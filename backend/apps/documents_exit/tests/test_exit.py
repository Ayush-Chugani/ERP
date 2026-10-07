from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.admission_enrolment.models import EnrolmentStatusHistory
from apps.documents_exit import integrations
from apps.documents_exit import models as m
from apps.documents_exit import services as s
from apps.term_registration.tests import test_registration as fixtures


@override_settings(
    DOCUMENTS_EXIT_ENABLED=True,
    ADMISSION_ENROLMENT_ENABLED=True,
    PEOPLE_MASTER_ENABLED=True,
    TERM_REGISTRATION_ENABLED=True,
    DOCUMENTS_EXIT_CLEARANCE="apps.documents_exit.tests.providers.cleared",
)
class ExitTests(TestCase):
    def setUp(self):
        fixtures.RegistrationTests.setUp(self)

    def finalize(self, kind="COMPLETION", **changes):
        values = {
            "actor": self.root,
            "enrolment_id": self.enrolment.pk,
            "exit_type": kind,
            "exit_date": timezone.localdate(),
            "reason": "Approved clearance",
            "confirmed": True,
        }
        values.update(changes)
        return s.finalize_exit(**values)

    def test_completion_owner_history_and_idempotency(self):
        obj = self.finalize()
        self.enrolment.refresh_from_db()
        self.assertEqual(self.enrolment.enrolment_status, "COMPLETED")
        self.assertEqual(self.finalize().pk, obj.pk)
        self.assertEqual(m.StudentExit.objects.count(), 1)
        self.assertEqual(
            EnrolmentStatusHistory.objects.filter(
                enrolment=self.enrolment, new_status="COMPLETED"
            ).count(),
            1,
        )
        with self.assertRaises(s.Conflict):
            self.finalize("WITHDRAWAL")

    def test_provider_absence_and_rejected_clearance_rollback(self):
        with (
            override_settings(DOCUMENTS_EXIT_CLEARANCE=""),
            self.assertRaises(integrations.ProviderUnavailable),
        ):
            self.finalize()
        with (
            override_settings(
                DOCUMENTS_EXIT_CLEARANCE="apps.documents_exit.tests.providers.not_cleared"
            ),
            self.assertRaises(s.Conflict),
        ):
            self.finalize()
        self.enrolment.refresh_from_db()
        self.assertEqual(self.enrolment.enrolment_status, "ACTIVE")
        self.assertEqual(m.StudentExit.objects.count(), 0)

    def test_audit_failure_rolls_back_external_enrolment_change(self):
        count = EnrolmentStatusHistory.objects.count()
        with (
            patch(
                "apps.documents_exit.services.audit",
                side_effect=RuntimeError("injected"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.finalize()
        self.enrolment.refresh_from_db()
        self.assertEqual(self.enrolment.enrolment_status, "ACTIVE")
        self.assertEqual(EnrolmentStatusHistory.objects.count(), count)
        self.assertEqual(m.StudentExit.objects.count(), 0)

    def test_transfer_uses_owning_service(self):
        with self.assertRaises(ValidationError):
            self.finalize("TRANSFER")
        self.finalize("TRANSFER", destination_institution="Approved destination")
        self.enrolment.refresh_from_db()
        self.assertEqual(self.enrolment.enrolment_status, "TRANSFERRED")
        self.assertTrue(
            EnrolmentStatusHistory.objects.filter(
                enrolment=self.enrolment, new_status="TRANSFERRED"
            ).exists()
        )

    def test_termination_confirmation_dates_and_privilege(self):
        user = get_user_model().objects.create_user(username="unprivileged")
        with self.assertRaises(NotFound):
            self.finalize("TERMINATION", actor=user, remarks="Reason")
        with self.assertRaises(ValidationError):
            self.finalize("TERMINATION", confirmed=False, remarks="Reason")
        with self.assertRaises(ValidationError):
            self.finalize("TERMINATION")
        with self.assertRaises(ValidationError):
            self.finalize(exit_date=timezone.localdate() + timedelta(days=1))
        self.finalize("TERMINATION", remarks="Approved decision")
        self.enrolment.refresh_from_db()
        self.assertEqual(self.enrolment.enrolment_status, "TERMINATED")

    def test_other_explicit_mapping_and_withdrawal(self):
        self.finalize("OTHER", remarks="Explicit policy maps to withdrawal")
        self.enrolment.refresh_from_db()
        self.assertEqual(self.enrolment.enrolment_status, "WITHDRAWN")
