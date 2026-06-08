from django.db.models import Q
from django.utils import timezone

from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.domain.rules.date_ranges import ensure_start_not_after_end
from apps.admin_panel.infra.selectors.date_parsing import parse_optional_date_or_error
from apps.analysis.domain.review_rules import REVIEW_CONFIDENCE_THRESHOLD
from apps.analysis.models import AnalysisResult, Comment


def build_aware_datetime(date_value, use_end_of_day=False):
    if not date_value:
        return None
    boundary = (
        timezone.datetime.max.time() if use_end_of_day else timezone.datetime.min.time()
    )
    combined = timezone.datetime.combine(date_value, boundary)
    if timezone.is_naive(combined):
        return timezone.make_aware(combined, timezone.get_current_timezone())
    return combined


def _validate_optional_date_range(*, start_date, end_date):
    ensure_start_not_after_end(
        start_date=start_date,
        end_date=end_date,
        error_cls=AdminPanelApplicationError,
    )


def get_filtered_comments(*, project_name="", category="", start_date="", end_date=""):
    comments = Comment.objects.all()
    if project_name:
        comments = comments.filter(project_name=project_name)
    if category:
        comments = comments.filter(category=category)

    start = parse_optional_date_or_error(start_date, field_label="开始日期")
    end = parse_optional_date_or_error(end_date, field_label="结束日期")
    _validate_optional_date_range(start_date=start, end_date=end)
    if start:
        start_at = build_aware_datetime(start, use_end_of_day=False)
        comments = comments.filter(
            Q(comment_time__gte=start_at)
            | Q(comment_time__isnull=True, created_at__gte=start_at)
        )
    if end:
        end_at = build_aware_datetime(end, use_end_of_day=True)
        comments = comments.filter(
            Q(comment_time__lte=end_at)
            | Q(comment_time__isnull=True, created_at__lte=end_at)
        )
    return comments.order_by("-created_at")


def _parse_export_ids(ids):
    id_list = []
    for raw_id in ids.split(","):
        value = raw_id.strip()
        if not value:
            continue
        try:
            id_list.append(int(value))
        except ValueError:
            continue
    return id_list


def get_comments_for_export(
    *, ids="", project_name="", category="", start_date="", end_date=""
):
    start = parse_optional_date_or_error(start_date, field_label="开始日期")
    end = parse_optional_date_or_error(end_date, field_label="结束日期")
    _validate_optional_date_range(start_date=start, end_date=end)
    if ids:
        id_list = _parse_export_ids(ids)
        if not id_list:
            return Comment.objects.none()
        comments = Comment.objects.filter(id__in=id_list)
    else:
        comments = get_filtered_comments(
            project_name=project_name,
            category=category,
            start_date=start_date,
            end_date=end_date,
        )
    return comments


def _normalize_int_filter(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise AdminPanelApplicationError("情感标签格式无效", 400) from None


def _effective_reviewed_filter():
    return Q(confidence__gte=REVIEW_CONFIDENCE_THRESHOLD) | Q(
        reviewed_at__isnull=False
    )


def get_filtered_dataset_results(
    *,
    project_name="",
    category="",
    source="",
    keyword="",
    final_sentiment="",
    review_status="",
    analysis_channel="",
    start_date="",
    end_date="",
):
    results = AnalysisResult.objects.select_related("comment", "user", "reviewed_by")

    if project_name:
        results = results.filter(comment__project_name__icontains=project_name)
    if category:
        results = results.filter(comment__category__icontains=category)
    if source:
        results = results.filter(comment__source__icontains=source)
    if analysis_channel:
        results = results.filter(analysis_channel=analysis_channel)

    keyword = (keyword or "").strip()
    if keyword:
        results = results.filter(
            Q(comment__content__icontains=keyword)
            | Q(comment__category__icontains=keyword)
            | Q(comment__source__icontains=keyword)
            | Q(comment__project_name__icontains=keyword)
            | Q(user__email__icontains=keyword)
            | Q(analyst_note__icontains=keyword)
        )

    sentiment_value = _normalize_int_filter(final_sentiment)
    if sentiment_value is not None:
        results = results.filter(
            Q(corrected_sentiment=sentiment_value)
            | Q(corrected_sentiment__isnull=True, sentiment=sentiment_value)
        )

    review_status = (review_status or "").strip()
    if review_status == "corrected":
        results = results.filter(corrected_sentiment__isnull=False)
    elif review_status == "reviewed":
        results = results.filter(_effective_reviewed_filter())
    elif review_status == "unreviewed":
        results = results.filter(
            confidence__lt=REVIEW_CONFIDENCE_THRESHOLD,
            reviewed_at__isnull=True,
        )
    elif review_status:
        raise AdminPanelApplicationError("不支持的审核状态", 400)

    start = parse_optional_date_or_error(start_date, field_label="开始日期")
    end = parse_optional_date_or_error(end_date, field_label="结束日期")
    _validate_optional_date_range(start_date=start, end_date=end)
    if start:
        start_at = build_aware_datetime(start, use_end_of_day=False)
        results = results.filter(
            Q(comment__comment_time__gte=start_at)
            | Q(comment__comment_time__isnull=True, created_at__gte=start_at)
        )
    if end:
        end_at = build_aware_datetime(end, use_end_of_day=True)
        results = results.filter(
            Q(comment__comment_time__lte=end_at)
            | Q(comment__comment_time__isnull=True, created_at__lte=end_at)
        )

    return results.order_by("-created_at", "-id")


def get_dataset_results_for_export(
    *,
    ids="",
    project_name="",
    category="",
    source="",
    keyword="",
    final_sentiment="",
    review_status="",
    analysis_channel="",
    start_date="",
    end_date="",
):
    if ids:
        id_list = _parse_export_ids(ids)
        if not id_list:
            return AnalysisResult.objects.none()
        return AnalysisResult.objects.select_related("comment", "user", "reviewed_by").filter(
            id__in=id_list
        )

    return get_filtered_dataset_results(
        project_name=project_name,
        category=category,
        source=source,
        keyword=keyword,
        final_sentiment=final_sentiment,
        review_status=review_status,
        analysis_channel=analysis_channel,
        start_date=start_date,
        end_date=end_date,
    )
