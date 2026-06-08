from importlib import import_module

_SERIALIZER_EXPORTS = {
    "DashboardStatsSerializer": "apps.admin_panel.api.serializers.dashboard",
    "AnalysisResultAdminSerializer": "apps.admin_panel.api.serializers.datasets",
    "CommentAdminSerializer": "apps.admin_panel.api.serializers.datasets",
    "DatasetAnalysisResultSerializer": "apps.admin_panel.api.serializers.datasets",
    "ReportAdminSerializer": "apps.admin_panel.api.serializers.datasets",
    "ModelAdminSerializer": "apps.admin_panel.api.serializers.runtime_registry",
    "TrainingRecordCreateSerializer": "apps.admin_panel.api.serializers.training_admin",
    "TrainingRecordQuerySerializer": "apps.admin_panel.api.serializers.training_admin",
    "TrainingRecordSerializer": "apps.admin_panel.api.serializers.training_admin",
    "OperationLogSerializer": "apps.admin_panel.api.serializers.users_admin",
    "UserAdminSerializer": "apps.admin_panel.api.serializers.users_admin",
}

__all__ = sorted(_SERIALIZER_EXPORTS)


def __getattr__(name):
    module_path = _SERIALIZER_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
