from rest_framework.response import Response

from apps.admin_panel.api.responses import StandardResultsSetPagination
from apps.admin_panel.api.serializers import OperationLogSerializer
from apps.admin_panel.api.views.base import AdminOnlyAPIView
from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.infra.selectors.logs import get_filtered_logs


class OperationLogView(AdminOnlyAPIView):
    def get(self, request):
        try:
            logs = get_filtered_logs(
                user_id=request.query_params.get("user_id", ""),
                action=request.query_params.get("action", ""),
                start_date=request.query_params.get("start_date", ""),
                end_date=request.query_params.get("end_date", ""),
                search=request.query_params.get("search", ""),
            )
        except AdminPanelApplicationError as exc:
            return Response({"error": exc.message}, status=exc.status_code)

        paginator = StandardResultsSetPagination()
        paginated_logs = paginator.paginate_queryset(logs, request, view=self)
        return paginator.get_paginated_response(
            OperationLogSerializer(paginated_logs, many=True).data
        )
