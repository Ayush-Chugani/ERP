"""Transactional IAM mutations. All management authority is explicit and global.

Institution administrators do not get an implicit right to manage global identities.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from . import models as m
from .evaluator import Scope, has_permission, has_object_permission, usable
from .audit import record
from .security import step_up


def authorize(actor, action, proof=None):
    if not settings.IDENTITY_ACCESS_ENABLED:
        raise NotFound()
    actor=get_user_model().objects.select_for_update().get(pk=actor.pk)
    if actor.must_change_password or not usable(actor,timezone.now()) or not has_permission(actor,f'IAM.ALL.{action}','GLOBAL',0):
        raise PermissionDenied()
    if action != 'READ': step_up(actor,proof)
    return actor


def reason(value):
    if not isinstance(value,str) or not value.strip() or len(value)>500:
        raise ValidationError('A reason of 1-500 characters is required.')
    return value.strip()


def clean_save(obj):
    obj.full_clean(exclude=[f.name for f in obj._meta.fields if f.generated])
    obj.save()
    return obj


def grant_authority(actor,permission,scope):
    if not has_object_permission(actor,permission.permission_code,scopes=[Scope('GLOBAL',0),scope]):
        raise PermissionDenied('Cannot grant authority outside your effective permissions.')


@transaction.atomic
def assign_role(*, actor, user_id, role_id, scope_type, entity_id, valid_from, valid_to=None, proof=None, justification=''):
    actor=authorize(actor,'ASSIGN',proof)
    if actor.pk==user_id: raise PermissionDenied('Self-assignment is not permitted.')
    why=reason(justification); role=m.Role.objects.select_for_update().get(pk=role_id,is_active=True,is_assignable=True)
    if role.role_level != scope_type: raise ValidationError('Role level must match the selected scope.')
    scope=Scope(scope_type,user_id if scope_type=='SELF' else entity_id)
    for grant in m.RolePermission.objects.filter(role=role).select_related('permission'):
        grant_authority(actor,grant.permission,scope)
    data={} if scope_type in ('GLOBAL','SELF') else {scope_type.lower()+'_id':entity_id}
    row=m.UserRoleAssignment(user_id=user_id,role=role,scope_type=scope_type,valid_from=valid_from,
        valid_to=valid_to,assigned_by_user=actor,assignment_reason=why,**data)
    clean_save(row)
    row.refresh_from_db()
    record(actor=actor,action='ASSIGN',entity=row,after={'user_id':user_id,'role_id':role_id,'scope':scope_type,'entity_id':scope.entity_id},details={'reason':why})
    return row


@transaction.atomic
def end_assignment(*,actor,pk,proof,justification):
    actor=authorize(actor,'ASSIGN',proof); why=reason(justification)
    row=m.UserRoleAssignment.objects.select_for_update().get(pk=pk)
    if row.user_id==actor.pk: raise PermissionDenied('Another administrator must change your assignments.')
    before=row.assignment_status; row.assignment_status='REVOKED'; row.save(update_fields=['assignment_status'])
    record(actor=actor,action='ASSIGN',entity=row,before={'status':before},after={'status':'REVOKED'},details={'reason':why})
    return row


@transaction.atomic
def grant_override(*,actor,user_id,permission_id,scope_type,entity_id,effect,valid_from,valid_to,proof,justification):
    actor=authorize(actor,'ASSIGN',proof); why=reason(justification)
    if actor.pk==user_id: raise PermissionDenied('Self-overrides are not permitted.')
    permission=m.Permission.objects.get(pk=permission_id,is_active=True)
    scope=Scope(scope_type,user_id if scope_type=='SELF' else entity_id)
    if scope_type not in ('GLOBAL','SELF'):
        from django.apps import apps
        owner=apps.get_model('organization',scope_type.title())
        if not owner.objects.filter(pk=entity_id).exists(): raise ValidationError('Unknown scope entity.')
    grant_authority(actor,permission,scope)
    row=m.UserPermissionOverride(user_id=user_id,permission=permission,scope_type=scope_type,
        scope_entity_id=None if scope_type in ('GLOBAL','SELF') else entity_id,permission_effect=effect,
        valid_from=valid_from,valid_to=valid_to,granted_by_user=actor,justification=why)
    clean_save(row); record(actor=actor,action='ASSIGN',entity=row,after={'effect':effect,'scope':scope_type,'entity_id':scope.entity_id,'user_id':user_id},details={'reason':why})
    return row


@transaction.atomic
def end_override(*,actor,pk,proof,justification):
    actor=authorize(actor,'ASSIGN',proof); why=reason(justification)
    row=m.UserPermissionOverride.objects.select_for_update().get(pk=pk)
    if row.user_id==actor.pk: raise PermissionDenied('Another administrator must change your overrides.')
    row.revoked_at=timezone.now(); row.save(update_fields=['revoked_at'])
    record(actor=actor,action='ASSIGN',entity=row,after={'revoked_at':row.revoked_at},details={'reason':why})
    return row


@transaction.atomic
def request_delegation(*,actor,source_assignment_id,delegate_user_id,valid_from,valid_to,proof,justification):
    actor=authorize(actor,'ASSIGN',proof); why=reason(justification)
    source=m.UserRoleAssignment.objects.select_for_update().get(pk=source_assignment_id,user=actor,assignment_status='ACTIVE',role__is_active=True)
    if valid_from<source.valid_from or valid_to<=valid_from or (source.valid_to and valid_to>source.valid_to):
        raise ValidationError('Delegation must stay within the source validity window.')
    row=m.RoleDelegation(delegator_user=actor,delegate_user_id=delegate_user_id,source_assignment=source,
        valid_from=valid_from,valid_to=valid_to,reason=why)
    clean_save(row); record(actor=actor,action='ASSIGN',entity=row,after={'status':'PENDING'},details={'reason':why})
    return row


@transaction.atomic
def transition_delegation(*,actor,pk,status,proof,justification):
    actor=authorize(actor,'APPROVE',proof); why=reason(justification)
    row=m.RoleDelegation.objects.select_for_update().select_related('source_assignment').get(pk=pk)
    if status not in ('ACTIVE','REVOKED') or row.delegation_status not in ('PENDING','ACTIVE'):
        raise ValidationError('Invalid delegation transition.')
    if actor.pk in (row.delegator_user_id,row.delegate_user_id): raise PermissionDenied('Independent approval required.')
    source=row.source_assignment
    if status=='ACTIVE':
        if (row.valid_to<=timezone.now() or source.assignment_status!='ACTIVE' or not source.role.is_active
            or source.user_id!=row.delegator_user_id or row.valid_from<source.valid_from
            or (source.valid_to and row.valid_to>source.valid_to)):
            raise ValidationError('Source is unavailable.')
        scope=Scope(source.scope_type,row.delegate_user_id if source.scope_type=='SELF' else source.scope_entity_id)
        for grant in m.RolePermission.objects.filter(role=source.role).select_related('permission'):
            grant_authority(actor,grant.permission,scope)
        row.approved_by_user=actor
    old=row.delegation_status; row.delegation_status=status; clean_save(row)
    record(actor=actor,action='APPROVE',entity=row,before={'status':old},after={'status':status},details={'reason':why})
    return row


@transaction.atomic
def save_role(*,actor,values,proof,justification,pk=None):
    actor=authorize(actor,'CONFIGURE',proof); why=reason(justification)
    row=m.Role.objects.select_for_update().get(pk=pk) if pk else m.Role()
    allowed={'role_code','role_name','role_category','role_level','description','is_active','is_assignable','parent_role_id'}
    if set(values)-allowed: raise ValidationError('Unsupported role fields.')
    if row.pk and row.is_system_role and any(k in values and values[k]!=getattr(row,k) for k in ('role_code','role_name','role_category','role_level')):
        raise ValidationError('System role identity cannot be changed.')
    before={k:getattr(row,k) for k in values}
    for key,value in values.items(): setattr(row,key,value)
    parent=row.parent_role; seen={row.pk} if row.pk else set()
    while parent:
        if parent.pk in seen: raise ValidationError('Role hierarchy cannot contain a cycle.')
        seen.add(parent.pk); parent=parent.parent_role
    clean_save(row); record(actor=actor,action='CONFIGURE',entity=row,before=before,after=values,details={'reason':why})
    return row


@transaction.atomic
def set_matrix(*,actor,role_id,entries,proof,justification):
    actor=authorize(actor,'CONFIGURE',proof); why=reason(justification)
    role=m.Role.objects.select_for_update().get(pk=role_id)
    if m.UserRoleAssignment.objects.filter(user=actor,role=role,assignment_status='ACTIVE').exists():
        raise PermissionDenied('Another administrator must change your role matrix.')
    if len(entries)>220 or len({e['permission_id'] for e in entries})!=len(entries):
        raise ValidationError('Bounded unique permission entries required.')
    before={}; after={}
    for entry in entries:
        permission=m.Permission.objects.get(pk=entry['permission_id'],is_active=True)
        grant_authority(actor,permission,Scope('GLOBAL',0))
        effect=entry['effect']
        if effect not in ('ALLOW','DENY'): raise ValidationError('Invalid effect.')
        old=m.RolePermission.objects.filter(role=role,permission=permission).first()
        before[permission.permission_code]=old.permission_effect if old else None
        m.RolePermission.objects.update_or_create(role=role,permission=permission,defaults={'permission_effect':effect})
        after[permission.permission_code]=effect
    record(actor=actor,action='CONFIGURE',entity=role,before=before,after=after,details={'reason':why})
    return role

@transaction.atomic
def save_user(*,actor,values,proof,justification,pk=None):
    actor=authorize(actor,'UPDATE' if pk else 'CREATE',proof); why=reason(justification)
    allowed={'username','email','account_status','must_change_password','password'} if not pk else {'email','account_status','must_change_password'}
    if set(values)-allowed: raise ValidationError('Unsupported account fields.')
    if pk==actor.pk: raise PermissionDenied('Another administrator must change your account policy.')
    row=get_user_model().objects.select_for_update().get(pk=pk) if pk else get_user_model()()
    if not pk:
        from django.contrib.auth.password_validation import validate_password
        password=values.get('password',''); validate_password(password,row)
        row.set_password(password);row.must_change_password=True
    before={k:getattr(row,k) for k in values if k!='password'}
    for key,value in values.items():
        if key!='password': setattr(row,key,value)
    if pk: row.security_version+=1
    clean_save(row)
    record(actor=actor,action='UPDATE' if pk else 'CREATE',entity=row,before=before,after={k:getattr(row,k) for k in values if k!='password'},details={'reason':why})
    return row

@transaction.atomic
def transition_assignment(*,actor,pk,status,proof,justification):
    actor=authorize(actor,'ASSIGN',proof);why=reason(justification)
    row=m.UserRoleAssignment.objects.select_for_update().select_related('role').get(pk=pk)
    if row.user_id==actor.pk: raise PermissionDenied('Independent assignment management required.')
    allowed={'PENDING':{'ACTIVE','REVOKED'},'ACTIVE':{'SUSPENDED','REVOKED'},'SUSPENDED':{'ACTIVE','REVOKED'}}
    if status not in allowed.get(row.assignment_status,set()): raise ValidationError('Invalid assignment transition.')
    if status=='ACTIVE':
        if not row.role.is_active or not row.role.is_assignable or (row.valid_to and row.valid_to<=timezone.now()): raise ValidationError('Assignment is unavailable.')
        scope=Scope(row.scope_type,row.user_id if row.scope_type=='SELF' else row.scope_entity_id)
        for grant in m.RolePermission.objects.filter(role=row.role).select_related('permission'):
            grant_authority(actor,grant.permission,scope)
    old=row.assignment_status;row.assignment_status=status;row.save(update_fields=['assignment_status'])
    record(actor=actor,action='ASSIGN',entity=row,before={'status':old},after={'status':status},details={'reason':why})
    return row
