from importlib import import_module

_VIEW_EXPORTS = {
    "AdminOnlyAPIView": "apps.admin_panel.api.views.base",
    "DashboardStatsView": "apps.admin_panel.api.views.dashboard",
    "DatasetExportView": "apps.admin_panel.api.views.datasets",
    "DatasetImportView": "apps.admin_panel.api.views.datasets",
    "DatasetView": "apps.admin_panel.api.views.datasets",
    "OperationLogView": "apps.admin_panel.api.views.logs",
    "ModelActivateView": "apps.admin_panel.api.views.runtime_registry",
    "ModelLogsView": "apps.admin_panel.api.views.runtime_registry",
    "ModelManagementView": "apps.admin_panel.api.views.runtime_registry",
    "TrainingComparisonView": "apps.admin_panel.api.views.training_admin",
    "TrainingDashboardView": "apps.admin_panel.api.views.training_admin",
    "TrainingRecordActivateModelView": "apps.admin_panel.api.views.training_admin",
    "TrainingRecordDetailView": "apps.admin_panel.api.views.training_admin",
    "TrainingRecordListView": "apps.admin_panel.api.views.training_admin",
    "TrainingRecordLogDownloadView": "apps.admin_panel.api.views.training_admin",
    "TrainingRecordLogView": "apps.admin_panel.api.views.training_admin",
    "TrainingRecordRetryPostRunView": "apps.admin_panel.api.views.training_admin",
    "TrainingRecordRetryView": "apps.admin_panel.api.views.training_admin",
    "UserDetailManagementView": "apps.admin_panel.api.views.users_admin",
    "UserManagementView": "apps.admin_panel.api.views.users_admin",
    "UserStatusView": "apps.admin_panel.api.views.users_admin",
}

__all__ = sorted(_VIEW_EXPORTS)


def __getattr__(name):
    module_path = _VIEW_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
