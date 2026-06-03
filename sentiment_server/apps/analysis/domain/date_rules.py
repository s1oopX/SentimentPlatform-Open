from datetime import timedelta

from django.utils import timezone


def resolve_overview_dates(*, start_date=None, end_date=None):
    resolved_end_date = end_date or timezone.localdate()
    resolved_start_date = start_date or (resolved_end_date - timedelta(days=6))
    return resolved_start_date, resolved_end_date
