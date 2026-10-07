from decimal import Decimal
from rest_framework import serializers as z
from rest_framework.exceptions import ValidationError
from ... import services as s
class Strict(z.Serializer):
    def to_internal_value(self,data):
        if not isinstance(data,dict) or set(data)-set(self.fields):raise ValidationError('Unknown fields or invalid object.')
        return super().to_internal_value(data)
def schema(name,**fields):return type('Assessment'+name,(Strict,),fields)
def ID(**kw):return z.IntegerField(min_value=1,**kw)
def D(**kw):return z.DecimalField(max_digits=7,decimal_places=2,min_value=0,**kw)
def Reason():return z.CharField(max_length=500)
ComponentValues=schema('ComponentValues',component_code=z.CharField(max_length=30),component_name=z.CharField(max_length=100),component_type=z.ChoiceField(choices='INTERNAL_TEST QUIZ ASSIGNMENT LAB PROJECT PRESENTATION TERM_WORK OTHER'.split()),maximum_marks=D(),weightage_percent=D(max_value=100),is_mandatory=z.BooleanField())
EventValues=schema('EventValues',event_number=ID(required=False),event_title=z.CharField(max_length=150),assessment_date=z.DateField(),start_time=z.TimeField(required=False,allow_null=True),end_time=z.TimeField(required=False,allow_null=True),maximum_marks=D(),reduced_maximum_marks=D(required=False,allow_null=True),details=z.CharField(required=False,allow_blank=True),attempt_number=z.IntegerField(min_value=1,max_value=255))
ScaleValues=schema('ScaleValues',scale_name=z.CharField(max_length=100),effective_from=z.DateField(),effective_to=z.DateField(required=False,allow_null=True))
Grade=schema('Grade',grade_letter=z.CharField(max_length=5),grade_point=D(max_value=Decimal('99.99')),minimum_percentage=D(max_value=100),maximum_percentage=D(max_value=100),result_status=z.ChoiceField(choices='PASS FAIL ABSENT WITHHELD EXEMPTED'.split()))
Mark=schema('Mark',course_registration_id=ID(),attendance_status=z.ChoiceField(choices='PRESENT ABSENT EXEMPTED MALPRACTICE'.split()),marks_obtained=D(required=False,allow_null=True),reduced_marks=D(required=False,allow_null=True),remarks=z.CharField(max_length=500,required=False,allow_blank=True))
COMMANDS={
 'update-event':(schema('UpdateEvent',pk=ID(),expected_version=ID(),values=EventValues(),reason=Reason()),s.update_event),
 'configure-scale':(schema('ConfigureScale',institution_id=ID(),values=ScaleValues(),rules=Grade(many=True,min_length=1,max_length=30),reason=Reason()),s.configure_scale),
 'configure-policy':(schema('ConfigurePolicy',offering_id=ID(),grade_scale_id=ID(),expected_number=z.IntegerField(min_value=0),rules=z.JSONField(),reason=Reason()),s.configure_policy),
 'component':(schema('Component',offering_id=ID(),values=ComponentValues(),pk=ID(required=False),expected_version=ID(required=False),reason=Reason()),s.component),
 'create-event':(schema('CreateEvent',component_id=ID(),policy_id=ID(),values=EventValues(),reason=Reason()),s.create_event),
 'transition-event':(schema('TransitionEvent',pk=ID(),expected_version=ID(),action=z.ChoiceField(choices=['conduct','cancel','publish','reopen']),reason=Reason()),s.transition_event),
 'mark':(schema('MarkBatch',event_id=ID(),expected_version=ID(),entries=Mark(many=True,min_length=1,max_length=500),reason=Reason()),s.mark),
 'calculate-course':(schema('CalculateCourse',registration_id=ID(),attempt=z.IntegerField(min_value=1,max_value=255),policy_id=ID(),external_percentage=D(max_value=100),expected_version=z.IntegerField(min_value=0),reason=Reason()),s.calculate_course),
 'calculate-term':(schema('CalculateTerm',term_registration_id=ID(),expected_version=z.IntegerField(min_value=0),reason=Reason()),s.calculate_term),
 'transition-result':(schema('TransitionResult',resource=z.ChoiceField(choices=['course','term']),pk=ID(),expected_version=ID(),action=z.ChoiceField(choices=['publish','withhold','reopen']),reason=Reason()),s.transition_result),
}
Result=schema('CommandResult',id=z.CharField(),version=z.IntegerField(allow_null=True),resource=z.CharField())
