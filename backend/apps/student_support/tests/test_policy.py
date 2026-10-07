from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from apps.student_support.policies import policy


class PolicyTests(SimpleTestCase):
    @override_settings(
        STUDENT_SUPPORT_POLICIES={"1": {"student_normal_notes": "false"}}
    )
    def test_text_boolean_fails_closed(self):
        with self.assertRaises(ImproperlyConfigured):
            policy(1, "student_normal_notes", True)

    @override_settings(STUDENT_SUPPORT_POLICIES={"1": {"student_normal_notes": False}})
    def test_explicit_false_disables_policy(self):
        self.assertFalse(policy(1, "student_normal_notes", True))
