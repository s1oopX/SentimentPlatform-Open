from django.urls import path

from apps.reports.api.views.download import ReportDownloadView
from apps.reports.api.views.generate import ReportGenerateView
from apps.reports.api.views.list_reports import ReportListView

urlpatterns = [
    path("generate/", ReportGenerateView.as_view(), name="report-generate"),
    path("download/<int:pk>/", ReportDownloadView.as_view(), name="report-download"),
    path("list/", ReportListView.as_view(), name="report-list"),
]
