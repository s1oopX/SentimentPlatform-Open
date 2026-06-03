from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.admin_panel.application.training_admin.commands import (
    TrainingServiceError,
)
from apps.admin_panel.application.training_admin.queries import (
    build_training_comparison_payload,
    build_training_dashboard_payload,
    build_training_log_download_metadata,
    build_training_log_preview_payload,
    get_training_record_detail,
    list_training_records,
)
from apps.admin_panel.api.serializers import (
    TrainingRecordCreateSerializer,
    TrainingRecordQuerySerializer,
)
from apps.admin_panel.api.views.base import AdminOnlyAPIView, get_required_reason
from apps.admin_panel.infra.selectors.training_admin import get_training_run_by_id
from apps.admin_panel.infra.training.artifacts import build_artifact_summaries
from apps.admin_panel.infra.training.selectors import (
    read_training_log_preview,
    resolve_training_run_log_path,
)
from apps.admin_panel.training_services import (
    activate_registered_model_for_run,
    create_training_run,
    delete_training_run,
    retry_training_post_run,
    retry_training_run,
)
from core.request_ip import get_request_ip

def _build_content_disposition(filename, ascii_fallback):
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )


def _resolve_training_run_log_path(training_run):
    return resolve_training_run_log_path(training_run)


def _read_training_log_preview(log_path, max_bytes):
    return read_training_log_preview(log_path, max_bytes=max_bytes)


def _build_training_run_submit_note(training_run):
    if training_run.status == "running":
        return "真实训练任务已开始执行。"
    if training_run.status == "queued":
        return "真实训练任务已排队，等待 worker 执行。"
    return training_run.error_message or ""


def _parse_training_record_run_id(record_id):
    record_key = str(record_id or "")
    if not record_key.startswith("run-") or not record_key[4:].isdigit():
        return None
    return int(record_key[4:])


class TrainingDashboardView(AdminOnlyAPIView):
    def get(self, request):
        serializer = TrainingRecordQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(build_training_dashboard_payload())
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class TrainingComparisonView(AdminOnlyAPIView):
    def get(self, request):
        serializer = TrainingRecordQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(build_training_comparison_payload())
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class TrainingRecordListView(AdminOnlyAPIView):
    @extend_schema(operation_id="admin_training_records_list")
    def get(self, request):
        serializer = TrainingRecordQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                list_training_records(
                    page=serializer.validated_data.get("page", 1),
                    page_size=serializer.validated_data.get("page_size", 20),
                )
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        serializer = TrainingRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            training_run = create_training_run(
                validated_data=serializer.validated_data,
                operator=request.user,
                client_ip=get_request_ip(request),
            )
        except TrainingServiceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "record_id": f"run-{training_run.id}",
                "title": training_run.name,
                "source_type": "training_run",
                "workflow_type": training_run.task_type,
                "execution_mode": training_run.execution_mode,
                "status": training_run.status,
                "metric_highlights": training_run.metrics_snapshot,
                "artifact_summaries": build_artifact_summaries(
                    training_run.artifact_paths
                ),
                "has_log": bool(getattr(training_run, "log_path", "")),
                "log_filename": Path(getattr(training_run, "log_path", "")).name
                if getattr(training_run, "log_path", "")
                else "",
                "created_at": training_run.created_at.isoformat(),
                "note": _build_training_run_submit_note(training_run),
            },
            status=status.HTTP_201_CREATED,
        )


class TrainingRecordDetailView(AdminOnlyAPIView):
    @extend_schema(operation_id="admin_training_record_retrieve")
    def get(self, request, record_id):
        serializer = TrainingRecordQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            detail = get_training_record_detail(record_id)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not detail:
            return Response(
                {"error": "训练记录不存在"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(detail)

    @extend_schema(operation_id="admin_training_record_delete")
    def delete(self, request, record_id):
        run_id = _parse_training_record_run_id(record_id)
        if run_id is None:
            return Response(
                {"error": "训练记录编号不合法"}, status=status.HTTP_400_BAD_REQUEST
            )

        training_run = get_training_run_by_id(run_id)
        if not training_run:
            return Response(
                {"error": "训练记录不存在"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            reason = get_required_reason(request)
            delete_training_run(
                training_run=training_run,
                operator=request.user,
                reason=reason,
                client_ip=get_request_ip(request),
            )
        except TrainingServiceError as exc:
            return Response({"error": str(exc)}, status=exc.status_code)

        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainingRecordLogView(AdminOnlyAPIView):
    def get(self, _request, run_id):
        try:
            return Response(
                build_training_log_preview_payload(
                    run_id=run_id,
                    max_bytes=getattr(
                        settings, "TRAINING_LOG_PREVIEW_MAX_BYTES", 64 * 1024
                    ),
                    resolve_training_run_log_path_fn=_resolve_training_run_log_path,
                    read_training_log_preview_fn=_read_training_log_preview,
                )
            )
        except TrainingServiceError as exc:
            return Response({"error": str(exc)}, status=exc.status_code)


class TrainingRecordLogDownloadView(AdminOnlyAPIView):
    _MAX_LOG_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

    def get(self, _request, run_id):
        try:
            metadata = build_training_log_download_metadata(
                run_id=run_id,
                resolve_training_run_log_path_fn=_resolve_training_run_log_path,
            )
        except TrainingServiceError as exc:
            return Response({"error": str(exc)}, status=exc.status_code)

        log_path = Path(metadata["path"])
        file_size = log_path.stat().st_size
        if file_size > self._MAX_LOG_DOWNLOAD_BYTES:
            return Response(
                {"error": f"日志文件过大（{file_size // (1024 * 1024)}MB），请联系管理员通过其他方式获取"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        response = FileResponse(
            log_path.open("rb"),
            content_type=metadata["content_type"],
        )
        response["Content-Disposition"] = _build_content_disposition(
            metadata["download_filename"],
            f"training-log-{run_id}.log",
        )
        return response


class TrainingRecordRetryView(AdminOnlyAPIView):
    def post(self, request, run_id):
        training_run = get_training_run_by_id(run_id)
        if not training_run:
            return Response(
                {"error": "训练记录不存在"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            training_run = retry_training_run(
                training_run=training_run,
                operator=request.user,
                client_ip=get_request_ip(request),
            )
        except TrainingServiceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "record_id": f"run-{training_run.id}",
                "status": training_run.status,
                "note": "训练任务重试请求已提交。",
            }
        )


class TrainingRecordRetryPostRunView(AdminOnlyAPIView):
    def post(self, request, run_id):
        training_run = get_training_run_by_id(run_id)
        if not training_run:
            return Response(
                {"error": "训练记录不存在"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            training_run = retry_training_post_run(
                training_run=training_run,
                operator=request.user,
                client_ip=get_request_ip(request),
            )
        except TrainingServiceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "record_id": f"run-{training_run.id}",
                "status": training_run.status,
                "post_run_status": training_run.post_run_status,
                "note": "训练后处理重试请求已提交。",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TrainingRecordActivateModelView(AdminOnlyAPIView):
    def post(self, request, run_id):
        training_run = get_training_run_by_id(run_id)
        if not training_run:
            return Response(
                {"error": "训练记录不存在"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            model = activate_registered_model_for_run(
                training_run=training_run,
                operator=request.user,
                client_ip=get_request_ip(request),
            )
        except TrainingServiceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "record_id": f"run-{training_run.id}",
                "model_id": model.id,
                "model_name": model.name,
                "status": "activated",
            }
        )
