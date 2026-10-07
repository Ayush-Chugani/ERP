from rest_framework.pagination import PageNumberPagination

class BoundedPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
    def paginate_queryset(self, queryset, request, view=None):
        if hasattr(queryset, "order_by"):
            ordering = tuple(queryset.query.order_by) or tuple(queryset.model._meta.ordering or ())
            key = queryset.model._meta.pk
            # A composite key cannot be ordered through the "pk" alias under DISTINCT.
            pks = [f.name for f in key.fields] if getattr(key, "fields", None) else [key.name]
            named = [item.lstrip("-") for item in ordering if isinstance(item, str)]
            if getattr(key, "fields", None) and "pk" in named:
                ordering = tuple(x for item in ordering for x in (
                    [("-" if item.startswith("-") else "") + n for n in pks] if item.lstrip("-") == "pk" else [item]))
                named = [item.lstrip("-") for item in ordering if isinstance(item, str)]
            ordering += tuple(n for n in pks if n not in named)
            queryset = queryset.order_by(*ordering)
        return super().paginate_queryset(queryset, request, view)
