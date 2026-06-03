from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.application.queries.runtime_capabilities import (
    build_runtime_capabilities_payload,
)


class RuntimeCapabilitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, _request):
        return Response(build_runtime_capabilities_payload())
