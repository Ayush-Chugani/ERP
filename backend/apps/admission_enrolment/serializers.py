from rest_framework import serializers
from . import models as m
from .policies import allowed


class StrictSerializer(serializers.ModelSerializer):
    def to_internal_value(self,data):
        unknown=set(data)-set(self.fields)
        readonly={k for k in data if k in self.fields and self.fields[k].read_only}
        if unknown or readonly:
            raise serializers.ValidationError({'fields':'Unsupported or protected fields.'})
        return super().to_internal_value(data)


class ApplicantSerializer(StrictSerializer):
    institution_id=serializers.IntegerField(min_value=1)
    gender_id=serializers.IntegerField(min_value=1,allow_null=True,required=False)
    nationality_country_id=serializers.IntegerField(min_value=1,allow_null=True,required=False)
    social_category_id=serializers.IntegerField(min_value=1,allow_null=True,required=False)
    caste_id=serializers.IntegerField(min_value=1,allow_null=True,required=False)
    sub_caste_id=serializers.IntegerField(min_value=1,allow_null=True,required=False)

    class Meta:
        model=m.AdmissionApplicant
        fields=('admission_applicant_id','institution_id','first_name','middle_name','last_name','display_name','date_of_birth','gender_id','primary_email','primary_phone','nationality_country_id','social_category_id','caste_id','sub_caste_id','version')
        read_only_fields=('admission_applicant_id','version')

    def to_representation(self,obj):
        data=super().to_representation(obj)
        if not allowed(self.context['request'].user,'sensitive'):
            for name in ('date_of_birth','primary_email','primary_phone','social_category_id','caste_id','sub_caste_id'):
                data.pop(name,None)
        data['admission_applicant_id']=str(obj.pk)
        return data


class ApplicationSerializer(StrictSerializer):
    admission_applicant_id=serializers.IntegerField(min_value=1)
    programme_id=serializers.IntegerField(min_value=1)
    specialization_id=serializers.IntegerField(min_value=1,allow_null=True,required=False)
    academic_year_id=serializers.IntegerField(min_value=1)
    admission_category_id=serializers.IntegerField(min_value=1,allow_null=True,required=False)

    class Meta:
        model=m.AdmissionApplication
        fields=('application_id','application_number','admission_applicant_id','programme_id','specialization_id','academic_year_id','admission_category_id','application_date','remarks','application_status','eligibility_status','version')
        read_only_fields=('application_id','application_number','application_status','eligibility_status','version')

    def to_representation(self,obj):
        data=super().to_representation(obj)
        data['application_id']=str(obj.pk)
        data['admission_applicant_id']=str(obj.admission_applicant_id)
        data['programme_name']=obj.programme.programme_name
        return data


class EnrolmentSerializer(serializers.ModelSerializer):
    class Meta:
        model=m.StudentProgrammeEnrolment
        fields=('enrolment_id','application_id','student_id','programme_id','specialization_id','curriculum_scheme_id','admission_academic_year_id','admission_category_id','admission_date','admission_semester_id','expected_completion_date','enrolment_status','version')
        read_only_fields=fields

    def to_representation(self,obj):
        data=super().to_representation(obj)
        for name in ('enrolment_id','application_id','student_id'):
            data[name]=str(data[name])
        return data


class HistorySerializer(serializers.ModelSerializer):
    class Meta:
        model=m.EnrolmentStatusHistory
        fields=('enrolment_status_history_id','enrolment_id','old_status','new_status','effective_date','reason','actor_id','occurred_at','sequence_number','request_id')
        read_only_fields=fields


class TransitionSerializer(serializers.Serializer):
    target=serializers.CharField(max_length=20)
    reason=serializers.CharField(max_length=500)


class LifecycleSerializer(TransitionSerializer):
    effective_date=serializers.DateField()


class ClearanceSerializer(serializers.Serializer):
    reference=serializers.CharField(max_length=150)


class AdmitSerializer(serializers.Serializer):
    student_id=serializers.IntegerField(min_value=1)
    curriculum_scheme_id=serializers.IntegerField(min_value=1)
    admission_semester_id=serializers.IntegerField(min_value=1)
    admission_date=serializers.DateField()
    expected_completion_date=serializers.DateField(required=False,allow_null=True)
