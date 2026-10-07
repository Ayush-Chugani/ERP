"""Source-exact seed installation; existing institutional edits are preserved."""
import json
from pathlib import Path
from django.db import transaction
from . import models as m


def catalogue():
    return json.loads(Path(__file__).with_name('source_catalogue.json').read_text(encoding='utf-8'))


@transaction.atomic
def seed():
    source = catalogue()
    actions = {}
    for row in source['actions']:
        values = dict(row); code = values.pop('action_code')
        actions[code], _ = m.AccessAction.objects.get_or_create(action_code=code, defaults=values)
    permissions = {}
    for row in source['modules']:
        values = dict(row); code = values.pop('module_code')
        module, _ = m.AccessModule.objects.get_or_create(module_code=code, defaults=values)
        resource, _ = m.AccessResource.objects.get_or_create(access_module=module, resource_code='ALL',
            defaults={'resource_name': module.module_name + ' - All Resources'})
        for action_code, action in actions.items():
            permission_code = f'{code}.ALL.{action_code}'
            permissions[permission_code], _ = m.Permission.objects.get_or_create(permission_code=permission_code,
                defaults={'access_resource':resource,'access_action':action,
                          'permission_name':f'{action.action_name} {module.module_name}',
                          'is_sensitive':permission_code in source['sensitive_permissions']})
    for row in source['roles']:
        values = dict(row); code = values.pop('role_code')
        role, _ = m.Role.objects.get_or_create(role_code=code, defaults=values)
        for permission_code in source['role_permissions'][code]:
            m.RolePermission.objects.get_or_create(role=role,permission=permissions[permission_code],
                                                  defaults={'permission_effect':'ALLOW'})
    return {'actions':len(actions),'permissions':len(permissions),'roles':len(source['roles'])}
