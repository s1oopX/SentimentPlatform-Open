import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.data.constants import MODELS_DIR
from ml_assets.workspace.training.consumption import (
    build_comparison_rows,
    discover_experiment_records,
    load_experiment_record,
)
from ml_assets.workspace.training.reporting import (
    build_comparison_report_view,
    build_experiment_report_view,
    build_experiment_summary_view,
    render_comparison_report_markdown,
    render_comparison_report_text,
    render_report_markdown,
    render_report_text,
    render_summary_markdown,
    render_summary_text,
)
from ml_assets.workspace.training.history import build_history_browser_view, build_history_dashboard_view
from ml_assets.workspace.training.tracking import build_long_term_tracking_view
from ml_assets.workspace.training.trends import build_grouped_trend_summary, filter_experiment_records


SUPPORTED_FORMATS = ("text", "json", "markdown")
SUPPORTED_METRICS = ("macro_f1", "accuracy", "negative_recall")
SUPPORTED_TREND_GROUPS = ("workflow_type", "runtime_profile")


def _emit(payload, output_format):
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if isinstance(payload, list):
        for line in payload:
            print(line)
        return

    print(payload)


def _default_roots(paths):
    if paths:
        return [Path(path) for path in paths]
    return [MODELS_DIR]


def _parse_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _record_overview(record):
    metrics = record["core_metrics"]
    return {
        "workflow_type": record["workflow_type"],
        "experiment_name": record["experiment_name"],
        "path": record["path"],
        "macro_f1": metrics.get("macro_f1"),
        "accuracy": metrics.get("accuracy"),
        "negative_recall": metrics.get("negative_recall"),
        "is_ranked_workflow": record["is_ranked_workflow"],
        "leaderboard_size": record["leaderboard_size"],
        "artifact_paths": record["artifact_paths"],
    }


def _load_records(args):
    records = []
    if getattr(args, "path", None):
        records.extend(load_experiment_record(path) for path in args.path)
    records.extend(
        discover_experiment_records(
            roots=_default_roots(getattr(args, "root", [])),
            workflow_names=getattr(args, "workflow", []),
        )
    )
    return _dedupe_records(records)


def _render_list_text(records):
    if not records:
        return ["No experiments found."]

    lines = []
    for record in records:
        metrics = record["core_metrics"]
        lines.append(
            f"{record['workflow_type']} | {record['experiment_name']} | "
            f"macro_f1={metrics.get('macro_f1')} | path={record['path']}"
        )
    return lines


def _render_show_text(record):
    lines = [
        f"workflow_type: {record['workflow_type']}",
        f"experiment_name: {record['experiment_name']}",
        f"path: {record['path']}",
        f"macro_f1: {record['core_metrics'].get('macro_f1')}",
        f"accuracy: {record['core_metrics'].get('accuracy')}",
        f"negative_recall: {record['core_metrics'].get('negative_recall')}",
        "artifacts:",
    ]
    for key, value in sorted(record["artifact_paths"].items()):
        lines.append(f"- {key}: {value}")

    if record["leaderboard_rows"]:
        lines.append("leaderboard:")
        for row in record["leaderboard_rows"][:5]:
            subject_name = row.get("model_name") or row.get("run_name") or row.get("entry_name")
            metric_value = row.get("eval_macro_f1", row.get("cv_macro_f1_mean"))
            lines.append(f"- {subject_name}: macro_f1={metric_value}")

    return lines


def _render_compare_text(rows):
    if not rows:
        return ["No comparison rows found."]

    lines = []
    for row in rows:
        lines.append(
            f"#{row['rank']} {row['workflow_type']} | {row['subject_name']} | "
            f"macro_f1={row.get('macro_f1')} | summary={row['summary_path']} | "
            f"root={row['experiment_root_path']}"
        )
    return lines


def _dedupe_records(records):
    deduped = {}
    for record in records:
        deduped[record["path"]] = record
    return list(deduped.values())


def _emit_summary_views(summary_views, output_format):
    if output_format == "json":
        _emit(summary_views, output_format)
        return

    if output_format == "markdown":
        payload = "\n\n---\n\n".join(render_summary_markdown(item) for item in summary_views)
        _emit(payload, "text")
        return

    lines = []
    for index, item in enumerate(summary_views):
        if index:
            lines.append("")
        lines.extend(render_summary_text(item))
    _emit(lines, "text")


def _emit_report_view(report_view, output_format):
    if output_format == "json":
        _emit(report_view, output_format)
        return
    if output_format == "markdown":
        _emit(render_report_markdown(report_view), "text")
        return
    _emit(render_report_text(report_view), "text")


def _emit_comparison_report_view(report_view, output_format):
    if output_format == "json":
        _emit(report_view, output_format)
        return
    if output_format == "markdown":
        _emit(render_comparison_report_markdown(report_view), "text")
        return
    _emit(render_comparison_report_text(report_view), "text")


def _render_trends_text(summary):
    if not summary["groups"]:
        return ["No trend records found."]

    lines = [
        f"group_by: {summary['group_by']}",
        f"total_records: {summary['total_records']}",
        f"group_count: {summary['group_count']}",
    ]

    for group in summary["groups"]:
        lines.extend(
            [
                "",
                f"[{group['group_value']}]",
                f"record_count: {group['record_count']}",
                f"active_count: {group['active_count']}",
                f"archived_count: {group['archived_count']}",
                "metric_averages:",
            ]
        )
        for metric_key, metric_value in group["metric_averages"].items():
            lines.append(f"- {metric_key}: {metric_value}")
        lines.append("trend_points:")
        for item in group["trend_points"]:
            lines.append(
                f"- {item['experiment_name']} | archived={item['is_archived']} | "
                f"timestamp={item['timestamp']} | metrics={item['metrics']}"
            )

    return lines


def _render_trends_markdown(summary):
    if not summary["groups"]:
        return "## Trends\n\nNo trend records found."

    sections = [
        "## Trends",
        "",
        f"- group_by: `{summary['group_by']}`",
        f"- total_records: `{summary['total_records']}`",
        f"- group_count: `{summary['group_count']}`",
    ]

    for group in summary["groups"]:
        sections.extend(
            [
                "",
                f"### {group['group_value']}",
                "",
                f"- record_count: `{group['record_count']}`",
                f"- active_count: `{group['active_count']}`",
                f"- archived_count: `{group['archived_count']}`",
                "",
                "Metric averages:",
            ]
        )
        for metric_key, metric_value in group["metric_averages"].items():
            sections.append(f"- `{metric_key}`: `{metric_value}`")
        sections.extend(["", "Trend points:"])
        for item in group["trend_points"]:
            sections.append(
                f"- `{item['experiment_name']}` | archived=`{item['is_archived']}` | "
                f"timestamp=`{item['timestamp']}` | metrics=`{item['metrics']}`"
            )

    return "\n".join(sections)


def _render_dashboard_text(dashboard):
    lines = [
        "dashboard:",
        f"total_records: {dashboard['totals']['total_records']}",
        f"active_records: {dashboard['totals']['active_records']}",
        f"archived_records: {dashboard['totals']['archived_records']}",
        f"ranked_workflow_records: {dashboard['totals']['ranked_workflow_records']}",
        f"workflow_count: {dashboard['totals']['workflow_count']}",
        f"meets_target_records: {dashboard['totals']['meets_target_records']}",
        f"below_target_records: {dashboard['totals']['below_target_records']}",
        "recent_records:",
    ]
    for item in dashboard["recent_records"]:
        lines.append(
            f"- {item['experiment_name']} | {item['workflow_type']} | "
            f"archived={item['is_archived']} | timestamp={item['timestamp']} | "
            f"macro_f1={item['metric_highlights'].get('macro_f1')}"
        )
    lines.append("best_records:")
    for item in dashboard["best_records"]:
        lines.append(
            f"- {item['experiment_name']} | {item['workflow_type']} | "
            f"macro_f1={item['metric_highlights'].get('macro_f1')} | path={item['path']}"
        )
    lines.append("archive_summary:")
    lines.append(f"- active_records: {dashboard['archive_summary']['active_records']}")
    lines.append(f"- archived_records: {dashboard['archive_summary']['archived_records']}")
    for item in dashboard["archive_summary"]["workflow_breakdown"]:
        lines.append(
            f"- workflow={item['workflow_type']} total={item['total_records']} "
            f"active={item['active_records']} archived={item['archived_records']}"
        )
    return lines


def _render_dashboard_markdown(dashboard):
    sections = [
        "# History Dashboard",
        "",
        "## Totals",
        "",
        f"- total_records: `{dashboard['totals']['total_records']}`",
        f"- active_records: `{dashboard['totals']['active_records']}`",
        f"- archived_records: `{dashboard['totals']['archived_records']}`",
        f"- ranked_workflow_records: `{dashboard['totals']['ranked_workflow_records']}`",
        f"- workflow_count: `{dashboard['totals']['workflow_count']}`",
        f"- meets_target_records: `{dashboard['totals']['meets_target_records']}`",
        f"- below_target_records: `{dashboard['totals']['below_target_records']}`",
        "",
        "## Recent Records",
        "",
    ]
    for item in dashboard["recent_records"]:
        sections.append(
            f"- `{item['experiment_name']}` | workflow=`{item['workflow_type']}` | "
            f"archived=`{item['is_archived']}` | timestamp=`{item['timestamp']}` | "
            f"macro_f1=`{item['metric_highlights'].get('macro_f1')}`"
        )
    sections.extend(["", "## Best Records", ""])
    for item in dashboard["best_records"]:
        sections.append(
            f"- `{item['experiment_name']}` | workflow=`{item['workflow_type']}` | "
            f"macro_f1=`{item['metric_highlights'].get('macro_f1')}` | path=`{item['path']}`"
        )
    sections.extend(["", "## Archive Summary", ""])
    sections.append(f"- active_records: `{dashboard['archive_summary']['active_records']}`")
    sections.append(f"- archived_records: `{dashboard['archive_summary']['archived_records']}`")
    for item in dashboard["archive_summary"]["workflow_breakdown"]:
        sections.append(
            f"- workflow=`{item['workflow_type']}` total=`{item['total_records']}` "
            f"active=`{item['active_records']}` archived=`{item['archived_records']}`"
        )
    return "\n".join(sections)


def _render_browse_text(browser):
    if not browser["items"]:
        return ["No browser records found."]

    lines = [
        f"total_records: {browser['total_records']}",
        f"returned_records: {browser['returned_records']}",
        f"sort_by: {browser['sort_by']}",
        f"applied_filters: {browser['applied_filters']}",
        "items:",
    ]
    for item in browser["items"]:
        lines.append(
            f"- {item['experiment_name']} | {item['workflow_type']} | archive={item['status_labels']['archive']} | "
            f"ranking={item['status_labels']['ranking']} | target={item['status_labels']['target']} | "
            f"macro_f1={item['metric_highlights'].get('macro_f1')} | path={item['path']}"
        )
        lines.append(
            f"  summary={item['detail_bundle']['primary_summary_path']} | "
            f"config={item['detail_bundle']['config_snapshot_path']} | "
            f"leaderboard={item['detail_bundle']['leaderboard_path']} | "
            f"best_run={item['detail_bundle']['best_run_path']}"
        )
    return lines


def _render_browse_markdown(browser):
    if not browser["items"]:
        return "# History Browser\n\nNo browser records found."

    sections = [
        "# History Browser",
        "",
        f"- total_records: `{browser['total_records']}`",
        f"- returned_records: `{browser['returned_records']}`",
        f"- sort_by: `{browser['sort_by']}`",
        f"- applied_filters: `{browser['applied_filters']}`",
        "",
        "## Items",
        "",
    ]
    for item in browser["items"]:
        sections.append(
            f"- `{item['experiment_name']}` | workflow=`{item['workflow_type']}` | archive=`{item['status_labels']['archive']}` | "
            f"ranking=`{item['status_labels']['ranking']}` | target=`{item['status_labels']['target']}` | "
            f"macro_f1=`{item['metric_highlights'].get('macro_f1')}` | path=`{item['path']}`"
        )
        sections.append(
            f"  detail: summary=`{item['detail_bundle']['primary_summary_path']}` "
            f"config=`{item['detail_bundle']['config_snapshot_path']}` "
            f"leaderboard=`{item['detail_bundle']['leaderboard_path']}` "
            f"best_run=`{item['detail_bundle']['best_run_path']}`"
        )
    return "\n".join(sections)


def _render_track_text(tracking):
    lines = [f"total_records: {tracking['total_records']}"]
    best = tracking.get('best_so_far')
    if best:
        lines.append(
            f"best_so_far: {best['experiment_name']} | macro_f1={best['metric_highlights'].get('macro_f1')} | "
            f"summary={best['detail_bundle']['primary_summary_path']}"
        )
    regression = tracking.get('recent_regression')
    if regression:
        lines.append(
            f"recent_regression: {regression['experiment_name']} | "
            f"delta_from_best={regression['delta_from_best']}"
        )
    lines.append(
        f"archive_status: active={tracking['archive_status']['active_records']} "
        f"archived={tracking['archive_status']['archived_records']}"
    )
    lines.append("recent_window:")
    for item in tracking.get('recent_window', {}).get('items', []):
        lines.append(
            f"- {item['experiment_name']} | {item['workflow_type']} | "
            f"macro_f1={item['metric_highlights'].get('macro_f1')} | timestamp={item['timestamp']}"
        )
    lines.append("workflow_statuses:")
    for item in tracking.get('workflow_statuses', []):
        lines.append(
            f"- {item['workflow_type']} | status={item['status_label']} | "
            f"delta_from_previous={item['delta_from_previous']} | delta_from_best={item['delta_from_best']}"
        )
    lines.append("profile_statuses:")
    for item in tracking.get('profile_statuses', []):
        lines.append(
            f"- {item['runtime_profile']} | status={item['status_label']} | "
            f"delta_from_previous={item['delta_from_previous']} | delta_from_best={item['delta_from_best']}"
        )
    lines.append("tracking_facets:")
    for item in tracking.get('tracking_facets', {}).get('workflows', []):
        lines.append(f"- workflow {item['workflow_type']}: {item['record_count']}")
    for item in tracking.get('tracking_facets', {}).get('runtime_profiles', []):
        lines.append(f"- profile {item['runtime_profile']}: {item['record_count']}")
    archive = tracking.get('tracking_facets', {}).get('archive', {})
    if archive:
        lines.append(
            f"- archive active={archive.get('active_records')} archived={archive.get('archived_records')}"
        )
    return lines


def _render_track_markdown(tracking):
    lines = [
        "# Long-Term Tracking",
        "",
        f"- total_records: `{tracking['total_records']}`",
    ]
    best = tracking.get('best_so_far')
    if best:
        lines.extend(
            [
                "",
                "## Best So Far",
                "",
                f"- experiment: `{best['experiment_name']}`",
                f"- macro_f1: `{best['metric_highlights'].get('macro_f1')}`",
                f"- summary: `{best['detail_bundle']['primary_summary_path']}`",
            ]
        )
    regression = tracking.get('recent_regression')
    if regression:
        lines.extend(
            [
                "",
                "## Recent Regression",
                "",
                f"- experiment: `{regression['experiment_name']}`",
                f"- delta_from_best: `{regression['delta_from_best']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Archive Status",
            "",
            f"- active_records: `{tracking['archive_status']['active_records']}`",
            f"- archived_records: `{tracking['archive_status']['archived_records']}`",
        ]
    )
    if tracking.get('recent_window', {}).get('items'):
        lines.extend(["", "## Recent Window", ""])
        for item in tracking['recent_window']['items']:
            lines.append(
                f"- `{item['experiment_name']}` | workflow=`{item['workflow_type']}` | "
                f"macro_f1=`{item['metric_highlights'].get('macro_f1')}` | timestamp=`{item['timestamp']}`"
            )
    if tracking.get('workflow_statuses'):
        lines.extend(["", "## Workflow Statuses", ""])
        for item in tracking['workflow_statuses']:
            lines.append(
                f"- `{item['workflow_type']}` | status=`{item['status_label']}` | "
                f"delta_from_previous=`{item['delta_from_previous']}` | "
                f"delta_from_best=`{item['delta_from_best']}`"
            )
    if tracking.get('profile_statuses'):
        lines.extend(["", "## Profile Statuses", ""])
        for item in tracking['profile_statuses']:
            lines.append(
                f"- `{item['runtime_profile']}` | status=`{item['status_label']}` | "
                f"delta_from_previous=`{item['delta_from_previous']}` | "
                f"delta_from_best=`{item['delta_from_best']}`"
            )
    if tracking.get('tracking_facets'):
        lines.extend(["", "## Tracking Facets", ""])
        for item in tracking['tracking_facets'].get('workflows', []):
            lines.append(f"- workflow `{item['workflow_type']}`: `{item['record_count']}`")
        for item in tracking['tracking_facets'].get('runtime_profiles', []):
            lines.append(f"- profile `{item['runtime_profile']}`: `{item['record_count']}`")
        archive = tracking['tracking_facets'].get('archive', {})
        lines.append(
            f"- archive active=`{archive.get('active_records')}` archived=`{archive.get('archived_records')}`"
        )
    return "\n".join(lines)


def handle_list(args):
    records = discover_experiment_records(
        roots=_default_roots(args.root),
        workflow_names=args.workflow,
    )
    payload = [_record_overview(record) for record in records]
    if args.format == "json":
        _emit(payload, args.format)
        return
    _emit(_render_list_text(records), args.format)


def handle_show(args):
    record = load_experiment_record(args.path)
    if args.format == "json":
        _emit(record, args.format)
        return
    _emit(_render_show_text(record), args.format)


def handle_summary(args):
    records = _load_records(args)
    summary_views = [build_experiment_summary_view(record) for record in records]
    _emit_summary_views(summary_views, args.format)


def handle_report(args):
    record = load_experiment_record(args.path)
    report_view = build_experiment_report_view(record)
    _emit_report_view(report_view, args.format)


def handle_compare(args):
    records = _load_records(args)
    rows = build_comparison_rows(records, metric_key=args.metric)
    if args.format == "json":
        _emit(rows, args.format)
        return
    _emit(_render_compare_text(rows), args.format)


def handle_compare_report(args):
    records = _load_records(args)
    rows = build_comparison_rows(records, metric_key=args.metric)
    report_view = build_comparison_report_view(rows, metric_key=args.metric)
    _emit_comparison_report_view(report_view, args.format)


def handle_trends(args):
    records = _load_records(args)
    filtered = filter_experiment_records(
        records,
        workflow_types=args.workflow,
        runtime_profiles=args.profile,
        start_time=args.start_time,
        end_time=args.end_time,
        tags=args.tag,
    )
    summary = build_grouped_trend_summary(filtered, group_by=args.group_by)

    if args.format == "json":
        _emit(summary, args.format)
        return
    if args.format == "markdown":
        _emit(_render_trends_markdown(summary), "text")
        return
    _emit(_render_trends_text(summary), "text")


def handle_dashboard(args):
    records = _load_records(args)
    filtered = filter_experiment_records(
        records,
        workflow_types=args.workflow,
        runtime_profiles=args.profile,
        start_time=args.start_time,
        end_time=args.end_time,
        tags=args.tag,
    )
    dashboard = build_history_dashboard_view(
        filtered,
        recent_limit=args.recent_limit,
        best_limit=args.best_limit,
        metric_key=args.metric,
    )

    if args.format == "json":
        _emit(dashboard, args.format)
        return
    if args.format == "markdown":
        _emit(_render_dashboard_markdown(dashboard), "text")
        return
    _emit(_render_dashboard_text(dashboard), "text")


def handle_browse(args):
    records = _load_records(args)
    filtered = filter_experiment_records(
        records,
        workflow_types=args.workflow,
        runtime_profiles=args.profile,
        start_time=args.start_time,
        end_time=args.end_time,
        tags=args.tag,
    )
    browser = build_history_browser_view(
        filtered,
        archived=args.archived,
        ranked_only=args.ranked_only,
        meets_target=args.meets_target,
        sort_by=args.sort_by,
        limit=args.limit,
    )

    if args.format == "json":
        _emit(browser, args.format)
        return
    if args.format == "markdown":
        _emit(_render_browse_markdown(browser), "text")
        return
    _emit(_render_browse_text(browser), "text")


def handle_track(args):
    records = _load_records(args)
    filtered = filter_experiment_records(
        records,
        workflow_types=args.workflow,
        runtime_profiles=args.profile,
        start_time=args.start_time,
        end_time=args.end_time,
        tags=args.tag,
    )
    tracking = build_long_term_tracking_view(filtered)

    if args.format == "json":
        _emit(tracking, args.format)
        return
    if args.format == "markdown":
        _emit(_render_track_markdown(tracking), "text")
        return
    _emit(_render_track_text(tracking), "text")


def build_parser(
    description="维护态实验消费入口：浏览、查看和比较已完成实验 artifact。",
):
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(dest="command", metavar="command")
    subparsers.required = True

    list_parser = subparsers.add_parser("list", help="浏览已完成实验")
    list_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    list_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    list_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    list_parser.set_defaults(handler=handle_list)

    summary_parser = subparsers.add_parser("summary", help="查看实验摘要")
    summary_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    summary_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    summary_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    summary_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    summary_parser.set_defaults(handler=handle_summary)

    show_parser = subparsers.add_parser("show", help="查看单个实验详情")
    show_parser.add_argument("--path", type=Path, required=True, help="实验根目录")
    show_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    show_parser.set_defaults(handler=handle_show)

    report_parser = subparsers.add_parser("report", help="查看单个实验报告")
    report_parser.add_argument("--path", type=Path, required=True, help="实验根目录")
    report_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    report_parser.set_defaults(handler=handle_report)

    compare_parser = subparsers.add_parser("compare", help="比较多个实验或模型结果")
    compare_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    compare_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    compare_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    compare_parser.add_argument("--metric", choices=SUPPORTED_METRICS, default="macro_f1", help="排序指标")
    compare_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    compare_parser.set_defaults(handler=handle_compare)

    compare_report_parser = subparsers.add_parser("compare-report", help="生成实验比较报告")
    compare_report_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    compare_report_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    compare_report_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    compare_report_parser.add_argument("--metric", choices=SUPPORTED_METRICS, default="macro_f1", help="排序指标")
    compare_report_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    compare_report_parser.set_defaults(handler=handle_compare_report)

    trends_parser = subparsers.add_parser("trends", help="查看实验趋势聚合摘要")
    trends_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    trends_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    trends_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    trends_parser.add_argument("--profile", action="append", default=[], help="按 runtime profile 过滤")
    trends_parser.add_argument("--tag", action="append", default=[], help="按标签过滤")
    trends_parser.add_argument("--start-time", type=_parse_datetime, help="起始时间，ISO-8601")
    trends_parser.add_argument("--end-time", type=_parse_datetime, help="结束时间，ISO-8601")
    trends_parser.add_argument("--group-by", choices=SUPPORTED_TREND_GROUPS, default="workflow_type", help="趋势聚合分组方式")
    trends_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    trends_parser.set_defaults(handler=handle_trends)

    dashboard_parser = subparsers.add_parser("dashboard", help="查看实验历史与仪表盘摘要")
    dashboard_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    dashboard_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    dashboard_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    dashboard_parser.add_argument("--profile", action="append", default=[], help="按 runtime profile 过滤")
    dashboard_parser.add_argument("--tag", action="append", default=[], help="按标签过滤")
    dashboard_parser.add_argument("--start-time", type=_parse_datetime, help="起始时间，ISO-8601")
    dashboard_parser.add_argument("--end-time", type=_parse_datetime, help="结束时间，ISO-8601")
    dashboard_parser.add_argument("--recent-limit", type=int, default=5, help="最近记录数量")
    dashboard_parser.add_argument("--best-limit", type=int, default=5, help="最佳记录数量")
    dashboard_parser.add_argument("--metric", choices=SUPPORTED_METRICS, default="macro_f1", help="最佳记录排序指标")
    dashboard_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    dashboard_parser.set_defaults(handler=handle_dashboard)

    browse_parser = subparsers.add_parser("browse", help="浏览统一实验历史卡片")
    browse_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    browse_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    browse_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    browse_parser.add_argument("--profile", action="append", default=[], help="按 runtime profile 过滤")
    browse_parser.add_argument("--tag", action="append", default=[], help="按标签过滤")
    browse_parser.add_argument("--start-time", type=_parse_datetime, help="起始时间，ISO-8601")
    browse_parser.add_argument("--end-time", type=_parse_datetime, help="结束时间，ISO-8601")
    browse_parser.add_argument("--archived", choices=("active", "archived", "all"), default="active", help="归档状态过滤")
    browse_parser.add_argument("--ranked-only", action="store_true", help="仅保留 ranked workflow")
    browse_parser.add_argument("--meets-target", choices=("all", "met", "unmet"), default="all", help="按目标达成状态过滤")
    browse_parser.add_argument("--sort-by", choices=("recent", "best"), default="recent", help="浏览排序方式")
    browse_parser.add_argument("--limit", type=int, default=20, help="返回记录数量")
    browse_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    browse_parser.set_defaults(handler=handle_browse)

    track_parser = subparsers.add_parser("track", help="查看长期跟踪与状态摘要")
    track_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    track_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    track_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    track_parser.add_argument("--profile", action="append", default=[], help="按 runtime profile 过滤")
    track_parser.add_argument("--tag", action="append", default=[], help="按标签过滤")
    track_parser.add_argument("--start-time", type=_parse_datetime, help="起始时间，ISO-8601")
    track_parser.add_argument("--end-time", type=_parse_datetime, help="结束时间，ISO-8601")
    track_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    track_parser.set_defaults(handler=handle_track)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    main()

