from rest_framework import serializers

from apps.admin_panel.infra.runtime_registry.registry import (
    is_effectively_runtime_compatible,
    runtime_artifact_type,
    runtime_artifacts_complete,
)
from apps.analysis.models import Model


class ModelAdminSerializer(serializers.ModelSerializer):
    source_run_id = serializers.ReadOnlyField()
    source_run_record_id = serializers.SerializerMethodField()
    source_run_name = serializers.SerializerMethodField()
    dataset_ref = serializers.SerializerMethodField()
    is_runtime_compatible = serializers.SerializerMethodField()
    runtime_type = serializers.SerializerMethodField()
    artifact_complete = serializers.SerializerMethodField()
    runtime_incompatibility_reason = serializers.SerializerMethodField()

    class Meta:
        model = Model
        fields = [
            "id",
            "name",
            "version",
            "model_type",
            "metrics",
            "path",
            "is_active",
            "activated_at",
            "is_best_candidate",
            "source_run_id",
            "source_run_record_id",
            "source_run_name",
            "dataset_ref",
            "artifact_summary",
            "is_runtime_compatible",
            "runtime_type",
            "artifact_complete",
            "runtime_incompatibility_reason",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "activated_at"]

    def get_source_run_record_id(self, obj):
        if not obj.source_run_id:
            return ""
        return f"run-{obj.source_run_id}"

    def get_source_run_name(self, obj):
        if not obj.source_run_id:
            return ""
        return obj.source_run.name

    def get_dataset_ref(self, obj):
        if not obj.source_run_id:
            return ""
        return obj.source_run.dataset_ref

    def get_runtime_type(self, obj):
        return runtime_artifact_type(obj.path)

    def get_artifact_complete(self, obj):
        return runtime_artifacts_complete(obj.path)

    def get_is_runtime_compatible(self, obj):
        return is_effectively_runtime_compatible(obj)

    def get_runtime_incompatibility_reason(self, obj):
        runtime_type = self.get_runtime_type(obj)
        artifact_complete = self.get_artifact_complete(obj)
        if not is_effectively_runtime_compatible(obj):
            if runtime_type == "unsupported":
                return "当前运行时暂不支持该模型产物格式"
            return "该模型记录标记为不兼容在线运行"
        if not artifact_complete:
            return "模型产物缺失或格式不完整"
        return ""
