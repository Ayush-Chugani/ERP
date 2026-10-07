from django.conf import settings
from django.db.models import Q,F
from rest_framework.exceptions import NotFound,PermissionDenied
from apps.tenancy.models import ScopeGrant,Membership
from apps.organization.models import Institution
from apps.people_master.models import AccountLink
from . import models as m
ADMIN=['INSTITUTION_ADMIN','CAMPUS_ADMIN','DEPARTMENT_ADMIN']
def enabled(actor,cap):return bool(settings.FEEDBACK_ENABLED and actor.is_authenticated and actor.is_active and (actor.is_superuser or actor.has_perm('feedback.'+cap)))
def grants(actor):
    return ScopeGrant.objects.filter(membership__user=actor,membership__is_active=True,is_active=True,membership__institution__institutionmodule__feedback=True,membership__institution__is_active=True,membership__institution__university__is_active=True).filter(Q(campus__isnull=True)|Q(campus__institution=F('membership__institution'))).filter(Q(department__isnull=True)|Q(department__campus=F('campus')))
def valid_limits(limits):return isinstance(limits,dict) and all(isinstance(v,list) and len(v)<=500 and all(type(k)is int and k>0 for k in v) for v in limits.values())
def institutions(actor,cap):
    qs=Institution.objects.filter(is_active=True,university__is_active=True)
    if not enabled(actor,cap):return qs.none()
    if actor.is_superuser:return qs
    return qs.filter(pk__in=grants(actor).filter(role='INSTITUTION_ADMIN',record_limits={}).values('membership__institution_id'))
def bank(actor,inst,cap):
    if not institutions(actor,cap).filter(pk=inst).exists():raise NotFound('Feedback resource unavailable.')
def cycles(actor,cap='manage_cycles'):
    qs=m.Cycle.objects.filter(questionnaire__institution__is_active=True,questionnaire__institution__university__is_active=True)
    if not enabled(actor,cap):return qs.none()
    if actor.is_superuser:return qs
    cond=Q(pk__in=[])
    for g in grants(actor):
        if g.role not in ADMIN or not valid_limits(g.record_limits):continue
        part=Q(questionnaire__institution_id=g.membership.institution_id)
        if g.campus_id:part &= Q(programme__department__campus_id=g.campus_id)
        if g.department_id:part &= Q(programme__department_id=g.department_id)
        if set(g.record_limits)-{'feedback-cycles','programmes'}:continue
        if 'feedback-cycles' in g.record_limits:part &= Q(pk__in=g.record_limits['feedback-cycles'])
        if 'programmes' in g.record_limits:part &= Q(programme_id__in=g.record_limits['programmes'])
        cond |= part
    return qs.filter(cond).distinct()
def cycle(actor,pk,cap='manage_cycles',lock=False):
    qs=cycles(actor,cap).select_related('questionnaire','academic_term','programme')
    if lock:qs=qs.select_for_update()
    obj=qs.filter(pk=pk).first()
    if obj is None:raise NotFound('Feedback resource unavailable.')
    return obj
def student(actor,inst):
    if not settings.FEEDBACK_ENABLED or not actor.is_authenticated or not actor.is_active:raise PermissionDenied()
    link=AccountLink.objects.filter(user=actor,student__institution_id=inst).select_related('student').first()
    if not link or not Membership.objects.filter(user=actor,institution_id=inst,is_active=True,institution__institutionmodule__feedback=True,institution__is_active=True,institution__university__is_active=True).exists():raise NotFound('Feedback unavailable.')
    return link.student_id


def schedule(actor,questionnaire,values):
    if institutions(actor,'manage_cycles').filter(pk=questionnaire.institution_id).exists():return
    if not enabled(actor,'manage_cycles') or not values.get('programme_id'):raise NotFound()
    from apps.organization.models import Programme
    programme=Programme.objects.select_related('department__campus').filter(pk=values['programme_id'],is_active=True,department__is_active=True,department__campus__is_active=True,department__campus__institution_id=questionnaire.institution_id).first()
    if not programme:raise NotFound()
    for grant in grants(actor):
        if grant.role not in ADMIN or not valid_limits(grant.record_limits) or set(grant.record_limits)-{'programmes'}:continue
        if grant.membership.institution_id!=questionnaire.institution_id:continue
        if grant.campus_id and grant.campus_id!=programme.department.campus_id:continue
        if grant.department_id and grant.department_id!=programme.department_id:continue
        if 'programmes' in grant.record_limits and programme.pk not in grant.record_limits['programmes']:continue
        return
    raise NotFound()


def scheduling_programmes(actor):
    from apps.organization.models import Programme
    qs=Programme.objects.filter(is_active=True,department__is_active=True,department__campus__is_active=True,department__campus__institution__is_active=True,department__campus__institution__university__is_active=True)
    if not enabled(actor,'manage_cycles'):return qs.none()
    if actor.is_superuser:return qs
    cond=Q(pk__in=[])
    for grant in grants(actor):
        if grant.role not in ADMIN or not valid_limits(grant.record_limits) or set(grant.record_limits)-{'programmes'}:continue
        part=Q(department__campus__institution_id=grant.membership.institution_id)
        if grant.campus_id:part &= Q(department__campus_id=grant.campus_id)
        if grant.department_id:part &= Q(department_id=grant.department_id)
        if 'programmes' in grant.record_limits:part &= Q(pk__in=grant.record_limits['programmes'])
        cond |= part
    return qs.filter(cond).distinct()
