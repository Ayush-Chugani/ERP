from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from .errors import envelope

class StatusSerializer(serializers.Serializer):
    status = serializers.CharField()

class Liveness(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    @extend_schema(responses=StatusSerializer, auth=[])
    def get(self, request):
        return Response({"status": "ok"})

class Readiness(Liveness):
    @extend_schema(responses={200: StatusSerializer, 503: dict}, auth=[])
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                raise RuntimeError("Pending migrations")
        except Exception:
            return Response(envelope("not_ready", "Service unavailable."), status=503)
        return Response({"status": "ready"})

class ApiRoot(APIView):
    @extend_schema(responses=dict)
    def get(self, request):
        return Response({"version": "v1"})
