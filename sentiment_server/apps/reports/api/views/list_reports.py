from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import StandardResultsSetPagination
from apps.reports.application.queries.list_reports import list_reports_query
from apps.reports.api.serializers.reports import ReportSerializer


class ReportListView(APIView):
    """
    报告列表
    GET /api/report/list/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get("report_type", "")
        status_filter = request.query_params.get("status", "")

        reports = list_reports_query(
            user=request.user,
            report_type=report_type,
            status=status_filter,
        )

        paginator = StandardResultsSetPagination()
        paginated_reports = paginator.paginate_queryset(
            reports,
            request,
            view=self,
        )

        return paginator.get_paginated_response(
            ReportSerializer(paginated_reports, many=True).data
        )
