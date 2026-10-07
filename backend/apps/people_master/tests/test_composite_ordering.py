"""Regression: composite-key tables must paginate and order under SELECT DISTINCT."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.request import Request

from apps.core.pagination import BoundedPagination
from apps.people_master import models as m
from apps.tenancy.models import Membership, ScopeGrant
from .test_services import fixture


@override_settings(PEOPLE_MASTER_ENABLED=True)
class CompositeOrderingTests(TestCase):
    def setUp(self):
        fixture(self)
        self.viewer = get_user_model().objects.create_user(username="m5viewer", password="x")
        self.viewer.user_permissions.add(Permission.objects.get(codename="view_employeecompetency"))
        membership = Membership.objects.create(user=self.viewer, institution=self.institution)
        ScopeGrant.objects.create(membership=membership, role="INSTITUTION_ADMIN")
        self.client = APIClient()
        self.client.force_authenticate(self.viewer)

    def test_scoped_competency_list_orders_by_member_columns(self):
        for ordering in ("", "?ordering=pk", "?ordering=-pk"):
            response = self.client.get(f"/api/v1/people/competencies/{ordering}")
            self.assertEqual(response.status_code, 200, ordering)
            self.assertEqual(response.data["count"], 0)

    def test_paginator_expands_pk_alias_for_composite_keys(self):
        request = Request(APIRequestFactory().get("/"))
        paginator = BoundedPagination()
        query = m.EmployeeCompetency.objects.order_by("-pk").distinct()
        self.assertEqual(list(paginator.paginate_queryset(query, request)), [])
        self.assertEqual(list(paginator.paginate_queryset(m.EmployeeCompetency.objects.distinct(), request)), [])
        simple = m.Student.objects.order_by("student_number")
        self.assertEqual(list(paginator.paginate_queryset(simple, request)), [])
        self.assertEqual(list(paginator.paginate_queryset([1, 2, 3], request)), [1, 2, 3])
