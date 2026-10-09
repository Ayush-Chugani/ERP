"""Identity and access administration: users, roles, role assignments, permission overrides and audit trail."""
import secrets
import string
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.api.deps import client_ip, forget_principals, require
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.security import hash_password
from app.db.session import get_db
from app.models.accounts import UserAccount
from app.models.identity_access import Permission, Role, RolePermission, UserRoleAssignment
from app.models.platform import AuditLog
from app.rbac import catalogue
from app.rbac.engine import Principal, reset_org_cache
from app.services import audit
from app.services import auth as auth_svc

router = APIRouter(prefix="/security", tags=["Identity and access"])
Scope = Literal["GLOBAL", "INSTITUTION", "CAMPUS", "DEPARTMENT", "PROGRAMME", "SELF"]
PRIVILEGED_ROLES = {"SUPER_ADMIN", "SYSTEM_ADMIN", "SECURITY_ADMIN", "DATABASE_ADMIN", "INSTITUTION_ADMIN"}


def temp_password() -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"{core}#{secrets.choice(string.digits)}a"


def user_out(u: UserAccount, roles: list[dict] | None = None) -> dict:
    return {"user_id": u.user_id, "username": u.username, "email": u.email, "first_name": u.first_name,
            "last_name": u.last_name, "is_active": u.is_active, "is_superuser": u.is_superuser,
            "account_status": u.account_status, "mfa_enabled": u.multi_factor_enabled,
            "must_change_password": u.must_change_password, "last_login_at": u.last_login_at,
            "locked_until": u.locked_until, "created_at": u.created_at, "roles": roles or []}


def roles_of(db: Session, user_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {i: [] for i in user_ids}
    rows = db.execute(text(
        "SELECT ura.user_role_assignment_id, ura.user_id, r.role_code, r.role_name, ura.scope_type, ura.scope_entity_id, "
        "ura.assignment_status, ura.valid_from, ura.valid_to FROM user_role_assignment ura "
        "JOIN role r ON r.role_id = ura.role_id WHERE ura.user_id = ANY(:ids) AND ura.assignment_status = 'ACTIVE' "
        "ORDER BY r.role_code"), {"ids": user_ids}).mappings()
    for r in rows:
        out[r["user_id"]].append({"assignment_id": r["user_role_assignment_id"], "role_code": r["role_code"],
                                  "role_name": r["role_name"], "scope_type": r["scope_type"],
                                  "scope_id": r["scope_entity_id"] if r["scope_type"] not in ("GLOBAL", "SELF") else None,
                                  "valid_from": r["valid_from"], "valid_to": r["valid_to"]})
    return out


def _my_institutions(principal: Principal) -> set[int] | None:
    """Organisations whose people the caller may manage; ``None`` means all (super administrator)."""
    return None if principal.is_superuser else principal.institution_ids()


def _actor_may_manage(principal: Principal, target: UserAccount) -> None:
    mine = _my_institutions(principal)
    if mine is not None and (target.is_superuser or target.institution_id not in mine):
        raise NotFound()        # someone else's organisation (or the platform owner): indistinguishable from "does not exist"


def _load_user(db: Session, principal: Principal, user_id: int) -> UserAccount:
    u = db.get(UserAccount, user_id)
    if u is None:
        raise NotFound()
    _actor_may_manage(principal, u)
    return u


# ------------------------------------------------------------------------------------------------------- users
class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9_.@-]+$")
    email: EmailStr
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    password: str | None = Field(default=None, max_length=128)
    student_id: int | None = None
    employee_id: int | None = None
    institution_id: int | None = Field(default=None, description="Organisation the login belongs to (required unless you administer exactly one)")
    role_code: str | None = Field(default=None, max_length=60, description="Optionally give the first role straight away")
    scope_type: Scope | None = None
    scope_id: int | None = None


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    is_active: bool | None = None


@router.get("/users")
def list_users(search: str | None = Query(default=None, max_length=100), page: int = Query(default=1, ge=1),
               page_size: int = Query(default=25, ge=1, le=100), principal: Principal = Depends(require("IAM", "USERS", "READ")),
               db: Session = Depends(get_db)):
    q = select(UserAccount)
    mine = _my_institutions(principal)
    if mine is not None:
        q = q.where(UserAccount.institution_id.in_(mine or {-1}))
    if search:
        like = f"%{search.strip().replace('%', '').replace('_', ' ')}%"
        q = q.where(or_(UserAccount.username.ilike(like), UserAccount.email.ilike(like),
                        UserAccount.first_name.ilike(like), UserAccount.last_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    users = db.scalars(q.order_by(UserAccount.username).limit(page_size).offset((page - 1) * page_size)).all()
    roles = roles_of(db, [u.user_id for u in users])
    return {"count": total, "page": page, "page_size": page_size,
            "next": page + 1 if page * page_size < total else None, "previous": page - 1 if page > 1 else None,
            "results": [user_out(u, roles[u.user_id]) for u in users]}


def _owning_institution(db: Session, principal: Principal, requested: int | None) -> int | None:
    mine = _my_institutions(principal)
    if requested is not None:
        if not db.execute(text("SELECT 1 FROM institution WHERE institution_id = :i"), {"i": requested}).first():
            raise NotFound("That organisation does not exist.")
        if mine is not None and requested not in mine:
            raise Forbidden("You can only create accounts inside the organisation you administer.")
        return requested
    if mine is None:
        return None
    if len(mine) == 1:
        return next(iter(mine))
    raise Invalid("institution_id is required because you administer more than one organisation.",
                  details={"institution_id": ["Required."]})


@router.post("/users", status_code=201)
def create_user(body: UserCreate, request: Request, principal: Principal = Depends(require("IAM", "USERS", "CREATE")),
                db: Session = Depends(get_db)):
    if db.scalar(select(UserAccount.user_id).where(func.lower(UserAccount.username) == body.username.lower())):
        raise Conflict("That username is already taken.", code="duplicate")
    generated = body.password is None
    password = body.password or temp_password()
    institution_id = _owning_institution(db, principal, body.institution_id)
    for kind, table, pid in (("student_id", "student", body.student_id), ("employee_id", "employee", body.employee_id)):
        if pid is None:
            continue
        owner = db.execute(text(f"SELECT institution_id FROM {table} WHERE {table}_id = :p"), {"p": pid}).first()
        if owner is None:
            raise NotFound("That person does not exist.")
        mine = _my_institutions(principal)
        if mine is not None and owner[0] not in mine:
            raise NotFound("That person does not exist.")
        if db.execute(text(f"SELECT 1 FROM person_account_link WHERE {kind} = :p"), {"p": pid}).first():
            raise Conflict("That person already has a login.", code="duplicate")
        if institution_id is None:
            institution_id = owner[0]
    user = UserAccount(username=body.username, email=body.email, first_name=body.first_name, last_name=body.last_name,
                       password_hash="!", account_status="ACTIVE", is_active=True, must_change_password=True,
                       institution_id=institution_id)
    auth_svc.validate_password(password, user)
    user.password_hash = hash_password(password)
    db.add(user)
    db.flush()
    for kind, pid in (("student_id", body.student_id), ("employee_id", body.employee_id)):
        if pid is not None:
            db.execute(text(f"INSERT INTO person_account_link ({kind}, user_id, created_at) VALUES (:p, :u, now())"),
                       {"p": pid, "u": user.user_id})
    if body.employee_id is not None:
        catalogue.ensure_staff_self(db, user.user_id)
    if body.role_code:
        role = db.scalar(select(Role).where(Role.role_code == body.role_code, Role.is_active))
        scope_type = body.scope_type or (role.role_level if role and role.role_level != "GLOBAL" else None)
        scope_id = body.scope_id
        if scope_type == "INSTITUTION" and scope_id is None:
            scope_id = institution_id
        if scope_type is None:
            raise Invalid("scope_type is required for this role.")
        _assign(db, principal, user, body.role_code, scope_type, scope_id, None, "Assigned when the account was created",
                request.state.request_id, client_ip(request))
    audit.record(db, principal, action="create", module="IAM", resource="user_account", record_id=user.user_id,
                 after={"username": user.username, "email": user.email}, request_id=request.state.request_id,
                 ip=client_ip(request))
    db.commit()
    out = user_out(user)
    if generated:
        out["temporary_password"] = password   # shown once; the user must change it at first sign-in
    return out


@router.get("/users/{user_id}")
def get_user(user_id: int, principal: Principal = Depends(require("IAM", "USERS", "READ")), db: Session = Depends(get_db)):
    u = _load_user(db, principal, user_id)
    return user_out(u, roles_of(db, [user_id])[user_id])


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, request: Request,
                principal: Principal = Depends(require("IAM", "USERS", "UPDATE")), db: Session = Depends(get_db)):
    u = _load_user(db, principal, user_id)
    changes = body.model_dump(exclude_unset=True)
    if "is_active" in changes and user_id == principal.user_id and not changes["is_active"]:
        raise Invalid("You cannot deactivate your own account.")
    before = {k: getattr(u, k) for k in changes}
    for k, v in changes.items():
        setattr(u, k, v)
    if "is_active" in changes:
        u.account_status = "ACTIVE" if changes["is_active"] else "DISABLED"
        if not changes["is_active"]:
            auth_svc.revoke_all(db, u, "account disabled")
    audit.record(db, principal, action="update", module="IAM", resource="user_account", record_id=user_id,
                 before=before, after=changes, request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    forget_principals(user_id)
    return user_out(u, roles_of(db, [user_id])[user_id])


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, request: Request, principal: Principal = Depends(require("IAM", "USERS", "UPDATE")),
                   db: Session = Depends(get_db)):
    u = _load_user(db, principal, user_id)
    password = temp_password()
    auth_svc.set_password(db, u, password, must_change=True)
    u.failed_login_count, u.locked_until = 0, None
    audit.record(db, principal, action="reset_password", module="IAM", resource="user_account", record_id=user_id,
                 request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    forget_principals(user_id)
    return {"temporary_password": password}


@router.post("/users/{user_id}/unlock", status_code=204)
def unlock(user_id: int, principal: Principal = Depends(require("IAM", "USERS", "UPDATE")), db: Session = Depends(get_db)):
    u = _load_user(db, principal, user_id)
    u.failed_login_count, u.locked_until = 0, None
    db.commit()
    return Response(status_code=204)


@router.post("/users/{user_id}/revoke-sessions", status_code=204)
def revoke_sessions(user_id: int, principal: Principal = Depends(require("IAM", "USERS", "UPDATE")),
                    db: Session = Depends(get_db)):
    u = _load_user(db, principal, user_id)
    auth_svc.revoke_all(db, u, "revoked by administrator")
    db.commit()
    forget_principals(user_id)
    return Response(status_code=204)


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: int | None = None
    employee_id: int | None = None


@router.post("/users/{user_id}/link-person", status_code=204)
def link_person(user_id: int, body: LinkIn, request: Request,
                principal: Principal = Depends(require("IAM", "USERS", "ASSIGN")), db: Session = Depends(get_db)):
    """Tie a login to a student or staff record; this link is what makes SELF-scoped access work."""
    if (body.student_id is None) == (body.employee_id is None):
        raise Invalid("Provide exactly one of student_id or employee_id.")
    user = _load_user(db, principal, user_id)
    kind, pid, table = ("student_id", body.student_id, "student") if body.student_id else (
        "employee_id", body.employee_id, "employee")
    owner = db.execute(text(f"SELECT institution_id FROM {table} WHERE {table}_id = :p"), {"p": pid}).first()
    mine = _my_institutions(principal)
    if owner is None or (mine is not None and owner[0] not in mine):
        raise NotFound("That person does not exist.")
    if user.institution_id is None and not user.is_superuser:
        user.institution_id = owner[0]
    if db.execute(text(f"SELECT 1 FROM person_account_link WHERE {kind} = :p"), {"p": pid}).first():
        raise Conflict("That person already has a login.", code="duplicate")
    if db.execute(text(f"SELECT 1 FROM person_account_link WHERE user_id = :u AND {kind} IS NOT NULL"), {"u": user_id}).first():
        raise Conflict("This user is already linked to a person of that type.", code="duplicate")
    db.execute(text(f"INSERT INTO person_account_link ({kind}, user_id, created_at) VALUES (:p, :u, now())"),
               {"p": pid, "u": user_id})
    if kind == "employee_id":
        catalogue.ensure_staff_self(db, user_id)
    audit.record(db, principal, action="link_person", module="IAM", resource="person_account_link", record_id=user_id,
                 after={kind: pid}, request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    forget_principals(user_id)
    return Response(status_code=204)


# ------------------------------------------------------------------------------------------------------- roles
@router.get("/roles")
def list_roles(principal: Principal = Depends(require("IAM", "ROLES", "READ")), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT r.role_id, r.role_code, r.role_name, r.role_category, r.role_level, r.description, r.is_system_role, "
        "r.is_assignable, r.is_active, (SELECT count(*) FROM role_permission rp WHERE rp.role_id = r.role_id) AS permissions "
        "FROM role r ORDER BY r.role_code")).mappings().all()
    out = [dict(r) for r in rows]
    if not principal.is_superuser:
        out = [r for r in out if r["is_assignable"] and r["is_active"] and r["role_code"] not in PRIVILEGED_ROLES]
    return {"results": out}


@router.get("/roles/{role_id}")
def role_detail(role_id: int, principal: Principal = Depends(require("IAM", "ROLES", "READ")), db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound()
    perms = db.execute(text(
        "SELECT p.permission_code, rp.permission_effect FROM role_permission rp "
        "JOIN permission p ON p.permission_id = rp.permission_id WHERE rp.role_id = :r ORDER BY p.permission_code"),
        {"r": role_id}).all()
    return {"role_id": role.role_id, "role_code": role.role_code, "role_name": role.role_name,
            "role_level": role.role_level, "description": role.description, "is_system_role": role.is_system_role,
            "permissions": [{"code": c, "effect": e} for c, e in perms]}


class RolePermissionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow: list[str] = Field(default_factory=list, max_length=3000)
    deny: list[str] = Field(default_factory=list, max_length=3000)


@router.put("/roles/{role_id}/permissions", status_code=204)
def set_role_permissions(role_id: int, body: RolePermissionsIn, request: Request,
                         principal: Principal = Depends(require("IAM", "ROLES", "CONFIGURE")),
                         db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound()
    if role.role_code in PRIVILEGED_ROLES and not principal.is_superuser:
        raise Forbidden("Only a super administrator can change this role.")
    if role.role_code == "SUPER_ADMIN":
        raise Invalid("SUPER_ADMIN always holds every permission.")
    wanted = {c: "ALLOW" for c in body.allow} | {c: "DENY" for c in body.deny}
    known = {p.permission_code: p.permission_id for p in db.scalars(select(Permission).where(
        Permission.permission_code.in_(list(wanted))))}
    unknown = sorted(set(wanted) - set(known))
    if unknown:
        raise Invalid("Unknown permission codes.", details={"permissions": unknown[:20]})
    if not principal.is_superuser:
        mine = set(principal.allowed_codes())
        extra = sorted(c for c, e in wanted.items() if e == "ALLOW" and c not in mine)
        if extra:
            raise Forbidden("You cannot grant permissions you do not hold yourself: " + ", ".join(extra[:5]))
    db.execute(text("DELETE FROM role_permission WHERE role_id = :r"), {"r": role_id})
    for code, effect in wanted.items():
        db.add(RolePermission(role_id=role_id, permission_id=known[code], permission_effect=effect))
    audit.record(db, principal, action="set_permissions", module="IAM", resource="role", record_id=role_id,
                 after={"allow": len(body.allow), "deny": len(body.deny)}, request_id=request.state.request_id,
                 ip=client_ip(request))
    db.commit()
    forget_principals()
    return Response(status_code=204)


@router.get("/permissions")
def list_permissions(module: str | None = None, principal: Principal = Depends(require("IAM", "ROLES", "READ")),
                     db: Session = Depends(get_db)):
    q = select(Permission.permission_code, Permission.permission_name, Permission.is_sensitive).order_by(
        Permission.permission_code)
    if module:
        q = q.where(Permission.permission_code.like(f"{module.upper()}.%"))
    return {"results": [{"code": c, "name": n, "sensitive": s} for c, n, s in db.execute(q.limit(5000))]}


# ----------------------------------------------------------------------------------------------- assignments
class AssignmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int
    role_code: str = Field(max_length=60)
    scope_type: Scope
    scope_id: int | None = None
    valid_to: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


def _assign(db: Session, principal: Principal, user: UserAccount, role_code: str, scope_type: str, scope_id: int | None,
            valid_to: datetime | None, reason: str | None, request_id: str, ip: str | None) -> UserRoleAssignment:
    """Validate and create one role assignment. Shared by the assignment endpoint and one-step account creation."""
    role = db.scalar(select(Role).where(Role.role_code == role_code, Role.is_active))
    if role is None:
        raise NotFound("User or role not found.")
    _actor_may_manage(principal, user)
    if not role.is_assignable:
        raise Invalid("This role cannot be assigned directly.")
    if role.role_code in PRIVILEGED_ROLES and not principal.is_superuser:
        raise Forbidden("Only a super administrator can assign this role.")
    if role.role_level != "GLOBAL" and scope_type != role.role_level and role.role_level != "SELF":
        raise Invalid(f"{role.role_code} must be assigned at {role.role_level} level.")
    needs_id = scope_type not in ("GLOBAL", "SELF")
    if needs_id and not scope_id:
        raise Invalid("scope_id is required for this scope.")
    if not needs_id and scope_id:
        raise Invalid("scope_id must be omitted for GLOBAL and SELF scopes.")
    if scope_type == "GLOBAL" and not principal.is_superuser:
        raise Forbidden("Only a super administrator can assign global roles.")
    if needs_id and not principal.is_superuser:
        covered = principal.scope_for("IAM", "USERS", "ASSIGN")
        level_ids = {"INSTITUTION": covered.institutions, "CAMPUS": covered.campuses,
                     "DEPARTMENT": covered.departments, "PROGRAMME": covered.programmes}[scope_type]
        if scope_id not in level_ids:
            raise Forbidden("You can only assign roles inside the organisation you administer.")
    if not principal.is_superuser:
        # Reference data and the (institution-scoped) audit trail do not count; a module-wide grant covers its resources.
        mine = set(principal.allowed_codes())
        wanted = {c for (c,) in db.execute(text(
            "SELECT p.permission_code FROM role_permission rp JOIN permission p USING (permission_id) "
            "WHERE rp.role_id = :r AND rp.permission_effect = 'ALLOW' AND p.permission_code NOT LIKE 'REFERENCE.%' "
            "AND p.permission_code NOT LIKE 'AUDIT.%'"), {"r": role.role_id})}
        missing = {c for c in wanted if c not in mine and f"{c.split('.')[0]}.ALL.{c.split('.')[2]}" not in mine}
        if missing:
            raise Forbidden("You cannot assign a role that grants permissions you do not hold yourself.")
    col = {"INSTITUTION": "institution_id", "CAMPUS": "campus_id", "DEPARTMENT": "department_id",
           "PROGRAMME": "programme_id"}.get(scope_type)
    a = UserRoleAssignment(user_id=user.user_id, role_id=role.role_id, scope_type=scope_type,
                           valid_from=func.now(), valid_to=valid_to, assignment_status="ACTIVE",
                           assignment_reason=reason, assigned_by_user_id=principal.user_id)
    if col:
        setattr(a, col, scope_id)
    db.add(a)
    db.flush()
    if role.role_code in catalogue.AUTO_STAFF_SELF:
        catalogue.ensure_staff_self(db, user.user_id)
    audit.record(db, principal, action="assign_role", module="IAM", resource="user_role_assignment",
                 record_id=a.user_role_assignment_id,
                 after={"user_id": user.user_id, "role": role.role_code, "scope": scope_type, "scope_id": scope_id},
                 request_id=request_id, ip=ip)
    return a


@router.post("/role-assignments", status_code=201)
def assign_role(body: AssignmentIn, request: Request, principal: Principal = Depends(require("IAM", "USERS", "ASSIGN")),
                db: Session = Depends(get_db)):
    user = db.get(UserAccount, body.user_id)
    if user is None or not db.scalar(select(Role.role_id).where(Role.role_code == body.role_code, Role.is_active)):
        raise NotFound("User or role not found.")
    a = _assign(db, principal, user, body.role_code, body.scope_type, body.scope_id, body.valid_to, body.reason,
                request.state.request_id, client_ip(request))
    db.commit()
    forget_principals(user.user_id)
    return {"assignment_id": a.user_role_assignment_id}


@router.delete("/role-assignments/{assignment_id}", status_code=204)
def revoke_assignment(assignment_id: int, request: Request,
                      principal: Principal = Depends(require("IAM", "USERS", "ASSIGN")), db: Session = Depends(get_db)):
    a = db.get(UserRoleAssignment, assignment_id)
    if a is None or a.assignment_status != "ACTIVE":
        raise NotFound()
    role = db.get(Role, a.role_id)
    target = db.get(UserAccount, a.user_id)
    _actor_may_manage(principal, target)
    if role.role_code in PRIVILEGED_ROLES and not principal.is_superuser:
        raise Forbidden("Only a super administrator can revoke this role.")
    if a.user_id == principal.user_id and role.role_code == "SUPER_ADMIN":
        raise Invalid("You cannot remove your own super administrator role.")
    a.assignment_status = "REVOKED"
    a.valid_to = datetime.now(UTC)
    audit.record(db, principal, action="revoke_role", module="IAM", resource="user_role_assignment",
                 record_id=assignment_id, before={"role": role.role_code, "user_id": a.user_id},
                 request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    forget_principals(a.user_id)
    reset_org_cache()
    return Response(status_code=204)


# ----------------------------------------------------------------------------------------------------- audit
@router.get("/audit")
def audit_trail(module: str | None = None, resource: str | None = None, record_id: str | None = None,
                actor: int | None = None, action: str | None = None, page: int = Query(default=1, ge=1),
                page_size: int = Query(default=50, ge=1, le=200),
                principal: Principal = Depends(require("AUDIT", "AUDIT_LOG", "READ")), db: Session = Depends(get_db)):
    q = select(AuditLog)
    scope = principal.scope_for("AUDIT", "AUDIT_LOG", "READ")
    if not scope.everything:
        q = q.where(AuditLog.institution_id.in_(scope.institutions or {-1}))
    for col, val in ((AuditLog.module, module), (AuditLog.resource, resource), (AuditLog.record_id, record_id),
                     (AuditLog.actor_user_id, actor), (AuditLog.action, action)):
        if val is not None:
            q = q.where(col == val)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditLog.audit_id.desc()).limit(page_size).offset((page - 1) * page_size)).all()
    return {"count": total, "page": page, "page_size": page_size, "results": [{
        "audit_id": r.audit_id, "occurred_at": r.occurred_at, "actor_user_id": r.actor_user_id, "action": r.action,
        "module": r.module, "resource": r.resource, "record_id": r.record_id, "before": r.before, "after": r.after,
        "reason": r.reason, "ip_address": r.ip_address, "request_id": r.request_id} for r in rows]}


# ------------------------------------------------------------------------------------------------- organisations
class OrganisationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)
    university_id: int | None = Field(default=None, description="Defaults to the only university on record")
    email: EmailStr | None = None
    admin_username: str = Field(min_length=3, max_length=150, pattern=r"^[A-Za-z0-9_.@-]+$")
    admin_email: EmailStr
    admin_first_name: str = Field(default="", max_length=150)
    admin_last_name: str = Field(default="", max_length=150)
    admin_password: str | None = Field(default=None, max_length=128, description="Generated when omitted")


@router.get("/organisations")
def list_organisations(principal: Principal = Depends(require("IAM", "USERS", "READ")), db: Session = Depends(get_db)):
    """Organisations (institutions) with their administrators and head-count. Super administrators see all of them;
    organisation administrators see their own."""
    mine = _my_institutions(principal)
    rows = db.execute(text(
        "SELECT i.institution_id, i.institution_code, i.institution_name, i.is_active, "
        "(SELECT count(*) FROM user_account u WHERE u.institution_id = i.institution_id) AS accounts, "
        "(SELECT count(*) FROM student s WHERE s.institution_id = i.institution_id) AS students, "
        "(SELECT count(*) FROM employee e WHERE e.institution_id = i.institution_id) AS staff, "
        "COALESCE((SELECT json_agg(u.username ORDER BY u.username) FROM user_account u "
        "JOIN user_role_assignment a ON a.user_id = u.user_id AND a.assignment_status = 'ACTIVE' "
        "JOIN role r ON r.role_id = a.role_id AND r.role_code = 'INSTITUTION_ADMIN' "
        "WHERE a.institution_id = i.institution_id), '[]'::json) AS administrators "
        "FROM institution i WHERE (:all OR i.institution_id = ANY(:ids)) ORDER BY i.institution_name"),
        {"all": mine is None, "ids": sorted(mine or [])}).mappings().all()
    return {"results": [dict(r) for r in rows]}


@router.post("/organisations", status_code=201)
def create_organisation(body: OrganisationCreate, request: Request,
                        principal: Principal = Depends(require("IAM", "USERS", "CREATE")), db: Session = Depends(get_db)):
    """Super administrators only: create an organisation and its first administrator in one step.
    The administrator then creates every other login (registrar, faculty, students, ...) inside that organisation."""
    if not principal.is_superuser:
        raise Forbidden("Only a super administrator can create organisations.")
    if db.scalar(select(UserAccount.user_id).where(func.lower(UserAccount.username) == body.admin_username.lower())):
        raise Conflict("That username is already taken.", code="duplicate")
    if db.execute(text("SELECT 1 FROM institution WHERE lower(institution_code) = lower(:c)"), {"c": body.code}).first():
        raise Conflict("An organisation with that code already exists.", code="duplicate")
    university_id = body.university_id
    if university_id is None:
        ids = [u for (u,) in db.execute(text("SELECT university_id FROM university ORDER BY university_id LIMIT 2"))]
        if len(ids) != 1:
            raise Invalid("university_id is required." if ids else "Create a university first.",
                          details={"university_id": ["Required."]})
        university_id = ids[0]
    elif not db.execute(text("SELECT 1 FROM university WHERE university_id = :u"), {"u": university_id}).first():
        raise NotFound("That university does not exist.")
    inst_id = db.execute(text(
        "INSERT INTO institution (institution_code, institution_name, email, university_id) VALUES (:c, :n, :e, :u) "
        "RETURNING institution_id"), {"c": body.code, "n": body.name, "e": body.email, "u": university_id}).scalar()
    generated = body.admin_password is None
    password = body.admin_password or temp_password()
    admin = UserAccount(username=body.admin_username, email=body.admin_email, first_name=body.admin_first_name,
                        last_name=body.admin_last_name, password_hash="!", account_status="ACTIVE", is_active=True,
                        must_change_password=True, institution_id=inst_id)
    auth_svc.validate_password(password, admin)
    admin.password_hash = hash_password(password)
    db.add(admin)
    db.flush()
    _assign(db, principal, admin, "INSTITUTION_ADMIN", "INSTITUTION", inst_id, None, "Organisation created",
            request.state.request_id, client_ip(request))
    audit.record(db, principal, action="create", module="INSTITUTION", resource="institution", record_id=inst_id,
                 after={"code": body.code, "name": body.name, "administrator": body.admin_username},
                 request_id=request.state.request_id, ip=client_ip(request))
    db.commit()
    reset_org_cache()
    out = {"institution": {"institution_id": inst_id, "code": body.code, "name": body.name},
           "administrator": {"user_id": admin.user_id, "username": admin.username, "email": admin.email,
                             "portal": "Organisation administrator"}}
    if generated:
        out["administrator"]["temporary_password"] = password     # shown once; changed at first sign-in
    return out
