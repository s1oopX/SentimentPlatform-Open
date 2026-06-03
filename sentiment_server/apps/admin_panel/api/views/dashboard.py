from rest_framework.response import Response

from apps.admin_panel.api.views.base import AdminOnlyAPIView
from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.application.dashboard.queries import (
    build_dashboard_stats_response,
    parse_dashboard_date_range,
)


class DashboardStatsView(AdminOnlyAPIView):
    def get(self, request):
        try:
            start_date, end_date = parse_dashboard_date_range(request.query_params)
        except AdminPanelApplicationError as exc:
            return Response({"error": exc.message}, status=exc.status_code)

        return Response(build_dashboard_stats_response(start_date, end_date))
