from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection, connections, IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TransactionTestCase
from apps.core.fields import UnsignedAutoField, ReferenceTextField
from .models import Country, State, SocialCategory, Caste, SubCaste, Religion

class FieldTests(SimpleTestCase):
    def test_unsigned_fields_roundtrip_and_bounds(self):
        for bits in (8, 16, 32):
            field = UnsignedAutoField(bits=bits, primary_key=True)
            _, path, args, kwargs = field.deconstruct()
            module, name = path.rsplit(".", 1)
            clone = getattr(import_module(module), name)(*args, **kwargs)
            self.assertEqual(clone.bits, bits)
            field.run_validators(2**bits-1)
            for invalid in (-1, 0, 2**bits):
                with self.assertRaises(ValidationError):
                    field.run_validators(invalid)

    def test_normalization(self):
        field = Religion._meta.get_field("religion_code")
        self.assertIsNone(field.clean("  ", None))
        self.assertEqual(field.clean(" ab-1 ", None), "AB-1")
        with self.assertRaises(ValidationError):
            field.clean("A B", None)
        self.assertEqual(Caste._meta.get_field("caste_name").clean("  Cafe\u0301   Name ", None), "Caf\u00e9 Name")

class MySQLReferenceTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "mysql", "Run these checks against actual MySQL")
        self.assertFalse(connection.mysql_is_mariadb)

    def test_schema_types_defaults_and_constraints(self):
        expected = {"country":16,"state":16,"gender":8,"blood_group":8,"religion":16,
                    "social_category":16,"caste":32,"sub_caste":32,"admission_category":16,"document_type":16}
        for model in apps.get_app_config("common_reference").get_models():
            table = model._meta.db_table
            with connection.cursor() as cur:
                cur.execute("SELECT ENGINE,TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", [table])
                self.assertEqual(cur.fetchone(), ("InnoDB", "utf8mb4_0900_ai_ci"))
                cur.execute("SELECT COLUMN_NAME,COLUMN_TYPE,EXTRA,COLUMN_DEFAULT,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", [table])
                columns = {row[0]:row[1:] for row in cur.fetchall()}
                expected_type={8:"tinyint unsigned",16:"smallint unsigned",32:"int unsigned"}[expected[table]]
                self.assertEqual(columns[table+"_id"][0],expected_type)
                self.assertIn("auto_increment",columns[table+"_id"][1])
                self.assertEqual(str(columns["is_active"][2]),"1")
                self.assertFalse(any(name.endswith("_id_id") for name in columns))
                for field in model._meta.fields:
                    if field.is_relation:
                        self.assertEqual(columns[field.column][0], {16:"smallint unsigned",32:"int unsigned"}[field.target_field.bits])
                    if isinstance(field, ReferenceTextField) or field.generated:
                        self.assertEqual(columns[field.column][3],"utf8mb4_0900_ai_ci")
                constraints=connection.introspection.get_constraints(cur,table)
                for constraint in model._meta.constraints:
                    self.assertTrue(constraints[constraint.name]["unique"])
                self.assertFalse(any(c["index"] and not c["unique"] and not c["primary_key"] for c in constraints.values()), "No redundant standalone FK indexes")
                foreign=[c for c in constraints.values() if c["foreign_key"]]
                self.assertEqual(len(foreign),sum(f.is_relation for f in model._meta.fields))
        with connection.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM country LIKE 'iso_code'")
            self.assertEqual(cur.fetchone()[1],"char(2)")
            cur.execute("SHOW COLUMNS FROM caste LIKE 'uncategorized_caste_name'")
            self.assertIn("STORED GENERATED",cur.fetchone()[5])

    def test_null_category_uniqueness_raw_sql_and_updates(self):
        with connection.cursor() as cur:
            cur.execute("INSERT INTO caste(caste_name) VALUES ('Caf\u00e9')")
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("INSERT INTO caste(caste_name) VALUES ('CAFE')")
        a=SocialCategory.objects.create(category_code="A",category_name="Alpha")
        b=SocialCategory.objects.create(category_code="B",category_name="Beta")
        first=Caste.objects.create(caste_name="Cafe",social_category=a)
        Caste.objects.create(caste_name="Cafe",social_category=b)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Caste.objects.bulk_create([Caste(caste_name="CAF\u00c9",social_category=a)])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Caste.objects.filter(pk=first.pk).update(social_category=None)
        Caste.objects.filter(social_category=None).update(is_active=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Caste.objects.bulk_create([Caste(caste_name="cafe")])

    def test_concurrent_null_duplicates(self):
        def insert():
            try:
                with connections["default"].cursor() as cur:
                    cur.execute("INSERT INTO caste(caste_name) VALUES ('Concurrent')")
                return "created"
            except IntegrityError:
                return "duplicate"
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _:insert(),range(2))),["created","duplicate"])

    def test_fk_history_and_orphans(self):
        country=Country.objects.create(iso_code="in",country_name="India")
        state=State.objects.create(country=country,state_code="MH",state_name="Maharashtra")
        with self.assertRaises(ProtectedError): country.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cur: cur.execute("DELETE FROM country WHERE country_id=%s",[country.pk])
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("INSERT INTO state(country_id,state_code,state_name) VALUES (65535,'XX','Orphan')")
        country.is_active=False; country.save()
        state.refresh_from_db(); self.assertEqual(state.country_id,country.pk)
        category=SocialCategory.objects.create(category_code="S",category_name="Social")
        caste=Caste.objects.create(caste_name="Parent",social_category=category)
        SubCaste.objects.create(caste=caste,sub_caste_name="Child")
        for parent in (category,caste):
            with self.assertRaises(ProtectedError): parent.delete()
            with self.assertRaises(IntegrityError), transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(f"DELETE FROM {parent._meta.db_table} WHERE {parent._meta.pk.column}=%s",[parent.pk])

    def test_optional_codes_and_unsigned_high_values(self):
        first=Religion.objects.create(religion_name="First",religion_code="  ")
        second=Religion.objects.create(religion_name="Second",religion_code="")
        self.assertIsNone(first.religion_code); self.assertIsNone(second.religion_code)
        caste=Caste.objects.create(caste_id=3000000000,caste_name="Wide ID")
        child=SubCaste.objects.create(caste=caste,sub_caste_name="Wide FK")
        child.refresh_from_db(); self.assertEqual(child.caste_id,3000000000)
        with connection.cursor() as cur:
            cur.execute("INSERT INTO gender(gender_code,gender_name) VALUES ('X','Example')")
            self.assertGreater(cur.lastrowid,0)
