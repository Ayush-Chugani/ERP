import csv
import io
from rest_framework.exceptions import ValidationError
from .serializers import Assignment


def parse_allocations(text, reason):
    """Explicit upstream IDs only. Never guess identity from a faculty name."""
    if len(text.encode('utf-8')) > 250000:
        raise ValidationError('Import is limited to 250 KB.')
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required = {'source_id', 'course_offering_section_id', 'employee_id', 'assignment_role',
        'workload_hours', 'start_date', 'end_date'}
    if set(reader.fieldnames or []) != required:
        raise ValidationError({'columns': sorted(required)})
    rows, quarantine, seen = [], [], set()
    for index, raw in enumerate(reader, start=2):
        if index > 51:
            raise ValidationError('Import at most 50 rows per batch.')
        source_id = raw.pop('source_id', '')
        if not source_id or source_id in seen:
            quarantine.append({'line': index, 'source_id': source_id, 'error': 'Missing or duplicate source_id.'})
            continue
        seen.add(source_id)
        serializer = Assignment(data={**raw, 'end_date': raw.get('end_date') or None,
            'workload_hours': raw.get('workload_hours') or None, 'reason': reason})
        if serializer.is_valid():
            rows.append({'source_id': source_id, 'line': index,
                'values': {k: v for k, v in serializer.validated_data.items() if k != 'reason'}})
        else:
            quarantine.append({'line': index, 'source_id': source_id, 'error': serializer.errors})
    if not rows and not quarantine:
        raise ValidationError('The import has no data rows.')
    return rows, quarantine
