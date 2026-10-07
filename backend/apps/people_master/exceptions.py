from rest_framework.exceptions import APIException


class PeopleConflict(APIException):
    status_code = 409
    default_code = "people_conflict"
    default_detail = "The requested change conflicts with the current record."


class StalePeopleVersion(PeopleConflict):
    default_code = "stale_version"
    default_detail = "This record changed. Reload it before saving."
