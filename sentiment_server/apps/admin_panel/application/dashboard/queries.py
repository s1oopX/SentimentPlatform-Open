from datetime import timedelta

from django.utils import timezone

from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.domain.rules.date_ranges import ensure_start_not_after_end
from apps.admin_panel.infra.selectors.date_parsing import parse_date_or_default_or_error
from apps.admin_panel.infra.selectors.dashboard import build_dashboard_stats_payload


def parse_dashboard_date_range(query_params):
    today = timezone.localdate()
    default_start = today - timedelta(days=6)
    default_end = today
    start_date_raw = query_params.get("start_date", "")
    end_date_raw = query_params.get("end_date", "")
    start_date = parse_date_or_default_or_error(
        start_date_raw,
        default_value=default_start,
        field_label="开始日期",
    )
    end_date = parse_date_or_default_or_error(
        end_date_raw,
        default_value=default_end,
        field_label="结束日期",
    )

    ensure_start_not_after_end(
        start_date=start_date,
        end_date=end_date,
        error_cls=AdminPanelApplicationError,
    )
    return start_date, end_date


def build_dashboard_stats_response(start_date, end_date):
    return build_dashboard_stats_payload(start_date, end_date)
