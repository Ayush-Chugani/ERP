from django.db.models import Q, F
from apps.tenancy.models import ScopeGrant
from .catalogue import BY_MODEL
from .models import University, Institution, Campus


def scoped(model, actor, *, write=False):
    query=model.objects.all()
    if not actor or not actor.is_authenticated or not actor.is_active:
        return query.none()
    if actor.is_superuser:
        return query
    resource=BY_MODEL[model]
    grants=ScopeGrant.objects.filter(membership__user=actor,membership__is_active=True,
        membership__institution__institutionmodule__organization_structure=True,is_active=True)
    grants=grants.filter(Q(campus__isnull=True)|Q(campus__institution=F('membership__institution')))
    grants=grants.filter(Q(department__isnull=True)|Q(department__campus=F('campus')))
    if write:
        grants=grants.exclude(role__in=['TEACHER','STUDENT'])
    visibility=Q(pk__in=[])
    for grant in grants.select_related('membership__institution','campus','department'):
        if model is University:
            if write: continue
            part=Q(pk=grant.membership.institution.university_id)
        elif model is Institution:
            if write and grant.role!='INSTITUTION_ADMIN': continue
            part=Q(pk=grant.membership.institution_id)
        else:
            part=Q(**{resource.institution:grant.membership.institution_id})
            if grant.campus_id:
                part &= Q(**{resource.campus:grant.campus_id})
            if grant.department_id:
                if model is Campus:
                    if write: continue
                elif resource.department:
                    part &= Q(**{resource.department:grant.department_id})
                else:
                    continue
        if grant.role in ('TEACHER','STUDENT'):
            part &= Q(is_active=True)
            chain='';current=model
            while BY_MODEL[current].parent:
                name=BY_MODEL[current].parent;chain+=name+'__'
                part &= Q(**{chain+'is_active':True})
                current=current._meta.get_field(name).related_model
        limits=grant.record_limits
        if not isinstance(limits,dict): continue
        if resource.path in limits:
            ids=limits[resource.path]
            if not isinstance(ids,list) or any(type(pk) is not int or pk<1 for pk in ids): continue
            part &= Q(pk__in=ids[:500])
        visibility |= part
    return query.filter(visibility).distinct()


def related(query):
    r=BY_MODEL[query.model]
    paths=[f.name for f in query.model._meta.fields if f.is_relation]
    if r.institution and r.institution!='pk': paths.append(r.institution)
    model=query.model
    chain=''
    while BY_MODEL[model].parent:
        name=BY_MODEL[model].parent
        chain += ('__' if chain else '') + name
        paths.append(chain)
        model=model._meta.get_field(name).related_model
    return query.select_related(*paths)


def available(obj):
    if not obj.is_active: return False
    r=BY_MODEL.get(type(obj))
    if r and r.parent: return available(getattr(obj,r.parent))
    return True
