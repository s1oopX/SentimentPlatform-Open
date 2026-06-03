from django.urls import path
from apps.analysis.api.views.actions import (
    BatchAnalyzeView,
    BatchSchemaView,
    BatchTemplateView,
    SingleAnalyzeView,
)
from apps.analysis.api.views.analyst import (
    AnalystCommentDetailView,
    AnalystCommentListView,
    AnalystOverviewView,
    AnalystReportView,
)
from apps.analysis.api.views.history import (
    AnalysisHistorySummaryView,
    AnalysisHistoryView,
    AnalysisResultDetailView,
)
from apps.analysis.api.views.runtime import RuntimeCapabilitiesView

urlpatterns = [
    # 情感分析接口
    path(
        "runtime-capabilities/",
        RuntimeCapabilitiesView.as_view(),
        name="analysis-runtime-capabilities",
    ),
    path("single/", SingleAnalyzeView.as_view(), name="single-analyze"),
    path("batch/template/", BatchTemplateView.as_view(), name="batch-analyze-template"),
    path("batch/schema/", BatchSchemaView.as_view(), name="batch-analyze-schema"),
    path("batch/", BatchAnalyzeView.as_view(), name="batch-analyze"),
    path("history/", AnalysisHistoryView.as_view(), name="analysis-history"),
    path(
        "history/summary/",
        AnalysisHistorySummaryView.as_view(),
        name="analysis-history-summary",
    ),
    path(
        "result/<int:pk>/",
        AnalysisResultDetailView.as_view(),
        name="analysis-result-detail",
    ),
    path("analyst/overview/", AnalystOverviewView.as_view(), name="analyst-overview"),
    path(
        "analyst/comments/", AnalystCommentListView.as_view(), name="analyst-comments"
    ),
    path(
        "analyst/comments/<int:pk>/",
        AnalystCommentDetailView.as_view(),
        name="analyst-comment-detail",
    ),
    path("analyst/report/", AnalystReportView.as_view(), name="analyst-report"),
]
