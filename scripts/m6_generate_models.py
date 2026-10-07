"""One-time source generator for the approved M6 schema (no database writes)."""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'backend/apps/admission_enrolment'
target.mkdir(exist_ok=True)
(target / 'migrations').mkdir(exist_ok=True)
(target / '__init__.py').touch()
(target / 'migrations/__init__.py').touch()
mapping = {
    'admission_applicant': 'AdmissionApplicant', 'admission_application': 'AdmissionApplication',
    'student_programme_enrolment': 'StudentProgrammeEnrolment', 'enrolment_status_history': 'EnrolmentStatusHistory',
    'institution': 'organization.Institution', 'student': 'people_master.Student', 'user_account': 'accounts.User',
    'programme': 'organization.Programme', 'programme_specialization': 'organization.ProgrammeSpecialization',
    'curriculum_scheme': 'curriculum_catalog.CurriculumScheme', 'academic_year': 'academic_calendar.AcademicYear',
    'semester': 'academic_calendar.Semester', 'admission_category': 'common_reference.AdmissionCategory',
    'gender': 'common_reference.Gender', 'country': 'common_reference.Country', 'social_category': 'common_reference.SocialCategory',
    'caste': 'common_reference.Caste', 'sub_caste': 'common_reference.SubCaste',
}
sql = (root / 'Manuals/M6_REVISED_SCHEMA_PROPOSAL.sql').read_text()
out = ['from django.db import models', 'from django.db.models import Q, F', 'from apps.people_master.fields import UnsignedBigAutoField', '']
for table, body in re.findall(r'CREATE TABLE (\w+) \((.*?)\n\) ENGINE', sql, re.S):
    relations = dict(re.findall(r'FOREIGN KEY \((\w+)\) REFERENCES (\w+)\(', body))
    relations['specialization_id'] = 'programme_specialization'
    if table == 'student_programme_enrolment':
        relations['application_id'] = 'admission_application'
    out.append(f'class {mapping[table]}(models.Model):')
    unique, indexes = [], []
    for raw in body.splitlines():
        line = raw.strip().rstrip(',')
        match = re.match(r'(\w+) (BIGINT|SMALLINT|INT|TINYINT|VARCHAR|CHAR|DATE|DATETIME|TIMESTAMP|TEXT|ENUM)\b(.*)', line)
        if not match:
            continue
        name, kind, rest = match.groups()
        optional = 'NOT NULL' not in rest and 'PRIMARY KEY' not in rest
        args = ['null=True', 'blank=True'] if optional else []
        if 'PRIMARY KEY' in rest:
            field = 'UnsignedBigAutoField(primary_key=True)'
        elif name in relations:
            original = name
            name = name.removesuffix('_id')
            model = mapping[relations[original]]
            if '.' not in model:
                model = 'admission_enrolment.' + model
            if 'UNIQUE' in rest:
                args.append('unique=True')
            field = f'models.ForeignKey({model!r}, on_delete=models.PROTECT, related_name="+", ' + ', '.join(args) + ')'
        elif kind in ('VARCHAR', 'CHAR', 'ENUM', 'TEXT'):
            if kind == 'ENUM':
                values = re.findall(r"'([^']+)'", rest.split(')')[0])
                enumname = ''.join(p.title() for p in name.split('_'))
                out += [f'    class {enumname}(models.TextChoices):'] + [f'        {v} = {v!r}' for v in values]
                args += [f'max_length={max(map(len, values))}', f'choices={enumname}.choices']
            elif kind != 'TEXT':
                args.append('max_length=' + re.search(r'\((\d+)\)', rest).group(1))
            if 'UNIQUE' in rest:
                args.append('unique=True')
            default = re.search(r"DEFAULT '([^']+)'", rest)
            if default:
                args.append(f'default={default.group(1)!r}')
            args.append('db_collation="utf8mb4_unicode_ci"')
            field = f'models.{"TextField" if kind == "TEXT" else "CharField"}(' + ', '.join(args) + ')'
        elif kind in ('DATE', 'DATETIME', 'TIMESTAMP'):
            if 'CURRENT_TIMESTAMP' in rest:
                args = ['auto_now=True' if 'ON UPDATE' in rest else 'auto_now_add=True']
            field = f'models.{"DateField" if kind == "DATE" else "DateTimeField"}(' + ', '.join(args) + ')'
        else:
            default = re.search(r'DEFAULT (\d+)', rest)
            if default:
                args.append('default=' + default.group(1))
            field = 'models.PositiveBigIntegerField(' + ', '.join(args) + ')'
        out.append(f'    {name} = {field}')
    for cname, fields in re.findall(r'CONSTRAINT (\w+) UNIQUE \(([^)]+)\)', body):
        fields = [f.strip().removesuffix('_id') if f.strip() in relations else f.strip() for f in fields.split(',')]
        unique.append(f'models.UniqueConstraint(fields={fields!r}, name={cname!r})')
    for iname, fields in re.findall(r'INDEX (\w+) \(([^)]+)\)', body):
        fields = [f.strip().removesuffix('_id') if f.strip() in relations else f.strip() for f in fields.split(',')]
        indexes.append(f'models.Index(fields={fields!r}, name={iname!r})')
    checks = {
        'admission_application': ["models.CheckConstraint(condition=Q(application_status='ADMITTED', admitted_student__isnull=False) | (~Q(application_status='ADMITTED') & Q(admitted_student__isnull=True)), name='chk_m6_application_conversion')", "models.CheckConstraint(condition=~Q(application_status__in=['ELIGIBLE','SELECTED','ADMITTED']) | Q(eligibility_status='ELIGIBLE'), name='chk_m6_application_eligible')"],
        'student_programme_enrolment': ["models.CheckConstraint(condition=Q(expected_completion_date__isnull=True) | Q(expected_completion_date__gte=F('admission_date')), name='chk_m6_enrolment_completion')"],
        'enrolment_status_history': ["models.CheckConstraint(condition=Q(sequence_number__gt=0), name='chk_m6_history_sequence')", "models.CheckConstraint(condition=~Q(reason=''), name='chk_m6_history_reason')"],
    }
    unique += checks.get(table, [])
    out += ['    class Meta:', f'        db_table = {table!r}', "        ordering = ['pk']", '        constraints = [' + ', '.join(unique) + ']', '        indexes = [' + ', '.join(indexes) + ']', '']
(target / 'models.py').write_text('\n'.join(out), encoding='utf-8')
