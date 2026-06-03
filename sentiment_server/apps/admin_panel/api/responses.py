from rest_framework.response import Response

from core.pagination import StandardResultsSetPagination


def build_service_error_response(exc):
    return Response({"error": exc.message}, status=exc.status_code)
