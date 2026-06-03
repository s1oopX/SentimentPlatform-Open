from rest_framework import status
from rest_framework.response import Response

from apps.admin_panel.api.responses import StandardResultsSetPagination
from apps.admin_panel.api.serializers.runtime_registry import ModelAdminSerializer
from apps.admin_panel.api.views.base import AdminOnlyAPIView
from apps.analysis.models import Model
from apps.admin_panel.application.runtime_registry.queries import (
    build_runtime_model_list_response,
    build_runtime_model_payload as _build_runtime_model_payload,
    sanitize_runtime_model_payload,
)
from apps.admin_panel.domain.rules.runtime_registry import (
    needs_runtime_record_persistence,
)
from apps.admin_panel.application.runtime_registry.commands import (
    persist_runtime_model_payload,
)
from apps.admin_panel.infra.runtime_registry.registry import (
    is_effectively_runtime_compatible,
)


class ModelManagementView(AdminOnlyAPIView):
    def get(self, request):
        paginator = StandardResultsSetPagination()
        paginated_models = paginator.paginate_queryset(
            build_runtime_model_list_response(
                operator=request.user,
                build_runtime_model_payload_fn=_build_runtime_model_payload,
                needs_runtime_record_persistence_fn=needs_runtime_record_persistence,
                persist_runtime_model_payload_fn=persist_runtime_model_payload,
                sanitize_runtime_model_payload_fn=sanitize_runtime_model_payload,
            ),
            request,
            view=self,
        )
        serializer = ModelAdminSerializer(paginated_models, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, _request):
        return Response(
            {
                "error": "当前后端固定使用 settings.MODEL_PATH 指向的真实模型，不支持手工创建虚拟模型记录"
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class ModelActivateView(AdminOnlyAPIView):
    def post(self, _request, pk):
        model = Model.objects.filter(pk=pk).first()
        if not model:
            return Response({"error": "模型不存在"}, status=status.HTTP_404_NOT_FOUND)
        if not is_effectively_runtime_compatible(model):
            return Response(
                {"error": "该模型不兼容在线运行，不能直接启用"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not model.is_runtime_compatible:
            model.is_runtime_compatible = True
            model.save(update_fields=["is_runtime_compatible"])
        try:
            model.activate()
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"message": "模型已激活", "id": model.id, "is_active": model.is_active}
        )


class ModelLogsView(AdminOnlyAPIView):
    def get(self, request, pk):
        model = Model.objects.filter(pk=pk).first()
        if not model:
            return Response({"error": "模型不存在"}, status=status.HTTP_404_NOT_FOUND)

        from apps.admin_panel.infra.runtime_registry.selectors import (
            build_runtime_logs as _build_logs_from_payload,
        )

        # Build a payload compatible with build_runtime_logs
        # Don't call get_model_loader() — it blocks if model is loading
        payload = {
            "id": model.id,
            "path": model.path or "",
            "model_type": model.model_type or "",
            "metrics": {
                "runtime_type": model.model_type or "",
                "loaded": model.is_active,
                "device": "cpu",
            },
        }
        logs = _build_logs_from_payload(payload)
        return Response({"model_id": model.id, "logs": logs})
