"""Thin serializers; every write delegates to the governed command service."""

from django.db import models
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .catalogue import FIELDS, RESTRICTED, CONFIDENTIAL
from .permissions import permitted, scoped
from .services import key, version
from .models import PeopleRevision
from .catalogue import PATHS


@extend_schema_field({"type": "string", "pattern": "^[1-9][0-9]*$"})
class Identifier(serializers.Field):
    def to_internal_value(self, value):
        if (
            type(value) is bool
            or not str(value).isdigit()
            or not 1 <= int(value) <= 2**64 - 1
        ):
            raise serializers.ValidationError("Use a positive integer ID.")
        return int(value)

    def to_representation(self, value):
        return str(value)


class BatchedPeopleList(serializers.ListSerializer):
    def to_representation(self, data):
        rows = list(data)
        if rows:
            model = type(rows[0])
            ids = [row.pk for row in rows]
            actor = self.context["request"].user
            self.context["versions"] = {
                r.record_key: str(r.version)
                for r in PeopleRevision.objects.filter(
                    resource=PATHS[model], record_key__in=[key(pk) for pk in ids]
                )
            }
            self.context["capabilities"] = {
                action: {
                    key(pk)
                    for pk in scoped(model, actor, action)
                    .filter(pk__in=ids)
                    .values_list("pk", flat=True)
                }
                for action in ("change", "transition", "export")
            }
        return super().to_representation(rows)


class ReadSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    version = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    masked_fields = serializers.SerializerMethodField()

    def get_id(self, obj) -> str:
        return key(obj.pk)

    def get_version(self, obj) -> str:
        return (
            self.context["versions"].get(key(obj.pk), "0")
            if "versions" in self.context
            else version(obj)
        )

    def get_actions(self, obj) -> list[str]:
        actor = self.context["request"].user
        return [
            a
            for a in ("change", "transition", "export")
            if (
                a != "transition"
                or any(
                    f.name
                    in (
                        "student_status",
                        "employment_status",
                        "is_active",
                        "is_primary",
                    )
                    for f in obj._meta.fields
                )
            )
            and (
                key(obj.pk) in self.context["capabilities"][a]
                if "capabilities" in self.context
                else scoped(type(obj), actor, a).filter(pk=obj.pk).exists()
            )
        ]

    def get_masked_fields(self, obj) -> list[str]:
        actor = self.context["request"].user
        hidden = (
            RESTRICTED if not permitted(actor, type(obj), "restricted") else set()
        ) | (CONFIDENTIAL if not permitted(actor, type(obj), "confidential") else set())
        return sorted(hidden & set(self.fields))

    def to_representation(self, obj):
        values = super().to_representation(obj)
        for name in values["masked_fields"]:
            values.pop(name, None)
        return values


class WriteSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError(
                {"fields": "Unsupported or protected fields."}
            )
        result = super().to_internal_value(data)
        return {
            k: (
                None
                if isinstance(v, str) and not v.strip() and self.fields[k].allow_null
                else v
            )
            for k, v in result.items()
        }

    def create(self, validated_data):
        raise RuntimeError("Use the people command service.")

    def update(self, instance, validated_data):
        raise RuntimeError("Use the people command service.")


READ = {}
WRITE = {}
for model, names in FIELDS.items():
    read_fields = {}
    write_fields = {}
    output = []
    for f in model._meta.fields:
        if isinstance(f, (models.CompositePrimaryKey, models.GeneratedField)):
            continue
        name = f.attname
        output.append(name)
        if f.is_relation or f.primary_key:
            read_fields[name] = Identifier(read_only=True, allow_null=f.null)
            if name in names:
                write_fields[name] = Identifier(required=not f.null, allow_null=f.null)
    meta = type(
        "Meta",
        (),
        {
            "model": model,
            "fields": tuple(output) + ("id", "version", "actions", "masked_fields"),
            "list_serializer_class": BatchedPeopleList,
        },
    )
    READ[model] = type(
        model.__name__ + "ReadSerializer",
        (ReadSerializer,),
        {"Meta": meta, **read_fields},
    )
    meta = type(
        "Meta",
        (),
        {
            "model": model,
            "fields": names,
            "validators": [],
            "extra_kwargs": {n: {"validators": []} for n in names},
        },
    )
    WRITE[model] = type(
        model.__name__ + "WriteSerializer",
        (WriteSerializer,),
        {"Meta": meta, **write_fields},
    )
