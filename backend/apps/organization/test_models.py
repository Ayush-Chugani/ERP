from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from .models import University, Programme, Room

class ModelContractTests(SimpleTestCase):
    def test_unsigned_and_validation_contract(self):
        self.assertEqual(University._meta.pk.bits,16)
        self.assertEqual(Room._meta.pk.bits,32)
        for value in [0,256]:
            with self.assertRaises(ValidationError):
                Programme._meta.get_field('duration_semesters').clean(value,None)
        with self.assertRaises(ValidationError):
            University(phone='letters').clean()
        obj=University(university_code=' abc ',university_name=' Example ')
        obj.clean()
        self.assertEqual(obj.university_code,'ABC')
