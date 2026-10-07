"""Read-only plan evidence, not a production benchmark or index recommendation."""
import json
from pathlib import Path
from django.conf import settings
from django.db import connection
from apps.conferences.models import ConferenceActivity, ConferenceActivityIndexing, ConferenceEvent

queries = {
    'recent_events': ConferenceEvent.objects.filter(is_active=True).order_by('-start_date', '-pk')[:25],
    'employee_activities': ConferenceActivity.objects.filter(staff_activity__employee_id=1,
        staff_activity__deleted_at__isnull=True).select_related('conference_event', 'staff_activity').order_by('-pk')[:25],
    'indexing_status': ConferenceActivity.objects.filter(pk__in=ConferenceActivityIndexing.objects.filter(
        indexing_status='VERIFIED').values('staff_activity_id')).order_by('-pk')[:25],
}
report = {'environment': 'Local database; EXPLAIN only, no activity rows read',
          'limitation': 'Plans on the current local distribution do not establish production benefit. No speculative indexes added.',
          'plans': {name: json.loads(query.explain(format='JSON')) for name, query in queries.items()}}
with connection.cursor() as cursor:
    cursor.execute('SELECT VERSION()')
    report['database_version'] = cursor.fetchone()[0]
(Path(settings.BASE_DIR).parent / 'Manuals/M22_QUERY_PLANS.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('Recorded three local EXPLAIN plans; no row values or performance claims.')
