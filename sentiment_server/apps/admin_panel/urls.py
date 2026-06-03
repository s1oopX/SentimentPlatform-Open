from django.urls import path

from apps.admin_panel.api.views.dashboard import DashboardStatsView
from apps.admin_panel.api.views.backup import DatabaseBackupView
from apps.admin_panel.api.views.datasets import (
    DatasetExportView,
    DatasetImportView,
    DatasetView,
)
from apps.admin_panel.api.views.logs import OperationLogView
from apps.admin_panel.api.views.runtime_registry import (
    ModelActivateView,
    ModelLogsView,
    ModelManagementView,
)
from apps.admin_panel.api.views.training_admin import (
    TrainingComparisonView,
    TrainingDashboardView,
    TrainingRecordActivateModelView,
    TrainingRecordDetailView,
    TrainingRecordListView,
    TrainingRecordLogDownloadView,
    TrainingRecordLogView,
    TrainingRecordRetryPostRunView,
    TrainingRecordRetryView,
)
from apps.admin_panel.api.views.users_admin import (
    UserDetailManagementView,
    UserManagementView,
    UserStatusView,
)

urlpatterns = [
    # 用户管理
    path("users/", UserManagementView.as_view(), name="admin-users"),
    path(
        "users/<int:pk>/", UserDetailManagementView.as_view(), name="admin-user-detail"
    ),
    path("users/<int:pk>/status/", UserStatusView.as_view(), name="admin-user-status"),
    # 操作日志
    path("logs/", OperationLogView.as_view(), name="admin-logs"),
    # 仪表盘统计
    path(
        "dashboard/stats/", DashboardStatsView.as_view(), name="admin-dashboard-stats"
    ),
    # 数据库备份
    path("backup/", DatabaseBackupView.as_view(), name="admin-backup"),
    # 数据管理
    path("datasets/", DatasetView.as_view(), name="admin-datasets"),
    path("datasets/import/", DatasetImportView.as_view(), name="admin-dataset-import"),
    path("datasets/export/", DatasetExportView.as_view(), name="admin-dataset-export"),
    # 模型管理
    path("models/", ModelManagementView.as_view(), name="admin-models"),
    path("models/<int:pk>/logs/", ModelLogsView.as_view(), name="admin-model-logs"),
    path("models/<int:pk>/activate/", ModelActivateView.as_view(), name="admin-model-activate"),
    # 训练中心
    path(
        "training/dashboard/",
        TrainingDashboardView.as_view(),
        name="admin-training-dashboard",
    ),
    path(
        "training/comparison/",
        TrainingComparisonView.as_view(),
        name="admin-training-comparison",
    ),
    path(
        "training/records/",
        TrainingRecordListView.as_view(),
        name="admin-training-records",
    ),
    path(
        "training/records/<int:run_id>/log/",
        TrainingRecordLogView.as_view(),
        name="admin-training-record-log",
    ),
    path(
        "training/records/<int:run_id>/log/download/",
        TrainingRecordLogDownloadView.as_view(),
        name="admin-training-record-log-download",
    ),
    path(
        "training/records/<int:run_id>/retry/",
        TrainingRecordRetryView.as_view(),
        name="admin-training-record-retry",
    ),
    path(
        "training/records/<int:run_id>/retry-post-run/",
        TrainingRecordRetryPostRunView.as_view(),
        name="admin-training-record-retry-post-run",
    ),
    path(
        "training/records/<int:run_id>/activate-model/",
        TrainingRecordActivateModelView.as_view(),
        name="admin-training-record-activate-model",
    ),
    # slug is intentional: record_id uses "run-{id}" format (e.g. "run-5"), not a bare integer
    path(
        "training/records/<slug:record_id>/",
        TrainingRecordDetailView.as_view(),
        name="admin-training-record-detail",
    ),
]
