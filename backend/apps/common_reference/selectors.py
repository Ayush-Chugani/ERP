from django.db.models import Q
from .models import State, Caste, SubCaste

def related(queryset):
    if queryset.model is State: return queryset.select_related("country")
    if queryset.model is Caste: return queryset.select_related("social_category")
    if queryset.model is SubCaste: return queryset.select_related("caste__social_category")
    return queryset

def available(queryset):
    queryset=queryset.filter(is_active=True)
    if queryset.model is State: return queryset.filter(country__is_active=True)
    if queryset.model is Caste:
        return queryset.filter(Q(social_category__isnull=True)|Q(social_category__is_active=True))
    if queryset.model is SubCaste:
        return queryset.filter(caste__is_active=True).filter(Q(caste__social_category__isnull=True)|Q(caste__social_category__is_active=True))
    return queryset

def is_available(obj):
    if not obj.is_active: return False
    if isinstance(obj,State): return is_available(obj.country)
    if isinstance(obj,Caste): return obj.social_category is None or is_available(obj.social_category)
    if isinstance(obj,SubCaste): return is_available(obj.caste)
    return True
