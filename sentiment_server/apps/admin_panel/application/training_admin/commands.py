import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.admin_panel.application.errors import TrainingApplicationError
from apps.admin_panel.domain.rules.training_admin import (
    build_candidate_models,
    build_pending_enqueue_state,
    build_queued_state,
    build_retry_reset_state,
    get_training_run_delete_state,
    get_training_run_action_state as build_training_run_action_state,
    validate_candidate_models_for_task as validate_training_candidate_models_for_task,
)
from apps.admin_panel.infra.training.selectors import (
    resolve_runtime_activation_candidate,
)
from apps.admin_panel.infra.training.tasks import (
    retry_training_post_run_task,
    run_training_task,
)
from apps.admin_panel.models import OperationLog, TrainingRun
from apps.admin_panel.training_constants import (
    TASK_TYPE_NEURAL_BASELINE_TRAIN,
    WORKSPACE_DATASET_SOURCE,
)
from apps.analysis.models import Model
from apps.admin_panel.infra.runtime_registry.registry import runtime_artifacts_complete

logger = logging.getLogger(__name__)

TrainingServiceError = TrainingApplicationError


POST_RUN_RETRY_CLAIM_KEYS = (
    "retry_claimed_at",
    "retry_claimed_by",
    "retry_claimed_task_id",
)


def _ensure_relative_to(path, root):
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise TrainingServiceError("dataset_ref 超出允许的数据集目录") from exc


def resolve_dataset_ref(*, dataset_source, dataset_ref, split_strategy="pre_split"):
    if dataset_source != WORKSPACE_DATASET_SOURCE:
        raise TrainingServiceError("当前仅支持 workspace_dataset 类型的数据集来源")

    datasets_root = Path(
        getattr(settings, "TRAINING_DATASETS_ROOT", settings.MODEL_WORKSPACE_DIR)
    ).resolve()
    dataset_dir = (datasets_root / dataset_ref).resolve()
    _ensure_relative_to(dataset_dir, datasets_root)

    if split_strategy == "auto_split":
        if not dataset_dir.exists():
            raise TrainingServiceError("dataset_ref 指向的原始数据集目录不存在")
        return {
            "datasets_root": str(datasets_root),
            "dataset_dir": str(dataset_dir),
            "raw_dataset_path": str(dataset_dir),
            "train_dataset_path": "",
            "eval_dataset_path": "",
            "test_dataset_path": "",
        }

    train_dir = dataset_dir / "train"
    eval_dir = dataset_dir / "eval"
    test_dir = dataset_dir / "test"

    if not train_dir.exists():
        raise TrainingServiceError("dataset_ref 缺少 train 子目录")
    if eval_dir.exists():
        resolved_eval_dir = eval_dir
        resolved_test_dir = test_dir if test_dir.exists() else None
    elif test_dir.exists():
        resolved_eval_dir = test_dir
        resolved_test_dir = test_dir
    else:
        raise TrainingServiceError("dataset_ref 缺少 eval 或 test 子目录")

    return {
        "datasets_root": str(datasets_root),
        "dataset_dir": str(dataset_dir),
        "train_dataset_path": str(train_dir),
        "eval_dataset_path": str(resolved_eval_dir),
        "test_dataset_path": str(resolved_test_dir) if resolved_test_dir else "",
    }


def _build_output_dir(training_run):
    return (
        Path(settings.MODEL_WORKSPACE_DIR)
        / "models"
        / "_training_runs"
        / f"run-{training_run.id}"
        / f"attempt-{training_run.execution_revision}"
    )


def _build_log_path(training_run):
    return _build_output_dir(training_run) / "run.log"


def _build_candidate_models(validated_data):
    return build_candidate_models(validated_data.get("candidate_models") or [])


def _build_config_snapshot(*, training_run, validated_data, resolved_dataset_paths):
    output_dir = _build_output_dir(training_run)
    log_path = _build_log_path(training_run)
    task_type = validated_data["task_type"]
    return {
        "request": {
            "task_type": task_type,
            "dataset_source": validated_data["dataset_source"],
            "dataset_ref": validated_data["dataset_ref"],
            "model_family": validated_data.get("model_family") or "",
            "candidate_models": _build_candidate_models(validated_data),
            "search_type": validated_data.get("search_type") or "",
            "split_strategy": validated_data.get("split_strategy") or "pre_split",
            "target_macro_f1": validated_data.get("target_macro_f1", 0.85),
            "max_length": validated_data.get("max_length", 256),
            "use_gpu": bool(validated_data.get("use_gpu", False))
            if task_type == TASK_TYPE_NEURAL_BASELINE_TRAIN
            else False,
            "max_trials": validated_data.get("max_trials", 8),
            "cv_folds": validated_data.get("cv_folds", 3),
        },
        "resolved_paths": {
            **resolved_dataset_paths,
            "output_dir": str(output_dir),
            "log_path": str(log_path),
        },
    }


def _refresh_execution_paths(*, training_run, resolved_dataset_paths=None):
    config_snapshot = dict(training_run.config_snapshot or {})
    resolved_paths = dict(config_snapshot.get("resolved_paths") or {})
    if resolved_dataset_paths:
        resolved_paths.update(resolved_dataset_paths)
    resolved_paths["output_dir"] = str(_build_output_dir(training_run))
    resolved_paths["log_path"] = str(_build_log_path(training_run))
    config_snapshot["resolved_paths"] = resolved_paths
    training_run.config_snapshot = config_snapshot
    training_run.log_path = resolved_paths["log_path"]


def _reset_post_run_retry_claim(config_snapshot):
    snapshot = dict(config_snapshot or {})
    post_run = dict(snapshot.get("post_run") or {})
    for key in POST_RUN_RETRY_CLAIM_KEYS:
        post_run.pop(key, None)
    snapshot["post_run"] = post_run
    return snapshot


def _enqueue_training_run(training_run_id, execution_revision):
    run_training_task.delay(training_run_id, execution_revision)


def _enqueue_post_run_retry(training_run_id, execution_revision):
    retry_training_post_run_task.delay(training_run_id, execution_revision)


def _write_training_operation_log(
    *, operator, detail, client_ip=None, action="model_train"
):
    if not operator:
        return
    try:
        OperationLog.objects.create(
            user=operator,
            action=action,
            detail=detail,
            ip=client_ip,
        )
    except Exception:
        logger.warning("Failed to write training operation log", exc_info=True)


def _write_training_deletion_log(*, operator, training_run_snapshot, reason, client_ip=None):
    detail = (
        f"删除训练任务 run-{training_run_snapshot['id']} {training_run_snapshot['name']} "
        f"({training_run_snapshot['task_type']}/{training_run_snapshot['status']})，理由: {reason}"
    )
    _write_training_operation_log(
        operator=operator,
        detail=detail,
        client_ip=client_ip,
        action="delete_training",
    )


def _snapshot_training_run_state(training_run):
    return {
        "status": training_run.status,
        "execution_revision": training_run.execution_revision,
        "error_message": training_run.error_message,
        "post_run_status": training_run.post_run_status,
        "post_run_message": training_run.post_run_message,
        "post_run_warnings": list(training_run.post_run_warnings or []),
        "started_at": training_run.started_at,
        "completed_at": training_run.completed_at,
        "metrics_snapshot": dict(training_run.metrics_snapshot or {}),
        "artifact_paths": dict(training_run.artifact_paths or {}),
        "config_snapshot": dict(training_run.config_snapshot or {}),
        "log_path": training_run.log_path,
    }


def _update_training_run_state_if_matches(
    *, training_run_id, expected_state, next_state
):
    with transaction.atomic():
        locked_run = TrainingRun.objects.select_for_update().get(pk=training_run_id)
        if _snapshot_training_run_state(locked_run) != expected_state:
            return False

        for field, value in next_state.items():
            setattr(locked_run, field, value)
        locked_run.save(update_fields=list(next_state.keys()))
        return True


def _restore_training_run_state(
    *, training_run_id, previous_state, expected_intermediate_state
):
    return _update_training_run_state_if_matches(
        training_run_id=training_run_id,
        expected_state=expected_intermediate_state,
        next_state=previous_state,
    )


def create_training_run(
    *,
    validated_data,
    operator,
    client_ip=None,
    resolve_dataset_ref_fn=None,
    enqueue_training_run_fn=None,
    write_operation_log_fn=None,
):
    resolve_dataset_ref_fn = resolve_dataset_ref_fn or resolve_dataset_ref
    enqueue_training_run_fn = enqueue_training_run_fn or _enqueue_training_run
    write_operation_log_fn = write_operation_log_fn or _write_training_operation_log
    resolved_dataset_paths = resolve_dataset_ref_fn(
        dataset_source=validated_data["dataset_source"],
        dataset_ref=validated_data["dataset_ref"],
        split_strategy=validated_data.get("split_strategy") or "pre_split",
    )

    with transaction.atomic():
        training_run = TrainingRun.objects.create(
            name=validated_data["name"],
            task_type=validated_data["task_type"],
            status="failed",
            dataset_source=validated_data["dataset_source"],
            dataset_ref=validated_data["dataset_ref"],
            model_family=validated_data.get("model_family") or "",
            candidate_models=_build_candidate_models(validated_data),
            search_type=validated_data.get("search_type") or "",
            split_strategy=validated_data.get("split_strategy") or "pre_split",
            created_by=operator,
        )
        training_run.config_snapshot = _build_config_snapshot(
            training_run=training_run,
            validated_data=validated_data,
            resolved_dataset_paths=resolved_dataset_paths,
        )
        training_run.log_path = training_run.config_snapshot["resolved_paths"][
            "log_path"
        ]
        pending_enqueue_state = build_pending_enqueue_state()
        training_run.error_message = pending_enqueue_state["error_message"]
        training_run.post_run_status = pending_enqueue_state["post_run_status"]
        training_run.post_run_message = pending_enqueue_state["post_run_message"]
        training_run.post_run_warnings = pending_enqueue_state["post_run_warnings"]
        training_run.save(
            update_fields=[
                "config_snapshot",
                "log_path",
                "error_message",
                "post_run_status",
                "post_run_message",
                "post_run_warnings",
            ]
        )
        pending_enqueue_snapshot = _snapshot_training_run_state(training_run)

    try:
        enqueue_training_run_fn(training_run.id, training_run.execution_revision)
    except Exception as exc:
        _update_training_run_state_if_matches(
            training_run_id=training_run.id,
            expected_state=pending_enqueue_snapshot,
            next_state=build_pending_enqueue_state(f"训练任务提交失败: {exc}"),
        )
        raise TrainingServiceError("训练任务提交失败，请稍后重试") from exc

    _update_training_run_state_if_matches(
        training_run_id=training_run.id,
        expected_state=pending_enqueue_snapshot,
        next_state=build_queued_state(),
    )
    training_run.refresh_from_db()
    write_operation_log_fn(
        operator=operator,
        client_ip=client_ip,
        detail=f"创建训练任务 run-{training_run.id} {training_run.name} ({training_run.task_type})",
    )
    return training_run


def get_training_run_action_state(
    *, training_run, resolve_runtime_activation_candidate_fn=None
):
    resolve_runtime_activation_candidate_fn = (
        resolve_runtime_activation_candidate_fn or resolve_runtime_activation_candidate
    )
    return build_training_run_action_state(
        status=training_run.status,
        task_type=training_run.task_type,
        post_run_status=training_run.post_run_status,
        has_activation_candidate=(
            resolve_runtime_activation_candidate_fn(training_run=training_run)
            is not None
        ),
    )


def retry_training_run(
    *,
    training_run,
    operator=None,
    client_ip=None,
    enqueue_training_run_fn=None,
    write_operation_log_fn=None,
):
    enqueue_training_run_fn = enqueue_training_run_fn or _enqueue_training_run
    write_operation_log_fn = write_operation_log_fn or _write_training_operation_log
    with transaction.atomic():
        locked_run = TrainingRun.objects.select_for_update().get(pk=training_run.pk)
        action_state = get_training_run_action_state(training_run=locked_run)
        if not action_state["can_retry"]:
            raise TrainingServiceError(action_state["retry_denied_reason"])

        previous_state = _snapshot_training_run_state(locked_run)
        next_state = build_retry_reset_state(
            execution_revision=locked_run.execution_revision + 1
        )
        locked_run.execution_revision = next_state["execution_revision"]
        locked_run.status = next_state["status"]
        locked_run.error_message = next_state["error_message"]
        locked_run.post_run_status = next_state["post_run_status"]
        locked_run.post_run_message = next_state["post_run_message"]
        locked_run.post_run_warnings = next_state["post_run_warnings"]
        locked_run.started_at = next_state["started_at"]
        locked_run.completed_at = next_state["completed_at"]
        locked_run.metrics_snapshot = next_state["metrics_snapshot"]
        locked_run.artifact_paths = next_state["artifact_paths"]
        _refresh_execution_paths(training_run=locked_run)
        locked_run.save(
            update_fields=[
                "status",
                "error_message",
                "post_run_status",
                "post_run_message",
                "post_run_warnings",
                "started_at",
                "completed_at",
                "metrics_snapshot",
                "artifact_paths",
                "config_snapshot",
                "log_path",
            ]
        )
        pending_enqueue_state = _snapshot_training_run_state(locked_run)

    try:
        enqueue_training_run_fn(locked_run.id, locked_run.execution_revision)
    except Exception as exc:
        _restore_training_run_state(
            training_run_id=locked_run.id,
            previous_state=previous_state,
            expected_intermediate_state=pending_enqueue_state,
        )
        raise TrainingServiceError("训练任务重新加入队列失败，请稍后重试") from exc

    _update_training_run_state_if_matches(
        training_run_id=locked_run.id,
        expected_state=pending_enqueue_state,
        next_state=build_queued_state(),
    )
    retried_run = TrainingRun.objects.get(pk=locked_run.id)
    write_operation_log_fn(
        operator=operator or retried_run.created_by,
        client_ip=client_ip,
        detail=f"重试训练任务 run-{retried_run.id} rev-{retried_run.execution_revision}",
    )
    return retried_run


def retry_training_post_run(
    *,
    training_run,
    operator=None,
    client_ip=None,
    enqueue_post_run_fn=None,
    write_operation_log_fn=None,
):
    enqueue_post_run_fn = enqueue_post_run_fn or _enqueue_post_run_retry
    write_operation_log_fn = write_operation_log_fn or _write_training_operation_log
    with transaction.atomic():
        locked_run = TrainingRun.objects.select_for_update().get(pk=training_run.pk)
        action_state = get_training_run_action_state(training_run=locked_run)
        if not action_state["can_retry_post_run"]:
            raise TrainingServiceError(action_state["retry_post_run_denied_reason"])

        previous_state = _snapshot_training_run_state(locked_run)
        locked_run.config_snapshot = _reset_post_run_retry_claim(
            locked_run.config_snapshot
        )
        locked_run.post_run_status = "pending"
        locked_run.post_run_message = ""
        locked_run.post_run_warnings = []
        locked_run.save(
            update_fields=[
                "config_snapshot",
                "post_run_status",
                "post_run_message",
                "post_run_warnings",
            ]
        )
        pending_enqueue_state = _snapshot_training_run_state(locked_run)

    try:
        enqueue_post_run_fn(locked_run.id, locked_run.execution_revision)
    except Exception as exc:
        _restore_training_run_state(
            training_run_id=locked_run.id,
            previous_state=previous_state,
            expected_intermediate_state=pending_enqueue_state,
        )
        raise TrainingServiceError("训练后处理重新加入队列失败，请稍后重试") from exc

    _update_training_run_state_if_matches(
        training_run_id=locked_run.id,
        expected_state=pending_enqueue_state,
        next_state={
            "post_run_status": "pending",
            "post_run_message": "",
            "post_run_warnings": [],
        },
    )
    retried_run = TrainingRun.objects.get(pk=locked_run.id)
    write_operation_log_fn(
        operator=operator or retried_run.created_by,
        client_ip=client_ip,
        detail=f"重试训练后处理 run-{retried_run.id} rev-{retried_run.execution_revision}",
    )
    return retried_run


def activate_registered_model_for_run(*, training_run, operator=None, client_ip=None):
    with transaction.atomic():
        locked_run = TrainingRun.objects.select_for_update().get(pk=training_run.pk)
        action_state = get_training_run_action_state(training_run=locked_run)
        if not action_state["can_activate_model"]:
            raise TrainingServiceError(action_state["activate_denied_reason"])

        model = resolve_runtime_activation_candidate(training_run=locked_run)
        if not model:
            raise TrainingServiceError("当前训练任务没有可激活的运行时兼容模型")

        locked_model = Model.objects.get(pk=model.pk)
        if not runtime_artifacts_complete(locked_model.path):
            raise TrainingServiceError("当前运行时模型文件不完整")
        if not locked_model.is_runtime_compatible:
            locked_model.is_runtime_compatible = True
            locked_model.save(update_fields=["is_runtime_compatible"])

        try:
            locked_model.activate()
        except ValueError as exc:
            raise TrainingServiceError(str(exc)) from exc

    _write_training_operation_log(
        operator=operator or locked_run.created_by,
        client_ip=client_ip,
        action="model_switch",
        detail=f"激活训练产出模型 run-{locked_run.id} {locked_model.name} v{locked_model.version}",
    )
    return locked_model


def delete_training_run(*, training_run, operator=None, reason="", client_ip=None):
    with transaction.atomic():
        locked_run = TrainingRun.objects.select_for_update().filter(pk=training_run.pk).first()
        if not locked_run:
            raise TrainingServiceError("训练记录不存在")

        delete_state = get_training_run_delete_state(
            status=locked_run.status,
            name=locked_run.name,
        )
        if not delete_state["can_delete"]:
            raise TrainingServiceError(delete_state["delete_denied_reason"])

        training_run_snapshot = {
            "id": locked_run.id,
            "name": locked_run.name,
            "task_type": locked_run.task_type,
            "status": locked_run.status,
        }
        locked_run.delete()

    _write_training_deletion_log(
        operator=operator,
        training_run_snapshot=training_run_snapshot,
        reason=reason,
        client_ip=client_ip,
    )
    return training_run_snapshot


def validate_candidate_models_for_task(task_type, candidate_models):
    validate_training_candidate_models_for_task(
        task_type,
        candidate_models,
        error_cls=TrainingServiceError,
    )
