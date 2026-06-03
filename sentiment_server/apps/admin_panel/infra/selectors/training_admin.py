from django.db.models import Count, F, FloatField, Q, Value
from django.db.models.functions import Cast, Coalesce

from apps.admin_panel.domain.rules.training_admin import DISPOSABLE_TRAINING_NAME_MARKERS
from apps.admin_panel.models import TrainingRun


TRAINING_COMPARISON_LIMIT = 50
TRAINING_DASHBOARD_RECENT_LIMIT = 5
TRAINING_DASHBOARD_BEST_LIMIT = 5
TRAINING_OVERVIEW_EXCLUDED_STATUSES = {"failed", "cancelled"}


def _overview_training_runs_queryset():
    queryset = TrainingRun.objects.exclude(status__in=TRAINING_OVERVIEW_EXCLUDED_STATUSES)
    for marker in DISPOSABLE_TRAINING_NAME_MARKERS:
        queryset = queryset.exclude(name__icontains=marker)
    return queryset


def get_training_run_page(*, page, page_size):
    queryset = TrainingRun.objects.all().order_by("-created_at", "-id")
    offset = (page - 1) * page_size
    limit = offset + page_size
    return queryset.count(), list(queryset[offset:limit])


def list_training_runs_for_dashboard():
    return list(_overview_training_runs_queryset().order_by("-created_at", "-id"))


def get_training_dashboard_totals():
    queryset = _overview_training_runs_queryset()
    totals = queryset.aggregate(
        total_records=Count("id"),
        active_records=Count("id", filter=Q(status__in={"queued", "running"})),
    )
    meets_target_records = (
        queryset.annotate(
            macro_f1_value=Coalesce(
                Cast(F("metrics_snapshot__macro_f1"), FloatField()),
                Value(0.0),
                output_field=FloatField(),
            ),
            target_macro_f1_value=Coalesce(
                Cast(F("config_snapshot__request__target_macro_f1"), FloatField()),
                Value(0.85),
                output_field=FloatField(),
            ),
        )
        .filter(macro_f1_value__gte=F("target_macro_f1_value"))
        .count()
    )
    return {
        "total_records": int(totals["total_records"] or 0),
        "active_records": int(totals["active_records"] or 0),
        "meets_target_records": int(meets_target_records),
    }


def list_recent_training_runs(*, limit=TRAINING_DASHBOARD_RECENT_LIMIT):
    return list(_overview_training_runs_queryset().order_by("-created_at", "-id")[:limit])


def list_best_successful_training_runs(*, limit=TRAINING_DASHBOARD_BEST_LIMIT):
    return list(
        _overview_training_runs_queryset()
        .filter(status="succeeded")
        .annotate(
            macro_f1_value=Coalesce(
                Cast(F("metrics_snapshot__macro_f1"), FloatField()),
                Value(0.0),
                output_field=FloatField(),
            ),
        )
        .order_by("-macro_f1_value", "-created_at", "-id")[:limit]
    )


def get_training_workflow_summary():
    return list(
        _overview_training_runs_queryset()
        .values("task_type")
        .annotate(count=Count("id"))
        .order_by("task_type")
    )


def list_recent_successful_training_runs(*, limit=TRAINING_COMPARISON_LIMIT):
    return list(
        _overview_training_runs_queryset()
        .filter(status="succeeded")
        .order_by("-created_at", "-id")[:limit]
    )


def get_training_run_by_id(run_id):
    return (
        TrainingRun.objects.filter(pk=run_id)
        .prefetch_related("registered_models")
        .first()
    )
