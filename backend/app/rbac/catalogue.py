"""Keep the permission catalogue (modules, resources, actions, permissions) and baseline role grants in sync with
the resources the API actually exposes. Safe to run repeatedly (idempotent)."""
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.identity_access import AccessAction, AccessModule, AccessResource, Permission, Role, RolePermission
from app.rbac.matrix import MATRIX, desired_codes
from app.resources.registry import MODULES, build_registry
from app.resources.spec import REGISTRY

ACTIONS = [
    ("READ", "Read"), ("CREATE", "Create"), ("UPDATE", "Update"), ("DELETE", "Delete"), ("APPROVE", "Approve"),
    ("VERIFY", "Verify"), ("PUBLISH", "Publish"), ("ASSIGN", "Assign"), ("CONFIGURE", "Configure"),
    ("EXPORT", "Export"), ("IMPERSONATE", "Impersonate"),
]
RESOURCE_ACTIONS = ("READ", "CREATE", "UPDATE", "DELETE", "EXPORT", "APPROVE", "VERIFY", "PUBLISH")
SENSITIVE = {"DELETE", "IMPERSONATE", "CONFIGURE"}

# Built-in role grants live in app/rbac/matrix.py (authoritative; sync makes the database match it).
# Teaching roles act on their own research records through STAFF_SELF, not department-wide.
TEACHING_ROLES = ("FACULTY", "LAB_INSTRUCTOR", "FACULTY_ADVISOR", "MENTOR", "EVALUATOR", "COURSE_COORDINATOR")
# Assigning one of these also gives the user STAFF_SELF so they can maintain their own records.
AUTO_STAFF_SELF = {*TEACHING_ROLES, "HEAD_DEPARTMENT", "PROGRAMME_COORDINATOR",
                   "SEMESTER_COORDINATOR", "TIMETABLE_COORDINATOR"}
NEW_ROLES = [("INSTITUTION_ADMIN", "Organisation administrator", "ADMINISTRATIVE", "INSTITUTION",
               "Runs one organisation: creates its people and logins and assigns their roles, inside that organisation only."),
              ("STAFF_SELF", "Staff self-service", "FACULTY", "SELF",
              "Create and maintain one's own research, awards and professional records.")]


def ensure_lookups(db: Session) -> None:
    """Reference rows the application logic relies on."""
    db.execute(text(
        "INSERT INTO activity_type (activity_type_code, activity_type_name, activity_group, is_active) "
        "SELECT 'JOURNAL_PUBLICATION', 'Journal publication', 'RESEARCH', true "
        "WHERE NOT EXISTS (SELECT 1 FROM activity_type WHERE activity_type_code = 'JOURNAL_PUBLICATION')"))


def sync(db: Session) -> dict[str, int]:
    build_registry()
    ensure_lookups(db)
    stats = {"modules": 0, "resources": 0, "permissions": 0, "grants": 0, "revoked": 0, "missing": 0}
    actions = {a.action_code: a for a in db.scalars(select(AccessAction))}
    for code, name in ACTIONS:
        if code not in actions:
            actions[code] = AccessAction(action_code=code, action_name=name, is_active=True)
            db.add(actions[code])
    db.flush()

    modules = {m.module_code: m for m in db.scalars(select(AccessModule))}
    needed = {m[1] for m in MODULES.values()} | {s.perm_module for s in REGISTRY.values()}
    order = max([m.display_order for m in modules.values()] + [0])
    for code in sorted(needed):
        if code not in modules:
            order += 10
            modules[code] = AccessModule(module_code=code, module_name=code.replace("_", " ").title(),
                                         display_order=order, is_active=True)
            db.add(modules[code])
            stats["modules"] += 1
    db.flush()

    resources = {(r.access_module_id, r.resource_code): r for r in db.scalars(select(AccessResource))}
    wanted: dict[tuple[str, str], str] = {(m, "ALL"): "All resources" for m in needed}
    for s in REGISTRY.values():
        wanted[(s.perm_module, s.perm_resource)] = s.title
    for (mod, res), title in wanted.items():
        key = (modules[mod].access_module_id, res)
        if key not in resources:
            resources[key] = AccessResource(access_module_id=modules[mod].access_module_id, resource_code=res,
                                            resource_name=title[:150], is_active=True)
            db.add(resources[key])
            stats["resources"] += 1
    db.flush()

    perms = {p.permission_code: p for p in db.scalars(select(Permission))}
    for (mod, res), title in wanted.items():
        r = resources[(modules[mod].access_module_id, res)]
        codes = [a for a, _ in ACTIONS] if res == "ALL" else RESOURCE_ACTIONS
        for act in codes:
            code = f"{mod}.{res}.{act}"
            if code not in perms:
                perms[code] = Permission(
                    permission_code=code, permission_name=f"{act.title()} {title}"[:200],
                    is_sensitive=act in SENSITIVE, is_active=True, access_action_id=actions[act].access_action_id,
                    access_resource_id=r.access_resource_id)
                db.add(perms[code])
                stats["permissions"] += 1
    db.flush()

    roles = {r.role_code: r for r in db.scalars(select(Role))}
    for code, name, category, level, desc in NEW_ROLES:
        if code not in roles:
            roles[code] = Role(role_code=code, role_name=name, role_category=category, role_level=level,
                               description=desc, is_system_role=True, is_assignable=True, is_active=True)
            db.add(roles[code])
    db.flush()

    have = {(rp.role_id, rp.permission_id) for rp in db.scalars(select(RolePermission))}
    perm_by_code = {code: p for code, p in perms.items()}
    for role_code, entries in MATRIX.items():
        role = roles.get(role_code)
        if role is None:
            continue
        wanted = desired_codes(entries)
        current = {rp.permission_id: rp for rp in db.scalars(select(RolePermission).where(
            RolePermission.role_id == role.role_id, RolePermission.permission_effect == "ALLOW"))}
        wanted_ids = set()
        for code in wanted:
            perm = perm_by_code.get(code)
            if perm is None:
                stats["missing"] += 1       # the matrix names a resource/action that does not exist (caught by tests)
                continue
            wanted_ids.add(perm.permission_id)
            if perm.permission_id not in current:
                db.add(RolePermission(role_id=role.role_id, permission_id=perm.permission_id, permission_effect="ALLOW"))
                have.add((role.role_id, perm.permission_id))
                stats["grants"] += 1
        for pid, rp in current.items():
            if pid not in wanted_ids:
                db.delete(rp)                 # least privilege: a built-in role holds exactly what the matrix lists
                have.discard((role.role_id, pid))
                stats["revoked"] += 1
    grants = {"SUPER_ADMIN": [(m, [a for a, _ in ACTIONS]) for m in needed]}
    for role_code, entries in grants.items():
        role = roles.get(role_code)
        if role is None:
            continue
        for mod, acts in entries:
            for act in acts:
                perm = perms.get(f"{mod}.ALL.{act}")
                if perm and (role.role_id, perm.permission_id) not in have:
                    db.add(RolePermission(role_id=role.role_id, permission_id=perm.permission_id,
                                          permission_effect="ALLOW"))
                    have.add((role.role_id, perm.permission_id))
                    stats["grants"] += 1
    if role_org := roles.get("INSTITUTION_ADMIN"):
        # Everything operational inside the organisation, but no platform configuration (roles, jobs, impersonation).
        admin_actions = [a for a, _ in ACTIONS if a not in ("CONFIGURE", "IMPERSONATE")]
        special = {"IAM": ["READ", "CREATE", "UPDATE", "ASSIGN"], "AUDIT": ["READ"], "REFERENCE": ["READ"],
                   "INSTITUTION": ["READ", "CREATE", "UPDATE", "EXPORT"]}
        for mod in sorted({c.split(".")[0] for c in perms}):
            for act in special.get(mod, admin_actions):
                perm = perms.get(f"{mod}.ALL.{act}")
                if perm and (role_org.role_id, perm.permission_id) not in have:
                    db.add(RolePermission(role_id=role_org.role_id, permission_id=perm.permission_id, permission_effect="ALLOW"))
                    have.add((role_org.role_id, perm.permission_id))
                    stats["grants"] += 1
    if role_super := roles.get("SUPER_ADMIN"):
        for perm in perms.values():
            if (role_super.role_id, perm.permission_id) not in have:
                db.add(RolePermission(role_id=role_super.role_id, permission_id=perm.permission_id,
                                      permission_effect="ALLOW"))
                stats["grants"] += 1
    db.flush()
    return stats


def ensure_staff_self(db: Session, user_id: int) -> None:
    """Give an employee the SELF-scoped STAFF_SELF role (idempotent)."""
    db.execute(text(
        "INSERT INTO user_role_assignment (user_id, role_id, scope_type, valid_from, assignment_status) "
        "SELECT :u, r.role_id, 'SELF', now(), 'ACTIVE' FROM role r WHERE r.role_code = 'STAFF_SELF' "
        "AND NOT EXISTS (SELECT 1 FROM user_role_assignment a WHERE a.user_id = :u AND a.role_id = r.role_id "
        "AND a.assignment_status = 'ACTIVE')"), {"u": user_id})
