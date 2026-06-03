from apps.admin_panel.infra.runtime_registry.registry import (
    cleanup_stale_training_run_model_rows as _cleanup_stale_training_run_model_rows,
    persist_runtime_model_payload as _persist_runtime_model_payload,
    register_runtime_baseline_model as _register_runtime_baseline_model,
    register_training_run_models as _register_training_run_models,
)


def persist_runtime_model_payload(
    *, runtime_payload, operator, validate_artifacts=True
):
    return _persist_runtime_model_payload(
        runtime_payload=runtime_payload,
        operator=operator,
        validate_artifacts=validate_artifacts,
    )


def register_runtime_baseline_model(*, operator):
    return _register_runtime_baseline_model(operator=operator)


def cleanup_stale_training_run_model_rows():
    return _cleanup_stale_training_run_model_rows()


def register_training_run_models(*, training_run, operator):
    return _register_training_run_models(training_run=training_run, operator=operator)


__all__ = [
    "cleanup_stale_training_run_model_rows",
    "persist_runtime_model_payload",
    "register_runtime_baseline_model",
    "register_training_run_models",
]
