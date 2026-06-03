import shutil
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.admin_panel.training_constants import (
    TASK_TYPE_CLASSICAL_COMPARE,
    TASK_TYPE_NEURAL_BASELINE_TRAIN,
    TASK_TYPE_TRANSFORMER_SEARCH,
    TASK_TYPE_TRANSFORMER_TRAIN,
)
from apps.analysis.models import Model
from ml_assets.workspace.data.constants import sanitize_model_dir_name


def _normalize_model_path(value):
    return str(Path(value).resolve()).replace("/", "\\")


def _validate_runtime_model_dir(model_path):
    required_files = (
        model_path / "config.json",
        model_path / "model.safetensors",
        model_path / "tokenizer_config.json",
    )
    return all(path.exists() for path in required_files)


def _validate_classical_joblib_artifact(model_path):
    return (
        model_path.exists()
        and model_path.is_file()
        and model_path.suffix.lower() == ".joblib"
    )


def _validate_neural_torch_artifact(model_path):
    return (
        model_path.exists()
        and model_path.is_file()
        and model_path.suffix.lower() == ".pt"
        and (model_path.parent / "vocab.json").exists()
        and (model_path.parent / "config_snapshot.json").exists()
    )


def runtime_artifact_type(model_path):
    path = Path(model_path)
    if _validate_classical_joblib_artifact(path):
        return "classical_joblib"
    if _validate_neural_torch_artifact(path):
        return "neural_torch"
    if _validate_runtime_model_dir(path):
        return "transformer"
    return "unsupported"


def runtime_artifacts_complete(model_path):
    return runtime_artifact_type(model_path) != "unsupported"


def is_effectively_runtime_compatible(model):
    return bool(model.is_runtime_compatible or runtime_artifacts_complete(model.path))


def _is_runtime_compatible(task_type):
    return task_type in {
        TASK_TYPE_CLASSICAL_COMPARE,
        TASK_TYPE_NEURAL_BASELINE_TRAIN,
        TASK_TYPE_TRANSFORMER_TRAIN,
        TASK_TYPE_TRANSFORMER_SEARCH,
    }


def _execution_revision(training_run):
    return getattr(training_run, "execution_revision", None) or 1


def _build_version(training_run, row, index):
    name = str(row.get("name") or training_run.name or f"candidate-{index + 1}")
    normalized = name.replace(" ", "-").replace("_", "-").lower()
    return (
        f"run-{training_run.id}-rev-{_execution_revision(training_run)}-{normalized}"[
            :50
        ]
    )


def _model_run_dir(training_run, row):
    model_name = sanitize_model_dir_name(
        row.get("name") or training_run.name or "model"
    )
    execution_revision = _execution_revision(training_run)
    return (
        Path(settings.MODEL_WORKSPACE_DIR)
        / "models"
        / model_name
        / f"run-{training_run.id}-rev-{execution_revision}"
    )


def _promote_candidate_artifacts(*, training_run, row):
    source_path = Path(row["path"])
    destination_dir = _model_run_dir(training_run, row)
    execution_revision = _execution_revision(training_run)
    if source_path.is_dir():
        source_root = source_path
        final_path = destination_dir
    else:
        source_root = source_path.parent
        final_path = destination_dir / source_path.name

    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    try:
        shutil.copytree(source_root, destination_dir)
    except Exception:
        if destination_dir.exists():
            shutil.rmtree(destination_dir, ignore_errors=True)
        raise

    promoted_row = dict(row)
    promoted_row["path"] = str(final_path)
    promoted_row["artifact_dir"] = str(destination_dir)
    promoted_row["execution_revision"] = execution_revision
    return promoted_row


def _cleanup_promoted_dirs(paths):
    for path in reversed(paths):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def _existing_promoted_model(*, training_run, normalized_path, execution_revision):
    model = (
        Model.objects.filter(source_run=training_run, path=normalized_path)
        .order_by("-created_at")
        .first()
    )
    if model and Path(model.path).exists():
        artifact_summary = model.artifact_summary or {}
        stored_revision = artifact_summary.get("execution_revision")
        if stored_revision in (None, execution_revision):
            return model
    return None


def _promoted_model_runtime_dir(model):
    model_path = Path(model.path)
    return model_path if model_path.is_dir() else model_path.parent


def _runtime_model_record_for_path(normalized_path):
    return (
        Model.objects.filter(path=normalized_path)
        .order_by("-is_active", "-created_at", "-pk")
        .first()
    )


def _persist_runtime_model_record(
    *,
    model_path,
    operator,
    name,
    version,
    model_type,
    metrics,
    artifact_summary,
    is_best_candidate,
):
    normalized_path = _normalize_model_path(model_path)
    defaults = {
        "name": name,
        "version": version,
        "model_type": model_type,
        "metrics": metrics,
        "artifact_summary": artifact_summary,
        "registered_by": operator,
        "is_best_candidate": is_best_candidate,
        "is_runtime_compatible": True,
        "source_run": None,
    }

    try:
        with transaction.atomic():
            return Model.objects.create(path=normalized_path, **defaults)
    except IntegrityError:
        existing_model = _runtime_model_record_for_path(normalized_path)
        if existing_model is None:
            raise

        update_fields = []
        for field, value in defaults.items():
            if getattr(existing_model, field) != value:
                setattr(existing_model, field, value)
                update_fields.append(field)
        if update_fields:
            existing_model.save(update_fields=update_fields)
        return existing_model


def persist_runtime_model_payload(
    *, runtime_payload, operator, validate_artifacts=True
):
    model_path = Path(runtime_payload["path"])
    if not model_path.exists():
        raise ValueError("当前运行时模型目录不存在")
    if validate_artifacts and not runtime_artifacts_complete(model_path):
        raise ValueError("当前运行时模型文件不完整")

    normalized_path = _normalize_model_path(model_path)
    baseline_path = _normalize_model_path(settings.MODEL_PATH)
    if normalized_path == baseline_path:
        return _persist_runtime_model_record(
            model_path=model_path,
            operator=operator,
            name=model_path.name or "bert",
            version="runtime-baseline",
            model_type="transformer",
            metrics={"runtime_ready": True},
            artifact_summary={
                "source": "runtime_baseline",
                "normalized_path": normalized_path,
            },
            is_best_candidate=True,
        )

    return _persist_runtime_model_record(
        model_path=model_path,
        operator=operator,
        name=runtime_payload.get("name") or model_path.name or "runtime-model",
        version=runtime_payload.get("version") or "runtime",
        model_type=runtime_payload.get("model_type") or "transformer",
        metrics=runtime_payload.get("metrics") or {},
        artifact_summary={
            "source": "runtime_payload",
            "normalized_path": normalized_path,
        },
        is_best_candidate=False,
    )


def register_runtime_baseline_model(*, operator):
    with transaction.atomic():
        model = persist_runtime_model_payload(
            runtime_payload={"path": str(settings.MODEL_PATH)},
            operator=operator,
        )
        model.activate()
        return model


def cleanup_stale_training_run_model_rows():
    stale_rows = (
        Model.objects.filter(source_run__isnull=False)
        .filter(
            Q(path__icontains="\\_training_runs\\")
            | Q(path__icontains="/_training_runs/")
        )
        .order_by("id")
    )
    removed = 0
    for row in stale_rows:
        promoted = (
            Model.objects.filter(source_run=row.source_run, name=row.name)
            .exclude(pk=row.pk)
            .exclude(
                Q(path__icontains="\\_training_runs\\")
                | Q(path__icontains="/_training_runs/")
            )
            .order_by("-created_at")
            .first()
        )
        if promoted:
            row.delete()
            removed += 1
    return removed


def register_training_run_models(*, training_run, operator):
    post_run = (training_run.config_snapshot or {}).get("post_run") or {}
    rows = post_run.get("registry_candidates") or []
    if not rows:
        return []

    created_models = []
    task_is_runtime_compatible = _is_runtime_compatible(training_run.task_type)
    execution_revision = _execution_revision(training_run)
    promoted_dirs = []

    try:
        with transaction.atomic():
            for index, row in enumerate(rows):
                path = row.get("path")
                if not path:
                    continue
                source_path = Path(path)
                destination_dir = _model_run_dir(training_run, row)
                final_path = (
                    destination_dir
                    if source_path.is_dir()
                    else destination_dir / source_path.name
                )
                normalized_path = _normalize_model_path(final_path)
                existing_model = _existing_promoted_model(
                    training_run=training_run,
                    normalized_path=normalized_path,
                    execution_revision=execution_revision,
                )
                if existing_model:
                    if task_is_runtime_compatible and not runtime_artifacts_complete(
                        _promoted_model_runtime_dir(existing_model)
                    ):
                        raise ValueError("运行时模型文件不完整")
                    created_models.append(existing_model)
                    continue

                promoted_row = _promote_candidate_artifacts(
                    training_run=training_run, row=row
                )
                promoted_dirs.append(Path(promoted_row["artifact_dir"]))
                promoted_path = Path(promoted_row["path"])
                runtime_compatible = False
                if task_is_runtime_compatible:
                    runtime_dir = (
                        promoted_path
                        if promoted_path.is_dir()
                        else promoted_path.parent
                    )
                    if not runtime_artifacts_complete(runtime_dir):
                        raise ValueError("运行时模型文件不完整")
                    runtime_compatible = True
                normalized_path = _normalize_model_path(promoted_row["path"])
                promoted_row["path"] = normalized_path
                promoted_row["runtime_type"] = runtime_artifact_type(normalized_path)

                model, _created = Model.objects.update_or_create(
                    source_run=training_run,
                    path=normalized_path,
                    defaults={
                        "name": promoted_row.get("name") or training_run.name,
                        "version": _build_version(training_run, promoted_row, index),
                        "model_type": training_run.task_type,
                        "metrics": promoted_row.get("metrics")
                        or training_run.metrics_snapshot
                        or {},
                        "is_active": False,
                        "artifact_summary": promoted_row,
                        "registered_by": operator,
                        "is_best_candidate": index == 0,
                        "is_runtime_compatible": runtime_compatible,
                    },
                )
                created_models.append(model)
    except Exception:
        _cleanup_promoted_dirs(promoted_dirs)
        raise

    return created_models


__all__ = [
    "cleanup_stale_training_run_model_rows",
    "persist_runtime_model_payload",
    "register_runtime_baseline_model",
    "register_training_run_models",
    "is_effectively_runtime_compatible",
    "runtime_artifact_type",
    "runtime_artifacts_complete",
]
