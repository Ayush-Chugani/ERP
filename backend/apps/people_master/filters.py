from django.db.models import Q
from rest_framework.exceptions import ValidationError
from .catalogue import FIELDS, CONFIDENTIAL, RESTRICTED
from .permissions import permitted


def filter_rows(query, params, actor):
    model = query.model
    allowed = (
        {"page", "page_size", "search", "ordering"}
        | {n for n in FIELDS[model] if n.endswith("_id")}
        | {
            f.name
            for f in model._meta.fields
            if f.choices or f.name in ("is_active", "is_primary")
        }
    )
    hidden = (
        CONFIDENTIAL if not permitted(actor, model, "confidential") else set()
    ) | (RESTRICTED if not permitted(actor, model, "restricted") else set())
    allowed -= hidden
    if set(params) - allowed:
        raise ValidationError("Unsupported filter.")
    for name, values in params.lists():
        if len(values) != 1:
            raise ValidationError("Supply each parameter once.")
        value = values[0]
        if name.endswith("_id"):
            if not value.isdigit() or int(value) < 1:
                raise ValidationError({name: "Use a positive ID."})
            query = query.filter(**{name: int(value)})
        elif name.startswith("is_"):
            if value not in ("true", "false"):
                raise ValidationError({name: "Use true or false."})
            query = query.filter(**{name: value == "true"})
        elif name not in ("page", "page_size", "search", "ordering"):
            query = query.filter(**{name: value})
    search = params.get("search", "")
    if len(search) > 100:
        raise ValidationError("Search is limited to 100 characters.")
    # Never search masked demographics or contact fields (even indirectly).
    search_fields = [
        f.name
        for f in model._meta.fields
        if f.name
        in (
            "display_name",
            "student_number",
            "employee_number",
            "agency_name",
            "agency_code",
            "type_name",
            "type_code",
            "category_name",
            "category_code",
            "designation_name",
            "designation_code",
            "source_name",
            "source_code",
        )
    ]
    if search and search_fields:
        expr = Q()
        for name in search_fields:
            expr |= Q(**{name + "__icontains": search})
        query = query.filter(expr)
    ordering = params.get("ordering", "pk").split(",")
    if any(x.lstrip("-") not in {"pk", *search_fields} for x in ordering):
        raise ValidationError("Unsupported ordering field.")
    # A composite primary key cannot be ordered through the "pk" alias under
    # SELECT DISTINCT (invalid SQL); order by its member columns instead.
    key = query.model._meta.pk
    if getattr(key, "fields", None):
        expanded = []
        for item in ordering:
            if item.lstrip("-") == "pk":
                sign = "-" if item.startswith("-") else ""
                expanded.extend(sign + f.name for f in key.fields)
            else:
                expanded.append(item)
        ordering = expanded
    return query.order_by(*ordering)
