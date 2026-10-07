from rest_framework import serializers as z
from rest_framework.exceptions import ValidationError
from .. import services as s
class Strict(z.Serializer):
    def to_internal_value(self,data):
        if not isinstance(data,dict) or set(data)-set(self.fields):raise ValidationError('Unknown fields or invalid object.')
        return super().to_internal_value(data)
def schema(classname,**fields):return type('Feedback'+classname,(Strict,),fields)
def ID(**kw):return z.IntegerField(min_value=1,**kw)
def reason():return z.CharField(max_length=500)
Item=schema('Item',question_id=ID(),display_order=z.IntegerField(min_value=1,max_value=65535),is_required=z.BooleanField(),weightage=z.DecimalField(max_digits=6,decimal_places=2,min_value=0,allow_null=True,required=False))
CycleValues=schema('CycleValues',academic_term_id=ID(),programme_id=ID(allow_null=True,required=False),cycle_name=z.CharField(max_length=150),start_at=z.DateTimeField(),end_at=z.DateTimeField(),result_visibility=z.ChoiceField(choices=['HIDDEN','ADMIN_ONLY','FACULTY','PUBLIC']),minimum_cohort=z.IntegerField(min_value=2,max_value=65535),allow_text_review=z.BooleanField(),target_policy=z.ChoiceField(choices=['ENROLLED','COMPLETING','EXPLICIT']),explicit_registrations=z.ListField(child=ID(),max_length=500,required=False))
Target=schema('Target',course_offering_id=ID(required=False),faculty_assignment_id=ID(required=False))
Submission=schema('Submission',target=Target(),answers=z.JSONField())
COMMANDS={
 'bank':(schema('Bank',resource=z.ChoiceField(choices=['categories','questions','choices','questionnaires']),institution_id=ID(),values=z.JSONField(),pk=ID(required=False),expected_version=ID(required=False),reason=reason()),s.write_bank),
 'items':(schema('Items',pk=ID(),expected_version=ID(),items=Item(many=True,min_length=1,max_length=100),reason=reason()),s.replace_items),
 'questionnaire-action':(schema('QuestionnaireAction',pk=ID(),expected_version=ID(),action=z.ChoiceField(choices=['activate','retire','clone']),code=z.CharField(max_length=30,required=False),name=z.CharField(max_length=150,required=False),reason=reason()),s.questionnaire_action),
 'create-cycle':(schema('CreateCycle',questionnaire_id=ID(),values=CycleValues(),reason=reason()),s.create_cycle),
 'cycle-action':(schema('CycleAction',pk=ID(),expected_version=ID(),action=z.ChoiceField(choices=['open','close','cancel']),override=z.BooleanField(default=False),reason=reason()),s.cycle_action),
}
Result=schema('Result',id=z.CharField(),version=z.IntegerField(allow_null=True),resource=z.CharField())
