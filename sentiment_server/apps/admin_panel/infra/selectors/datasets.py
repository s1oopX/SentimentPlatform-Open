from django.db.models import Q
from django.utils import timezone

from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.domain.rules.date_ranges import ensure_start_not_after_end
from apps.admin_panel.infra.selectors.date_parsing import parse_optional_date_or_error
from apps.analysis.models import Comment


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
