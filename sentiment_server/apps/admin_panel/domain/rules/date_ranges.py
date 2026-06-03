from apps.admin_panel.domain.errors import AdminPanelDomainError


def ensure_start_not_after_end(
    *, start_date, end_date, error_cls=AdminPanelDomainError
):
    if start_date and end_date and start_date > end_date:
        raise error_cls(
            "invalid_date_range", "开始日期不能晚于结束日期", status_code=400
        )
