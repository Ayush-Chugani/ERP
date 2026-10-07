"""Deterministic Decimal policy primitives. No institutional defaults."""
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP,ROUND_HALF_EVEN,ROUND_DOWN
ROUNDING={'HALF_UP':ROUND_HALF_UP,'HALF_EVEN':ROUND_HALF_EVEN,'DOWN':ROUND_DOWN}
def number(value):
    if isinstance(value,(float,bool)):raise ValueError('Use decimal strings, not floating-point values.')
    try:result=Decimal(value)
    except (InvalidOperation,TypeError,ValueError):raise ValueError('Invalid decimal value.')
    if not result.is_finite():raise ValueError('Finite decimal required.')
    return result
def validate_policy(r):
    keys={'internal_weight','external_weight','minimum_internal','minimum_external','best_n','aggregation','special','rounding','repeat','gpa_statuses','credit_statuses','max_grade_point','grace','event_maximum','failure_grade','show_marks'}
    if not isinstance(r,dict) or set(r)!=keys:raise ValueError('Supply every policy field, with no unknown fields: '+', '.join(sorted(keys)))
    if number(r['internal_weight'])+number(r['external_weight'])!=100:raise ValueError('Internal/external weights must total 100.')
    for key in ['internal_weight','external_weight','minimum_internal','minimum_external','grace']:
        if not 0<=number(r[key])<=100:raise ValueError('Policy percentages must be 0..100.')
    if r['rounding'] not in ROUNDING or r['aggregation'] not in ['MEAN','BEST_N'] or r['repeat'] not in ['LATEST','BEST']:raise ValueError('Unsupported rounding, aggregation or repeat policy.')
    if type(r['best_n']) is not int or not 1<=r['best_n']<=100:raise ValueError('best_n must be 1..100.')
    if type(r['show_marks']) is not bool:raise ValueError('Explicit student mark-visibility choice required.')
    if not isinstance(r['failure_grade'],str) or not 1<=len(r['failure_grade'])<=5:raise ValueError('Explicit threshold-failure grade required.')
    if r['event_maximum'] not in ['EQUAL_COMPONENT','INDEPENDENT']:raise ValueError('Choose event maximum compatibility.')
    if not 0<number(r['max_grade_point'])<=Decimal('99.99'):raise ValueError('Invalid grade point scale.')
    if set(r['special'])!={'ABSENT','EXEMPTED','MALPRACTICE'} or any(v not in ['ZERO','EXCLUDE','BLOCK'] for v in r['special'].values()):raise ValueError('Explicit special-attendance behavior is required.')
    for key in ['gpa_statuses','credit_statuses']:
        if not isinstance(r[key],list) or not r[key] or set(r[key])-{'PASS','FAIL','ABSENT','EXEMPTED'}:raise ValueError('Invalid GPA or earned-credit statuses.')
    return r
def quantize(value,r,places='0.01'):return number(value).quantize(Decimal(places),rounding=ROUNDING[r['rounding']])
def validate_bands(bands):
    ordered=sorted(bands,key=lambda b:number(b['minimum_percentage']))
    if not ordered or number(ordered[0]['minimum_percentage'])!=0 or number(ordered[-1]['maximum_percentage'])!=100:raise ValueError('Grade bands must cover 0 through 100.')
    last=Decimal(0);letters=set()
    for row in ordered:
        low=number(row['minimum_percentage']);high=number(row['maximum_percentage'])
        if low!=last or not low<high<=100:raise ValueError('Grade bands must be contiguous and non-overlapping.')
        if number(row['grade_point'])<0 or row['grade_letter'] in letters:raise ValueError('Invalid grade points or duplicate letter.')
        last=high;letters.add(row['grade_letter'])
    return ordered
def resolve_grade(bands,percentage):
    value=number(percentage)
    matches=[b for b in bands if number(b['minimum_percentage'])<=value and (value<number(b['maximum_percentage']) or value==100==number(b['maximum_percentage']))]
    if len(matches)!=1:raise ValueError('Percentage must resolve to exactly one grade rule.')
    return matches[0]
class InternalAssessmentPolicy:
    @staticmethod
    def calculate(components,marks,r):
        total=Decimal(0);weight=Decimal(0)
        for component in components:
            values=[]
            for mark in marks.get(component['id'],[]):
                status=mark['attendance_status']
                if status!='PRESENT':
                    treatment=r['special'][status]
                    if treatment=='BLOCK':raise ValueError('Special attendance blocks calculation.')
                    if treatment=='EXCLUDE':continue
                    values.append(Decimal(0));continue
                maximum=number(mark['maximum']);raw=number(mark['value'])
                if maximum<=0 or not 0<=raw<=maximum:raise ValueError('Mark outside scoring range.')
                values.append(raw/maximum*100)
            if not values:
                if component['mandatory']:raise ValueError('Mandatory component has no countable evaluations.')
                continue
            if r['aggregation']=='BEST_N':
                if len(values)<r['best_n']:raise ValueError('Insufficient events for best-of-N.')
                values=sorted(values,reverse=True)[:r['best_n']]
            w=number(component['weight']);total+=sum(values)/len(values)*w;weight+=w
        if weight<=0:raise ValueError('No countable component weights.')
        return total/weight
class CourseResultPolicy:
    @staticmethod
    def calculate(internal,external,r):
        internal=number(internal);external=number(external)
        if not 0<=external<=100:raise ValueError('External percentage must be 0..100.')
        passed=internal>=number(r['minimum_internal']) and external>=number(r['minimum_external'])
        total=min(Decimal(100),(internal*number(r['internal_weight'])+external*number(r['external_weight']))/100+number(r['grace']))
        return total,passed
class TermGpaPolicy:
    @staticmethod
    def calculate(rows,r):
        rows=[row for row in rows if row['result_status'] in r['gpa_statuses']]
        credits=sum((number(row['credits']) for row in rows),Decimal(0))
        if not credits:return None
        result=sum(number(row['credits'])*number(row['grade_point']) for row in rows)/credits
        if not 0<=result<=number(r['max_grade_point']):raise ValueError('GPA outside policy scale.')
        return quantize(result,r)
