"""Generate the reviewed, additive M15 model foundation from the source contract.

No database access. Identity links remain projections of the existing People owner.
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'Manuals/M15_prompt_pack_extracted.txt').read_text(encoding='utf-8')
target = root / 'backend/apps/identity_access'
target.mkdir(exist_ok=True)
for directory in ('migrations', 'tests', 'management', 'management/commands'):
    (target / directory).mkdir(exist_ok=True)
    (target / directory / '__init__.py').touch()
(target / '__init__.py').touch()
tables = dict(re.findall(r'CREATE TABLE (\w+) \((.*?)\n\) ENGINE', source, re.S))
external = {'user_account': 'accounts.User', 'student': 'people_master.Student',
    'employee': 'people_master.Employee', **{v: 'organization.' + v.title() for v in
    ('institution', 'campus', 'department', 'programme')}}
names = {t: ''.join(p.title() for p in t.split('_')) for t in tables}
output = ['from django.conf import settings', 'from django.db import models',
    'from django.db.models import Q, F, Case, When, Value',
    'from django.db.models.functions import Coalesce', 'from django.utils import timezone',
    'from apps.core.fields import UnsignedAutoField',
    'from apps.people_master.fields import UnsignedBigAutoField',
    'from apps.student_support.fields import NativeEnumField, CanonicalDateTimeField',
    'from apps.documents_exit.fields import NativeTimestampField',
    'from .model_support import Evidence, LinkProjection, scope_shape', '']
for table, body in tables.items():
    if table == 'user_account':
        continue
    links = table in ('student_user_account', 'employee_user_account')
    evidence = table in ('password_history', 'login_audit', 'activity_audit')
    output.append(f'class {names[table]}({"LinkProjection" if links else "Evidence" if evidence else "models.Model"}):')
    relations = dict(re.findall(r'FOREIGN KEY \((\w+)\) REFERENCES (\w+)\(', body))
    rename = lambda f: f.removesuffix('_id') if f in relations else f
    for raw in body.splitlines():
        match = re.match(r'\s*(\w+) (BIGINT|SMALLINT|INT|TINYINT|VARCHAR|DATETIME|TIMESTAMP|ENUM|BOOLEAN|JSON)\b(.*)', raw)
        if not match:
            continue
        name, kind, rest = match.groups()
        if 'GENERATED ALWAYS' in rest:
            if name == 'scope_entity_id':
                expr = "Case(When(scope_type='GLOBAL', then=Value(0)), When(scope_type='SELF', then=F('user')), " + ', '.join(f"When(scope_type='{v.upper()}', then=F('{v}'))" for v in ('institution','campus','department','programme')) + ', output_field=models.BigIntegerField())'
            else:
                expr = "Case(When(scope_type__in=['GLOBAL','SELF'], then=Value(0)), default=Coalesce('scope_entity_id', Value(0)), output_field=models.BigIntegerField())"
            output.append(f'    {name} = models.GeneratedField(expression={expr}, output_field=models.PositiveBigIntegerField(), db_persist=True)')
            continue
        args = []
        if 'NOT NULL' not in rest and 'PRIMARY KEY' not in rest:
            args += ['null=True', 'blank=True']
        if 'PRIMARY KEY' in rest:
            args.append('primary_key=True')
        if 'UNIQUE' in rest:
            args.append('unique=True')
        if name in relations:
            ref = external.get(relations[name], 'identity_access.' + names.get(relations[name], ''))
            ctor = 'models.OneToOneField' if links else 'models.ForeignKey'
            args = [repr(ref), 'on_delete=models.PROTECT', 'related_name="+"', f'db_column={name!r}', *args]
        elif 'AUTO_INCREMENT' in rest:
            ctor = 'UnsignedBigAutoField' if kind == 'BIGINT' else 'UnsignedAutoField'
            if kind != 'BIGINT':
                args.append('bits=' + str({'INT':32,'SMALLINT':16,'TINYINT':8}[kind]))
        elif kind in ('VARCHAR','ENUM'):
            ctor = 'NativeEnumField' if kind == 'ENUM' else 'models.CharField'
            if kind == 'ENUM':
                values = re.findall(r"'([^']+)'", rest.split(')')[0])
                args += [f'choices={[(v,v) for v in values]!r}', f'max_length={max(map(len,values))}']
            else:
                args.append('max_length=' + re.search(r'\((\d+)\)',rest)[1])
            args.append("db_collation='utf8mb4_unicode_ci'")
        elif kind in ('DATETIME', 'TIMESTAMP'):
            ctor = 'NativeTimestampField' if kind == 'TIMESTAMP' else 'CanonicalDateTimeField'
            if 'ON UPDATE' in rest:
                args.append('auto_now=True')
            elif 'CURRENT_TIMESTAMP' in rest:
                args.append('default=timezone.now')
        elif kind == 'BOOLEAN':
            ctor = 'models.BooleanField'
        elif kind == 'JSON':
            ctor = 'models.JSONField'
        else:
            ctor = 'models.PositiveSmallIntegerField' if kind == 'SMALLINT' else 'models.PositiveBigIntegerField'
        default = re.search(r"DEFAULT ('[^']*'|TRUE|FALSE|\d+)", rest)
        if default:
            args.append('default=' + {'TRUE':'True','FALSE':'False'}.get(default[1], default[1]))
        output.append(f'    {rename(name)} = {ctor}({", ".join(args)})')
    if table == 'role_permission':
        output.append("    pk = models.CompositePrimaryKey('role', 'permission')")
    if table == 'user_permission_override':
        output.append('    revoked_at = CanonicalDateTimeField(null=True, blank=True)')
    output += ['    class Meta:', f'        db_table = {table!r}', '        default_permissions = ()']
    if links:
        output.append('        managed = False')
    constraints = []
    for name, fields in re.findall(r'CONSTRAINT (\w+) UNIQUE \(([^)]+)\)', body):
        constraints.append(f'models.UniqueConstraint(fields={[rename(f.strip()) for f in fields.split(",")]!r}, name={name!r})')
    if table in ('user_role_assignment','user_permission_override'):
        prefix = 'user_role' if table == 'user_role_assignment' else 'user_permission_override'
        constraints.append(f"models.CheckConstraint(condition=Q(valid_to__isnull=True) | Q(valid_to__gt=F('valid_from')), name='chk_{prefix}_dates')")
        shape = 'scope_shape()' if table == 'user_role_assignment' else "(Q(scope_type__in=['GLOBAL','SELF'], scope_entity_id__isnull=True) | Q(scope_type__in=['INSTITUTION','CAMPUS','DEPARTMENT','PROGRAMME'], scope_entity_id__isnull=False))"
        constraints.append(f"models.CheckConstraint(condition={shape}, name='chk_{prefix}_scope')")
    if table == 'role_delegation':
        constraints += ["models.CheckConstraint(condition=Q(valid_to__gt=F('valid_from')), name='chk_role_delegation_dates')", "models.CheckConstraint(condition=~Q(delegator_user=F('delegate_user')), name='chk_role_delegation_users')"]
    output.append('        constraints = [' + ', '.join(constraints) + ']')
    output.append('')
output.append('from .support_models import ImpersonationSession')
(target / 'models.py').write_text('\n'.join(output), encoding='utf-8')
