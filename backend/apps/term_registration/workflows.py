"""Offering, allocation and course commands; all writes share the governance lock."""
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import models as m
from .services import command, require_reason, save_validated, audit, snapshot, RegistrationConflict, check_capacity, matching_enrolment
from .policies import require_programme, SEAT_STATUSES


def versioned(obj, expected):
    if expected is None or str(obj.version) != str(expected):
        raise RegistrationConflict('Stale version; refresh the record before retrying.')


def changed(obj, actor, reason, before, action):
    obj.version += 1
    obj.updated_by = actor
    save_validated(obj)
    audit(obj, actor, programme_id(obj), action, reason, before)
    return obj


def programme_id(obj):
    if isinstance(obj, (m.ProgrammeTermOffering, m.StudentTermRegistration, m.RegistrationPolicy)):
        return obj.programme_id
    if isinstance(obj, m.ClassBatch):
        return obj.class_section.programme_term_offering.programme_id
    if isinstance(obj, m.CourseOfferingSectionStudent):
        return obj.course_offering.programme_term_offering.programme_id
    return obj.programme_term_offering.programme_id


RESOURCES = {
    'offerings': (m.ProgrammeTermOffering, 'programme'),
    'sections': (m.ClassSection, 'programme_term_offering__programme'),
    'batches': (m.ClassBatch, 'class_section__programme_term_offering__programme'),
    'terms': (m.StudentTermRegistration, 'programme'),
    'courses': (m.CourseOffering, 'programme_term_offering__programme'),
    'mappings': (m.CourseOfferingSection, 'programme_term_offering__programme'),
    'registrations': (m.StudentCourseRegistration, 'programme_term_offering__programme'),
    'rosters': (m.CourseOfferingSectionStudent, 'course_offering__programme_term_offering__programme'),
    'policies': (m.RegistrationPolicy, 'programme'),
    'audit': (m.RegistrationAudit, 'programme'),
}


def get(actor, resource, pk, action='manage_registration'):
    from .selectors import scoped
    from rest_framework.exceptions import NotFound
    obj = scoped(actor, resource, action).select_for_update().filter(pk=pk).first()
    if obj is None:
        raise NotFound('Registration resource unavailable.')
    return obj


def allowed(values, fields):
    extra = set(values) - set(fields)
    if extra:
        raise ValidationError({key: 'Unknown or immutable field.' for key in extra})


def window(offering):
    term = offering.academic_term
    today = timezone.localdate()
    if offering.status != 'REGISTRATION_OPEN' or term.status != 'REGISTRATION_OPEN' or not term.registration_start_date or not term.registration_end_date or not term.registration_start_date <= today <= term.registration_end_date:
        raise RegistrationConflict('Registration window is closed or not configured.')


def validate_offering(obj):
    obj.clean()
    term, scheme = obj.academic_term, obj.curriculum_scheme
    if term.status in ('CANCELLED','CLOSED','COMPLETED') or scheme.status != 'ACTIVE':
        raise RegistrationConflict('An available term and active curriculum scheme are required.')
    if scheme.effective_from > term.start_date or (scheme.effective_to and scheme.effective_to < term.end_date):
        raise ValidationError('Curriculum scheme does not cover the academic term.')
    if obj.specialization_id and not obj.specialization.is_active:
        raise ValidationError('Specialization is inactive.')
    from apps.curriculum_catalog.models import CurriculumCourse
    if not CurriculumCourse.objects.filter(curriculum_scheme=scheme, semester=obj.semester).exists():
        raise ValidationError('The selected scheme has no curriculum for this semester.')


@command
def create_offering(*, actor, values, reason):
    require_reason(reason)
    allowed(values, ['programme_id','academic_term_id','specialization_id','curriculum_scheme_id','semester_id'])
    require_programme(actor, values.get('programme_id'))
    from .selectors import require_references
    require_references(actor, values['programme_id'], {'schemes':values.get('curriculum_scheme_id')})
    obj = m.ProgrammeTermOffering(**values, created_by=actor, updated_by=actor)
    validate_offering(obj)
    save_validated(obj)
    audit(obj, actor, obj.programme_id, 'offering_created', reason)
    return obj


@command
def transition_offering(*, actor, pk, expected_version, target, reason):
    require_reason(reason)
    obj = get(actor, 'offerings', pk)
    versioned(obj, expected_version)
    transitions = {'PLANNED': {'REGISTRATION_OPEN','CANCELLED'}, 'REGISTRATION_OPEN': {'ACTIVE','CANCELLED'}, 'ACTIVE': {'COMPLETED'}}
    if target not in transitions.get(obj.status, set()):
        raise RegistrationConflict('Invalid offering transition.')
    if target == 'REGISTRATION_OPEN':
        validate_offering(obj)
        if obj.academic_term.status != 'REGISTRATION_OPEN' or not obj.academic_term.registration_start_date or not obj.academic_term.registration_end_date:
            raise RegistrationConflict('Open and configure the academic term registration window first.')
        if not m.ClassSection.objects.filter(programme_term_offering=obj, is_active=True).exists():
            raise RegistrationConflict('Create an active section first.')
        if not m.RegistrationPolicy.objects.filter(programme=obj.programme).exists():
            raise RegistrationConflict('Configure credit limits before opening registration.')
    if target in ('CANCELLED','COMPLETED'):
        if m.StudentTermRegistration.objects.filter(programme_term_offering=obj, registration_status__in=['DRAFT',*SEAT_STATUSES]).exists() or m.CourseOffering.objects.filter(programme_term_offering=obj).exclude(status__in=['CANCELLED','COMPLETED']).exists():
            raise RegistrationConflict('Resolve unfinished term registrations and course offerings first.')
    before = snapshot(obj); obj.status = target
    return changed(obj, actor, reason, before, 'offering_transition')


@command
def save_group(*, actor, resource, values, reason, pk=None, expected_version=None):
    require_reason(reason)
    if resource not in ('sections','batches'):
        raise ValidationError('Choose sections or batches.')
    fields = ['section_code','section_name','capacity','home_room_id','is_active'] if resource == 'sections' else ['batch_code','batch_name','capacity','is_active']
    parent = 'programme_term_offering_id' if resource == 'sections' else 'class_section_id'
    allowed(values, fields + ([] if pk else [parent]))
    if pk:
        obj = get(actor, resource, pk); versioned(obj, expected_version)
        # Codes and ownership stay stable once created.
        code = 'section_code' if resource == 'sections' else 'batch_code'
        if code in values and values[code] != getattr(obj, code):
            raise ValidationError('Codes are stable; create a new group instead.')
        before = snapshot(obj)
    else:
        owner = get(actor, 'offerings' if resource == 'sections' else 'sections', values.get(parent))
        obj = RESOURCES[resource][0](**{parent:owner.pk}, created_by=actor, updated_by=actor)
        before = {}
    for key, value in values.items(): setattr(obj, key, value)
    offering = obj.programme_term_offering if resource == 'sections' else obj.class_section.programme_term_offering
    if offering.status in ('COMPLETED','CANCELLED'):
        raise RegistrationConflict('Offering is closed.')
    if resource == 'sections' and obj.home_room_id:
        room = obj.home_room
        from .selectors import require_references
        require_references(actor, offering.programme_id, {'rooms':room.pk})
        if room.building.campus_id != offering.programme.department.campus_id or not room.is_active or not room.building.is_active:
            raise ValidationError('Home room must be active and on the programme campus.')
    seats = m.StudentTermRegistration.objects.filter(**{('class_section' if resource == 'sections' else 'class_batch'):obj.pk}, registration_status__in=SEAT_STATUSES).count() if pk else 0
    if (obj.capacity is not None and obj.capacity < seats) or (not obj.is_active and seats):
        raise RegistrationConflict('Existing reservations prevent this capacity or activation change.')
    if pk: return changed(obj, actor, reason, before, 'group_updated')
    save_validated(obj); audit(obj, actor, offering.programme_id, 'group_created', reason)
    return obj


@command
def configure_policy(*, actor, programme_id, maximum_credits, minimum_credits, reason, expected_version=None):
    require_reason(reason); require_programme(actor, programme_id, 'configure_registration')
    obj = m.RegistrationPolicy.objects.filter(programme_id=programme_id).first()
    before = snapshot(obj) if obj else {}
    if obj:
        versioned(obj, expected_version); obj.version += 1
    elif expected_version is not None:
        raise RegistrationConflict('Policy does not exist.')
    else: obj = m.RegistrationPolicy(programme_id=programme_id)
    obj.maximum_credits = maximum_credits; obj.minimum_credits = minimum_credits; obj.updated_by = actor
    save_validated(obj); audit(obj, actor, programme_id, 'policy_configured', reason, before)
    return obj


@command
def allocate(*, actor, pk, expected_version, reason, section_id=None, batch_id=None, automatic=False, effective_date=None):
    require_reason(reason)
    if effective_date is not None and effective_date != timezone.localdate():
        raise ValidationError('Apply class transfers on their effective day; scheduled state changes are not supported.')
    obj = get(actor, 'terms', pk); versioned(obj, expected_version)
    if obj.registration_status not in ('DRAFT', *SEAT_STATUSES):
        raise RegistrationConflict('Only unfinished registrations can be allocated.')
    # Changing a class with active course registrations must be done after resolving rosters.
    active_courses = m.StudentCourseRegistration.objects.filter(term_registration=obj, registration_status__in=SEAT_STATUSES)
    if active_courses.exists() and effective_date is None:
        raise ValidationError('An effective date is required to transfer active course rosters.')
    if obj.programme_term_offering.status not in ('PLANNED','REGISTRATION_OPEN','ACTIVE'):
        raise RegistrationConflict('Offering is closed.')
    before = snapshot(obj)
    if automatic:
        if section_id or batch_id or obj.class_section_id:
            raise ValidationError('Automatic allocation only assigns an unallocated registration.')
        candidates = []
        from .selectors import scoped
        for section in scoped(actor, 'sections').filter(programme_term_offering=obj.programme_term_offering, is_active=True):
            count = m.StudentTermRegistration.objects.filter(class_section=section, registration_status__in=SEAT_STATUSES).exclude(pk=obj.pk).count()
            if section.capacity is None or count < section.capacity:
                batches = []
                for batch in scoped(actor, 'batches').filter(class_section=section, is_active=True):
                    occupied = m.StudentTermRegistration.objects.filter(class_batch=batch, registration_status__in=SEAT_STATUSES).exclude(pk=obj.pk).count()
                    if batch.capacity is None or occupied < batch.capacity:
                        batches.append((Decimal(occupied) / batch.capacity if batch.capacity else Decimal(occupied), batch.pk))
                if m.ClassBatch.objects.filter(class_section=section, is_active=True).exists() and not batches:
                    continue
                candidates.append((Decimal(count) / section.capacity if section.capacity else Decimal(count), section.pk, min(batches)[1] if batches else None))
        if not candidates: raise RegistrationConflict('No eligible section and batch has capacity.')
        _, section_id, batch_id = min(candidates)
    section = get(actor, 'sections', section_id)
    if batch_id: get(actor, 'batches', batch_id)
    obj.class_section = section; obj.class_batch_id = batch_id
    obj.clean(); check_capacity(obj)
    changed(obj, actor, reason, before, 'allocation_changed')
    for registration in active_courses.order_by('pk'):
        for old in list(m.CourseOfferingSectionStudent.objects.filter(course_registration=registration,roster_status='ACTIVE')):
            candidates = m.CourseOfferingSection.objects.filter(course_offering=registration.course_offering,class_section=section,session_type=old.session_type).filter(Q(class_batch_id=batch_id)|Q(class_batch__isnull=True))
            mapping = candidates.order_by('-class_batch_id','pk').first()
            if mapping is None: raise RegistrationConflict('Destination is missing a required course session mapping.')
            registration.refresh_from_db()
            assign_roster(actor=actor,registration_id=registration.pk,mapping_id=mapping.pk,expected_version=registration.version,effective_date=effective_date,reason=reason)
    return obj


@command
def create_course(*, actor, values, reason):
    require_reason(reason)
    allowed(values, ['programme_term_offering_id','curriculum_course_id','course_id','offering_code','registration_capacity'])
    offering = get(actor, 'offerings', values.get('programme_term_offering_id'))
    if offering.status not in ('PLANNED','REGISTRATION_OPEN'):
        raise RegistrationConflict('Course setup is closed.')
    obj = m.CourseOffering(**values, created_by=actor, updated_by=actor)
    from .selectors import require_references
    require_references(actor, offering.programme_id, {'courses':obj.course_id,'curriculum-courses':obj.curriculum_course_id})
    if obj.curriculum_course_id is None:
        require_programme(actor, offering.programme_id, 'authorize_special_course')
    course = obj.course
    if course.owning_department.campus.institution_id != offering.programme.department.campus.institution_id or not course.is_active or not course.owning_department.is_active:
        raise ValidationError('Course must be active and belong to the programme institution.')
    if (course.effective_from and course.effective_from > offering.academic_term.start_date) or (course.effective_to and course.effective_to < offering.academic_term.end_date):
        raise ValidationError('Course availability must cover the term.')
    save_validated(obj); audit(obj, actor, offering.programme_id, 'course_offered', reason)
    return obj


@command
def transition_course(*, actor, pk, expected_version, target, reason):
    require_reason(reason); obj = get(actor, 'courses', pk); versioned(obj, expected_version)
    transitions = {'PLANNED':{'OPEN','CANCELLED'},'OPEN':{'ACTIVE','CANCELLED'},'ACTIVE':{'COMPLETED'}}
    if target not in transitions.get(obj.status,set()): raise RegistrationConflict('Invalid course offering transition.')
    if target == 'OPEN':
        window(obj.programme_term_offering)
        if not m.CourseOfferingSection.objects.filter(course_offering=obj).exists():
            raise RegistrationConflict('Create session mappings before opening a course.')
    if target in ('CANCELLED','COMPLETED') and m.StudentCourseRegistration.objects.filter(course_offering=obj,registration_status__in=SEAT_STATUSES).exists():
        raise RegistrationConflict('Resolve active course registrations first.')
    before = snapshot(obj); obj.status = target
    return changed(obj, actor, reason, before, 'course_transition')


@command
def create_mapping(*, actor, values, reason):
    require_reason(reason)
    allowed(values,['course_offering_id','class_section_id','class_batch_id','session_type'])
    course = get(actor,'courses',values.get('course_offering_id'))
    section = get(actor,'sections',values.get('class_section_id'))
    if values.get('class_batch_id'): get(actor,'batches',values['class_batch_id'])
    if course.status not in ('PLANNED','OPEN') or not section.is_active:
        raise RegistrationConflict('Mapping requires an available course and active section.')
    obj = m.CourseOfferingSection(**values,programme_term_offering_id=course.programme_term_offering_id,created_by=actor,updated_by=actor)
    if obj.class_batch_id and not obj.class_batch.is_active: raise ValidationError('Batch is inactive.')
    save_validated(obj); audit(obj,actor,programme_id(obj),'mapping_created',reason)
    return obj


def credits(term):
    return m.StudentCourseRegistration.objects.filter(term_registration=term,registration_status__in=[*SEAT_STATUSES,'COMPLETED']).exclude(registration_type='AUDIT').aggregate(total=Sum('course_offering__course__credits'))['total'] or Decimal(0)


def check_course_eligibility(term, course, kind):
    from .integrations import require_eligibility
    offering = term.programme_term_offering
    matching_enrolment(term.enrolment, offering); window(offering)
    if term.registration_status not in SEAT_STATUSES or course.status != 'OPEN' or course.programme_term_offering_id != offering.pk:
        raise RegistrationConflict('An active term registration and open course in the same offering are required.')
    course.clean()
    if not course.course.is_active or offering.curriculum_scheme.status != 'ACTIVE': raise RegistrationConflict('Course or curriculum scheme is inactive.')
    policy = m.RegistrationPolicy.objects.filter(programme_id=offering.programme_id).first()
    if policy is None: raise RegistrationConflict('Credit policy is not configured.')
    if kind == 'REGULAR' and (not course.curriculum_course_id or not course.curriculum_course.is_mandatory):
        raise ValidationError('Regular registration requires a mandatory curriculum course.')
    if kind == 'ELECTIVE' and (not course.curriculum_course_id or course.curriculum_course.is_mandatory):
        raise ValidationError('Elective registration requires an elective curriculum course.')
    if kind != 'AUDIT' and credits(term) + course.course.credits > policy.maximum_credits:
        raise RegistrationConflict('Configured maximum credits would be exceeded.')
    evidence = require_eligibility(term, course, kind)
    occupied = m.StudentCourseRegistration.objects.filter(course_offering=course,registration_status__in=SEAT_STATUSES).count()
    if course.registration_capacity is not None and occupied >= course.registration_capacity:
        raise RegistrationConflict('Course registration capacity is full.')
    return evidence


@command
def register_course(*, actor, term_id, course_id, registration_type, reason):
    require_reason(reason)
    term = get(actor,'terms',term_id); course = get(actor,'courses',course_id)
    evidence = check_course_eligibility(term,course,registration_type)
    obj = m.StudentCourseRegistration(term_registration=term,course_offering=course,programme_term_offering=term.programme_term_offering,registration_type=registration_type,registration_date=timezone.localdate(),created_by=actor,updated_by=actor)
    save_validated(obj)
    from .integrations import require_timetable
    candidates = m.CourseOfferingSection.objects.filter(course_offering=course,class_section=term.class_section).filter(Q(class_batch=term.class_batch)|Q(class_batch__isnull=True))
    if not candidates.exists(): raise RegistrationConflict('No course mapping matches the allocated class.')
    # Validate a compatible published choice for each session type before reserving a seat.
    for kind in set(candidates.values_list('session_type',flat=True)):
        failure = None
        for mapping in candidates.filter(session_type=kind):
            try:
                require_timetable(obj,mapping,max(timezone.localdate(),offering_start(term)))
                failure = None
                break
            except RegistrationConflict as exc: failure = exc
        if failure: raise failure
    audit(obj,actor,term.programme_id,'course_registered',reason,{'eligibility_reference':str(evidence['reference'])[:500]})
    return obj


def validate_roster_date(offering, day):
    today = timezone.localdate()
    if day < today or not offering.academic_term.start_date <= day <= offering.academic_term.end_date:
        raise ValidationError('Roster changes must be today or later and within the academic term.')


def close_roster(row, day, status, actor, reason):
    if day != timezone.localdate():
        raise ValidationError('Apply roster closure or transfer on its effective day.')
    if day <= row.effective_from:
        raise RegistrationConflict('A roster episode must end after it starts; same-day corrections require reconciliation.')
    before = snapshot(row); row.effective_to = day; row.roster_status = status
    changed(row,actor,reason,before,'roster_closed')


@command
def transition_registration(*, actor, pk, expected_version, target, effective_date, reason):
    require_reason(reason)
    action = 'approve_registration' if target == 'APPROVED' else 'manage_registration'
    obj = get(actor,'registrations',pk,action); versioned(obj,expected_version)
    transitions = {'REGISTERED':{'APPROVED','DROPPED','WITHDRAWN'},'APPROVED':{'DROPPED','WITHDRAWN','COMPLETED'}}
    if target not in transitions.get(obj.registration_status,set()):
        raise RegistrationConflict('Invalid course registration transition.')
    if target == 'APPROVED':
        window(obj.programme_term_offering)
        from .integrations import require_eligibility
        evidence = require_eligibility(obj.term_registration,obj.course_offering,obj.registration_type)
        if obj.term_registration.registration_status not in SEAT_STATUSES: raise RegistrationConflict('Term registration is inactive.')
        policy = m.RegistrationPolicy.objects.filter(programme_id=programme_id(obj)).first()
        if not policy or credits(obj.term_registration) > policy.maximum_credits: raise RegistrationConflict('Credit policy is absent or exceeded.')
    else:
        if effective_date != timezone.localdate():
            raise ValidationError('Apply course status changes on their effective day.')
        # Administrative completion may occur after the teaching term has ended.
        for row in m.CourseOfferingSectionStudent.objects.select_for_update().filter(course_registration=obj,roster_status='ACTIVE'):
            close_roster(row,effective_date,'COMPLETED' if target=='COMPLETED' else 'DROPPED',actor,reason)
    before = snapshot(obj)
    if target=='APPROVED': before['eligibility_reference']=str(evidence['reference'])[:500]
    obj.registration_status = target
    return changed(obj,actor,reason,before,'registration_transition')


@command
def assign_roster(*, actor, registration_id, mapping_id, expected_version, effective_date, reason):
    require_reason(reason)
    registration = get(actor,'registrations',registration_id); versioned(registration,expected_version)
    mapping = get(actor,'mappings',mapping_id)
    if registration.registration_status != 'APPROVED' or registration.course_offering_id != mapping.course_offering_id:
        raise RegistrationConflict('Roster requires an approved registration for this exact course.')
    term = registration.term_registration
    if mapping.class_section_id != term.class_section_id or (mapping.class_batch_id and mapping.class_batch_id != term.class_batch_id):
        raise ValidationError('Roster mapping does not match the allocated class and batch.')
    if not mapping.class_section.is_active or (mapping.class_batch_id and not mapping.class_batch.is_active):
        raise RegistrationConflict('Roster mapping is inactive.')
    validate_roster_date(registration.programme_term_offering,effective_date)
    previous = m.CourseOfferingSectionStudent.objects.select_for_update().filter(course_registration=registration,session_type=mapping.session_type,roster_status='ACTIVE').first()
    if previous:
        if previous.course_offering_section_id == mapping.pk: raise RegistrationConflict('Already assigned to this mapping.')
        close_roster(previous,effective_date,'TRANSFERRED',actor,reason)
    if m.CourseOfferingSectionStudent.objects.filter(course_registration=registration,session_type=mapping.session_type).filter(Q(effective_to__isnull=True)|Q(effective_to__gt=effective_date)).exists():
        raise RegistrationConflict('Roster dates overlap existing history.')
    from .integrations import require_timetable
    require_timetable(registration,mapping,effective_date)
    obj = m.CourseOfferingSectionStudent(course_registration=registration,course_offering_section=mapping,course_offering=registration.course_offering,session_type=mapping.session_type,effective_from=effective_date,created_by=actor,updated_by=actor)
    save_validated(obj)
    before = snapshot(registration)
    changed(registration,actor,reason,before,'roster_assignment')
    audit(obj,actor,programme_id(obj),'roster_started',reason)
    return obj

@command
def amend_course_capacity(*, actor, pk, expected_version, capacity, reason):
    require_reason(reason); obj=get(actor,'courses',pk); versioned(obj,expected_version)
    if obj.status in ('CANCELLED','COMPLETED'): raise RegistrationConflict('Course is closed.')
    count=m.StudentCourseRegistration.objects.filter(course_offering=obj,registration_status__in=SEAT_STATUSES).count()
    if capacity is not None and capacity<count: raise RegistrationConflict('Existing reservations exceed the proposed capacity.')
    before=snapshot(obj);obj.registration_capacity=capacity
    return changed(obj,actor,reason,before,'course_capacity')


@command
def correct_roll(*, actor, pk, expected_version, roll_number, reason):
    require_reason(reason);obj=get(actor,'terms',pk);versioned(obj,expected_version)
    if obj.registration_status not in ('DRAFT',*SEAT_STATUSES): raise RegistrationConflict('Registration is closed.')
    if not isinstance(roll_number,str) or not roll_number.strip(): raise ValidationError('Roll number cannot be blank.')
    before=snapshot(obj);obj.roll_number=roll_number.strip()
    return changed(obj,actor,reason,before,'roll_corrected')


def offering_start(term):
    return term.programme_term_offering.academic_term.start_date
