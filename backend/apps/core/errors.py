import logging
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler
logger = logging.getLogger(__name__)

def envelope(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details or {}}}

def exception_handler(exc, context):
    response = drf_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API failure")
        return Response(envelope("internal_error", "An unexpected error occurred."), status=500)
    code = getattr(exc, "default_code", "request_error")
    message = "Request validation failed." if response.status_code == 400 else "Request failed."
    if isinstance(response.data, dict) and "detail" in response.data:
        message = str(response.data["detail"])
    response.data = envelope(code, message, response.data)
    return response

def not_found(request, exception=None):
    return JsonResponse(envelope("not_found", "Resource not found."), status=404)
def server_error(request):
    return JsonResponse(envelope("internal_error", "An unexpected error occurred."), status=500)
