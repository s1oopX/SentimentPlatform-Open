from collections import defaultdict
from datetime import datetime
from pathlib import Path


ARCHIVE_DIR_NAME = "_archive"
DEFAULT_METRIC_KEYS = ("macro_f1", "accuracy", "negative_recall")


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def _runtime_profile(record):
    runtime = record.get("config_snapshot", {}).get("runtime", {})
    return runtime.get("profile")


def _record_timestamp(record):
    for payload in (record.get("result_summary", {}), record.get("config_snapshot", {})):
        for key in ("created_at", "completed_at", "updated_at", "timestamp"):
            value = payload.get(key)
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue

    result_summary_path = record.get("result_summary_path")
    if result_summary_path:
        return datetime.fromtimestamp(_as_path(result_summary_path).stat().st_mtime)

    return None


def _record_tags(record):
    tags = record.get("config_snapshot", {}).get("tags") or []
    if isinstance(tags, (list, tuple, set)):
        return {str(item) for item in tags}
    return set()


def _is_archived(record):
    record_path = _as_path(record.get("path", "."))
    return ARCHIVE_DIR_NAME in record_path.parts


def _group_value(record, group_by):
    if group_by == "workflow_type":
        return record.get("workflow_type")
    if group_by == "runtime_profile":
        return _runtime_profile(record)
    raise ValueError(f"Unsupported group_by value: {group_by}")


def filter_experiment_records(
    records,
    *,
    workflow_types=None,
    runtime_profiles=None,
    start_time=None,
    end_time=None,
    tags=None,
):
    workflow_types = set(workflow_types or [])
    runtime_profiles = set(runtime_profiles or [])
    tags = set(tags or [])

    filtered = []
    for record in records:
        if workflow_types and record.get("workflow_type") not in workflow_types:
            continue

        runtime_profile = _runtime_profile(record)
        if runtime_profiles and runtime_profile not in runtime_profiles:
            continue

        if tags and not (_record_tags(record) & tags):
            continue

        timestamp = _record_timestamp(record)
        if start_time and timestamp and timestamp < start_time:
            continue
        if end_time and timestamp and timestamp > end_time:
            continue

        filtered.append(record)

    return filtered


def build_grouped_trend_summary(records, *, group_by="workflow_type", metric_keys=None):
    metric_keys = tuple(metric_keys or DEFAULT_METRIC_KEYS)
    grouped_records = defaultdict(list)
    for record in records:
        grouped_records[_group_value(record, group_by)].append(record)

    groups = []
    for group_value, group_records in sorted(grouped_records.items(), key=lambda item: str(item[0])):
        metric_buckets = {metric_key: [] for metric_key in metric_keys}
        trend_points = []
        archived_count = 0

        for record in group_records:
            metrics = record.get("core_metrics", {})
            for metric_key in metric_keys:
                metric_value = metrics.get(metric_key)
                if metric_value is not None:
                    metric_buckets[metric_key].append(metric_value)

            if _is_archived(record):
                archived_count += 1

            trend_points.append(
                {
                    "experiment_name": record.get("experiment_name"),
                    "path": record.get("path"),
                    "workflow_type": record.get("workflow_type"),
                    "runtime_profile": _runtime_profile(record),
                    "is_archived": _is_archived(record),
                    "timestamp": (
                        _record_timestamp(record).isoformat()
                        if _record_timestamp(record) is not None
                        else None
                    ),
                    "metrics": {metric_key: metrics.get(metric_key) for metric_key in metric_keys},
                }
            )

        groups.append(
            {
                "group_value": group_value,
                "record_count": len(group_records),
                "archived_count": archived_count,
                "active_count": len(group_records) - archived_count,
                "metric_averages": {
                    metric_key: (
                        sum(values) / len(values)
                        if values
                        else None
                    )
                    for metric_key, values in metric_buckets.items()
                },
                "trend_points": sorted(
                    trend_points,
                    key=lambda item: (item["timestamp"] is None, item["timestamp"] or "", item["experiment_name"] or ""),
                ),
            }
        )

    return {
        "group_by": group_by,
        "total_records": len(records),
        "group_count": len(groups),
        "metric_keys": list(metric_keys),
        "groups": groups,
    }
