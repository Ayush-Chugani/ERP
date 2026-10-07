from django.db import connection
from django.test import TestCase

from apps.documents_exit.migrations._canonical import DDL, verify


class SchemaTests(TestCase):
    def test_canonical_schema(self):
        with connection.cursor() as cursor:
            for sql in DDL:
                self.assertTrue(verify(cursor, sql))
