"""Read-only EXPLAIN evidence with temporary fixture writes rolled back."""
import os
from datetime import date
from uuid import uuid4
from pathlib import Path
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
django.setup()
from django.db import connection,transaction
from apps.organization.models import University,Institution,Campus,Department,Programme
from apps.academic_calendar.models import Semester
from apps.curriculum_catalog.models import CourseCategory,CourseCatalog,CurriculumScheme,CurriculumCourse,CoursePrerequisite

lines=['# M4 MySQL query plans','','Temporary fixture: 100 courses, 20 schemes, 100 mappings and 99 prerequisite edges. All fixture writes roll back; auto-increment gaps may remain. This is plan evidence, not a production load benchmark.']
with transaction.atomic():
    tag='QP'+uuid4().hex[:8].upper()
    u=University.objects.create(university_code=tag,university_name=tag)
    i=Institution.objects.create(university=u,institution_code=tag,institution_name=tag)
    c=Campus.objects.create(institution=i,campus_code=tag,campus_name=tag)
    d=Department.objects.create(campus=c,department_code=tag,department_name=tag)
    p=Programme.objects.create(department=d,programme_code=tag,programme_name=tag,programme_level='UG',duration_semesters=6)
    semester=Semester.objects.filter(semester_number=1).first() or Semester.objects.create(semester_number=1,semester_name=tag)
    category=CourseCategory.objects.create(category_code=tag,category_name=tag)
    courses=[CourseCatalog.objects.create(owning_department=d,course_category=category,course_code=f'{tag}{n}',course_title=f'Sample {n}',course_type='THEORY',credits=3) for n in range(100)]
    schemes=[CurriculumScheme.objects.create(programme=p,scheme_code=f'{tag}{n}',scheme_name=tag,regulation_year=2000+n,effective_from=date(2000+n,1,1),effective_to=date(2000+n,12,31),status='ACTIVE' if n==19 else 'RETIRED') for n in range(20)]
    for index,course in enumerate(courses):
        CurriculumCourse.objects.create(curriculum_scheme=schemes[index//5],semester=semester,course=course,course_category=category,internal_max_marks=40,external_max_marks=60,display_order=index%5+1)
        if index:CoursePrerequisite.objects.create(course=course,prerequisite_course=courses[index-1])
    queries={
        'Scoped active course list':CourseCatalog.objects.filter(owning_department=d,is_active=True).order_by('course_code','course_id'),
        'Current scheme candidates':CurriculumScheme.objects.filter(programme=p,specialization_id=None,status='ACTIVE',effective_from__lte=date(2019,6,1)).order_by('effective_from','pk'),
        'Semester composition':CurriculumCourse.objects.filter(curriculum_scheme=schemes[-1],semester=semester).select_related('course','course_category').order_by('display_order','pk'),
        'Prerequisite lookup':CoursePrerequisite.objects.filter(course=courses[-1]).select_related('prerequisite_course'),
    }
    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION()');lines += ['', 'MySQL: '+cursor.fetchone()[0]]
    for name,query in queries.items():lines += ['', '## '+name,'```text',query.explain(),'```']
    transaction.set_rollback(True)
Path('Manuals/M4_QUERY_PLANS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Saved M4_QUERY_PLANS.md; fixture rolled back.')
