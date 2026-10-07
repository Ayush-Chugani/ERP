"""Synthetic-only database contracts for restricted records."""
import re
from datetime import date
from django.db import connection, IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from apps.people_master.tests.test_services import fixture
from apps.people_master.models import Employee
from apps.employee_hr import models as m
from apps.employee_hr.crypto import IdentifierCipher
from apps.employee_hr.migrations._restricted_ddl import DDL


class RestrictedContractTests(TestCase):
    def setUp(self):
        fixture(self)
        self.employee = Employee.objects.create(
            institution=self.institution, employment_source=self.source,
            employee_number='M16-RESTRICTED-SYNTHETIC', first_name='Synthetic',
            display_name='Synthetic Employee', joining_date=date(2020, 1, 1),
            employment_type='REGULAR')
        self.cipher = IdentifierCipher(keys={1: b'a' * 32}, active_version=1,
                                       fingerprint_key=b'h' * 32)

    def bank(self, value='123456789012', **extra):
        protected = self.cipher.protect(kind='bank', employee_id=self.employee.pk, value=value)
        return m.EmployeeBankAccount.objects.create(
            employee=self.employee, account_holder_name='Synthetic', bank_name='Synthetic',
            account_number_ciphertext=protected.ciphertext,
            account_number_fingerprint=protected.fingerprint,
            account_number_last4=extra.pop('account_number_last4', protected.last4),
            ifsc_code=extra.pop('ifsc_code', 'TEST0123456'), **extra)

    def test_primary_uniqueness_and_soft_delete(self):
        row = self.bank(is_primary=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.bank('123456789013', is_primary=True)
        row.deleted_at = timezone.now()
        row.save(update_fields=['deleted_at'])
        self.bank('123456789013', is_primary=True)
        # Fingerprints remain reserved even after soft deletion.
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.bank()

    def test_bank_database_validation(self):
        for values in [dict(ifsc_code='INVALID'), dict(account_number_last4='ABCD'),
                       dict(effective_from=date(2025, 1, 2), effective_to=date(2025, 1, 1))]:
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                self.bank(**values)

    def test_pan_aadhaar_employee_uniqueness_survives_soft_delete(self):
        for kind, model, value in [('pan', m.EmployeePan, 'ABCDE1234F'),
                                   ('aadhaar', m.EmployeeAadhaar, '234567890123')]:
            protected = self.cipher.protect(kind=kind, employee_id=self.employee.pk, value=value)
            prefix = kind + '_number_'
            values = {'employee': self.employee, prefix + 'ciphertext': protected.ciphertext,
                      prefix + 'fingerprint': protected.fingerprint,
                      prefix + 'masked': protected.masked, 'name_as_per_' + kind: 'Synthetic'}
            if kind == 'aadhaar':
                values[prefix + 'last4'] = protected.last4
            row = model.objects.create(**values)
            row.deleted_at = timezone.now()
            row.save(update_fields=['deleted_at'])
            values[prefix + 'fingerprint'] = 'f' * 64
            with self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create(**values)

    def test_ciphertext_roundtrip_and_no_plaintext_column(self):
        row = self.bank()
        row.refresh_from_db()
        self.assertNotIn(b'123456789012', row.account_number_ciphertext)
        self.assertEqual(self.cipher._decrypt(kind='bank', employee_id=self.employee.pk,
                                             ciphertext=row.account_number_ciphertext), '123456789012')
        self.assertNotIn('account_number', {f.column for f in row._meta.local_fields})

    def test_source_columns_native_storage_and_named_foreign_keys(self):
        with connection.cursor() as cursor:
            for model, ddl in zip((m.EmployeeBankAccount, m.EmployeePan, m.EmployeeAadhaar), DDL):
                table = model._meta.db_table
                expected = set(re.findall(r'^\s*(\w+) (?:BIGINT|SMALLINT|VARCHAR|CHAR|VARBINARY|BOOLEAN|TIMESTAMP|ENUM|DATETIME|DATE)\b', ddl, re.M))
                self.assertEqual({f.column for f in model._meta.local_fields}, expected)
                cursor.execute('SELECT COLUMN_NAME,COLUMN_TYPE,EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', [table])
                columns = {name: (kind.lower(), extra.lower()) for name, kind, extra in cursor.fetchall()}
                for name in expected:
                    if name.endswith('_ciphertext'):
                        self.assertEqual(columns[name][0], 'varbinary(1024)')
                    if name.endswith('_fingerprint'):
                        self.assertEqual(columns[name][0], 'char(64)')
                    if name.endswith('_last4'):
                        self.assertEqual(columns[name][0], 'char(4)')
                self.assertIn('on update current_timestamp', columns['updated_at'][1])
                for wanted, column, target, target_column in re.findall(r'CONSTRAINT (\w+) FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)', ddl):
                    cursor.execute('SELECT CONSTRAINT_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL', [table, column])
                    self.assertEqual(cursor.fetchall(), ((wanted, target, target_column),))
