from __future__ import annotations

import base64
import io
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

from apps.admin_panel.infra.automation.system_config import load_system_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PdfSection:
    key: str
    title: str
    lines: list[str] = field(default_factory=list)
    image_base64: str = ""


def _format_keyword_lines(summary):
    keyword_top = summary.get("keyword_top") or []
    if not keyword_top:
        return ["暂无关键词数据"]

    return [f"{item['keyword']} ({item['count']})" for item in keyword_top]


def _format_metric_lines(items, *, label_key, value_key, empty_text):
    if not items:
        return [empty_text]
    return [f"{item[label_key]}：{item[value_key]}" for item in items]


def build_pdf_report_sections(*, report, user, summary):
    config = load_system_config()
    sections = [
        PdfSection(
            key="header",
            title=config["report_pdf_title"],
            lines=[
                config["report_pdf_subtitle"],
                f"生成用户：{user.email}",
            ]
            + (
                [config["report_pdf_footer_note"]]
                if config.get("report_pdf_footer_note")
                else []
            ),
        ),
        PdfSection(
            key="range",
            title="报告范围",
            lines=[
                f"报告类型：{report.get_report_type_display()}",
                f"日期范围：{report.start_date} 至 {report.end_date}",
            ],
        ),
    ]

    if config["report_pdf_show_summary"]:
        sections.append(
            PdfSection(
                key="summary",
                title="汇总数据",
                lines=[
                    f"总分析数：{summary['total']}",
                    f"积极情感：{summary['positive']}",
                    f"中性情感：{summary['neutral']}",
                    f"消极情感：{summary['negative']}",
                ],
            )
        )

    if config["report_pdf_show_keywords"]:
        sections.append(
            PdfSection(
                key="keywords",
                title="高频关键词",
                lines=_format_keyword_lines(summary),
            )
        )

    if config["report_pdf_show_category_distribution"]:
        sections.append(
            PdfSection(
                key="category_distribution",
                title="分类分布",
                lines=_format_metric_lines(
                    summary.get("category_distribution", []),
                    label_key="category",
                    value_key="count",
                    empty_text="暂无分类分布数据",
                ),
            )
        )

    if config["report_pdf_show_confidence_buckets"]:
        sections.append(
            PdfSection(
                key="confidence_buckets",
                title="置信度分布",
                lines=_format_metric_lines(
                    summary.get("confidence_buckets", []),
                    label_key="label",
                    value_key="value",
                    empty_text="暂无置信度分布数据",
                ),
            )
        )

    chart_b64 = _generate_sentiment_chart(summary)
    if chart_b64:
        sections.append(
            PdfSection(
                key="chart",
                title="情感分布图",
                image_base64=chart_b64,
            )
        )

    return sections


def _generate_sentiment_chart(summary):
    """生成情感分布饼图，返回 base64 PNG。"""
    try:
        from PIL import Image, ImageDraw

        counts = {
            "positive": summary.get("positive", 0),
            "neutral": summary.get("neutral", 0),
            "negative": summary.get("negative", 0),
        }
        total = sum(counts.values())
        if total == 0:
            return ""

        image = Image.new("RGB", (720, 520), "white")
        draw = ImageDraw.Draw(image)
        title_font = _load_chart_font(28)
        label_font = _load_chart_font(20)
        small_font = _load_chart_font(18)
        draw.text((280, 30), "情感分布", fill="#0f172a", font=title_font)

        box = (120, 110, 480, 470)
        slices = [
            ("积极", counts["positive"], "#16a34a"),
            ("中性", counts["neutral"], "#2563eb"),
            ("消极", counts["negative"], "#dc2626"),
        ]
        start = -90
        center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        radius = (box[2] - box[0]) / 2

        for label, value, color in slices:
            angle = 360 * value / total
            end = start + angle
            draw.pieslice(box, start=start, end=end, fill=color, outline="white", width=2)

            mid = math.radians((start + end) / 2)
            pct = f"{value / total:.1%}"
            text_x = center[0] + math.cos(mid) * radius * 0.58
            text_y = center[1] + math.sin(mid) * radius * 0.58
            draw.text((text_x - 28, text_y - 10), pct, fill="#0f172a", font=small_font)
            start = end

        legend_x = 535
        legend_y = 185
        for index, (label, value, color) in enumerate(slices):
            y = legend_y + index * 62
            draw.rounded_rectangle((legend_x, y, legend_x + 28, y + 18), radius=4, fill=color)
            draw.text(
                (legend_x + 42, y - 4),
                f"{label}：{value}（{value / total:.1%}）",
                fill="#334155",
                font=label_font,
            )

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        logger.warning("Failed to generate sentiment chart for PDF report", exc_info=True)
        return ""


def _load_chart_font(size):
    from PIL import ImageFont

    font_candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ]
    for font_path in font_candidates:
        if not font_path.exists():
            continue
        try:
            return ImageFont.truetype(str(font_path), size)
        except OSError:
            continue
    return ImageFont.load_default()
