from decimal import Decimal, InvalidOperation

from apps.admin_panel.domain.errors import AdminPanelDomainError

DATASET_IMPORT_SUPPORTED_FORMATS = (".xlsx", ".txt")

# 评论内容长度限制
COMMENT_MIN_LENGTH = 5
COMMENT_MAX_LENGTH = 1000


def normalize_text_value(value):
    if value is None:
        return ""
    return str(value).strip()


def normalize_optional_text_value(value):
    normalized = normalize_text_value(value)
    return normalized or None


def normalize_txt_lines(content):
    return [
        line
        for line in (normalize_text_value(item) for item in content.splitlines())
        if line
    ]


def normalize_optional_score(
    value, *, row_number, score_cleaner=None, error_cls=AdminPanelDomainError
):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None

    try:
        normalized_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise error_cls(
            "invalid_score", f"第 {row_number} 行评分格式无效", status_code=400
        ) from exc

    try:
        return score_cleaner(normalized_value) if score_cleaner else normalized_value
    except (ValueError, TypeError) as exc:
        raise error_cls(
            "invalid_score", f"第 {row_number} 行评分格式无效", status_code=400
        ) from exc


def normalize_excel_row(
    row, *, row_number, score_cleaner=None, error_cls=AdminPanelDomainError
):
    values = list(row or ())
    content = normalize_text_value(values[0] if len(values) > 0 else None)
    if not content:
        return None

    # 长度校验：跳过过短或过长的评论
    if len(content) < COMMENT_MIN_LENGTH or len(content) > COMMENT_MAX_LENGTH:
        return None

    return {
        "content": content,
        "score": normalize_optional_score(
            values[1] if len(values) > 1 else None,
            row_number=row_number,
            score_cleaner=score_cleaner,
            error_cls=error_cls,
        ),
        "category": normalize_optional_text_value(
            values[2] if len(values) > 2 else None
        ),
        "source": normalize_optional_text_value(values[3] if len(values) > 3 else None),
    }
