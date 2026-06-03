from django.utils.dateparse import parse_date

from apps.admin_panel.application.errors import AdminPanelApplicationError


def _parse_optional_date(raw_value, *, field_label):
    if raw_value is None or raw_value == "":
        return None
    if raw_value.strip() == "":
        raise AdminPanelApplicationError(f"{field_label}格式无效", 400)

    raw_value = raw_value.strip()

    try:
        parsed_date = parse_date(raw_value)
    except ValueError as exc:
        raise AdminPanelApplicationError(f"{field_label}格式无效", 400) from exc

    if parsed_date is None:
        raise AdminPanelApplicationError(f"{field_label}格式无效", 400)

    return parsed_date


def parse_optional_date_or_error(raw_value, *, field_label):
    return _parse_optional_date(raw_value, field_label=field_label)


def parse_date_or_default_or_error(raw_value, *, default_value, field_label):
    parsed_date = _parse_optional_date(raw_value, field_label=field_label)
    if parsed_date is None:
        return default_value
    return parsed_date
