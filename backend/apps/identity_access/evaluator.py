"""Exact-scope evaluation; object ancestry is an explicit caller-owned contract."""
from dataclasses import dataclass
from django.db.models import Q, F
from django.utils import timezone
from . import models as m

SCOPES = frozenset(('GLOBAL', 'INSTITUTION', 'CAMPUS', 'DEPARTMENT', 'PROGRAMME', 'SELF'))


@dataclass(frozen=True)
class Scope:
    kind: str
    entity_id: int

    def __post_init__(self):
        if self.kind not in SCOPES or type(self.entity_id) is not int:
            raise ValueError('Invalid scope.')
        if (self.kind == 'GLOBAL' and self.entity_id != 0) or (self.kind != 'GLOBAL' and self.entity_id <= 0):
            raise ValueError('Invalid scope entity.')


def window(now, prefix=''):
    return Q(**{prefix + 'valid_from__lte': now}) & (
        Q(**{prefix + 'valid_to__isnull': True}) | Q(**{prefix + 'valid_to__gt': now}))


def usable(user, now):
    return bool(user and user.is_authenticated and user.is_active
                and user.account_status == 'ACTIVE'
                and (user.locked_until is None or user.locked_until <= now))


def active_assignments(now):
    return m.UserRoleAssignment.objects.filter(window(now), assignment_status='ACTIVE',
                                               role__is_active=True)


def _scope(assignment, principal_id):
    return Scope(assignment.scope_type, principal_id if assignment.scope_type == 'SELF'
                 else assignment.scope_entity_id)


def evidence(user, permission_code, *, at=None, _source_only=False):
    """Internal evidence only. Never expose traces without administrative authorization."""
    now = at or timezone.now()
    # Always refresh persisted state, including for an already-authenticated request.
    from django.contrib.auth import get_user_model
    if not user or not user.is_authenticated:
        return []
    user = get_user_model().objects.filter(pk=user.pk).first()
    if not usable(user, now):
        return []
    permission = m.Permission.objects.filter(permission_code=permission_code,
        is_active=True, access_resource__is_active=True,
        access_resource__access_module__is_active=True, access_action__is_active=True).first()
    if permission is None:
        return []
    assignments = active_assignments(now)
    direct = list(assignments.filter(user=user))
    delegated = m.RoleDelegation.objects.filter(window(now), delegate_user=user,
        delegation_status='ACTIVE', source_assignment__in=assignments,
        delegator_user=F('source_assignment__user'),
        delegator_user__is_active=True, delegator_user__account_status='ACTIVE',
        valid_from__gte=F('source_assignment__valid_from')).filter(
        Q(source_assignment__valid_to__isnull=True) |
        Q(valid_to__lte=F('source_assignment__valid_to'))).select_related('source_assignment')
    delegated = [] if _source_only else list(delegated.filter(Q(delegator_user__locked_until__isnull=True) |
                                     Q(delegator_user__locked_until__lte=now)))
    roles = {a.role_id for a in direct} | {d.source_assignment.role_id for d in delegated}
    effects = dict(m.RolePermission.objects.filter(role_id__in=roles, permission=permission)
                   .values_list('role_id', 'permission_effect'))
    rows = []
    for a, source in [(a, 'DIRECT') for a in direct] + [(d.source_assignment, 'DELEGATED') for d in delegated]:
        if a.role_id in effects:
            effect=effects[a.role_id]
            if source == 'DELEGATED':
                source_scopes={Scope('GLOBAL',0), _scope(a,a.user_id)}
                source_rows=evidence(a.user,permission_code,at=now,_source_only=True)
                if any(r['effect']=='DENY' and r['scope'] in source_scopes for r in source_rows):
                    effect='DENY'
            rows.append({'scope': _scope(a, user.pk), 'effect': effect,
                         'source': source, 'assignment_id': a.pk})
    for override in m.UserPermissionOverride.objects.filter(window(now), user=user, permission=permission, revoked_at__isnull=True):
        entity = 0 if override.scope_type == 'GLOBAL' else user.pk if override.scope_type == 'SELF' else override.scope_entity_id
        rows.append({'scope': Scope(override.scope_type, entity), 'effect': override.permission_effect,
                     'source': 'OVERRIDE', 'override_id': override.pk})
    return rows


def effective_effect(user, permission_code, scopes, *, at=None):
    scopes = frozenset(scopes)
    effects = {r['effect'] for r in evidence(user, permission_code, at=at) if r['scope'] in scopes}
    return 'DENY' if 'DENY' in effects else 'ALLOW' if 'ALLOW' in effects else None


def has_permission(user, permission_code, scope_type, scope_entity_id, *, at=None):
    return effective_effect(user, permission_code, [Scope(scope_type, scope_entity_id)], at=at) == 'ALLOW'


def has_object_permission(user, permission_code, *, scopes, at=None):
    """Scopes MUST come from a registered business adapter, never request input.

    Include GLOBAL and only actual ancestors; SELF uses login identity, not person ID.
    ALL-resource matching is explicit here and DENY across either code wins.
    """
    parts = permission_code.split('.')
    if len(parts) != 3:
        return False
    # A missing concrete permission is a configuration error, not a wildcard grant.
    if not m.Permission.objects.filter(permission_code=permission_code, is_active=True,
            access_resource__is_active=True, access_resource__access_module__is_active=True,
            access_action__is_active=True).exists():
        return False
    codes = {permission_code, f'{parts[0]}.ALL.{parts[2]}'}
    scopes = tuple(scopes)
    effects = {effective_effect(user, code, scopes, at=at) for code in codes}
    return 'ALLOW' in effects and 'DENY' not in effects
