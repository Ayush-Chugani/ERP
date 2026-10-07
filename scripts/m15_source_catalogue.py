"""Extract the supplied M15 seed matrix as reviewable data; no database writes."""
import ast
import json
import re
from pathlib import Path

source=Path('Manuals/M15_prompt_pack_extracted.txt').read_text(encoding='utf-8')
result={}
for table,key in [('access_action','actions'),('access_module','modules'),('role','roles')]:
    match=re.search(r'INSERT INTO '+table+r' \(([^)]+)\) VALUES\s*([\s\S]*?);',source)
    cols=[s.strip() for s in match[1].split(',')]
    body=re.sub(r'\b(TRUE|FALSE)\b',lambda m:'True' if m[1]=='TRUE' else 'False',match[2])
    values=ast.literal_eval('['+body+']')
    result[key]=[dict(zip(cols,row)) for row in values]
rules=re.findall(r'INSERT INTO role_permission \(role_id, permission_id\)\s*([\s\S]*?);',source)
actions=[x['action_code'] for x in result['actions']]
modules=[x['module_code'] for x in result['modules']]
sets={x['role_code']:set() for x in result['roles']}
for sql in rules:
    direct=re.search(r"r.role_code = '([^']+)'",sql)
    group=re.search(r'r.role_code IN \(([^)]+)\)',sql)
    role_names=[direct[1]] if direct else re.findall(r"'([^']+)'",group[1])
    allowed_modules=set(modules);allowed_actions=set(actions)
    for column,values in [('am.module_code',allowed_modules),('aa.action_code',allowed_actions)]:
        expr=re.search(re.escape(column)+r' (NOT IN|IN) \(([^)]+)\)',sql)
        if expr:
            chosen=set(re.findall(r"'([^']+)'",expr[2]))
            if expr[1]=='IN': values.intersection_update(chosen)
            else: values.difference_update(chosen)
    for role in role_names: sets[role].update(m+'.ALL.'+a for m in allowed_modules for a in allowed_actions)
result['role_permissions']={role:sorted(values) for role,values in sets.items()}
result['sensitive_permissions']=[m+'.ALL.'+a for m in modules if m in ['IAM','AUDIT','RESULT','STUDENT','EMPLOYEE'] for a in actions if a in ['UPDATE','DELETE','APPROVE','EXPORT','CONFIGURE','IMPERSONATE']]
assert len(actions)==11 and len(modules)==20 and len(sets)==32
assert len(sets['SUPER_ADMIN'])==220 and len(sets['SYSTEM_ADMIN'])==60
assert all(not code.endswith('.IMPERSONATE') for code in sets['SYSTEM_ADMIN'])
Path('Manuals/M15_SOURCE_CATALOGUE.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'actions':len(actions),'modules':len(modules),'permissions':len(actions)*len(modules),'roles':len(sets),'role_permission_pairs':sum(map(len,sets.values())),'sensitive_permissions':len(result['sensitive_permissions']),'roles_without_source_grants':[r for r,v in sets.items() if not v]},indent=2))
