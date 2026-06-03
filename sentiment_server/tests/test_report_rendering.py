import base64
import io
import os
from datetime import datetime
from types import SimpleNamespace

import openpyxl
import pytest
from django.utils import timezone
from PIL import Image

from apps.reports.api.views.download import _build_content_disposition
from apps.reports.infra.file_rendering import (
    _render_csv_report,
    _render_excel_report,
    render_report_file,
)
from apps.reports.infra.templates import (
    _generate_sentiment_chart,
    build_pdf_report_sections,
)
from apps.reports.models import Report
from apps.users.models import User


def _make_result():
    return SimpleNamespace(
        id=1,
        comment=SimpleNamespace(content="页面布局清晰，报告导出稳定"),
        confidence=0.98,
        created_at=timezone.make_aware(datetime(2026, 5, 19, 21, 30, 0)),
        get_sentiment_display=lambda: "积极",
    )


@pytest.mark.django_db
def test_pdf_report_sections_use_chinese_copy():
    user = User.objects.create_user(
        email="report-render@example.com",
        password="TestPass123!",
        role="user",
    )
    report = Report.objects.create(
        user=user,
        report_type="weekly",
        report_format="pdf",
        start_date="2026-05-13",
        end_date="2026-05-19",
    )
    summary = {
        "total": 60,
        "positive": 27,
        "neutral": 25,
        "negative": 8,
        "keyword_top": [{"keyword": "稳定", "count": 3}],
        "category_distribution": [{"category": "报告导出", "count": 3}],
        "confidence_buckets": [{"label": "0.90-1.00", "value": 37}],
    }

    sections = build_pdf_report_sections(report=report, user=user, summary=summary)
    rendered_text = "\n".join(
        line for section in sections for line in [section.title, *section.lines]
    )

    assert "情感分析报告" in rendered_text
    assert "生成用户：" in rendered_text
    assert "报告范围" in rendered_text
    assert "报告类型：周报" in rendered_text
    assert "汇总数据" in rendered_text
    assert "高频关键词" in rendered_text
    assert "User:" not in rendered_text
    assert "Report Range" not in rendered_text
    assert "Summary" not in rendered_text
    assert "Top Keywords" not in rendered_text


def test_excel_and_csv_report_exports_use_chinese_headers(tmp_path):
    result = _make_result()

    excel_path = tmp_path / "report.xlsx"
    csv_path = tmp_path / "report.csv"

    _render_excel_report([result], excel_path)
    _render_csv_report([result], csv_path)

    workbook = openpyxl.load_workbook(excel_path)
    sheet = workbook.active
    assert sheet.title == "情感分析报告"
    assert [cell.value for cell in sheet[1]] == [
        "记录ID",
        "评论内容",
        "情感倾向",
        "置信度",
        "分析时间",
    ]

    csv_content = csv_path.read_text(encoding="utf-8-sig")
    assert csv_content.startswith("记录ID,评论内容,情感倾向,置信度,分析时间")
    assert "Comment" not in csv_content
    assert "Sentiment" not in csv_content


def test_excel_and_csv_report_exports_escape_spreadsheet_formulas(tmp_path):
    result = _make_result()
    result.comment.content = "=WEBSERVICE(\"http://example.invalid\")"

    excel_path = tmp_path / "report.xlsx"
    csv_path = tmp_path / "report.csv"

    _render_excel_report([result], excel_path)
    _render_csv_report([result], csv_path)

    workbook = openpyxl.load_workbook(excel_path)
    try:
        assert workbook.active["B2"].value.startswith("'=WEBSERVICE")
    finally:
        workbook.close()

    csv_content = csv_path.read_text(encoding="utf-8-sig")
    assert "'=WEBSERVICE" in csv_content


def test_rendered_report_filename_and_download_header_use_chinese(tmp_path, settings):
    settings.REPORT_ROOT = str(tmp_path)
    report = SimpleNamespace(id=7, report_format="csv")
    user = SimpleNamespace(id=3)

    file_path = render_report_file(report=report, user=user, results=[_make_result()])
    filename = os.path.basename(file_path)
    disposition = _build_content_disposition(filename)

    assert filename.startswith("情感分析报告_3_7_")
    assert filename.endswith(".csv")
    assert 'filename="' in disposition
    assert "filename*=UTF-8''%E6%83%85%E6%84%9F%E5%88%86%E6%9E%90%E6%8A%A5%E5%91%8A" in disposition


def test_pdf_sentiment_chart_generates_png_with_core_dependencies():
    chart_b64 = _generate_sentiment_chart({"positive": 27, "neutral": 25, "negative": 8})

    image = Image.open(io.BytesIO(base64.b64decode(chart_b64)))

    assert image.format == "PNG"
    assert image.size == (720, 520)
