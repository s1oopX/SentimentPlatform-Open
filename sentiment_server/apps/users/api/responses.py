from rest_framework.response import Response


def build_error_response(exc):
    return Response({"error": exc.message}, status=exc.status_code)
