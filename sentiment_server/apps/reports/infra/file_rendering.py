import base64
import csv
import io
import os
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from apps.reports.application.report_building import build_report_summary
from apps.reports.infra.templates import build_pdf_report_sections
from core.spreadsheet_safety import escape_spreadsheet_formula

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


PDF_FONT_NAME = "STSong-Light"
PDF_FONT_SIZE_TITLE = 18
PDF_FONT_SIZE_SECTION = 12
PDF_LEFT_MARGIN = 20 * mm
PDF_RIGHT_MARGIN = 20 * mm
PDF_TOP_MARGIN = 18 * mm
PDF_BOTTOM_MARGIN = 18 * mm
PDF_LINE_HEIGHT = 7 * mm
PDF_SECTION_GAP = 5 * mm

_pdf_font_registered = False
REPORT_FILE_EXTENSIONS = {
    "pdf": "pdf",
    "excel": "xlsx",
    "csv": "csv",
}


def _ensure_pdf_font_registered():
    global _pdf_font_registered

    if not _pdf_font_registered:
        pdfmetrics.registerFont(UnicodeCIDFont(PDF_FONT_NAME))
        _pdf_font_registered = True


def _create_pdf_canvas(file_path):
    _ensure_pdf_font_registered()
    canvas_obj = canvas.Canvas(file_path, pagesize=A4)
    canvas_obj.setPageCompression(0)
    return canvas_obj


def _draw_section_header(canvas_obj, title, y, *, font_size):
    canvas_obj.setFont(PDF_FONT_NAME, font_size)
    canvas_obj.drawString(PDF_LEFT_MARGIN, y, title)


def _start_new_pdf_page(canvas_obj):
    canvas_obj.showPage()
    return A4[1] - PDF_TOP_MARGIN


def _ensure_pdf_space(canvas_obj, y, *, required_height):
    if y - required_height < PDF_BOTTOM_MARGIN:
        return _start_new_pdf_page(canvas_obj)
    return y


def _draw_section_lines(canvas_obj, lines, y):
    canvas_obj.setFont(PDF_FONT_NAME, PDF_FONT_SIZE_SECTION)
    for line in lines:
        y = _ensure_pdf_space(canvas_obj, y, required_height=PDF_LINE_HEIGHT)
        canvas_obj.drawString(PDF_LEFT_MARGIN + 8 * mm, y, line)
        y -= PDF_LINE_HEIGHT
    return y


def _render_pdf_header_section(canvas_obj, section, y):
    y = _ensure_pdf_space(canvas_obj, y, required_height=PDF_LINE_HEIGHT * 1.3)
    _draw_section_header(canvas_obj, section.title, y, font_size=PDF_FONT_SIZE_TITLE)
    y -= PDF_LINE_HEIGHT * 1.3
    y = _draw_section_lines(canvas_obj, section.lines, y)
    return y - PDF_SECTION_GAP


def _render_pdf_range_section(canvas_obj, section, y):
    y = _ensure_pdf_space(canvas_obj, y, required_height=PDF_LINE_HEIGHT)
    _draw_section_header(canvas_obj, section.title, y, font_size=13)
    y -= PDF_LINE_HEIGHT
    y = _draw_section_lines(canvas_obj, section.lines, y)
    return y - PDF_SECTION_GAP


def _render_pdf_summary_section(canvas_obj, section, y):
    y = _ensure_pdf_space(canvas_obj, y, required_height=PDF_LINE_HEIGHT)
    _draw_section_header(canvas_obj, section.title, y, font_size=13)
    y -= PDF_LINE_HEIGHT
    y = _draw_section_lines(canvas_obj, section.lines, y)
    return y - PDF_SECTION_GAP


def _render_pdf_keywords_section(canvas_obj, section, y):
    y = _ensure_pdf_space(canvas_obj, y, required_height=PDF_LINE_HEIGHT)
    _draw_section_header(canvas_obj, section.title, y, font_size=13)
    y -= PDF_LINE_HEIGHT
    keyword_lines = [f"- {line}" for line in section.lines]
    y = _draw_section_lines(canvas_obj, keyword_lines, y)
    return y - PDF_SECTION_GAP


PDF_CHART_WIDTH = 140 * mm
PDF_CHART_HEIGHT = 110 * mm


def _render_pdf_chart_section(canvas_obj, section, y):
    if not section.image_base64:
        return y
    chart_height = PDF_CHART_HEIGHT
    title_height = PDF_LINE_HEIGHT * 1.5
    required = chart_height + title_height + PDF_SECTION_GAP
    y = _ensure_pdf_space(canvas_obj, y, required_height=required)
    _draw_section_header(canvas_obj, section.title, y, font_size=13)
    y -= title_height
    image_data = base64.b64decode(section.image_base64)
    image_reader = ImageReader(io.BytesIO(image_data))
    canvas_obj.drawImage(
        image_reader,
        PDF_LEFT_MARGIN,
        y - chart_height,
        width=PDF_CHART_WIDTH,
        height=chart_height,
        preserveAspectRatio=True,
        anchor="nw",
    )
    y -= chart_height
    return y - PDF_SECTION_GAP


def _render_pdf_section(canvas_obj, section, y):
    renderers = {
        "header": _render_pdf_header_section,
        "range": _render_pdf_range_section,
        "summary": _render_pdf_summary_section,
        "keywords": _render_pdf_keywords_section,
        "category_distribution": _render_pdf_summary_section,
        "confidence_buckets": _render_pdf_summary_section,
        "chart": _render_pdf_chart_section,
    }
    try:
        renderer = renderers[section.key]
    except KeyError as exc:
        raise ValueError(f"不支持的PDF模板块: {section.key}") from exc

    return renderer(canvas_obj, section, y)


def _render_pdf_report(report, user, results, file_path, *, summary=None):
    canvas_obj = _create_pdf_canvas(file_path)
    if summary is None:
        summary = build_report_summary(results)
    sections = build_pdf_report_sections(report=report, user=user, summary=summary)

    y = A4[1] - PDF_TOP_MARGIN
    for section in sections:
        y = _render_pdf_section(canvas_obj, section, y)

    canvas_obj.save()


def _render_excel_report(results, file_path):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "情感分析报告"
    sheet.append(["记录ID", "评论内容", "情感倾向", "置信度", "分析时间"])

    for result in results:
        sheet.append(
            [
                result.id,
                escape_spreadsheet_formula(result.comment.content[:100])
                if result.comment
                else "",
                result.get_sentiment_display(),
                float(result.confidence),
                result.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

    workbook.save(file_path)


def _render_csv_report(results, file_path):
    with open(file_path, "w", newline="", encoding="utf-8-sig") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["记录ID", "评论内容", "情感倾向", "置信度", "分析时间"])

        for result in results:
            writer.writerow(
                [
                    result.id,
                    escape_spreadsheet_formula(result.comment.content[:100])
                    if result.comment
                    else "",
                    result.get_sentiment_display(),
                    float(result.confidence),
                    result.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )


def get_report_file_extension(report_format):
    try:
        return REPORT_FILE_EXTENSIONS[report_format]
    except KeyError as exc:
        raise ValueError(f"不支持的报告格式: {report_format}") from exc


def _build_temp_report_file_path(final_file_path):
    directory, filename = os.path.split(final_file_path)
    stem, extension = os.path.splitext(filename)
    temp_token = uuid4().hex
    return os.path.join(directory, f"{stem}.{temp_token}.tmp{extension}")


def _remove_report_file_if_exists(file_path):
    try:
        os.remove(file_path)
    except FileNotFoundError:
        return


def render_report_file(*, report, user, results, summary=None):
    reports_dir = settings.REPORT_ROOT
    os.makedirs(reports_dir, exist_ok=True)

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    render_token = uuid4().hex
    report_id = report.id if report.id is not None else "unsaved"
    extension = get_report_file_extension(report.report_format)
    filename = f"情感分析报告_{user.id}_{report_id}_{timestamp}_{render_token}.{extension}"
    final_file_path = os.path.join(reports_dir, filename)
    temp_file_path = _build_temp_report_file_path(final_file_path)

    try:
        if report.report_format == "pdf":
            _render_pdf_report(
                report,
                user,
                results,
                temp_file_path,
                summary=summary,
            )
        elif report.report_format == "excel":
            _render_excel_report(
                results,
                temp_file_path,
            )
        elif report.report_format == "csv":
            _render_csv_report(
                results,
                temp_file_path,
            )
        else:
            raise ValueError(f"不支持的报告格式: {report.report_format}")

        os.replace(temp_file_path, final_file_path)
    except Exception:
        _remove_report_file_if_exists(temp_file_path)
        raise

    return final_file_path
