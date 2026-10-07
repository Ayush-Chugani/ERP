from django.core.exceptions import ValidationError


def clean_record(obj):
    from . import models as m
    errors={}
    if isinstance(obj,m.ProgrammeTermOffering):
        if obj.specialization_id and obj.specialization.programme_id!=obj.programme_id:
            errors['specialization']='Specialization belongs to another programme.'
        if (obj.curriculum_scheme.programme_id,obj.curriculum_scheme.specialization_id)!=(obj.programme_id,obj.specialization_id):
            errors['curriculum_scheme']='Scheme must match programme and specialization.'
        if obj.semester.semester_number>obj.programme.duration_semesters:
            errors['semester']='Semester exceeds programme duration.'
    if isinstance(obj,m.StudentTermRegistration):
        offering=obj.programme_term_offering
        if (obj.enrolment.programme_id,obj.enrolment.specialization_id,obj.enrolment.curriculum_scheme_id)!=(offering.programme_id,offering.specialization_id,offering.curriculum_scheme_id):
            errors['enrolment']='Enrolment must match offered programme, specialization and scheme.'
        if obj.programme_id!=offering.programme_id:
            errors['programme']='Derived programme does not match.'
    if isinstance(obj,(m.StudentTermRegistration,m.CourseOfferingSection)):
        if obj.class_section_id and obj.class_section.programme_term_offering_id!=obj.programme_term_offering_id:
            errors['class_section']='Section belongs to another offering.'
        if obj.class_batch_id and obj.class_batch.class_section_id!=obj.class_section_id:
            errors['class_batch']='Batch belongs to another section.'
    if isinstance(obj,m.CourseOffering) and obj.curriculum_course_id:
        curriculum=obj.curriculum_course
        offering=obj.programme_term_offering
        if (curriculum.course_id,curriculum.curriculum_scheme_id,curriculum.semester_id)!=(obj.course_id,offering.curriculum_scheme_id,offering.semester_id):
            errors['curriculum_course']='Course, scheme and semester must match.'
    if isinstance(obj,(m.CourseOfferingSection,m.StudentCourseRegistration)):
        if obj.course_offering.programme_term_offering_id!=obj.programme_term_offering_id:
            errors['course_offering']='Course offering belongs to another term context.'
    if isinstance(obj,m.StudentCourseRegistration) and obj.term_registration.programme_term_offering_id!=obj.programme_term_offering_id:
        errors['term_registration']='Term registration belongs to another offering.'
    if isinstance(obj,m.CourseOfferingSectionStudent):
        if obj.course_offering_section.course_offering_id!=obj.course_offering_id or obj.course_registration.course_offering_id!=obj.course_offering_id:
            errors['course_offering']='Roster owners must reference the same course offering.'
        if obj.session_type!=obj.course_offering_section.session_type:
            errors['session_type']='Session type does not match the mapping.'
    if errors:
        raise ValidationError(errors)
