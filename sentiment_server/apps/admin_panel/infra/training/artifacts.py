from pathlib import Path


ARTIFACT_LABELS = {
    "output_dir": "Output directory",
    "best_model_path": "Best model",
    "best_model_summary_path": "Best model summary",
    "best_model_config_snapshot_path": "Best model config",
    "best_model_report_path": "Best model report",
    "leaderboard_path": "Leaderboard",
    "leaderboard_csv_path": "Leaderboard CSV",
    "best_run_path": "Best run",
    "experiment_root_path": "Experiment root",
    "config_snapshot_path": "Config snapshot",
    "result_summary_path": "Result summary",
    "evaluation_report_path": "Evaluation report",
    "model_path": "Model artifact",
}


def safe_artifact_value(path_value):
    if not path_value:
        return ""
    return Path(path_value).name or str(path_value)


def build_artifact_summaries(artifact_paths):
    summaries = []
    for key, value in (artifact_paths or {}).items():
        if not value:
            continue
        summaries.append(
            {
                "key": key,
                "label": ARTIFACT_LABELS.get(key, key),
                "value": safe_artifact_value(value),
            }
        )
    return summaries
