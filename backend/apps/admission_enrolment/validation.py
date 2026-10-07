from django.core.exceptions import ValidationError
from django.utils import timezone


def clean_record(obj):
    from .models import AdmissionApplicant, AdmissionApplication, StudentProgrammeEnrolment, EnrolmentStatusHistory
    errors = {}
    if isinstance(obj, AdmissionApplicant):
        if obj.date_of_birth and obj.date_of_birth > timezone.localdate():
            errors['date_of_birth'] = 'Birth date cannot be in the future.'
        for child, parent in [('sub_caste', 'caste'), ('caste', 'social_category')]:
            if getattr(obj, child + '_id') and getattr(getattr(obj, child), parent + '_id') != getattr(obj, parent + '_id'):
                errors[child] = 'Parent selection does not match.'
        if obj.canonical_student_id and obj.canonical_student.institution_id != obj.institution_id:
            errors['canonical_student'] = 'Student must belong to the applicant institution.'
    if isinstance(obj, (AdmissionApplication, StudentProgrammeEnrolment)):
        if obj.specialization_id and obj.specialization.programme_id != obj.programme_id:
            errors['specialization'] = 'Specialization belongs to another programme.'
    if isinstance(obj, AdmissionApplication):
        if obj.admission_applicant_id and obj.programme_id and obj.admission_applicant.institution_id != obj.programme.department.campus.institution_id:
            errors['programme'] = 'Programme must belong to the applicant institution.'
    if isinstance(obj, StudentProgrammeEnrolment):
        scheme = obj.curriculum_scheme
        if scheme.programme_id != obj.programme_id or scheme.specialization_id != obj.specialization_id:
            errors['curriculum_scheme'] = 'Scheme must match programme and specialization exactly.'
        if obj.admission_semester.semester_number > obj.programme.duration_semesters:
            errors['admission_semester'] = 'Semester exceeds programme duration.'
        if not obj.admission_academic_year.start_date <= obj.admission_date <= obj.admission_academic_year.end_date:
            errors['admission_date'] = 'Admission date must be inside its academic year.'
        app = obj.application
        if (app.admitted_student_id, app.programme_id, app.specialization_id, app.academic_year_id, app.admission_category_id) != (obj.student_id, obj.programme_id, obj.specialization_id, obj.admission_academic_year_id, obj.admission_category_id):
            errors['application'] = 'Enrolment must match the admitted application.'
        if obj.student.institution_id != app.admission_applicant.institution_id:
            errors['student'] = 'Student institution does not match.'
        if obj.transfer_from_id == obj.pk and obj.pk:
            errors['transfer_from'] = 'An enrolment cannot transfer to itself.'
    if isinstance(obj, EnrolmentStatusHistory):
        if not obj.reason.strip():
            errors['reason'] = 'A reason is required.'
        if (obj.sequence_number == 1) != (obj.old_status is None):
            errors['old_status'] = 'Only the initial event has no old status.'
        if obj.correction_of_id and obj.correction_of.enrolment_id != obj.enrolment_id:
            errors['correction_of'] = 'Correction must refer to this enrolment.'
    if errors:
        raise ValidationError(errors)
