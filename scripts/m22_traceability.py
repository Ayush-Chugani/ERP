"""Document field ownership and API/UI boundaries without reading row values."""
import json
import re
from pathlib import Path
from django.apps import apps
from django.conf import settings
from apps.conferences.migrations._ddl import DDL

root = Path(settings.BASE_DIR).parent
records = []
for ddl in DDL:
    table = re.search(r'CREATE TABLE (\w+)', ddl)[1]
    model = next(m for m in apps.get_app_config('conferences').get_models() if m._meta.db_table == table)
    fields = []
    for field in model._meta.concrete_fields:
        if not field.column:
            continue
        server = field.primary_key or field.column in ('staff_activity_id', 'created_at', 'updated_at')
        read_name = field.name if field.is_relation else field.column
        write_name = None if server else field.column
        if table == 'conference_activity_indexing':
            read_name = None if field.column == 'staff_activity_id' else field.column
            if field.column == 'indexing_status':
                write_name = 'status (verification action only)'
        fields.append({'sql_column': field.column, 'model_field': field.name,
            'nullable': field.null, 'read_api_field': read_name,
            'write_api_field': write_name,
            'ui': 'Server-managed identity/timestamp or inherited context' if server else
                  'Dedicated verification control' if field.column == 'indexing_status' else 'Named form field',
            'validation': 'models.py + validators.py + services.py; protected write allowlists in api.py'})
    records.append({'table': table, 'model': model._meta.label, 'fields': fields,
                    'constraints': re.findall(r'CONSTRAINT (\w+)', ddl),
                    'migration': 'conferences.0001_initial',
                    'tests': ['conferences.tests.test_schema', 'conferences.tests.test_services', 'conferences.tests.test_api']})
report = {'scope': 'Field/schema traceability; not a claim of production acceptance', 'tables': records,
          'ui_file': 'frontend/src/features/conferences/ConferencesApp.tsx',
          'ui_tests': 'frontend/tests/conferences.test.tsx',
          'remaining_acceptance': ['Institution policy and role assignments', 'Real-browser mobile/keyboard QA',
                                   'Representative staging load and query plans', 'Approved deployment and production smoke checks']}
(root / 'Manuals/M22_TRACEABILITY.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(f"Recorded {len(records)} tables and {sum(len(t['fields']) for t in records)} physical columns.")
