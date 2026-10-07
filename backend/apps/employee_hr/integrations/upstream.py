"""Narrow reuse of upstream owners; this module introduces no identity or storage copy."""
from apps.people_master.models import Employee, EmployeeAssignment, AccountLink
from apps.identity_access.evaluator import Scope, has_object_permission
from apps.identity_access.audit import record as activity_audit
from apps.documents_exit.models import FileObject
