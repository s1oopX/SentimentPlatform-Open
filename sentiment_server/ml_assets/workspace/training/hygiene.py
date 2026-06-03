import json
from pathlib import Path
import shutil
from ml_assets.workspace.data.constants import MODELS_DIR
from ml_assets.workspace.training.consumption import ROOT_WORKFLOW_TYPES, load_experiment_record


RANKED_WORKFLOW_TYPES = {
    "transformer_search",
    "classical_compare",
    "neural_baseline_train",
}

REQUIRED_ROOT_ARTIFACTS = {
    "transformer_train": ("config_snapshot.json", "result_summary.json"),
    "transformer_search": (
        "config_snapshot.json",
        "result_summary.json",
        "leaderboard.json",
        "best_run.json",
    ),
    "classical_compare": (
        "config_snapshot.json",
        "result_summary.json",
        "leaderboard.json",
        "best_run.json",
    ),
    "neural_baseline_train": (
        "config_snapshot.json",
        "result_summary.json",
        "leaderboard.json",
        "best_run.json",
    ),
}

OPTIONAL_ROOT_ARTIFACTS = {
    "transformer_train": ("evaluation_report.json",),
    "transformer_search": ("leaderboard.csv", "evaluation_report.json"),
    "classical_compare": ("leaderboard.csv",),
    "neural_baseline_train": ("leaderboard.csv",),
}

TRANSIENT_DIR_NAMES = {
    "__pycache__",
    ".cache",
    "cache",
    "checkpoints",
    "logs",
}

TRANSIENT_FILE_SUFFIXES = (
    ".cache",
    ".log",
    ".tmp",
)

TRANSIENT_FILE_NAMES = {
    ".ds_store",
}


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def _safe_read_json(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file), None
    except FileNotFoundError:
        return None, None
    except json.JSONDecodeError as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _workflow_type_from_payloads(config_snapshot, result_summary):
    if isinstance(result_summary, dict) and result_summary.get("workflow_type"):
        return result_summary["workflow_type"]
    if isinstance(config_snapshot, dict) and config_snapshot.get("workflow_type"):
        return config_snapshot["workflow_type"]
    return None


def _iter_candidate_roots(roots):
    seen = set()
    for base_root in roots:
        base_root = _as_path(base_root)
        if not base_root.exists():
            continue

        candidates = []
        if base_root.is_dir() and any(
            (base_root / name).exists()
            for name in ("config_snapshot.json", "result_summary.json")
        ):
            candidates.append(base_root)

        if base_root.is_dir():
            for file_name in ("config_snapshot.json", "result_summary.json"):
                candidates.extend(path.parent for path in base_root.rglob(file_name))

        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            yield candidate, base_root.resolve()


def _has_ranked_root_ancestor(candidate, scan_root):
    current = candidate.parent
    while current != current.parent:
        if current == scan_root.parent:
            break
        if current == scan_root:
            break
        if (current / "leaderboard.json").exists() or (current / "best_run.json").exists():
            return True
        current = current.parent
    return False


def _required_artifact_entries(root, workflow_type):
    names = REQUIRED_ROOT_ARTIFACTS.get(workflow_type, ("config_snapshot.json", "result_summary.json"))
    entries = []
    for name in names:
        path = root / name
        entries.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
            }
        )
    return entries


def _optional_artifact_entries(root, workflow_type):
    names = OPTIONAL_ROOT_ARTIFACTS.get(workflow_type, ())
    entries = []
    for name in names:
        path = root / name
        entries.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
            }
        )
    return entries


def _referenced_paths(record):
    root = _as_path(record["path"])
    referenced = set()

    def add_path(value):
        if not value:
            return
        path = _as_path(value)
        if path.exists():
            referenced.add(path.resolve())

    for entry in record.get("required_artifacts", []):
        add_path(entry["path"])
    for entry in record.get("optional_artifacts", []):
        if entry["exists"]:
            add_path(entry["path"])

    for key, value in record.get("artifact_paths", {}).items():
        if not value:
            continue
        if key.endswith("_path"):
            add_path(value)

    best_run = record.get("best_run") or {}
    for key in ("summary_path", "config_snapshot_path"):
        add_path(best_run.get(key))
    for value in best_run.get("artifact_paths", {}).values():
        add_path(value)

    for row in record.get("leaderboard_rows", []):
        add_path(row.get("summary_path"))
        add_path(row.get("config_snapshot_path"))
        for value in row.get("artifact_paths", {}).values():
            add_path(value)

    return {
        path
        for path in referenced
        if path == root or root in path.parents
    }


def _build_broken_references(record):
    broken = []

    def add_if_missing(label, value):
        if not value:
            return
        path = _as_path(value)
        if not path.exists():
            broken.append({"label": label, "path": str(path)})

    artifact_paths = record.get("artifact_paths", {})
    required_reference_keys = {
        "config_snapshot_path",
        "result_summary_path",
        "leaderboard_path",
        "best_run_path",
    }
    for key in required_reference_keys:
        add_if_missing(key, artifact_paths.get(key))

    best_run = record.get("best_run") or {}
    add_if_missing("best_run.summary_path", best_run.get("summary_path"))
    add_if_missing("best_run.config_snapshot_path", best_run.get("config_snapshot_path"))

    for index, row in enumerate(record.get("leaderboard_rows", []), start=1):
        add_if_missing(f"leaderboard[{index}].summary_path", row.get("summary_path"))
        add_if_missing(
            f"leaderboard[{index}].config_snapshot_path",
            row.get("config_snapshot_path"),
        )

    return broken


def _is_transient_path(path):
    if path.name in TRANSIENT_DIR_NAMES or path.name in TRANSIENT_FILE_NAMES:
        return True
    if path.is_file() and path.suffix in TRANSIENT_FILE_SUFFIXES:
        return True
    return any(part in TRANSIENT_DIR_NAMES for part in path.parts)


def _cleanup_candidates(root, preserved_paths):
    preserved_paths = {path.resolve() for path in preserved_paths}
    candidates = []
    candidate_directories = set()

    for path in sorted(root.rglob("*")):
        resolved = path.resolve()
        if resolved in preserved_paths:
            continue
        if any(parent in candidate_directories for parent in resolved.parents):
            continue
        if path.is_dir():
            if not _is_transient_path(path):
                continue
            has_preserved_descendant = any(resolved in keep.parents for keep in preserved_paths)
            if has_preserved_descendant:
                continue
            candidate_directories.add(resolved)
            candidates.append(
                {
                    "path": str(path),
                    "kind": "directory",
                    "reason": "classified transient directory",
                }
            )
            continue

        if not _is_transient_path(path):
            continue
        candidates.append(
            {
                "path": str(path),
                "kind": "file",
                "reason": "classified transient file",
            }
        )

    deduped = {}
    for item in candidates:
        deduped[item["path"]] = item
    return [deduped[path] for path in sorted(deduped)]


def load_hygiene_record(path):
    root = _as_path(path).resolve()
    config_path = root / "config_snapshot.json"
    result_path = root / "result_summary.json"
    config_snapshot, config_error = _safe_read_json(config_path)
    result_summary, result_error = _safe_read_json(result_path)
    workflow_type = _workflow_type_from_payloads(config_snapshot, result_summary)

    experiment_record = None
    if config_error is None and result_error is None and config_path.exists() and result_path.exists():
        try:
            experiment_record = load_experiment_record(root)
        except FileNotFoundError:
            experiment_record = None

    artifact_paths = {}
    leaderboard_rows = []
    best_run = None
    experiment_name = root.name
    core_metrics = {
        "accuracy": None,
        "macro_f1": None,
        "negative_recall": None,
    }
    target_macro_f1 = None
    meets_target_macro_f1 = None

    if experiment_record is not None:
        artifact_paths = dict(experiment_record["artifact_paths"])
        leaderboard_rows = list(experiment_record["leaderboard_rows"])
        best_run = experiment_record["best_run"]
        experiment_name = experiment_record["experiment_name"]
        core_metrics = dict(experiment_record["core_metrics"])
        target_macro_f1 = experiment_record["target_macro_f1"]
        meets_target_macro_f1 = experiment_record["meets_target_macro_f1"]
        workflow_type = experiment_record["workflow_type"]
    else:
        if config_path.exists():
            artifact_paths["config_snapshot_path"] = str(config_path)
        if result_path.exists():
            artifact_paths["result_summary_path"] = str(result_path)
        for name in ("leaderboard.json", "leaderboard.csv", "best_run.json", "evaluation_report.json"):
            artifact = root / name
            if artifact.exists():
                artifact_paths[f"{artifact.stem}_path"] = str(artifact)
        artifact_paths.setdefault("experiment_root_path", str(root))
        if isinstance(config_snapshot, dict):
            experiment_name = config_snapshot.get("experiment_name") or experiment_name
        if isinstance(result_summary, dict):
            core_metrics.update(result_summary.get("core_metrics", {}))
            target_macro_f1 = result_summary.get("target_macro_f1")
            meets_target_macro_f1 = result_summary.get("meets_target_macro_f1")

    invalid_json_files = []
    if config_error is not None:
        invalid_json_files.append({"path": str(config_path), "error": config_error})
    if result_error is not None:
        invalid_json_files.append({"path": str(result_path), "error": result_error})

    record = {
        "path": str(root),
        "experiment_name": experiment_name,
        "workflow_type": workflow_type,
        "config_snapshot": config_snapshot if isinstance(config_snapshot, dict) else None,
        "result_summary": result_summary if isinstance(result_summary, dict) else None,
        "artifact_paths": artifact_paths,
        "leaderboard_rows": leaderboard_rows,
        "best_run": best_run,
        "core_metrics": core_metrics,
        "target_macro_f1": target_macro_f1,
        "meets_target_macro_f1": meets_target_macro_f1,
        "required_artifacts": _required_artifact_entries(root, workflow_type),
        "optional_artifacts": _optional_artifact_entries(root, workflow_type),
        "invalid_json_files": invalid_json_files,
    }
    return record


def discover_hygiene_records(roots=None, workflow_names=None):
    roots = roots or [MODELS_DIR]
    workflow_names = set(workflow_names or [])
    records = []

    for candidate, scan_root in _iter_candidate_roots(roots):
        if _has_ranked_root_ancestor(candidate, scan_root):
            continue
        record = load_hygiene_record(candidate)
        if record["workflow_type"] not in ROOT_WORKFLOW_TYPES:
            continue
        if workflow_names and record["workflow_type"] not in workflow_names:
            continue
        records.append(record)

    deduped = {}
    for record in records:
        deduped[record["path"]] = record
    return sorted(
        deduped.values(),
        key=lambda item: (
            item["workflow_type"] or "",
            item["experiment_name"],
            item["path"],
        ),
    )


def validate_hygiene_record(record):
    missing_required_artifacts = [
        item for item in record.get("required_artifacts", [])
        if not item["exists"]
    ]
    broken_references = _build_broken_references(record)
    return {
        "path": record["path"],
        "workflow_type": record["workflow_type"],
        "experiment_name": record["experiment_name"],
        "missing_required_artifacts": missing_required_artifacts,
        "invalid_json_files": list(record.get("invalid_json_files", [])),
        "broken_references": broken_references,
        "is_valid": not (
            missing_required_artifacts
            or record.get("invalid_json_files")
            or broken_references
        ),
    }


def build_cleanup_plan(record):
    root = _as_path(record["path"])
    preserved_paths = _referenced_paths(record)
    preserved_paths.add(root.resolve())

    cleanup_candidates = _cleanup_candidates(root, preserved_paths)
    return {
        "path": record["path"],
        "workflow_type": record["workflow_type"],
        "experiment_name": record["experiment_name"],
        "preserved_paths": [str(path) for path in sorted(preserved_paths)],
        "cleanup_candidates": cleanup_candidates,
    }


def apply_cleanup_plan(cleanup_plan):
    removed_paths = []
    candidates = sorted(
        cleanup_plan.get("cleanup_candidates", []),
        key=lambda item: (item["kind"] != "directory", item["path"]),
        reverse=True,
    )
    for item in candidates:
        path = _as_path(item["path"])
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed_paths.append(str(path))
    return removed_paths

