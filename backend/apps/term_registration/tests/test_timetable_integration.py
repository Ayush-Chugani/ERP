from datetime import date
from unittest.mock import patch
from django.test import TestCase,override_settings
from apps.teaching_timetable.tests import test_services as fixtures
from apps.teaching_timetable import models as tm
from apps.teaching_timetable.engine import operational
from apps.term_registration import models as m,services as s,workflows as w
from apps.tenancy.models import InstitutionModule


@override_settings(ADMISSION_ENROLMENT_ENABLED=True,PEOPLE_MASTER_ENABLED=True,TERM_REGISTRATION_ENABLED=True,
    TEACHING_TIMETABLE_ENABLED=True,REGISTRATION_ELIGIBILITY_ADAPTER='apps.term_registration.tests.test_workflows.eligible')
class TimetableIntegrationTests(TestCase):
    setUp=fixtures.TimetableTests.setUp
    session=fixtures.TimetableTests.session
    transition=fixtures.TimetableTests.transition
    publish=fixtures.TimetableTests.publish
    @patch("apps.term_registration.workflows.timezone.localdate", return_value=date(2026,9,23))
    def test_post_publication_roster_updates_operational_membership_only(self, _clock):
        self.session();self.publish()
        InstitutionModule.objects.filter(institution=self.institution).update(teaching_timetable=True,term_registration=True)
        self.course_offering.status='OPEN';self.course_offering.save()
        w.configure_policy(actor=self.root,programme_id=self.programme.pk,maximum_credits=20,minimum_credits=0,reason='Test policy')
        term=s.create_draft(actor=self.root,enrolment_id=self.enrolment.pk,offering_id=self.offering.pk,section_id=self.section.pk)
        s.approve_progression(actor=self.root,enrolment_id=self.enrolment.pk,offering_id=self.offering.pk,enrolment_version=self.enrolment.version,offering_version=1,reason='Verified')
        s.transition_term(actor=self.root,registration_id=term.pk,expected_version=1,target='REGISTERED',reason='Register')
        row=w.register_course(actor=self.root,term_id=term.pk,course_id=self.course_offering.pk,registration_type='AUDIT',reason='Audit registration')
        row=w.transition_registration(actor=self.root,pk=row.pk,expected_version=1,target='APPROVED',effective_date=date(2026,9,23),reason='Approve')
        w.assign_roster(actor=self.root,registration_id=row.pk,mapping_id=self.mapping.pk,expected_version=row.version,effective_date=date(2026,9,23),reason='Assign')
        self.assertTrue(all(not item.student_ids for item in tm.PublishedOccurrence.objects.all()))
        self.assertTrue(all(self.enrolment.student_id in item.students for item in operational(date_from=date(2026,9,23),date_to=date(2026,9,30))))
        self.assertTrue(all(not item.students for item in operational(revision_id=self.revision.pk)))
        self.assertTrue(all(not item.students for item in operational(date_from=date(2026,9,1),date_to=date(2026,9,22))))

        from apps.teaching_timetable.engine import current_membership
        self.assertIn(self.enrolment.student_id,current_membership(self.mapping.pk,date(2026,9,28),[]))
        row.refresh_from_db()
        from unittest.mock import patch
        with patch('apps.term_registration.workflows.timezone.localdate',return_value=date(2026,9,29)):
            w.transition_registration(actor=self.root,pk=row.pk,expected_version=row.version,target='DROPPED',effective_date=date(2026,9,29),reason='End membership')
        self.assertIn(self.enrolment.student_id,current_membership(self.mapping.pk,date(2026,9,28),[]))
        self.assertNotIn(self.enrolment.student_id,current_membership(self.mapping.pk,date(2026,9,29),[]))
