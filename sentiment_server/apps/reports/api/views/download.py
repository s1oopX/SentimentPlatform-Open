import re
from urllib.parse import quote

from django.http import FileResponse
from rest_framework.views import APIView

from core.request_ip import get_request_ip
from apps.reports.application.errors import ReportApplicationError
from apps.users.permissions import IsUserOrAdmin
from apps.reports.application.requests.download_report import download_report_request
from apps.reports.api.responses import error_response


def _sanitize_filename(name):
    safe_name = re.sub(r"[^A-Za-z0-9.\-]", "_", name)
    return safe_name.strip("._") or "report"


def _build_content_disposition(filename):
    safe_filename = _sanitize_filename(filename)
    encoded_filename = quote(filename)
    return (
        f'attachment; filename="{safe_filename}"; '
        f"filename*=UTF-8''{encoded_filename}"
    )


class ReportDownloadView(APIView):
    """
    下载报告
    GET /api/report/download/<id>/
    """

    permission_classes = [IsUserOrAdmin]


    def get(self, request, pk):
        try:
            result = download_report_request(
                user=request.user,
                report_id=pk,
                request_ip=get_request_ip(request),
            )
        except ReportApplicationError as exc:
            return error_response(exc.message, status_code=exc.status_code)

        response = FileResponse(
            result.artifact_path.open("rb"),
            content_type="application/octet-stream",
        )
        response["Content-Disposition"] = _build_content_disposition(result.filename)
        return response
