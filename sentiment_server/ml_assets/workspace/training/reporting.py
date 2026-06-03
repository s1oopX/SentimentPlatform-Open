from copy import deepcopy


def _copy_mapping(value):
    if isinstance(value, dict):
        return deepcopy(value)
    return {}


def _sorted_artifact_paths(paths):
    filtered = {
        key: value
        for key, value in _copy_mapping(paths).items()
        if value is not None
    }
    return dict(sorted(filtered.items()))


def _metric_highlights(metrics):
    return {
        "accuracy": metrics.get("accuracy"),
        "macro_f1": metrics.get("macro_f1"),
        "negative_recall": metrics.get("negative_recall"),
    }


def _format_value(value):
    if value is None:
        return "n/a"
    return value


def _render_artifact_lines(artifact_paths, prefix="- "):
    lines = []
    for key, value in artifact_paths.items():
        lines.append(f"{prefix}{key}: {value}")
    return lines


def _best_run_overview(best_run):
    if not best_run:
        return None

    return {
        "workflow_type": best_run.get("workflow_type"),
        "model_name": best_run.get("model_name") or best_run.get("run_name"),
        "summary_path": best_run.get("summary_path"),
        "config_snapshot_path": best_run.get("config_snapshot_path"),
        "core_metrics": _metric_highlights(best_run.get("core_metrics", {})),
        "artifact_paths": _sorted_artifact_paths(best_run.get("artifact_paths")),
    }


def build_experiment_summary_view(record):
    metric_highlights = _metric_highlights(record.get("core_metrics", {}))
    artifact_paths = _sorted_artifact_paths(record.get("artifact_paths"))

    return {
        "workflow_type": record.get("workflow_type"),
        "experiment_name": record.get("experiment_name"),
        "path": record.get("path"),
        "is_ranked_workflow": record.get("is_ranked_workflow", False),
        "leaderboard_size": record.get("leaderboard_size", 0),
        "target_macro_f1": record.get("target_macro_f1"),
        "meets_target_macro_f1": record.get("meets_target_macro_f1"),
        "metric_highlights": metric_highlights,
        "artifact_paths": artifact_paths,
        "primary_artifacts": {
            "config_snapshot_path": record.get("config_snapshot_path"),
            "result_summary_path": record.get("result_summary_path"),
            "leaderboard_path": artifact_paths.get("leaderboard_path"),
            "best_run_path": artifact_paths.get("best_run_path"),
            "evaluation_report_path": artifact_paths.get("evaluation_report_path"),
        },
    }


def build_experiment_report_view(record):
    summary_view = build_experiment_summary_view(record)
    leaderboard_rows = record.get("leaderboard_rows", [])

    return {
        **summary_view,
        "result_summary": _copy_mapping(record.get("result_summary")),
        "best_run_overview": _best_run_overview(record.get("best_run")),
        "leaderboard_preview": leaderboard_rows[:5],
        "leaderboard_preview_count": min(len(leaderboard_rows), 5),
        "leaderboard_total_count": len(leaderboard_rows),
    }


def build_comparison_report_view(rows, metric_key="macro_f1"):
    copied_rows = []
    top_metric_value = None

    for row in rows:
        metric_value = row.get("metric_value")
        if top_metric_value is None and metric_value is not None:
            top_metric_value = metric_value

        copied_rows.append(
            {
                "rank": row.get("rank"),
                "workflow_type": row.get("workflow_type"),
                "experiment_name": row.get("experiment_name"),
                "subject_type": row.get("subject_type"),
                "subject_name": row.get("subject_name"),
                "metric_key": row.get("metric_key", metric_key),
                "metric_value": metric_value,
                "delta_from_best": (
                    None
                    if metric_value is None or top_metric_value is None
                    else metric_value - top_metric_value
                ),
                "accuracy": row.get("accuracy"),
                "macro_f1": row.get("macro_f1"),
                "negative_recall": row.get("negative_recall"),
                "summary_path": row.get("summary_path"),
                "config_snapshot_path": row.get("config_snapshot_path"),
                "leaderboard_path": row.get("leaderboard_path"),
                "best_run_path": row.get("best_run_path"),
                "experiment_root_path": row.get("experiment_root_path"),
                "artifact_paths": _sorted_artifact_paths(row.get("artifact_paths")),
            }
        )

    return {
        "metric_key": metric_key,
        "row_count": len(copied_rows),
        "top_metric_value": top_metric_value,
        "top_subject": copied_rows[0] if copied_rows else None,
        "rows": copied_rows,
    }


def render_summary_text(summary_view):
    lines = [
        f"workflow_type: {summary_view['workflow_type']}",
        f"experiment_name: {summary_view['experiment_name']}",
        f"path: {summary_view['path']}",
        f"macro_f1: {_format_value(summary_view['metric_highlights'].get('macro_f1'))}",
        f"accuracy: {_format_value(summary_view['metric_highlights'].get('accuracy'))}",
        f"negative_recall: {_format_value(summary_view['metric_highlights'].get('negative_recall'))}",
        f"target_macro_f1: {_format_value(summary_view.get('target_macro_f1'))}",
        f"meets_target_macro_f1: {_format_value(summary_view.get('meets_target_macro_f1'))}",
        f"is_ranked_workflow: {summary_view.get('is_ranked_workflow')}",
        f"leaderboard_size: {_format_value(summary_view.get('leaderboard_size'))}",
        "artifacts:",
    ]
    lines.extend(_render_artifact_lines(summary_view["artifact_paths"]))
    return lines


def render_report_text(report_view):
    lines = render_summary_text(report_view)

    best_run = report_view.get("best_run_overview")
    if best_run:
        lines.append("best_run:")
        lines.append(f"- model_name: {_format_value(best_run.get('model_name'))}")
        lines.append(f"- macro_f1: {_format_value(best_run['core_metrics'].get('macro_f1'))}")
        lines.append(f"- summary_path: {_format_value(best_run.get('summary_path'))}")
        lines.extend(_render_artifact_lines(best_run["artifact_paths"], prefix="  - "))

    if report_view["leaderboard_preview"]:
        lines.append("leaderboard_preview:")
        for row in report_view["leaderboard_preview"]:
            subject_name = row.get("model_name") or row.get("run_name") or row.get("entry_name")
            metric_value = row.get("eval_macro_f1", row.get("cv_macro_f1_mean"))
            lines.append(f"- {subject_name}: macro_f1={_format_value(metric_value)}")

    return lines


def render_summary_markdown(summary_view):
    lines = [
        f"# Experiment Summary: {summary_view['experiment_name']}",
        "",
        f"- Workflow: `{summary_view['workflow_type']}`",
        f"- Path: `{summary_view['path']}`",
        f"- Macro F1: `{_format_value(summary_view['metric_highlights'].get('macro_f1'))}`",
        f"- Accuracy: `{_format_value(summary_view['metric_highlights'].get('accuracy'))}`",
        f"- Negative Recall: `{_format_value(summary_view['metric_highlights'].get('negative_recall'))}`",
        f"- Target Macro F1: `{_format_value(summary_view.get('target_macro_f1'))}`",
        f"- Meets Target: `{_format_value(summary_view.get('meets_target_macro_f1'))}`",
        "",
        "## Artifact Paths",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in summary_view["artifact_paths"].items())
    return "\n".join(lines)


def render_report_markdown(report_view):
    lines = [
        f"# Experiment Report: {report_view['experiment_name']}",
        "",
        f"- Workflow: `{report_view['workflow_type']}`",
        f"- Path: `{report_view['path']}`",
        f"- Macro F1: `{_format_value(report_view['metric_highlights'].get('macro_f1'))}`",
        f"- Accuracy: `{_format_value(report_view['metric_highlights'].get('accuracy'))}`",
        f"- Negative Recall: `{_format_value(report_view['metric_highlights'].get('negative_recall'))}`",
        "",
        "## Artifact Paths",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in report_view["artifact_paths"].items())

    best_run = report_view.get("best_run_overview")
    if best_run:
        lines.extend(
            [
                "",
                "## Best Run",
                "",
                f"- Model/Run: `{_format_value(best_run.get('model_name'))}`",
                f"- Macro F1: `{_format_value(best_run['core_metrics'].get('macro_f1'))}`",
                f"- Summary Path: `{_format_value(best_run.get('summary_path'))}`",
            ]
        )

    if report_view["leaderboard_preview"]:
        lines.extend(["", "## Leaderboard Preview", ""])
        for row in report_view["leaderboard_preview"]:
            subject_name = row.get("model_name") or row.get("run_name") or row.get("entry_name")
            metric_value = row.get("eval_macro_f1", row.get("cv_macro_f1_mean"))
            lines.append(f"- `{subject_name}`: macro_f1=`{_format_value(metric_value)}`")

    return "\n".join(lines)


def render_comparison_report_text(report_view):
    if not report_view["rows"]:
        return ["No comparison rows found."]

    lines = [
        f"metric_key: {report_view['metric_key']}",
        f"row_count: {report_view['row_count']}",
        f"top_metric_value: {_format_value(report_view['top_metric_value'])}",
    ]
    for row in report_view["rows"]:
        lines.append(
            f"#{row['rank']} {row['workflow_type']} | {row['subject_name']} | "
            f"metric={_format_value(row['metric_value'])} | "
            f"delta_from_best={_format_value(row['delta_from_best'])}"
        )
        lines.append(f"- summary_path: {_format_value(row['summary_path'])}")
        lines.append(f"- config_snapshot_path: {_format_value(row['config_snapshot_path'])}")
        if row.get("leaderboard_path"):
            lines.append(f"- leaderboard_path: {row['leaderboard_path']}")
        if row.get("best_run_path"):
            lines.append(f"- best_run_path: {row['best_run_path']}")
    return lines


def render_comparison_report_markdown(report_view):
    lines = [
        "# Experiment Comparison Report",
        "",
        f"- Metric: `{report_view['metric_key']}`",
        f"- Row Count: `{report_view['row_count']}`",
        f"- Top Metric Value: `{_format_value(report_view['top_metric_value'])}`",
        "",
    ]
    for row in report_view["rows"]:
        lines.extend(
            [
                f"## Rank {row['rank']}: {row['subject_name']}",
                "",
                f"- Workflow: `{row['workflow_type']}`",
                f"- Experiment: `{row['experiment_name']}`",
                f"- Metric Value: `{_format_value(row['metric_value'])}`",
                f"- Delta From Best: `{_format_value(row['delta_from_best'])}`",
                f"- Summary Path: `{_format_value(row['summary_path'])}`",
                f"- Config Snapshot Path: `{_format_value(row['config_snapshot_path'])}`",
                "",
            ]
        )
    return "\n".join(lines)
