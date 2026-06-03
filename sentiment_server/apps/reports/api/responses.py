from rest_framework.response import Response


def error_response(message: str, *, status_code: int, **extra):
    payload = {"error": message}
    payload.update(extra)
    return Response(payload, status=status_code)


def message_response(message: str, *, status_code: int, **extra):
    payload = {"message": message}
    payload.update(extra)
    return Response(payload, status=status_code)
