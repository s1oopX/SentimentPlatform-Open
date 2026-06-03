from django.db.models import Q
from django.utils import timezone

from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.domain.rules.date_ranges import ensure_start_not_after_end
from apps.admin_panel.infra.selectors.date_parsing import parse_optional_date_or_error
from apps.admin_panel.models import OperationLog


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


def get_filtered_logs(*, user_id="", action="", start_date="", end_date="", search=""):
    logs = OperationLog.objects.select_related("user")
    if user_id:
        logs = logs.filter(user_id=user_id)
    if action:
        logs = logs.filter(action=action)
    search_text = str(search or "").strip()
    if search_text:
        search_filter = (
            Q(user__email__icontains=search_text)
            | Q(detail__icontains=search_text)
            | Q(ip__icontains=search_text)
        )
        if search_text.isdigit():
            search_filter |= Q(id=int(search_text)) | Q(user_id=int(search_text))
        logs = logs.filter(search_filter)

    start = parse_optional_date_or_error(start_date, field_label="开始日期")
    end = parse_optional_date_or_error(end_date, field_label="结束日期")
    _validate_optional_date_range(start_date=start, end_date=end)
    if start:
        logs = logs.filter(
            created_at__gte=build_aware_datetime(start, use_end_of_day=False)
        )
    if end:
        logs = logs.filter(
            created_at__lte=build_aware_datetime(end, use_end_of_day=True)
        )
    return logs.order_by("-created_at")
