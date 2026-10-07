from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.conferences.tests import test_services


@override_settings(
    CONFERENCES_ENABLED=True,
    IDENTITY_ACCESS_ENABLED=True,
    IDENTITY_ACCESS_SECURITY_ENABLED=True,
)
class ApiTests(TestCase):
    def setUp(self):
        test_services.ConferenceTests.setUp(self)
        self.client = APIClient()
        self.client.force_authenticate(self.root)
        self.url = "/api/v1/conferences/activities/"

    def payload(self):
        return {
            "context": self.context,
            "activity": {
                "conference_event_id": self.event.pk,
                "conference_contribution_type_id": self.contribution.pk,
                "paper_title": "Synthetic paper",
            },
        }

    def test_crud_and_protected_fields(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["staff_activity"]
        detail = self.client.get(self.url + str(pk) + "/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["employee_id"], str(self.employee.pk))
        response = self.client.patch(
            self.url + str(pk) + "/",
            {"version": detail.data["version"], "activity": {"paper_title": "Changed"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = self.payload()
        data["context"]["institution_id"] = self.institution.pk
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_list_filter_and_scope_revocation(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["staff_activity"]
        response = self.client.get(self.url, {"search": "Synthetic"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.grant.assignment_status = "REVOKED"
        self.grant.save()
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(self.url + str(pk) + "/").status_code, 404)

    def test_event_and_off_switch(self):
        response = self.client.post(
            "/api/v1/conferences/events/",
            {
                "conference_title": "API event",
                "start_date": "2026-03-01",
                "end_date": "2026-03-02",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        with override_settings(CONFERENCES_ENABLED=False):
            self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_list_query_count_does_not_grow_with_rows(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.assertEqual(
            self.client.post(self.url, self.payload(), format="json").status_code, 201
        )
        with CaptureQueriesContext(connection) as first:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for _ in range(4):
            self.assertEqual(
                self.client.post(self.url, self.payload(), format="json").status_code,
                201,
            )
        with CaptureQueriesContext(connection) as several:
            response = self.client.get(self.url)
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(first), len(several))

    def test_export_scope_and_formula_escaping(self):
        data = self.payload()
        data["activity"]["paper_title"] = "=SUM(1,2)"
        self.assertEqual(
            self.client.post(self.url, data, format="json").status_code, 201
        )
        export = self.client.get(self.url + "export/")
        self.assertEqual(export.status_code, 200)
        self.assertIn("'=SUM", export.content.decode())
        self.assertEqual(export["Cache-Control"], "private, no-store")
        self.grant.assignment_status = "REVOKED"
        self.grant.save()
        self.assertNotIn("SUM", self.client.get(self.url + "export/").content.decode())

    def test_self_scope_requires_employee_link_and_assignment_choices_are_scoped(self):
        from apps.people_master.models import AccountLink

        self.assertEqual(
            self.client.post(self.url, self.payload(), format="json").status_code, 201
        )
        self.grant.scope_type = "SELF"
        self.grant.save()
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        AccountLink.objects.create(user=self.root, employee=self.employee)
        self.assertEqual(self.client.get(self.url).data["count"], 1)
        choices = self.client.get("/api/v1/conferences/lookups/assignments/")
        self.assertEqual(choices.status_code, 200, choices.data)
        self.assertEqual(
            [r["employee_id"] for r in choices.data["results"]], [str(self.employee.pk)]
        )
