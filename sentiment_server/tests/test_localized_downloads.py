from types import SimpleNamespace
from pathlib import Path

import pytest
from django.test import override_settings
from openpyxl import load_workbook
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.admin_panel.api.views.datasets import DatasetExportView
from apps.admin_panel.api.views.training_admin import _build_content_disposition
from apps.admin_panel.application.dataset_admin.commands import export_dataset_command
from apps.admin_panel.application.training_admin.queries import (
    build_training_log_download_metadata,
)
from apps.analysis.api.views.actions import BatchTemplateView
from apps.analysis.api.views.analyst import AnalystReportExportView
from apps.analysis.models import AnalysisResult, Comment
from apps.users.models import User


def _admin_user():
    return User.objects.create_user(
        email="admin-localized-download@example.com",
        password="TestPass123!",
        role="admin",
    )


@pytest.mark.django_db
def test_batch_template_download_uses_chinese_filename():
    request = APIRequestFactory().get("/api/analyze/batch/template/?format=txt")
    force_authenticate(request, user=_admin_user())

    response = BatchTemplateView.as_view()(request)

    assert response.status_code == 200
    disposition = response["Content-Disposition"]
    assert "batch-analysis-template.txt" in disposition
    assert "filename*=UTF-8''%E6%89%B9%E9%87%8F%E5%88%86%E6%9E%90%E6%A8%A1%E6%9D%BF.txt" in disposition


@pytest.mark.django_db
def test_dataset_export_command_uses_chinese_filename(tmp_path):
    operator = _admin_user()
    Comment.objects.create(content="用于导出的评论", project_name="本地测试")

    file_path = export_dataset_command(
        comments=Comment.objects.all(),
        export_format="csv",
        operator=operator,
        export_root=tmp_path,
    )

    assert file_path.endswith(".csv")
    assert "数据集导出_" in file_path


@pytest.mark.django_db
def test_dataset_export_command_xlsx_handles_timezone_datetimes(tmp_path):
    operator = _admin_user()
    Comment.objects.create(content="用于导出的评论", project_name="本地测试")

    file_path = export_dataset_command(
        comments=Comment.objects.all(),
        export_format="excel",
        operator=operator,
        export_root=tmp_path,
    )

    assert file_path.endswith(".xlsx")
    assert "数据集导出_" in file_path


@pytest.mark.django_db
def test_dataset_export_escapes_spreadsheet_formulas(tmp_path):
    operator = _admin_user()
    Comment.objects.create(
        content="=HYPERLINK(\"http://example.invalid\")",
        project_name="+恶意项目",
        category="-类别",
        source="@来源",
    )

    csv_path = export_dataset_command(
        comments=Comment.objects.all(),
        export_format="csv",
        operator=operator,
        export_root=tmp_path,
    )
    csv_content = Path(csv_path).read_text(encoding="utf-8-sig")
    assert "'=HYPERLINK" in csv_content
    assert "'+恶意项目" in csv_content
    assert "'-类别" in csv_content
    assert "'@来源" in csv_content

    xlsx_path = export_dataset_command(
        comments=Comment.objects.all(),
        export_format="excel",
        operator=operator,
        export_root=tmp_path,
    )
    workbook = load_workbook(xlsx_path)
    try:
        row = [cell.value for cell in workbook.active[2]]
    finally:
        workbook.close()

    assert row[1].startswith("'=HYPERLINK")
    assert row[2] == "'+恶意项目"
    assert row[4] == "'-类别"
    assert row[5] == "'@来源"


@pytest.mark.django_db
def test_labeled_dataset_export_uses_corrected_sentiment(tmp_path):
    operator = _admin_user()
    comment = Comment.objects.create(content="售后一直没有回复", category="售后服务")
    result = AnalysisResult.objects.create(
        user=operator,
        comment=comment,
        sentiment=1,
        corrected_sentiment=-1,
        confidence=0.82,
        analyst_note="人工复核后修正为消极",
    )

    csv_path = export_dataset_command(
        results=AnalysisResult.objects.filter(pk=result.pk),
        export_format="csv",
        operator=operator,
        export_root=tmp_path,
    )

    csv_content = Path(csv_path).read_text(encoding="utf-8-sig")
    assert csv_content.startswith("text,label,label_name")
    assert "售后一直没有回复,0,negative,2,positive,0,negative" in csv_content


@pytest.mark.django_db
def test_dataset_export_view_maps_xlsx_to_excel(tmp_path, monkeypatch):
    operator = _admin_user()
    exported = tmp_path / "数据集导出_20260520_120000.xlsx"
    exported.write_bytes(b"xlsx")

    def fake_export_dataset(**kwargs):
        assert kwargs["export_format"] == "excel"
        return exported

    monkeypatch.setattr(
        "apps.admin_panel.api.views.datasets.build_dataset_export_response",
        lambda **_query: [],
    )
    monkeypatch.setattr("apps.admin_panel.api.views.datasets.export_dataset", fake_export_dataset)

    with override_settings(EXPORT_ROOT=tmp_path):
        request = APIRequestFactory().get("/api/admin/datasets/export/?format=xlsx")
        force_authenticate(request, user=operator)
        response = DatasetExportView.as_view()(request)

    assert response.status_code == 200
    assert (
        "%E6%95%B0%E6%8D%AE%E9%9B%86%E5%AF%BC%E5%87%BA_20260520_120000.xlsx"
        in response["Content-Disposition"]
    )


@pytest.mark.django_db
def test_analyst_report_export_downloads_csv_with_chinese_filename():
    analyst = User.objects.create_user(
        email="analyst-report-download@example.com",
        password="TestPass123!",
        role="analyst",
    )
    comment = Comment.objects.create(content="客服回复慢")
    AnalysisResult.objects.create(
        user=analyst,
        comment=comment,
        sentiment=-1,
        confidence=0.66,
        keywords=["客服"],
    )

    request = APIRequestFactory().get("/api/analyze/analyst/report/export/?format=csv")
    force_authenticate(request, user=analyst)
    response = AnalystReportExportView.as_view()(request)

    assert response.status_code == 200
    assert "analyst-report-" in response["Content-Disposition"]
    assert "filename*=UTF-8''%E5%88%86%E6%9E%90%E5%B8%88%E6%8A%A5%E8%A1%A8_" in response[
        "Content-Disposition"
    ]
    assert "摘要" in response.content.decode("utf-8-sig")
    assert "低置信样本" in response.content.decode("utf-8-sig")


def test_training_log_download_metadata_uses_chinese_filename(tmp_path, monkeypatch):
    log_path = tmp_path / "run.log"
    log_path.write_text("训练日志", encoding="utf-8")
    training_run = SimpleNamespace(id=12)

    monkeypatch.setattr(
        "apps.admin_panel.application.training_admin.queries.get_training_run_by_id",
        lambda _run_id: training_run,
    )

    metadata = build_training_log_download_metadata(
        run_id=12,
        resolve_training_run_log_path_fn=lambda _training_run: log_path,
    )

    assert metadata["download_filename"] == "训练日志_12.log"


def test_training_log_content_disposition_supports_chinese_filename():
    disposition = _build_content_disposition("训练日志_12.log", "training-log-12.log")

    assert 'filename="training-log-12.log"' in disposition
    assert "filename*=UTF-8''%E8%AE%AD%E7%BB%83%E6%97%A5%E5%BF%97_12.log" in disposition
