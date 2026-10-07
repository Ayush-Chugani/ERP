"""Student-only, server-derived target policies; no arbitrary respondent IDs."""
from django.db.models import Q
from rest_framework.exceptions import NotFound,PermissionDenied
from apps.term_registration import models as r
from apps.teaching_timetable.models import FacultyAssignment
from . import permissions as p
class FeedbackTargetPolicy:
    def registrations(self,actor,cycle):
        if not p.enabled(actor,'submit_feedback'):raise PermissionDenied()
        student=p.student(actor,cycle.questionnaire.institution_id)
        qs=r.StudentTermRegistration.objects.filter(enrolment__student_id=student,programme_term_offering__academic_term=cycle.academic_term,programme__department__campus__institution_id=cycle.questionnaire.institution_id,registration_status__in=['APPROVED','COMPLETED'],programme__is_active=True,programme__department__is_active=True,programme__department__campus__is_active=True)
        if cycle.programme_id:qs=qs.filter(programme_id=cycle.programme_id)
        if cycle.target_policy=='COMPLETING':qs=qs.filter(enrolment__enrolment_status='COMPLETED')
        elif cycle.target_policy=='EXPLICIT':qs=qs.filter(pk__in=cycle.explicit_registrations)
        else:qs=qs.filter(enrolment__enrolment_status__in=['ACTIVE','COMPLETED'])
        return student,qs
    def targets(self,actor,cycle):
        _,terms=self.registrations(actor,cycle)
        if not terms.exists():return []
        kind=cycle.questionnaire.questionnaire_type
        if kind=='COURSE':
            courses=r.StudentCourseRegistration.objects.filter(term_registration__in=terms,registration_status__in=['APPROVED','COMPLETED']).select_related('course_offering__course')
            return [{'target':{'course_offering_id':str(row.course_offering_id)},'label':row.course_offering.course.course_code} for row in courses]
        if kind=='FACULTY':
            assignments=self.assignments(cycle,terms)
            return [{'target':{'faculty_assignment_id':str(a.pk)},'label':a.employee.display_name+' / '+a.course_offering_section.course_offering.course.course_code} for a in assignments]
        return [{'target':{},'label':cycle.programme.programme_name if cycle.programme_id else cycle.questionnaire.questionnaire_name}]
    def assignments(self,cycle,terms):
        rosters=r.CourseOfferingSectionStudent.objects.filter(course_registration__term_registration__in=terms,course_registration__registration_status__in=['APPROVED','COMPLETED'],effective_from__lte=cycle.academic_term.end_date).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=cycle.academic_term.start_date))
        return FacultyAssignment.objects.filter(course_offering_section_id__in=rosters.values('course_offering_section_id'),assignment_status__in=['ACTIVE','COMPLETED'],start_date__lte=cycle.academic_term.end_date).filter(Q(end_date__isnull=True)|Q(end_date__gte=cycle.academic_term.start_date)).select_related('employee','course_offering_section__course_offering__course')
    def validate_eligibility(self,actor,cycle,target):
        if not isinstance(target,dict):raise NotFound('Feedback unavailable.')
        student,terms=self.registrations(actor,cycle);term=terms.order_by('pk').first()
        if term is None:raise NotFound('Feedback unavailable.')
        kind=cycle.questionnaire.questionnaire_type;context={};key='institution:'+str(cycle.questionnaire.institution_id)
        if kind=='COURSE':
            if set(target)!={'course_offering_id'}:raise NotFound('Feedback unavailable.')
            course=r.StudentCourseRegistration.objects.filter(term_registration__in=terms,course_offering_id=target['course_offering_id'],registration_status__in=['APPROVED','COMPLETED']).select_related('term_registration').first()
            if course is None:raise NotFound('Feedback unavailable.')
            term=course.term_registration;context['course_offering_id']=course.course_offering_id;key='course:'+str(course.course_offering_id)
        elif kind=='FACULTY':
            if set(target)!={'faculty_assignment_id'}:raise NotFound('Feedback unavailable.')
            assignment=self.assignments(cycle,terms).filter(pk=target['faculty_assignment_id']).first()
            if assignment is None:raise NotFound('Feedback unavailable.')
            roster=r.CourseOfferingSectionStudent.objects.filter(course_offering_section=assignment.course_offering_section,course_registration__term_registration__in=terms,effective_from__lte=assignment.end_date or cycle.academic_term.end_date).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=assignment.start_date)).select_related('course_registration__term_registration').first()
            if roster is None:raise NotFound('Feedback unavailable.')
            term=roster.course_registration.term_registration;context.update(course_offering_id=assignment.course_offering_section.course_offering_id,faculty_assignment_id=assignment.pk);key='faculty:'+str(assignment.pk)
        else:
            if target:raise NotFound('Feedback unavailable.')
            if kind=='PROGRAMME':key='programme:'+str(cycle.programme_id)
            elif kind in ['EXIT','OTHER']:key=kind.lower()+':'+str(cycle.pk)
        return {'student':student,'registration':term.pk,'key':key,'context':context}
POLICY=FeedbackTargetPolicy()
