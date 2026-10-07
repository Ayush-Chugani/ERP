from django.apps import apps
from django.urls import resolve
def test_app_boundary():
    assert apps.get_app_config("feedback").name=="apps.feedback"
    assert resolve("/api/v1/core/live/").url_name=="live"
