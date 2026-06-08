import csv
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook

from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.domain.rules.dataset_import import (
    COMMENT_MAX_LENGTH,
    COMMENT_MIN_LENGTH,
    DATASET_IMPORT_SUPPORTED_FORMATS,
    normalize_excel_row,
)
from apps.analysis.models import AnalysisResult, Comment
from core.spreadsheet_safety import escape_spreadsheet_formula

DATASET_EXPORT_SUPPORTED_FORMATS = {"csv", "excel"}
DATASET_EXPORT_FILE_PREFIX = "数据集导出"
SENTIMENT_TO_DATASET_LABEL = {-1: 0, 0: 1, 1: 2}
SENTIMENT_TO_DATASET_NAME = {-1: "negative", 0: "neutral", 1: "positive"}


def _clean_comment_score(value):
    score_field = Comment._meta.get_field("score")
    try:
        return score_field.clean(value, None)
    except DjangoValidationError as exc:
        raise ValueError(str(exc)) from exc


def _normalize_export_format(value, *, error_cls=AdminPanelApplicationError):
    if value is None:
        return "csv"

    normalized_value = str(value).strip().lower()
    if not normalized_value:
        return "csv"
    if normalized_value not in DATASET_EXPORT_SUPPORTED_FORMATS:
        raise error_cls("不支持的导出格式", 400)

    return normalized_value


def _export_cell_value(value):
    if isinstance(value, datetime) and timezone.is_aware(value):
        return timezone.localtime(value).replace(tzinfo=None)
    return escape_spreadsheet_formula(value)


def _queryset_count(rows):
    if hasattr(rows, "count"):
        return rows.count()
    return len(rows)


def _sentiment_label_value(sentiment):
    return SENTIMENT_TO_DATASET_LABEL.get(sentiment, "")


def _sentiment_label_name(sentiment):
    return SENTIMENT_TO_DATASET_NAME.get(sentiment, "")


def _labeled_dataset_header():
    return [
        "text",
        "label",
        "label_name",
        "model_label",
        "model_label_name",
        "corrected_label",
        "corrected_label_name",
        "confidence",
        "category",
        "source",
        "project",
        "analysis_channel",
        "analysis_source",
        "user_email",
        "analysis_time",
        "reviewed_by",
        "reviewed_at",
        "analyst_note",
    ]


def _labeled_dataset_row(result):
    final_sentiment = result.final_sentiment
    corrected_sentiment = result.corrected_sentiment
    return [
        _export_cell_value(result.comment.content),
        _sentiment_label_value(final_sentiment),
        _sentiment_label_name(final_sentiment),
        _sentiment_label_value(result.sentiment),
        _sentiment_label_name(result.sentiment),
        _sentiment_label_value(corrected_sentiment),
        _sentiment_label_name(corrected_sentiment),
        result.confidence,
        _export_cell_value(result.comment.category),
        _export_cell_value(result.comment.source),
        _export_cell_value(result.comment.project_name),
        result.analysis_channel,
        _export_cell_value(result.analysis_source_name),
        _export_cell_value(result.user.email if result.user_id else ""),
        _export_cell_value(result.created_at),
        _export_cell_value(result.reviewed_by.email if result.reviewed_by_id else ""),
        _export_cell_value(result.reviewed_at),
        _export_cell_value(result.analyst_note),
    ]


def validate_uploaded_file_size_command(
    *, uploaded_file, max_upload_size=None, error_cls=AdminPanelApplicationError
):
    max_upload_size = (
        int(getattr(settings, "MAX_UPLOAD_SIZE", 0) or 0)
        if max_upload_size is None
        else int(max_upload_size or 0)
    )
    if max_upload_size > 0 and uploaded_file.size > max_upload_size:
        max_upload_size_mb = round(max_upload_size / (1024 * 1024), 2)
        raise error_cls(f"文件大小不能超过 {max_upload_size_mb}MB", 400)


def import_dataset_command(
    *,
    uploaded_file,
    project_name="",
    operator,
    client_ip=None,
    create_operation_log_fn=None,
    validate_uploaded_file_size_fn=None,
    error_cls=AdminPanelApplicationError,
):
    create_operation_log_fn = create_operation_log_fn or (lambda **kwargs: None)
    validate_uploaded_file_size_fn = (
        validate_uploaded_file_size_fn or validate_uploaded_file_size_command
    )

    validate_uploaded_file_size_fn(uploaded_file=uploaded_file)

    count = 0
    skipped = 0
    file_name = uploaded_file.name.lower()
    if not file_name.endswith(DATASET_IMPORT_SUPPORTED_FORMATS):
        raise error_cls("只支持 TXT 和 Excel(.xlsx) 格式文件", 400)

    with transaction.atomic():
        if file_name.endswith(".txt"):
            try:
                seen_contents = set()
                for raw_line in uploaded_file:
                    try:
                        line = raw_line.decode("utf-8").strip()
                    except UnicodeDecodeError as exc:
                        raise error_cls("TXT 文件必须使用 UTF-8 编码", 400) from exc
                    if not line:
                        continue
                    # 长度校验
                    if len(line) < COMMENT_MIN_LENGTH or len(line) > COMMENT_MAX_LENGTH:
                        skipped += 1
                        continue
                    # 去重（文件内去重）
                    if line in seen_contents:
                        skipped += 1
                        continue
                    seen_contents.add(line)
                    # 数据库去重（已存在相同内容则跳过）
                    if Comment.objects.filter(content=line).exists():
                        skipped += 1
                        continue
                    Comment.objects.create(content=line, project_name=project_name)
                    count += 1
            except AdminPanelApplicationError:
                raise
            except Exception as exc:
                raise error_cls(f"TXT 解析失败：{exc}", 400) from exc
        else:
            # Validate xlsx magic bytes before parsing (PK\x03\x04 ZIP header).
            header = uploaded_file.read(4)
            uploaded_file.seek(0)
            if not header.startswith(b"PK\x03\x04"):
                raise error_cls(
                    "文件内容与 Excel(.xlsx) 格式不匹配，请上传有效的 Excel 文件", 400
                )

            import openpyxl

            try:
                workbook = openpyxl.load_workbook(BytesIO(uploaded_file.read()))
            except Exception as exc:
                raise error_cls(f"Excel 解析失败：{exc}", 400) from exc

            try:
                worksheet = workbook.active
                seen_contents = set()
                for row_index, row in enumerate(
                    worksheet.iter_rows(min_row=2, values_only=True), start=2
                ):
                    normalized_row = normalize_excel_row(
                        row,
                        row_number=row_index,
                        score_cleaner=_clean_comment_score,
                        error_cls=error_cls,
                    )
                    if not normalized_row:
                        skipped += 1
                        continue

                    content = normalized_row["content"]
                    # 文件内去重
                    if content in seen_contents:
                        skipped += 1
                        continue
                    seen_contents.add(content)
                    # 数据库去重
                    if Comment.objects.filter(content=content).exists():
                        skipped += 1
                        continue

                    Comment.objects.create(
                        content=content,
                        project_name=project_name,
                        score=normalized_row["score"],
                        category=normalized_row["category"],
                        source=normalized_row["source"],
                    )
                    count += 1
            finally:
                workbook.close()

    create_operation_log_fn(
        user=operator,
        action="upload_file",
        detail=f"导入数据集：{uploaded_file.name}, 导入 {count} 条, 跳过 {skipped} 条（重复/异常）, 项目={project_name or '未分配'}",
        ip=client_ip,
    )
    return {"count": count, "skipped": skipped, "project_name": project_name}


def export_dataset_command(
    *,
    comments=None,
    results=None,
    export_format,
    operator,
    client_ip=None,
    create_operation_log_fn=None,
    export_root=None,
    retention_seconds=None,
    timezone_module=None,
    workbook_cls=None,
    path_cls=None,
    makedirs_fn=None,
):
    create_operation_log_fn = create_operation_log_fn or (lambda **kwargs: None)
    export_root = export_root or settings.EXPORT_ROOT
    retention_seconds = retention_seconds or getattr(
        settings, "DATASET_EXPORT_RETENTION_SECONDS", 24 * 60 * 60
    )
    timezone_module = timezone_module or timezone
    workbook_cls = workbook_cls or Workbook
    path_cls = path_cls or Path
    makedirs_fn = makedirs_fn or os.makedirs
    export_format = _normalize_export_format(
        export_format, error_cls=AdminPanelApplicationError
    )
    exporting_labeled_results = results is not None
    rows = results if exporting_labeled_results else comments

    makedirs_fn(export_root, exist_ok=True)
    cleanup_cutoff = timezone_module.now().timestamp() - retention_seconds
    for stale_file in [
        *path_cls(export_root).glob("数据集导出_*"),
        *path_cls(export_root).glob("dataset_export_*"),
    ]:
        try:
            if stale_file.is_file() and stale_file.stat().st_mtime < cleanup_cutoff:
                stale_file.unlink(missing_ok=True)
        except OSError:
            continue

    timestamp = timezone_module.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid4().hex[:8]
    if export_format == "excel":
        file_path = os.path.join(
            export_root, f"{DATASET_EXPORT_FILE_PREFIX}_{timestamp}_{unique_suffix}.xlsx"
        )
        workbook = workbook_cls()
        try:
            worksheet = workbook.active
            worksheet.title = "数据集"
            if exporting_labeled_results:
                worksheet.append(_labeled_dataset_header())
                for result in rows:
                    worksheet.append(_labeled_dataset_row(result))
            else:
                worksheet.append(
                    ["ID", "内容", "项目", "评分", "类别", "来源", "评论时间", "创建时间"]
                )
                for comment in rows:
                    worksheet.append(
                        [
                            comment.id,
                            _export_cell_value(comment.content),
                            _export_cell_value(comment.project_name),
                            comment.score,
                            _export_cell_value(comment.category),
                            _export_cell_value(comment.source),
                            _export_cell_value(comment.comment_time),
                            _export_cell_value(comment.created_at),
                        ]
                    )
            workbook.save(file_path)
        finally:
            workbook.close()
    else:
        file_path = os.path.join(
            export_root, f"{DATASET_EXPORT_FILE_PREFIX}_{timestamp}_{unique_suffix}.csv"
        )
        with open(file_path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            if exporting_labeled_results:
                writer.writerow(_labeled_dataset_header())
                for result in rows:
                    writer.writerow(_labeled_dataset_row(result))
            else:
                writer.writerow(
                    ["ID", "内容", "项目", "评分", "类别", "来源", "评论时间", "创建时间"]
                )
                for comment in rows:
                    writer.writerow(
                        [
                            comment.id,
                            _export_cell_value(comment.content),
                            _export_cell_value(comment.project_name),
                            comment.score,
                            _export_cell_value(comment.category),
                            _export_cell_value(comment.source),
                            _export_cell_value(comment.comment_time),
                            _export_cell_value(comment.created_at),
                        ]
                    )

    create_operation_log_fn(
        user=operator,
        action="download_file",
        detail=f"导出数据集：{_queryset_count(rows)} 条记录",
        ip=client_ip,
    )
    return file_path


def delete_datasets_command(
    *,
    ids,
    reason="",
    operator=None,
    client_ip=None,
    create_operation_log_fn=None,
    comment_model=None,
    analysis_result_model=None,
    error_cls=AdminPanelApplicationError,
):
    create_operation_log_fn = create_operation_log_fn or (lambda **kwargs: None)
    comment_model = comment_model or Comment
    analysis_result_model = analysis_result_model or AnalysisResult
    if not ids:
        raise error_cls("请指定要删除的数据 ID", 400)

    max_batch_delete = int(getattr(settings, "MAX_BATCH_DELETE_SIZE", 200))
    if len(ids) > max_batch_delete:
        raise error_cls(f"单次最多删除 {max_batch_delete} 条数据", 400)

    with transaction.atomic():
        locked_comments = list(
            comment_model.objects.select_for_update().filter(id__in=ids).order_by("id")
        )
        comment_ids = [comment.id for comment in locked_comments]
        if not comment_ids:
            return

        has_analysis_results = analysis_result_model.objects.filter(
            comment_id__in=comment_ids
        ).exists()
        if has_analysis_results:
            raise error_cls("所选评论已生成分析结果，不能直接删除", status_code=409)

        deleted_count = len(comment_ids)
        comment_model.objects.filter(id__in=comment_ids).delete()

    create_operation_log_fn(
        user=operator,
        action="other",
        detail=f"删除数据集：{deleted_count} 条记录，理由：{reason}",
        ip=client_ip,
    )
