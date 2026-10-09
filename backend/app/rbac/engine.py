"""Role-based access control with institution / campus / department / programme / self scopes.

Permissions are codes of the form ``MODULE.RESOURCE.ACTION``. A grant of ``MODULE.ALL.ACTION`` covers every resource
of the module. Each grant carries a scope; rows are visible when any of their organisational attributes falls
inside a granted scope. ``DENY`` grants always win over ``ALLOW`` grants for the same scope.
"""
import time
from dataclasses import dataclass, field
from threading import Lock

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.accounts import UserAccount
from app.models.organization import Campus, Department, Programme

LEVELS = ("institution", "campus", "department", "programme")


@dataclass
class ScopeSet:
    """Set of organisational entities a principal may act on for one permission."""

    everything: bool = False
    institutions: set[int] = field(default_factory=set)
    campuses: set[int] = field(default_factory=set)
    departments: set[int] = field(default_factory=set)
    programmes: set[int] = field(default_factory=set)
    own: bool = False  # SELF scope: records that belong to the principal

    @property
    def empty(self) -> bool:
        return not (self.everything or self.institutions or self.campuses or self.departments or self.programmes
                    or self.own)

    @property
    def organisational(self) -> bool:
        """True when at least one non-SELF scope is held (needed for tables without organisational columns)."""
        return bool(self.everything or self.institutions or self.campuses or self.departments or self.programmes)

    def for_level(self, level: str) -> set[int]:
        return {"institution": self.institutions, "campus": self.campuses, "department": self.departments,
                "programme": self.programmes}[level]


@dataclass(frozen=True)
class Grant:
    code: str
    scope_type: str
    scope_id: int
    effect: str


class OrgTree:
    def __init__(self, campus_inst: dict[int, int], dept_campus: dict[int, int], prog_dept: dict[int, int]):
        self.campus_inst, self.dept_campus, self.prog_dept = campus_inst, dept_campus, prog_dept

    def campuses_of(self, institutions: set[int]) -> set[int]:
        return {c for c, i in self.campus_inst.items() if i in institutions}

    def departments_of(self, campuses: set[int]) -> set[int]:
        return {d for d, c in self.dept_campus.items() if c in campuses}

    def programmes_of(self, departments: set[int]) -> set[int]:
        return {p for p, d in self.prog_dept.items() if d in departments}


_tree_cache: tuple[float, OrgTree] | None = None
_tree_lock = Lock()


def org_tree(db: Session, ttl: float = 30.0) -> OrgTree:
    global _tree_cache
    now = time.monotonic()
    with _tree_lock:
        if _tree_cache and now - _tree_cache[0] < ttl:
            return _tree_cache[1]
    tree = OrgTree(
        {c: i for c, i in db.execute(select(Campus.campus_id, Campus.institution_id))},
        {d: c for d, c in db.execute(select(Department.department_id, Department.campus_id))},
        {p: d for p, d in db.execute(select(Programme.programme_id, Programme.department_id))},
    )
    with _tree_lock:
        _tree_cache = (now, tree)
    return tree


def reset_org_cache() -> None:
    global _tree_cache
    with _tree_lock:
        _tree_cache = None


@dataclass
class Principal:
    user_id: int
    username: str
    email: str
    full_name: str
    is_superuser: bool
    must_change_password: bool
    session_id: str | None
    grants: list[Grant]
    student_ids: set[int]
    employee_ids: set[int]
    role_codes: list[str]
    tree: OrgTree
    code_roles: dict[str, set[str]] = field(default_factory=dict)   # permission code -> roles that grant it

    # ---- permission checks -------------------------------------------------------------------------------
    # Highly sensitive resources are never covered by a module-wide MODULE.ALL.* grant: the specific code is required.
    SPECIFIC_ONLY = frozenset({"EMPLOYEE_AADHAAR", "EMPLOYEE_PAN", "EMPLOYEE_BANK_ACCOUNT"})

    @classmethod
    def codes(cls, module: str, resource: str, action: str) -> tuple[str, ...]:
        module, resource, action = module.upper(), resource.upper(), action.upper()
        if resource in cls.SPECIFIC_ONLY:
            return (f"{module}.{resource}.{action}",)
        return (f"{module}.{resource}.{action}", f"{module}.ALL.{action}")

    def scope_for(self, module: str, resource: str, action: str) -> ScopeSet:
        if self.is_superuser:
            return ScopeSet(everything=True, own=True)
        wanted = self.codes(module, resource, action)
        allow, deny = ScopeSet(), ScopeSet()
        for g in self.grants:
            if g.code not in wanted:
                continue
            self._add(allow if g.effect == "ALLOW" else deny, g)
        if deny.everything:
            return ScopeSet()
        result = self._expand(allow)
        deny_x = self._expand(deny)
        for level in LEVELS:
            result.for_level(level).difference_update(deny_x.for_level(level))
        result.own = result.own and not deny_x.own
        return result

    def _add(self, target: ScopeSet, g: Grant) -> None:
        t = g.scope_type
        if t == "GLOBAL":
            target.everything = True
        elif t == "SELF":
            target.own = True
        elif t == "INSTITUTION":
            target.institutions.add(g.scope_id)
        elif t == "CAMPUS":
            target.campuses.add(g.scope_id)
        elif t == "DEPARTMENT":
            target.departments.add(g.scope_id)
        elif t == "PROGRAMME":
            target.programmes.add(g.scope_id)

    def _expand(self, s: ScopeSet) -> ScopeSet:
        campuses = set(s.campuses) | self.tree.campuses_of(s.institutions)
        departments = set(s.departments) | self.tree.departments_of(campuses)
        programmes = set(s.programmes) | self.tree.programmes_of(departments)
        return ScopeSet(s.everything, set(s.institutions), campuses, departments, programmes, s.own)

    def can(self, module: str, resource: str, action: str) -> bool:
        return not self.scope_for(module, resource, action).empty

    def granting_roles(self, module: str, resource: str, action: str) -> set[str]:
        """Roles that supply the permission (empty for super administrators and direct overrides)."""
        out: set[str] = set()
        for code in self.codes(module, resource, action):
            out |= self.code_roles.get(code, set())
        return out

    def modules(self) -> list[str]:
        if self.is_superuser:
            return []
        return sorted({g.code.split(".")[0] for g in self.grants if g.effect == "ALLOW"})

    def allowed_codes(self) -> list[str]:
        return sorted({g.code for g in self.grants if g.effect == "ALLOW"})

    def institution_ids(self) -> set[int]:
        """Institutions the principal can act within (used to default institution_id on create)."""
        out: set[int] = set()
        for g in self.grants:
            if g.effect != "ALLOW":
                continue
            if g.scope_type == "INSTITUTION":
                out.add(g.scope_id)
            elif g.scope_type == "CAMPUS" and g.scope_id in self.tree.campus_inst:
                out.add(self.tree.campus_inst[g.scope_id])
            elif g.scope_type == "DEPARTMENT" and g.scope_id in self.tree.dept_campus:
                out.add(self.tree.campus_inst.get(self.tree.dept_campus[g.scope_id], 0))
        out.discard(0)
        return out


def load_principal(db: Session, user: UserAccount, session_id: str | None = None) -> Principal:
    rows = db.execute(text(
        "SELECT permission_code, scope_type, scope_entity_id, permission_effect "
        "FROM v_effective_user_permission WHERE user_id = :u"), {"u": user.user_id}).all()
    grants = [Grant(code, scope, int(sid or 0), effect) for code, scope, sid, effect in rows]
    links = db.execute(text("SELECT student_id, employee_id FROM person_account_link WHERE user_id = :u"),
                       {"u": user.user_id}).all()
    roles = [r for (r,) in db.execute(text("SELECT DISTINCT role_code FROM v_active_user_role WHERE user_id = :u "
                                           "ORDER BY role_code"), {"u": user.user_id})]
    code_roles: dict[str, set[str]] = {}
    for code, role_code in db.execute(text(
            "SELECT permission_code, role_code FROM v_active_role_permission WHERE user_id = :u AND permission_effect = 'ALLOW'"),
            {"u": user.user_id}):
        code_roles.setdefault(code, set()).add(role_code)
    full = f"{user.first_name} {user.last_name}".strip() or user.username
    return Principal(
        user_id=user.user_id, username=user.username, email=user.email, full_name=full,
        is_superuser=bool(user.is_superuser), must_change_password=bool(user.must_change_password),
        session_id=session_id, grants=grants,
        student_ids={s for s, _ in links if s}, employee_ids={e for _, e in links if e},
        role_codes=roles, tree=org_tree(db), code_roles=code_roles,
    )
