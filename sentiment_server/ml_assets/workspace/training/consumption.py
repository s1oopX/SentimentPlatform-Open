import json
from pathlib import Path
from json import JSONDecodeError

from ml_assets.workspace.data.constants import MODELS_DIR


ROOT_WORKFLOW_TYPES = {
    "transformer_train",
    "transformer_search",
    "classical_compare",
    "neural_baseline_train",
}


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def _load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _optional_json(path):
    if not path.exists():
        return None
    return _load_json(path)


def _optional_path(path):
    return str(path) if path.exists() else None


def _workflow_type_for_root(root):
    summary_path = root / "result_summary.json"
    if not summary_path.exists():
        return None
    summary = _load_json(summary_path)
    workflow_type = summary.get("workflow_type")
    if workflow_type:
        return workflow_type

    config_path = root / "config_snapshot.json"
    if not config_path.exists():
        return None
    config_snapshot = _load_json(config_path)
    return config_snapshot.get("workflow_type")


def _is_experiment_root(root):
    root = _as_path(root)
    return (root / "config_snapshot.json").exists() and (root / "result_summary.json").exists()


def _is_ranked_workflow(record):
    artifact_paths = record["artifact_paths"]
    return bool(artifact_paths.get("leaderboard_path") or artifact_paths.get("best_run_path"))


def _normalize_artifact_paths(root, result_summary):
    artifact_paths = dict(result_summary.get("artifact_paths", {}))
    artifact_paths.setdefault("experiment_root_path", str(root))
    artifact_paths.setdefault("config_snapshot_path", str(root / "config_snapshot.json"))
    artifact_paths.setdefault("result_summary_path", str(root / "result_summary.json"))

    leaderboard_path = root / "leaderboard.json"
    leaderboard_csv_path = root / "leaderboard.csv"
    best_run_path = root / "best_run.json"
    evaluation_report_path = root / "evaluation_report.json"

    if leaderboard_path.exists():
        artifact_paths.setdefault("leaderboard_path", str(leaderboard_path))
    if leaderboard_csv_path.exists():
        artifact_paths.setdefault("leaderboard_csv_path", str(leaderboard_csv_path))
    if best_run_path.exists():
        artifact_paths.setdefault("best_run_path", str(best_run_path))
    if evaluation_report_path.exists():
        artifact_paths.setdefault("evaluation_report_path", str(evaluation_report_path))

    return artifact_paths


def _normalize_metrics(payload):
    core_metrics = dict(payload.get("core_metrics", {}))
    accuracy = core_metrics.get("accuracy")
    macro_f1 = core_metrics.get("macro_f1")
    negative_recall = core_metrics.get("negative_recall")

    if accuracy is None:
        accuracy = payload.get("eval_accuracy", payload.get("cv_accuracy_mean"))
    if macro_f1 is None:
        macro_f1 = payload.get("eval_macro_f1", payload.get("cv_macro_f1_mean"))
    if negative_recall is None:
        negative_recall = payload.get(
            "eval_negative_recall",
            payload.get("cv_negative_recall_mean"),
        )

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "negative_recall": negative_recall,
    }


def load_experiment_record(path):
    root = _as_path(path)
    if not _is_experiment_root(root):
        raise FileNotFoundError(f"Not a finished experiment root: {root}")

    config_snapshot = _load_json(root / "config_snapshot.json")
    result_summary = _load_json(root / "result_summary.json")
    workflow_type = result_summary.get("workflow_type") or config_snapshot.get("workflow_type")
    artifact_paths = _normalize_artifact_paths(root, result_summary)

    leaderboard_rows = []
    leaderboard_path = artifact_paths.get("leaderboard_path")
    if leaderboard_path:
        leaderboard_rows = _load_json(Path(leaderboard_path))

    best_run = None
    best_run_path = artifact_paths.get("best_run_path")
    if best_run_path:
        best_run = _load_json(Path(best_run_path))

    experiment_name = config_snapshot.get("experiment_name") or root.name

    return {
        "path": str(root),
        "experiment_name": experiment_name,
        "display_name": experiment_name,
        "workflow_type": workflow_type,
        "config_snapshot_path": str(root / "config_snapshot.json"),
        "result_summary_path": str(root / "result_summary.json"),
        "config_snapshot": config_snapshot,
        "result_summary": result_summary,
        "core_metrics": _normalize_metrics(result_summary),
        "target_macro_f1": result_summary.get("target_macro_f1"),
        "meets_target_macro_f1": result_summary.get("meets_target_macro_f1"),
        "artifact_paths": artifact_paths,
        "leaderboard_rows": leaderboard_rows,
        "leaderboard_size": len(leaderboard_rows),
        "best_run": best_run,
        "is_ranked_workflow": bool(leaderboard_rows or best_run),
    }


def _iter_experiment_root_candidates(roots):
    seen = set()
    for root in roots:
        root = _as_path(root)
        if not root.exists():
            continue

        candidates = []
        if root.is_dir() and _is_experiment_root(root):
            candidates.append(root)
        if root.is_dir():
            candidates.extend(path.parent for path in root.rglob("result_summary.json"))

        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            yield candidate


def _iter_experiment_roots(roots):
    for candidate in _iter_experiment_root_candidates(roots):
        workflow_type = _workflow_type_for_root(candidate)
        if workflow_type in ROOT_WORKFLOW_TYPES:
            yield candidate


def _warning_for_candidate(candidate, exc):
    message = str(exc)
    if 'result_summary.json' in message:
        filename = 'result_summary.json'
    elif 'config_snapshot.json' in message:
        filename = 'config_snapshot.json'
    else:
        filename = 'artifact.json'
    return f'{candidate.name}/{filename} 解析失败'


def discover_experiment_records_with_warnings(roots=None, workflow_names=None):
    roots = roots or [MODELS_DIR]
    workflow_names = set(workflow_names or [])
    records = []
    warnings = []
    skipped_count = 0

    for root in _iter_experiment_root_candidates(roots):
        try:
            workflow_type = _workflow_type_for_root(root)
            if workflow_type not in ROOT_WORKFLOW_TYPES:
                continue
            record = load_experiment_record(root)
        except (JSONDecodeError, OSError, TypeError, ValueError) as exc:
            warnings.append(_warning_for_candidate(root, exc))
            skipped_count += 1
            continue

        if workflow_names and record["workflow_type"] not in workflow_names:
            continue
        records.append(record)

    return {
        "records": sorted(
            records,
            key=lambda item: (item["workflow_type"], item["experiment_name"], item["path"]),
        ),
        "warnings": warnings,
        "skipped_count": skipped_count,
    }


def discover_experiment_records(roots=None, workflow_names=None):
    return discover_experiment_records_with_warnings(
        roots=roots,
        workflow_names=workflow_names,
    )["records"]


def _comparison_row_from_record(record, metric_key):
    metrics = _normalize_metrics(record["result_summary"])
    artifact_paths = dict(record["artifact_paths"])
    artifact_paths.setdefault("root_result_summary_path", record["result_summary_path"])
    artifact_paths.setdefault("root_config_snapshot_path", record["config_snapshot_path"])
    return {
        "workflow_type": record["workflow_type"],
        "experiment_name": record["experiment_name"],
        "subject_type": "experiment",
        "subject_name": record["experiment_name"],
        "metric_key": metric_key,
        "metric_value": metrics.get(metric_key),
        "accuracy": metrics.get("accuracy"),
        "macro_f1": metrics.get("macro_f1"),
        "negative_recall": metrics.get("negative_recall"),
        "summary_path": record["result_summary_path"],
        "config_snapshot_path": record["config_snapshot_path"],
        "root_result_summary_path": record["result_summary_path"],
        "root_config_snapshot_path": record["config_snapshot_path"],
        "leaderboard_path": artifact_paths.get("leaderboard_path"),
        "best_run_path": artifact_paths.get("best_run_path"),
        "artifact_paths": artifact_paths,
        "experiment_root_path": record["path"],
    }


def _comparison_rows_from_ranked_record(record, metric_key):
    rows = []
    for entry in record["leaderboard_rows"]:
        metrics = _normalize_metrics(entry)
        artifact_paths = dict(entry.get("artifact_paths", {}))
        if entry.get("summary_path"):
            artifact_paths.setdefault("summary_path", entry["summary_path"])
        if entry.get("config_snapshot_path"):
            artifact_paths.setdefault("config_snapshot_path", entry["config_snapshot_path"])
        artifact_paths.setdefault("experiment_root_path", record["path"])
        artifact_paths.setdefault("root_result_summary_path", record["result_summary_path"])
        artifact_paths.setdefault("root_config_snapshot_path", record["config_snapshot_path"])
        if record["artifact_paths"].get("leaderboard_path"):
            artifact_paths.setdefault("leaderboard_path", record["artifact_paths"]["leaderboard_path"])
        if record["artifact_paths"].get("best_run_path"):
            artifact_paths.setdefault("best_run_path", record["artifact_paths"]["best_run_path"])

        subject_name = (
            entry.get("model_name")
            or entry.get("run_name")
            or entry.get("entry_name")
            or record["experiment_name"]
        )
        rows.append(
            {
                "workflow_type": record["workflow_type"],
                "experiment_name": record["experiment_name"],
                "subject_type": "leaderboard_entry",
                "subject_name": subject_name,
                "metric_key": metric_key,
                "metric_value": metrics.get(metric_key),
                "accuracy": metrics.get("accuracy"),
                "macro_f1": metrics.get("macro_f1"),
                "negative_recall": metrics.get("negative_recall"),
                "summary_path": artifact_paths.get("summary_path", record["result_summary_path"]),
                "config_snapshot_path": artifact_paths.get(
                    "config_snapshot_path",
                    record["config_snapshot_path"],
                ),
                "root_result_summary_path": record["result_summary_path"],
                "root_config_snapshot_path": record["config_snapshot_path"],
                "leaderboard_path": artifact_paths.get("leaderboard_path"),
                "best_run_path": artifact_paths.get("best_run_path"),
                "artifact_paths": artifact_paths,
                "experiment_root_path": record["path"],
            }
        )
    return rows


def build_comparison_rows(records, metric_key="macro_f1"):
    rows = []
    for record in records:
        if _is_ranked_workflow(record):
            rows.extend(_comparison_rows_from_ranked_record(record, metric_key))
            continue
        rows.append(_comparison_row_from_record(record, metric_key))

    rows = sorted(
        rows,
        key=lambda item: (
            item["metric_value"] is None,
            -(item["metric_value"] or 0),
            item["workflow_type"],
            item["subject_name"],
        ),
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows

