from apps.admin_panel.domain.errors import AdminPanelDomainError
from apps.admin_panel.training_constants import (
    CLASSICAL_CANDIDATE_MODELS,
    NEURAL_CANDIDATE_MODELS,
    TASK_TYPE_CLASSICAL_COMPARE,
    TASK_TYPE_NEURAL_BASELINE_TRAIN,
    TASK_TYPE_TRANSFORMER_SEARCH,
    TASK_TYPE_TRANSFORMER_TRAIN,
    TRAINING_PENDING_ENQUEUE_ERROR,
)

RETRYABLE_TRAINING_STATUSES = {"failed", "cancelled"}
RETRYABLE_POST_RUN_STATUSES = {"warning", "failed"}
DELETABLE_TRAINING_STATUSES = {"failed", "cancelled"}
DISPOSABLE_TRAINING_NAME_MARKERS = (
    "[local-demo-training]",
    "演示训练任务",
    "全量测试训练任务",
)
RUNTIME_COMPATIBLE_TASK_TYPES = {
    TASK_TYPE_CLASSICAL_COMPARE,
    TASK_TYPE_NEURAL_BASELINE_TRAIN,
    TASK_TYPE_TRANSFORMER_TRAIN,
    TASK_TYPE_TRANSFORMER_SEARCH,
}


def build_candidate_models(candidate_models):
    return list(dict.fromkeys(list(candidate_models or [])))


def validate_candidate_models_for_task(
    task_type, candidate_models, *, error_cls=AdminPanelDomainError
):
    if task_type == TASK_TYPE_CLASSICAL_COMPARE:
        invalid = [
            model
            for model in candidate_models
            if model not in CLASSICAL_CANDIDATE_MODELS
        ]
    elif task_type == TASK_TYPE_NEURAL_BASELINE_TRAIN:
        invalid = [
            model for model in candidate_models if model not in NEURAL_CANDIDATE_MODELS
        ]
    else:
        invalid = []

    if invalid:
        raise error_cls(
            f"candidate_models 包含不支持的候选项: {', '.join(invalid)}", 400
        )


def is_runtime_compatible_training_task(task_type):
    return task_type in RUNTIME_COMPATIBLE_TASK_TYPES


def is_disposable_training_run_name(name):
    normalized = str(name or "").lower()
    return any(marker.lower() in normalized for marker in DISPOSABLE_TRAINING_NAME_MARKERS)


def get_training_run_delete_state(*, status, name):
    can_delete = status in DELETABLE_TRAINING_STATUSES or is_disposable_training_run_name(name)
    return {
        "can_delete": can_delete,
        "delete_denied_reason": ""
        if can_delete
        else "仅允许删除失败、已取消或演示命名的训练记录",
    }


def build_pending_enqueue_state(error_message=TRAINING_PENDING_ENQUEUE_ERROR):
    return {
        "status": "failed",
        "error_message": error_message,
        "post_run_status": "pending",
        "post_run_message": "",
        "post_run_warnings": [],
    }


def build_queued_state():
    return {
        "status": "queued",
        "error_message": "",
        "post_run_status": "pending",
        "post_run_message": "",
        "post_run_warnings": [],
    }


def build_retry_reset_state(*, execution_revision):
    return {
        **build_pending_enqueue_state(),
        "execution_revision": execution_revision,
        "started_at": None,
        "completed_at": None,
        "metrics_snapshot": {},
        "artifact_paths": {},
    }


def get_training_run_action_state(
    *, status, task_type, post_run_status, has_activation_candidate
):
    retry_denied_reason = (
        "" if status in RETRYABLE_TRAINING_STATUSES else "当前训练任务不允许重试"
    )
    can_retry = not retry_denied_reason
    can_retry_post_run = (
        status == "succeeded" and post_run_status in RETRYABLE_POST_RUN_STATUSES
    )
    retry_post_run_denied_reason = (
        "" if can_retry_post_run else "当前训练任务不允许重试后处理"
    )
    can_activate_model = (
        status == "succeeded"
        and is_runtime_compatible_training_task(task_type)
        and has_activation_candidate
    )
    activate_denied_reason = (
        "" if can_activate_model else "当前训练任务没有可激活的运行时兼容模型"
    )
    return {
        "can_retry": can_retry,
        "can_retry_post_run": can_retry_post_run,
        "can_activate_model": can_activate_model,
        "retry_denied_reason": retry_denied_reason,
        "retry_post_run_denied_reason": retry_post_run_denied_reason,
        "activate_denied_reason": activate_denied_reason,
    }
