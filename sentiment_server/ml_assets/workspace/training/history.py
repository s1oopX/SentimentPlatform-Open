from datetime import datetime
from pathlib import Path

from ml_assets.workspace.training.trends import build_grouped_trend_summary


ARCHIVE_DIR_NAME = "_archive"


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def _record_timestamp(record):
    for payload in (record.get("result_summary", {}), record.get("config_snapshot", {})):
        for key in ("completed_at", "updated_at", "created_at", "timestamp"):
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


def _is_archived(record):
    record_path = _as_path(record.get("path", "."))
    return ARCHIVE_DIR_NAME in record_path.parts


def _record_card(record):
    timestamp = _record_timestamp(record)
    is_archived = _is_archived(record)
    is_ranked = record.get("is_ranked_workflow", False)
    meets_target = record.get("meets_target_macro_f1")
    artifact_paths = dict(record.get("artifact_paths", {}))
    runtime_profile = (
        record.get("config_snapshot", {})
        .get("runtime", {})
        .get("profile")
    )
    return {
        "experiment_name": record.get("experiment_name"),
        "workflow_type": record.get("workflow_type"),
        "runtime_profile": runtime_profile,
        "path": record.get("path"),
        "timestamp": timestamp.isoformat() if timestamp else None,
        "is_archived": is_archived,
        "is_ranked_workflow": is_ranked,
        "leaderboard_size": record.get("leaderboard_size", 0),
        "meets_target_macro_f1": meets_target,
        "status": {
            "archived": is_archived,
            "ranked": is_ranked,
            "meets_target_macro_f1": meets_target,
        },
        "status_labels": {
            "archive": "archived" if is_archived else "active",
            "ranking": "ranked" if is_ranked else "single",
            "target": (
                "met"
                if meets_target is True
                else "unmet"
                if meets_target is False
                else "unknown"
            ),
        },
        "metric_highlights": {
            "macro_f1": record.get("core_metrics", {}).get("macro_f1"),
            "accuracy": record.get("core_metrics", {}).get("accuracy"),
            "negative_recall": record.get("core_metrics", {}).get("negative_recall"),
        },
        "detail_bundle": {
            "primary_summary_path": record.get("result_summary_path"),
            "config_snapshot_path": record.get("config_snapshot_path"),
            "leaderboard_path": artifact_paths.get("leaderboard_path"),
            "best_run_path": artifact_paths.get("best_run_path"),
            "evaluation_report_path": artifact_paths.get("evaluation_report_path"),
        },
        "artifact_paths": artifact_paths,
    }


def _recent_records(records, limit):
    sorted_records = sorted(
        records,
        key=lambda item: (
            _record_timestamp(item) is None,
            -_record_timestamp(item).timestamp() if _record_timestamp(item) else 0,
            item.get("experiment_name") or "",
        ),
    )
    return [_record_card(record) for record in sorted_records[:limit]]


def _best_records(records, limit, metric_key):
    sorted_records = sorted(
        records,
        key=lambda item: (
            item.get("core_metrics", {}).get(metric_key) is None,
            -(item.get("core_metrics", {}).get(metric_key) or 0),
            _record_timestamp(item) is None,
            -_record_timestamp(item).timestamp() if _record_timestamp(item) else 0,
            item.get("experiment_name") or "",
        ),
    )
    return [_record_card(record) for record in sorted_records[:limit]]


def _archive_summary(records):
    breakdown = {}
    archived_records = 0

    for record in records:
        workflow_type = record.get("workflow_type")
        group = breakdown.setdefault(
            workflow_type,
            {
                "workflow_type": workflow_type,
                "total_records": 0,
                "active_records": 0,
                "archived_records": 0,
            },
        )
        group["total_records"] += 1
        if _is_archived(record):
            group["archived_records"] += 1
            archived_records += 1
        else:
            group["active_records"] += 1

    return {
        "active_records": len(records) - archived_records,
        "archived_records": archived_records,
        "workflow_breakdown": [breakdown[key] for key in sorted(breakdown.keys(), key=str)],
    }


def build_history_dashboard_view(records, *, recent_limit=5, best_limit=5, metric_key="macro_f1"):
    workflow_summary = build_grouped_trend_summary(records, group_by="workflow_type")
    archived_count = sum(1 for record in records if _is_archived(record))
    ranked_count = sum(1 for record in records if record.get("is_ranked_workflow"))
    meets_target_count = sum(1 for record in records if record.get("meets_target_macro_f1") is True)

    return {
        "totals": {
            "total_records": len(records),
            "active_records": len(records) - archived_count,
            "archived_records": archived_count,
            "ranked_workflow_records": ranked_count,
            "workflow_count": workflow_summary["group_count"],
            "meets_target_records": meets_target_count,
            "below_target_records": sum(
                1 for record in records if record.get("meets_target_macro_f1") is False
            ),
        },
        "recent_records": _recent_records(records, recent_limit),
        "best_records": _best_records(records, best_limit, metric_key),
        "archive_summary": _archive_summary(records),
        "workflow_summary": workflow_summary,
    }


def _filter_browser_records(records, *, archived="active", ranked_only=False, meets_target="all"):
    filtered = []
    for record in records:
        is_archived = _is_archived(record)
        if archived == "active" and is_archived:
            continue
        if archived == "archived" and not is_archived:
            continue
        if ranked_only and not record.get("is_ranked_workflow", False):
            continue

        meets_target_value = record.get("meets_target_macro_f1")
        if meets_target == "met" and meets_target_value is not True:
            continue
        if meets_target == "unmet" and meets_target_value is not False:
            continue

        filtered.append(record)
    return filtered


def _sort_browser_records(records, sort_by):
    if sort_by == "best":
        return sorted(
            records,
            key=lambda item: (
                item.get("core_metrics", {}).get("macro_f1") is None,
                -(item.get("core_metrics", {}).get("macro_f1") or 0),
                _record_timestamp(item) is None,
                -_record_timestamp(item).timestamp() if _record_timestamp(item) else 0,
                item.get("experiment_name") or "",
            ),
        )

    return sorted(
        records,
        key=lambda item: (
            _record_timestamp(item) is None,
            -_record_timestamp(item).timestamp() if _record_timestamp(item) else 0,
            item.get("experiment_name") or "",
        ),
    )


def build_history_browser_view(
    records,
    *,
    archived="active",
    ranked_only=False,
    meets_target="all",
    sort_by="recent",
    limit=20,
):
    filtered = _filter_browser_records(
        records,
        archived=archived,
        ranked_only=ranked_only,
        meets_target=meets_target,
    )
    sorted_records = _sort_browser_records(filtered, sort_by)
    items = [_record_card(record) for record in sorted_records[:limit]]

    return {
        "total_records": len(filtered),
        "returned_records": len(items),
        "sort_by": sort_by,
        "applied_filters": {
            "archived": archived,
            "ranked_only": ranked_only,
            "meets_target": meets_target,
        },
        "items": items,
    }

