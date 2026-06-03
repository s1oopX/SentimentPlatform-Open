from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.request_ip import get_request_ip
from apps.reports.api.responses import error_response, message_response
from apps.reports.api.serializers.reports import (
    ReportGenerateSerializer,
    ReportSerializer,
)
from apps.reports.application.errors import ReportApplicationError
from apps.reports.application.requests.generate_report import generate_report_request
from apps.users.permissions import IsUserOrAdmin


class ReportGenerateView(APIView):
    """
    生成报告
    POST /api/report/generate/
    """

    permission_classes = [IsUserOrAdmin]


    def post(self, request):
        serializer = ReportGenerateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = generate_report_request(
                user=request.user,
                report_type=serializer.validated_data["report_type"],
                report_format=serializer.validated_data["report_format"],
                start_date=serializer.validated_data.get("start_date"),
                end_date=serializer.validated_data.get("end_date"),
                request_params={
                    "category": serializer.validated_data.get("category", ""),
                    "requested_by_role": getattr(request.user, "role", ""),
                },
                request_ip=get_request_ip(request),
            )
        except ReportApplicationError as exc:
            return error_response(exc.message, status_code=exc.status_code)

        return message_response(
            result.message,
            status_code=status.HTTP_202_ACCEPTED,
            report=ReportSerializer(result.report).data,
        )
