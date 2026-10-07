"""Demo user accounts, one per role, wired to people records and data scope.

Run after seed_sample_data / seed_sample_academics. Idempotent; development only.
All accounts except `admin` (left untouched) use DEMO_PASSWORD from
seed_sample_data.

  username   role                          scope                       linked record
  admin      Superuser                     everything                  -
  registrar  Admissions & registration     whole institution           -
  campusadm  Campus administrator          campus 1                    -
  hod        Head of department (CSE)      department CSE school       employee EMP002
  teacher    Faculty                       department CSE school       employee EMP004
  examcell   Examination / results cell    whole institution           -
  support    Student support officer       whole institution           -
  student    Student                       own record                  student 01FE24BCS001
  student2   Student                       own record                  student 01FE24BCS002
"""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from .seed_sample_data import DEMO_PASSWORD

STUDENT_GROUPS = ["Student", "Document Student", "M11 Respondent", "Support Student", "Calendar viewer", "Curriculum viewer"]
FACULTY_GROUPS = ["Calendar viewer", "Curriculum viewer", "Organization viewer", "People viewer", "Teacher", "M9 Faculty", "M10 Faculty", "M11 Faculty", "Timetable Reader", "Communication author", "Support Mentor"]

# username: (first, last, groups, grant role, department code or None, link kind, link number)
PERSONAS = {
    "registrar": ("Rekha", "Registrar", ["People manager", "Calendar viewer", "Curriculum viewer", "Organization viewer", "Admissions registrar", "Admissions reviewer", "Admissions fee clearance", "M7 Registrar", "M7 Reader", "Certificate Officer", "Document Verifier", "Exit Officer", "Communication author"], "INSTITUTION_ADMIN", None, None, None),
    "campusadm": ("Chetan", "Campus", ["People manager", "Calendar manager", "Curriculum manager", "Organization manager", "Admin", "Communication approver", "Communication institution publisher", "Timetable Reader"], "CAMPUS_ADMIN", None, None, None),
    "hod": ("Sunita", "Hegde", ["M7 Coordinator", "People viewer", "Calendar viewer", "Curriculum manager", "Organization viewer", "Teacher", "M9 Coordinator", "M9 Reviewer", "M10 Coordinator", "M10 Reviewer", "M11 Coordinator", "Timetable Planner", "Timetable Approver", "Timetable Publisher", "Communication author", "Communication approver", "Support Mentor"], "DEPARTMENT_ADMIN", "CSE", "employee", "EMP002"),
    "teacher": ("Anil", "Deshpande", FACULTY_GROUPS, "TEACHER", "CSE", "employee", "EMP004"),
    "examcell": ("Eshwar", "Exams", ["Calendar viewer", "Curriculum viewer", "Organization viewer", "M10 Result cell", "M10 Reviewer", "M10 Coordinator", "Timetable Reader"], "INSTITUTION_ADMIN", None, None, None),
    "support": ("Savita", "Support", ["People viewer", "Organization viewer", "Support Administrator", "Support Grievance Officer", "Support Mentor"], "INSTITUTION_ADMIN", None, None, None),
    "student": ("Chaitra", "Shenoy", STUDENT_GROUPS, "STUDENT", None, "student", "01FE24BCS001"),
    "student2": ("Nandini", "Naik", STUDENT_GROUPS, "STUDENT", None, "student", "01FE24BCS002"),
}


# group name -> (app label, "view" = view_* only, "manage" = everything except delete_*)
ACCESS_GROUPS = {
    "People viewer": ("people_master", "view"),
    "People manager": ("people_master", "manage"),
    "Calendar viewer": ("academic_calendar", "view"),
    "Calendar manager": ("academic_calendar", "manage"),
    "Curriculum viewer": ("curriculum_catalog", "view"),
    "Curriculum manager": ("curriculum_catalog", "manage"),
    "Organization viewer": ("organization", "view"),
    "Organization manager": ("organization", "manage"),
}


STAFF_MODULES = ["AWARDS", "COCURRICULAR", "CONFERENCES", "CONSULTANCY", "EVIDENCE", "EXTRACURRICULAR", "FACULTY_INTERNSHIPS",
                 "FUNDED_PROJECTS", "PROFESSIONAL_CONTRIBUTIONS", "PROFESSIONAL_MEMBERSHIPS", "RESEARCH_PROPOSALS"]
# role code -> staff-module actions granted (the installers grant these to SUPER_ADMIN only)
STAFF_ROLE_ACTIONS = {
    "FACULTY": {"READ", "CREATE", "UPDATE"},
    "HEAD_DEPARTMENT": {"READ", "CREATE", "UPDATE", "VERIFY", "APPROVE", "EXPORT"},
    "CAMPUS_DIRECTOR": {"READ", "VERIFY", "APPROVE", "EXPORT"},
    "REGISTRAR": {"READ", "EXPORT"},
}
# persona -> (role code, scope type)
IAM_ROLES = {
    "registrar": ("REGISTRAR", "INSTITUTION"), "campusadm": ("CAMPUS_DIRECTOR", "CAMPUS"), "hod": ("HEAD_DEPARTMENT", "DEPARTMENT"),
    "teacher": ("FACULTY", "DEPARTMENT"), "examcell": ("CONTROLLER_EXAMINATIONS", "INSTITUTION"),
    "support": ("GRIEVANCE_OFFICER", "INSTITUTION"), "student": ("STUDENT", "SELF"), "student2": ("STUDENT", "SELF"),
}


class Command(BaseCommand):
    help = "Create role-based demo users wired to people records and data scope."

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        Permission = apps.get_model("auth", "Permission")
        admin_user = User.objects.filter(is_superuser=True).order_by("pk").first()
        for gname, (app_label, mode) in ACCESS_GROUPS.items():
            group, _ = Group.objects.get_or_create(name=gname)
            perms = Permission.objects.filter(content_type__app_label=app_label)
            perms = perms.filter(codename__startswith="view_") if mode == "view" else perms.exclude(codename__startswith="delete_")
            group.permissions.set(perms)
        Membership = apps.get_model("tenancy", "Membership")
        ScopeGrant = apps.get_model("tenancy", "ScopeGrant")
        AccountLink = apps.get_model("people_master", "AccountLink")
        Student = apps.get_model("people_master", "Student")
        Employee = apps.get_model("people_master", "Employee")
        Department = apps.get_model("organization", "Department")
        Institution = apps.get_model("organization", "Institution")
        inst = Institution.objects.order_by("pk").first()
        # Per-institution module switches; without this row non-admin users see no records.
        InstitutionModule = apps.get_model("tenancy", "InstitutionModule")
        flags = {f.name: True for f in InstitutionModule._meta.concrete_fields if f.get_internal_type() == "BooleanField"}
        InstitutionModule.objects.update_or_create(institution=inst, defaults=flags)
        campus = apps.get_model("organization", "Campus").objects.filter(institution=inst).order_by("pk").first()

        iam = apps.get_app_config("identity_access").get_model
        IamRole, IamPerm, RolePerm, Assignment = iam("Role"), iam("Permission"), iam("RolePermission"), iam("UserRoleAssignment")
        for role_code, actions in STAFF_ROLE_ACTIONS.items():
            role = IamRole.objects.get(role_code=role_code)
            for perm in IamPerm.objects.filter(permission_code__regex=r"^(%s)\." % "|".join(STAFF_MODULES)):
                if perm.permission_code.rsplit(".", 1)[1] in actions and not perm.permission_code.endswith(".FINANCE.READ"):
                    RolePerm.objects.get_or_create(role=role, permission=perm, defaults={"permission_effect": "ALLOW"})

        for username, (first, last, groups, role, dept_code, link_kind, link_no) in PERSONAS.items():
            user, created = User.objects.get_or_create(
                username=username,
                defaults=dict(first_name=first, last_name=last, email=f"{username}@sample.edu", is_active=True),
            )
            # Also fixes accounts restored from the shared database dump, whose passwords are blanked.
            if created or username in ("teacher", "student") or not user.has_usable_password():
                user.set_password(DEMO_PASSWORD)
                user.must_change_password = False
                user.failed_login_count = 0
                user.locked_until = None
                user.save()
            user.groups.set(Group.objects.filter(name__in=groups))

            membership, _ = Membership.objects.get_or_create(user=user, institution=inst)
            ScopeGrant.objects.filter(membership=membership).delete()
            grant = dict(membership=membership, role=role)
            if role in ("CAMPUS_ADMIN", "DEPARTMENT_ADMIN"):
                grant["campus"] = campus
            if dept_code:
                dept = Department.objects.filter(department_code=dept_code, campus=campus).first()
                grant["campus"] = campus
                grant["department"] = dept
            ScopeGrant.objects.create(**grant)

            if username in IAM_ROLES:
                code, scope = IAM_ROLES[username]
                kw = dict(user=user, role=IamRole.objects.get(role_code=code), scope_type=scope)
                if scope == "INSTITUTION":
                    kw["institution"] = inst
                elif scope == "CAMPUS":
                    kw["campus"] = grant.get("campus")
                elif scope == "DEPARTMENT":
                    kw["department"] = grant.get("department")
                Assignment.objects.filter(user=user).delete()
                Assignment.objects.create(**kw, assignment_status="ACTIVE", is_primary=True, assigned_by_user=admin_user,
                                          assignment_reason="Sample role assignment")

            if link_kind:
                AccountLink.objects.filter(user=user).delete()
                if link_kind == "student":
                    target = Student.objects.get(student_number=link_no)
                    AccountLink.objects.filter(student=target).delete()
                    AccountLink.objects.create(user=user, student=target)
                else:
                    target = Employee.objects.get(employee_number=link_no)
                    AccountLink.objects.filter(employee=target).delete()
                    AccountLink.objects.create(user=user, employee=target)
            self.stdout.write(f"{'created' if created else 'updated'} {username} ({role})")
        self.stdout.write(self.style.SUCCESS("Demo users ready (password: DEMO_PASSWORD in seed_sample_data.py)."))
