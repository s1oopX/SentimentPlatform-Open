import json
import shutil
from pathlib import Path

from ml_assets.workspace.data.constants import MODELS_DIR
from ml_assets.workspace.training.hygiene import (
    build_cleanup_plan,
    discover_hygiene_records,
    load_hygiene_record,
    validate_hygiene_record,
)


DEFAULT_ARCHIVE_DIR_NAME = "_archive"
DEFAULT_ARCHIVE_ROOT = MODELS_DIR / DEFAULT_ARCHIVE_DIR_NAME
ARCHIVE_MANIFEST_NAME = "archive_manifest.json"


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def _relative_preserved_paths(record, preserved_paths):
    root = _as_path(record["path"]).resolve()
    relative_paths = []
    for path in preserved_paths:
        path = _as_path(path).resolve()
        if path == root:
            continue
        try:
            relative_paths.append(str(path.relative_to(root)))
        except ValueError:
            continue
    return sorted(relative_paths)


def _workflow_archive_bucket(record):
    workflow_type = record.get("workflow_type") or "unknown"
    root = _as_path(record["path"]).resolve()
    parent_name = root.parent.name or "experiments"
    if workflow_type in {"transformer_search", "classical_compare", "neural_baseline_train"}:
        return Path(workflow_type) / root.name
    return Path(workflow_type) / parent_name / root.name


def _is_within(path, parent):
    path = _as_path(path).resolve()
    parent = _as_path(parent).resolve()
    return path == parent or parent in path.parents


def _replace_paths(payload, source_root, archive_root):
    if isinstance(payload, dict):
        return {
            key: _replace_paths(value, source_root, archive_root)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_replace_paths(item, source_root, archive_root) for item in payload]
    if isinstance(payload, str):
        candidate = Path(payload)
        if _is_within(candidate, source_root):
            relative = candidate.resolve().relative_to(source_root.resolve())
            return str((archive_root / relative).resolve())
    return payload


def _rewrite_archived_json_paths(source_root, archive_root):
    archive_root = _as_path(archive_root).resolve()
    source_root = _as_path(source_root).resolve()
    for json_path in sorted(archive_root.rglob("*.json")):
        with json_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        rewritten = _replace_paths(payload, source_root, archive_root)
        with json_path.open("w", encoding="utf-8") as file:
            json.dump(rewritten, file, ensure_ascii=False, indent=2)
            file.write("\n")


def load_lifecycle_record(path, archive_root=None):
    archive_root = _as_path(archive_root or DEFAULT_ARCHIVE_ROOT).resolve()
    record = load_hygiene_record(path)
    findings = validate_hygiene_record(record)
    cleanup_plan = build_cleanup_plan(record)
    root = _as_path(record["path"]).resolve()
    preserved_paths = [_as_path(item).resolve() for item in cleanup_plan["preserved_paths"]]

    lifecycle_record = dict(record)
    lifecycle_record.update(
        {
            "path": str(root),
            "archive_root": str(archive_root),
            "validation": findings,
            "preserved_paths": [str(path) for path in sorted(preserved_paths)],
            "preserved_relative_paths": _relative_preserved_paths(record, preserved_paths),
            "archive_eligible": findings["is_valid"],
            "is_archived": _is_within(root, archive_root),
        }
    )
    return lifecycle_record


def discover_lifecycle_records(roots=None, workflow_names=None, archive_root=None):
    records = discover_hygiene_records(roots=roots, workflow_names=workflow_names)
    return [
        load_lifecycle_record(record["path"], archive_root=archive_root)
        for record in records
    ]


def build_retention_plan(record, archive_root=None):
    root = _as_path(record["path"]).resolve()
    archive_root = _as_path(
        archive_root or record.get("archive_root") or DEFAULT_ARCHIVE_ROOT
    ).resolve()
    archive_path = (archive_root / _workflow_archive_bucket(record)).resolve()

    action = "archive"
    reason = "eligible_for_archive"
    if record.get("is_archived") and _is_within(root, archive_root):
        action = "keep_active"
        reason = "already_archived"
    elif not record.get("validation", {}).get("is_valid", False):
        action = "skip"
        reason = "record_is_invalid"

    plan = {
        "path": str(root),
        "experiment_name": record["experiment_name"],
        "workflow_type": record["workflow_type"],
        "action": action,
        "reason": reason,
        "archive_root": str(archive_root),
        "archive_path": str(archive_path),
        "preserved_paths": list(record.get("preserved_paths", [])),
        "preserved_relative_paths": list(record.get("preserved_relative_paths", [])),
        "archive_manifest_path": str(archive_path / ARCHIVE_MANIFEST_NAME),
    }
    plan["archive_manifest"] = build_archive_manifest(record, plan)
    return plan


def build_archive_manifest(record, plan):
    return {
        "manifest_version": 1,
        "workflow_type": record["workflow_type"],
        "experiment_name": record["experiment_name"],
        "policy_action": plan["action"],
        "policy_reason": plan["reason"],
        "source_path": record["path"],
        "archive_root": plan["archive_root"],
        "archive_path": plan["archive_path"],
        "archive_manifest_path": plan["archive_manifest_path"],
        "preserved_paths": list(plan.get("preserved_paths", [])),
        "preserved_relative_paths": list(plan.get("preserved_relative_paths", [])),
        "core_metrics": dict(record.get("core_metrics") or {}),
        "target_macro_f1": record.get("target_macro_f1"),
        "meets_target_macro_f1": record.get("meets_target_macro_f1"),
    }


def apply_retention_plan(plan):
    source_root = _as_path(plan["path"]).resolve()
    archive_root = _as_path(plan["archive_root"]).resolve()
    archive_path = _as_path(plan["archive_path"]).resolve()
    manifest = dict(plan["archive_manifest"])

    if plan["action"] != "archive":
        return {
            "applied": False,
            "path": str(source_root),
            "archive_root": str(archive_root),
            "archive_path": str(archive_path),
            "archive_manifest_path": str(archive_path / ARCHIVE_MANIFEST_NAME),
            "archive_manifest": manifest,
        }

    if archive_path.exists():
        raise FileExistsError(f"Archive destination already exists: {archive_path}")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_root), str(archive_path))
    _rewrite_archived_json_paths(source_root, archive_path)

    manifest_path = archive_path / ARCHIVE_MANIFEST_NAME
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return {
        "applied": True,
        "path": str(source_root),
        "archive_root": str(archive_root),
        "archive_path": str(archive_path),
        "archive_manifest_path": str(manifest_path),
        "archive_manifest": manifest,
    }

