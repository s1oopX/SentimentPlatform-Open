from pathlib import Path

from ml_assets.workspace.evaluation.reporting import save_json
from ml_assets.workspace.evaluation.serialization import sanitize_for_json


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def to_artifact_path(path):
    return str(_as_path(path))


def build_config_snapshot(
    *,
    workflow_type,
    output_dir,
    dataset,
    runtime,
    model,
    extras=None,
):
    payload = {
        "schema_version": 1,
        "artifact_role": "config_snapshot",
        "workflow_type": workflow_type,
        "output_dir": to_artifact_path(output_dir),
        "dataset": dataset,
        "runtime": runtime,
        "model": model,
    }
    if extras:
        payload.update(extras)
    return sanitize_for_json(payload)


def build_result_summary(
    *,
    workflow_type,
    output_dir,
    core_metrics,
    target_macro_f1,
    artifact_paths,
    extras=None,
):
    macro_f1 = core_metrics.get("macro_f1", 0.0)
    payload = {
        "schema_version": 1,
        "artifact_role": "result_summary",
        "workflow_type": workflow_type,
        "output_dir": to_artifact_path(output_dir),
        "target_macro_f1": target_macro_f1,
        "meets_target_macro_f1": macro_f1 >= target_macro_f1,
        "core_metrics": core_metrics,
        "artifact_paths": artifact_paths,
    }
    if extras:
        payload.update(extras)
    return sanitize_for_json(payload)


def build_leaderboard_entry(
    *,
    workflow_type,
    entry_name,
    ranking_metric,
    core_metrics,
    artifact_paths,
    extras=None,
):
    summary_path = artifact_paths.get("result_summary_path") or artifact_paths.get("summary_path")
    config_snapshot_path = artifact_paths.get("config_snapshot_path")
    payload = {
        "schema_version": 1,
        "artifact_role": "leaderboard_entry",
        "workflow_type": workflow_type,
        "entry_name": entry_name,
        "ranking_metric": ranking_metric,
        "core_metrics": core_metrics,
        "summary_path": summary_path,
        "config_snapshot_path": config_snapshot_path,
        "artifact_paths": artifact_paths,
    }
    if extras:
        payload.update(extras)
    return sanitize_for_json(payload)


def persist_experiment_artifacts(
    output_dir,
    *,
    config_snapshot,
    result_summary,
):
    output_dir = _as_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config_snapshot_path = output_dir / "config_snapshot.json"
    result_summary_path = output_dir / "result_summary.json"

    save_json(config_snapshot_path, config_snapshot)
    save_json(result_summary_path, result_summary)

    return {
        "config_snapshot_path": to_artifact_path(config_snapshot_path),
        "result_summary_path": to_artifact_path(result_summary_path),
    }

