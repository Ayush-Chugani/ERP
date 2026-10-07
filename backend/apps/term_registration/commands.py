from decimal import Decimal
from rest_framework import serializers as z
from rest_framework.exceptions import ValidationError
from . import services as s, workflows as w
from .policies import require_programme


class Strict(z.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data,dict): raise ValidationError('Expected an object.')
        extra = set(data)-set(self.fields)
        if extra: raise ValidationError({key:'Unknown field.' for key in extra})
        return super().to_internal_value(data)


def ID(**kwargs): return z.IntegerField(min_value=1,**kwargs)
def reason(): return z.CharField(max_length=500,allow_blank=False)
def fields(name, **items): return type('Registration'+name,(Strict,),items)


Offering = fields('Offering',programme_id=ID(),academic_term_id=ID(),specialization_id=ID(required=False,allow_null=True),curriculum_scheme_id=ID(),semester_id=ID(),reason=reason())
Section = fields('Section',programme_term_offering_id=ID(required=False),pk=ID(required=False),expected_version=ID(required=False),section_code=z.CharField(max_length=20,required=False),section_name=z.CharField(max_length=100,required=False,allow_null=True,allow_blank=True),capacity=z.IntegerField(min_value=1,max_value=65535,required=False,allow_null=True),home_room_id=ID(required=False,allow_null=True),is_active=z.BooleanField(required=False),reason=reason())
Batch = fields('Batch',class_section_id=ID(required=False),pk=ID(required=False),expected_version=ID(required=False),batch_code=z.CharField(max_length=20,required=False),batch_name=z.CharField(max_length=100,required=False,allow_null=True,allow_blank=True),capacity=z.IntegerField(min_value=1,max_value=65535,required=False,allow_null=True),is_active=z.BooleanField(required=False),reason=reason())
Policy = fields('Policy',programme_id=ID(),maximum_credits=z.DecimalField(max_digits=6,decimal_places=1,min_value=Decimal("0.1")),minimum_credits=z.DecimalField(max_digits=6,decimal_places=1,min_value=0),expected_version=ID(required=False),reason=reason())
Progression = fields('Progression',enrolment_id=ID(),offering_id=ID(),offering_version=ID(),enrolment_version=ID(),reason=reason())
Draft = fields('Draft',enrolment_id=ID(),offering_id=ID(),section_id=ID(required=False,allow_null=True),batch_id=ID(required=False,allow_null=True))
TermTransition = fields('TermTransition',registration_id=ID(),expected_version=ID(),target=z.ChoiceField(choices=['REGISTERED','APPROVED','CANCELLED','COMPLETED']),reason=reason())
OfferingTransition = fields('OfferingTransition',pk=ID(),expected_version=ID(),target=z.ChoiceField(choices=['REGISTRATION_OPEN','ACTIVE','COMPLETED','CANCELLED']),reason=reason())
CourseTransition = fields('CourseTransition',pk=ID(),expected_version=ID(),target=z.ChoiceField(choices=['OPEN','ACTIVE','COMPLETED','CANCELLED']),reason=reason())
Allocation = fields('Allocation',pk=ID(),expected_version=ID(),section_id=ID(required=False,allow_null=True),batch_id=ID(required=False,allow_null=True),automatic=z.BooleanField(default=False),effective_date=z.DateField(required=False),reason=reason())
Course = fields('Course',programme_term_offering_id=ID(),curriculum_course_id=ID(required=False,allow_null=True),course_id=ID(),offering_code=z.CharField(max_length=50),registration_capacity=z.IntegerField(min_value=1,max_value=65535,required=False,allow_null=True),reason=reason())
Mapping = fields('Mapping',course_offering_id=ID(),class_section_id=ID(),class_batch_id=ID(required=False,allow_null=True),session_type=z.ChoiceField(choices=w.m.SessionType.values),reason=reason())
CourseRegistration = fields('CourseRegistration',term_id=ID(),course_id=ID(),registration_type=z.ChoiceField(choices=w.m.RegistrationType.values),reason=reason())
CourseRegistrationTransition = fields('CourseRegistrationTransition',pk=ID(),expected_version=ID(),target=z.ChoiceField(choices=['APPROVED','DROPPED','WITHDRAWN','COMPLETED']),effective_date=z.DateField(),reason=reason())
Roster = fields('Roster',registration_id=ID(),mapping_id=ID(),expected_version=ID(),effective_date=z.DateField(),reason=reason())
Result = fields('Result',id=z.CharField(),version=z.IntegerField(allow_null=True),resource=z.CharField())
BulkRow = fields('BulkRow',operation=z.CharField(),data=z.DictField())
Bulk = fields('Bulk',rows=BulkRow(many=True,min_length=1,max_length=100),dry_run=z.BooleanField(default=True))


def values_call(fn):
    def run(*,actor,**data):
        why=data.pop('reason')
        return fn(actor=actor,values=data,reason=why)
    return run


def group_call(resource):
    def run(*,actor,**data):
        why=data.pop('reason'); pk=data.pop('pk',None); version=data.pop('expected_version',None)
        return w.save_group(actor=actor,resource=resource,values=data,reason=why,pk=pk,expected_version=version)
    return run


Capacity = fields('Capacity',pk=ID(),expected_version=ID(),capacity=z.IntegerField(min_value=1,max_value=65535,allow_null=True),reason=reason())
Roll = fields('Roll',pk=ID(),expected_version=ID(),roll_number=z.CharField(max_length=30),reason=reason())
COMMANDS = {
    'amend-course-capacity':(Capacity,w.amend_course_capacity),
    'correct-roll':(Roll,w.correct_roll),
    'create-offering':(Offering,values_call(w.create_offering)),
    'transition-offering':(OfferingTransition,w.transition_offering),
    'save-section':(Section,group_call('sections')),
    'save-batch':(Batch,group_call('batches')),
    'configure-policy':(Policy,w.configure_policy),
    'approve-progression':(Progression,s.approve_progression),
    'create-draft':(Draft,s.create_draft),
    'transition-term':(TermTransition,s.transition_term),
    'allocate':(Allocation,w.allocate),
    'create-course':(Course,values_call(w.create_course)),
    'transition-course':(CourseTransition,w.transition_course),
    'create-mapping':(Mapping,values_call(w.create_mapping)),
    'register-course':(CourseRegistration,w.register_course),
    'transition-registration':(CourseRegistrationTransition,w.transition_registration),
    'assign-roster':(Roster,w.assign_roster),
}


def authorize(actor, operation, data):
    """Replay authorization uses current grants, permissions, and all referenced owners."""
    from .selectors import require_references
    action = 'approve_progression' if operation=='approve-progression' else 'configure_registration' if operation=='configure-policy' else 'approve_registration' if data.get('target')=='APPROVED' else 'manage_registration'
    if 'programme_id' in data: require_programme(actor,data['programme_id'],action)
    refs = {'offering_id':'offerings','programme_term_offering_id':'offerings','section_id':'sections','class_section_id':'sections','batch_id':'batches','class_batch_id':'batches','course_offering_id':'courses','term_id':'terms','mapping_id':'mappings'}
    if operation=='register-course': refs['course_id']='courses'
    if 'registration_id' in data: refs['registration_id']='registrations' if operation=='assign-roster' else 'terms'
    if 'pk' in data:
        refs['pk']={'amend-course-capacity':'courses','correct-roll':'terms','transition-offering':'offerings','save-section':'sections','save-batch':'batches','allocate':'terms','transition-course':'courses','transition-registration':'registrations'}[operation]
    programme = data.get('programme_id')
    for field,resource in refs.items():
        if data.get(field):
            obj=w.get(actor,resource,data[field],action); programme=w.programme_id(obj)
    if not programme: raise ValidationError('A scoped programme owner is required.')
    if data.get('enrolment_id'):
        from apps.admission_enrolment.models import StudentProgrammeEnrolment
        enrolment=StudentProgrammeEnrolment.objects.filter(pk=data['enrolment_id'],programme_id=programme).first()
        if not enrolment:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        require_references(actor,programme,{'students':enrolment.student_id})
    if operation=='create-course':
        require_references(actor,programme,{'courses':data['course_id'],'curriculum-courses':data.get('curriculum_course_id')})
        if not data.get('curriculum_course_id'): require_programme(actor,programme,'authorize_special_course')
    if data.get('home_room_id'): require_references(actor,programme,{'rooms':data['home_room_id']})
    if data.get('curriculum_scheme_id'): require_references(actor,programme,{'schemes':data['curriculum_scheme_id']})
