import os
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from rest_framework import status
from rest_framework.response import Response

from apps.admin_panel.api.responses import (
    StandardResultsSetPagination,
    build_service_error_response,
)
from apps.admin_panel.api.serializers import DatasetAnalysisResultSerializer
from apps.admin_panel.api.views.base import AdminOnlyAPIView
from apps.admin_panel.application.dataset_admin.commands import (
    import_dataset_command,
)
from apps.admin_panel.application.dataset_admin.queries import (
    build_dataset_export_query as _build_export_query_params,
    build_dataset_export_response,
    build_dataset_list_response,
)
from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.infra.audit_logs import create_operation_log
from apps.admin_panel.infra.automation.auto_retrain import build_auto_retrain_status
from apps.admin_panel.services import export_dataset
from core.request_ip import get_request_ip


def _resolve_export_file_path(file_path):
    export_root = Path(settings.EXPORT_ROOT).resolve()
    candidate = Path(file_path).resolve()
    try:
        candidate.relative_to(export_root)
    except ValueError as exc:
        raise AdminPanelApplicationError("导出文件路径不合法", 500) from exc
    if not candidate.exists() or not candidate.is_file():
        raise AdminPanelApplicationError("导出文件不存在", 404)
    return candidate


class DatasetView(AdminOnlyAPIView):
    def get(self, request):
        try:
            comments = build_dataset_list_response(
                project_name=request.query_params.get("project_name", ""),
                category=request.query_params.get("category", ""),
                source=request.query_params.get("source", ""),
                keyword=request.query_params.get("keyword", ""),
                final_sentiment=request.query_params.get("final_sentiment", ""),
                review_status=request.query_params.get("review_status", ""),
                analysis_channel=request.query_params.get("analysis_channel", ""),
                start_date=request.query_params.get("start_date", ""),
                end_date=request.query_params.get("end_date", ""),
            )
        except AdminPanelApplicationError as exc:
            return Response({"error": exc.message}, status=exc.status_code)

        paginator = StandardResultsSetPagination()
        paginated_comments = paginator.paginate_queryset(comments, request, view=self)
        return paginator.get_paginated_response(
            DatasetAnalysisResultSerializer(paginated_comments, many=True).data
        )

    _MAX_DELETE_IDS = 100

    def delete(self, request):
        return Response(
            {"error": "数据集管理用于沉淀用户分析记录，不支持删除记录"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class DatasetImportView(AdminOnlyAPIView):
    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "请上传文件"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = import_dataset_command(
                uploaded_file=file,
                project_name=request.data.get("project_name", ""),
                operator=request.user,
                client_ip=get_request_ip(request),
                create_operation_log_fn=create_operation_log,
                error_cls=AdminPanelApplicationError,
            )
        except AdminPanelApplicationError as exc:
            return build_service_error_response(exc)

        return Response(
            {
                "message": f"成功导入 {payload['count']} 条评论数据",
                "count": payload["count"],
            }
        )


class DatasetExportView(AdminOnlyAPIView):
    _ALLOWED_EXPORT_FORMATS = {"csv", "xlsx"}

    def get(self, request):
        export_format = request.query_params.get("format", "csv")
        if export_format not in self._ALLOWED_EXPORT_FORMATS:
            return Response(
                {"error": f"不支持的导出格式，仅允许 {', '.join(sorted(self._ALLOWED_EXPORT_FORMATS))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        service_export_format = "excel" if export_format == "xlsx" else export_format
        try:
            results = build_dataset_export_response(
                **_build_export_query_params(request)
            )
            file_path = export_dataset(
                results=results,
                export_format=service_export_format,
                operator=request.user,
                client_ip=get_request_ip(request),
            )
        except AdminPanelApplicationError as exc:
            return Response({"error": exc.message}, status=exc.status_code)

        try:
            resolved_file_path = _resolve_export_file_path(file_path)
        except AdminPanelApplicationError as exc:
            return Response({"error": exc.message}, status=exc.status_code)

        filename = os.path.basename(resolved_file_path)
        return FileResponse(
            resolved_file_path.open("rb"),
            content_type="application/octet-stream",
            as_attachment=True,
            filename=filename,
        )


class DatasetAutoRetrainStatusView(AdminOnlyAPIView):
    def get(self, _request):
        return Response(build_auto_retrain_status())
