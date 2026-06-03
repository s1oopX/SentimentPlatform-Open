import os
from pathlib import Path

from django.conf import settings

from apps.admin_panel.domain.rules.training_admin import (
    is_runtime_compatible_training_task,
)
from apps.admin_panel.infra.runtime_registry.registry import runtime_artifacts_complete
from apps.admin_panel.infra.runtime_registry.registry import is_effectively_runtime_compatible
from apps.admin_panel.infra.training.artifacts import safe_artifact_value
from apps.analysis.models import Model


def _normalize_path_key(value):
    if not value:
        return ""
    return os.path.normcase(str(Path(value).resolve()))


def list_training_run_runtime_models(training_run):
    models_by_key = {}
    for model in training_run.registered_models.all():
        models_by_key[_normalize_path_key(model.path)] = model

    artifact_path_keys = {
        _normalize_path_key(path)
        for path in (training_run.artifact_paths or {}).values()
        if path
    }
    if artifact_path_keys:
        fallback_models = Model.objects.filter(source_run__isnull=True).order_by(
            "-is_active",
            "-is_best_candidate",
            "-created_at",
            "-pk",
        )
        for model in fallback_models:
            path_key = _normalize_path_key(model.path)
            if path_key in artifact_path_keys:
                models_by_key.setdefault(path_key, model)

    return list(models_by_key.values())


def resolve_training_run_log_path(training_run):
    log_path_value = training_run.log_path or ""
    if not log_path_value:
        return None

    training_root = Path(settings.MODEL_WORKSPACE_DIR).resolve()
    training_runs_root = training_root / "models" / "_training_runs"
    candidate = Path(log_path_value).resolve()
    try:
        candidate.relative_to(training_root)
        candidate.relative_to(training_runs_root)
    except ValueError:
        return None
    if candidate.name != "run.log":
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def read_training_log_preview(log_path, *, max_bytes=None):
    preview_bytes = max(
        1,
        int(
            max_bytes or getattr(settings, "TRAINING_LOG_PREVIEW_MAX_BYTES", 64 * 1024)
        ),
    )
    size_bytes = log_path.stat().st_size

    with log_path.open("rb") as handle:
        if size_bytes <= preview_bytes:
            raw = handle.read()
            return raw.decode("utf-8", errors="replace"), size_bytes, False

        handle.seek(-preview_bytes, os.SEEK_END)
        raw = handle.read()
        return raw.decode("utf-8", errors="replace"), size_bytes, True


def is_runtime_compatible_training_run(training_run):
    return is_runtime_compatible_training_task(training_run.task_type)


def resolve_runtime_activation_candidate(*, training_run):
    if training_run.status != "succeeded":
        return None
    if not is_runtime_compatible_training_run(training_run):
        return None

    runtime_models = list_training_run_runtime_models(training_run)
    best_candidate = next(
        (model for model in runtime_models if model.is_best_candidate),
        None,
    )
    if (
        best_candidate
        and is_effectively_runtime_compatible(best_candidate)
        and runtime_artifacts_complete(best_candidate.path)
    ):
        return best_candidate

    for candidate in runtime_models:
        if (
            is_effectively_runtime_compatible(candidate)
            and runtime_artifacts_complete(candidate.path)
        ):
            return candidate
    return None


def build_registered_model_payloads(training_run):
    return [
        {
            "id": model.id,
            "name": model.name,
            "file_label": safe_artifact_value(model.path),
            "location_label": "已注册模型",
            "is_runtime_compatible": is_effectively_runtime_compatible(model),
            "is_active": model.is_active,
            "version": model.version,
        }
        for model in list_training_run_runtime_models(training_run)
    ]
