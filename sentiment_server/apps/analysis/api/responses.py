from rest_framework import status
from rest_framework.response import Response

from core.pagination import StandardResultsSetPagination
from apps.analysis.infra.model_runtime import build_model_unavailable_payload


def build_service_error_response(exc):
    return Response({"error": exc.message}, status=exc.status_code)


def model_unavailable_response(exc):
    return Response(
        build_model_unavailable_payload(exc),
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
