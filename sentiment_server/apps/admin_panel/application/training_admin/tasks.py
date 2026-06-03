import logging
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from apps.admin_panel.models import TrainingRun
from apps.admin_panel.training_constants import TRAINING_PENDING_ENQUEUE_ERROR


STALE_RUNNING_TIMEOUT = timedelta(hours=1)
STALE_RUNNING_ERROR = "训练任务执行超时或 worker 异常退出"
logger = logging.getLogger(__name__)


def build_post_run_state(result):
    warnings = list(result.get("post_run_warnings") or [])
    message = (result.get("post_run_message") or "").strip()
    status = (
        "warning"
        if (warnings or message or not result.get("artifacts_complete", True))
        else "succeeded"
    )
    if status == "warning" and not message:
        message = "训练完成，但后处理不完整"
    return status, message, warnings


def coerce_post_run_result(
    *, training_run, execution_result, finalize_training_run_post_run_fn
):
    if "metrics_snapshot" in execution_result:
        return execution_result
    return finalize_training_run_post_run_fn(training_run, execution_result)


def build_retry_post_run_execution_result(training_run):
    resolved_paths = (
        training_run.config_snapshot.get("resolved_paths")
        if training_run.config_snapshot
        else {}
    )
    log_path_value = (
        training_run.log_path or (resolved_paths or {}).get("log_path") or ""
    )
    log_path = Path(log_path_value) if log_path_value else None
    return {
        "output_dir": (resolved_paths or {}).get("output_dir")
        or (training_run.artifact_paths or {}).get("output_dir"),
        "log_path": str(log_path) if log_path else log_path_value,
        "preserve_existing_log": True,
    }


def finalize_training_run_success(
    *,
    training_run_id,
    expected_revision,
    result,
    register_training_run_models_fn,
    now_fn=None,
):
    now_fn = now_fn or timezone.now
    post_run_status, post_run_message, post_run_warnings = build_post_run_state(result)
    with transaction.atomic():
        locked_run = TrainingRun.objects.select_for_update().get(pk=training_run_id)
        if locked_run.execution_revision != expected_revision:
            return {"training_run_id": locked_run.id, "status": locked_run.status}

        locked_run.metrics_snapshot = result.get("metrics_snapshot") or {}
        locked_run.artifact_paths = result.get("artifact_paths") or {}
        locked_run.log_path = result.get("log_path") or locked_run.log_path
        locked_run.config_snapshot = {
            **(locked_run.config_snapshot or {}),
            "post_run": {
                "artifacts_complete": bool(result.get("artifacts_complete", True)),
                "registry_candidates": result.get("registry_candidates") or [],
                "warnings": list(post_run_warnings),
            },
        }
        try:
            register_training_run_models_fn(
                training_run=locked_run, operator=locked_run.created_by
            )
        except Exception as exc:
            post_run_status = "warning"
            registration_warning = f"模型注册失败: {exc}"
            if registration_warning not in post_run_warnings:
                post_run_warnings.append(registration_warning)
            if post_run_message:
                post_run_message = f"{post_run_message}；{registration_warning}"
            else:
                post_run_message = registration_warning
            locked_run.config_snapshot["post_run"]["warnings"] = list(post_run_warnings)
        locked_run.status = "succeeded"
        locked_run.completed_at = now_fn()
        locked_run.error_message = ""
        locked_run.post_run_status = post_run_status
        locked_run.post_run_message = post_run_message
        locked_run.post_run_warnings = post_run_warnings
        locked_run.save(
            update_fields=[
                "status",
                "completed_at",
                "error_message",
                "post_run_status",
                "post_run_message",
                "post_run_warnings",
                "metrics_snapshot",
                "artifact_paths",
                "log_path",
                "config_snapshot",
            ]
        )
        return {
            "training_run_id": locked_run.id,
            "status": locked_run.status,
            "post_run_status": locked_run.post_run_status,
            "artifact_paths": locked_run.artifact_paths,
        }


def retry_training_post_run_delivery(
    *,
    training_run_id,
    expected_revision,
    finalize_training_run_post_run_fn,
    register_training_run_models_fn,
    now_fn=None,
):
    now_fn = now_fn or timezone.now
    with transaction.atomic():
        training_run = TrainingRun.objects.select_for_update().get(pk=training_run_id)
        if training_run.execution_revision != expected_revision:
            return {"training_run_id": training_run.id, "status": training_run.status}
        if training_run.status != "succeeded":
            return {"training_run_id": training_run.id, "status": training_run.status}
        if training_run.post_run_status != "pending":
            return {"training_run_id": training_run.id, "status": training_run.status}
        post_run_snapshot = dict(
            (training_run.config_snapshot or {}).get("post_run") or {}
        )
        if post_run_snapshot.get("retry_claimed_at"):
            return {"training_run_id": training_run.id, "status": training_run.status}

        post_run_snapshot["retry_claimed_at"] = now_fn().isoformat()
        config_snapshot = dict(training_run.config_snapshot or {})
        config_snapshot["post_run"] = post_run_snapshot
        training_run.config_snapshot = config_snapshot
        training_run.save(update_fields=["config_snapshot"])

    try:
        refreshed_result = finalize_training_run_post_run_fn(
            training_run,
            build_retry_post_run_execution_result(training_run),
        )
        post_run_status, post_run_message, post_run_warnings = build_post_run_state(
            refreshed_result
        )
    except Exception as exc:
        with transaction.atomic():
            locked_run = TrainingRun.objects.select_for_update().get(pk=training_run_id)
            if (
                locked_run.execution_revision != expected_revision
                or locked_run.status != "succeeded"
            ):
                return {"training_run_id": locked_run.id, "status": locked_run.status}
            locked_run.post_run_status = "failed"
            locked_run.post_run_message = str(exc)
            locked_run.post_run_warnings = []
            post_run_snapshot = dict(
                (locked_run.config_snapshot or {}).get("post_run") or {}
            )
            post_run_snapshot.pop("retry_claimed_at", None)
            config_snapshot = dict(locked_run.config_snapshot or {})
            config_snapshot["post_run"] = post_run_snapshot
            locked_run.config_snapshot = config_snapshot
            locked_run.save(
                update_fields=[
                    "post_run_status",
                    "post_run_message",
                    "post_run_warnings",
                    "config_snapshot",
                ]
            )
        return {
            "training_run_id": training_run_id,
            "status": "succeeded",
            "post_run_status": "failed",
        }

    with transaction.atomic():
        locked_run = TrainingRun.objects.select_for_update().get(pk=training_run_id)
        if (
            locked_run.execution_revision != expected_revision
            or locked_run.status != "succeeded"
        ):
            return {"training_run_id": locked_run.id, "status": locked_run.status}

        locked_run.metrics_snapshot = (
            refreshed_result.get("metrics_snapshot") or locked_run.metrics_snapshot
        )
        locked_run.artifact_paths = (
            refreshed_result.get("artifact_paths") or locked_run.artifact_paths
        )
        locked_run.log_path = refreshed_result.get("log_path") or locked_run.log_path
        locked_run.config_snapshot = {
            **(locked_run.config_snapshot or {}),
            "post_run": {
                "artifacts_complete": bool(
                    refreshed_result.get("artifacts_complete", True)
                ),
                "registry_candidates": refreshed_result.get("registry_candidates")
                or [],
                "warnings": list(post_run_warnings),
            },
        }
        try:
            register_training_run_models_fn(
                training_run=locked_run, operator=locked_run.created_by
            )
        except Exception as exc:
            post_run_status = "warning"
            warning = f"模型注册失败: {exc}"
            post_run_warnings = list(post_run_warnings or [])
            if warning not in post_run_warnings:
                post_run_warnings.append(warning)
            post_run_message = (
                warning if not post_run_message else f"{post_run_message}；{warning}"
            )
            locked_run.config_snapshot["post_run"]["warnings"] = list(post_run_warnings)

        locked_run.post_run_status = post_run_status
        locked_run.post_run_message = post_run_message
        locked_run.post_run_warnings = post_run_warnings
        post_run_snapshot = dict(
            (locked_run.config_snapshot or {}).get("post_run") or {}
        )
        post_run_snapshot.pop("retry_claimed_at", None)
        locked_run.config_snapshot["post_run"] = post_run_snapshot
        locked_run.save(
            update_fields=[
                "metrics_snapshot",
                "artifact_paths",
                "log_path",
                "config_snapshot",
                "post_run_status",
                "post_run_message",
                "post_run_warnings",
            ]
        )
        return {
            "training_run_id": locked_run.id,
            "status": locked_run.status,
            "post_run_status": locked_run.post_run_status,
        }


def cleanup_stale_running_training_runs(
    *, now_fn=None, stale_timeout=STALE_RUNNING_TIMEOUT, stale_error=STALE_RUNNING_ERROR
):
    now_fn = now_fn or timezone.now
    stale_deadline = now_fn() - stale_timeout
    cleaned = 0
    stale_run_ids = list(
        TrainingRun.objects.filter(
            status="running",
            started_at__lt=stale_deadline,
        ).values_list("pk", flat=True)
    )
    for training_run_id in stale_run_ids:
        with transaction.atomic():
            locked_run = (
                TrainingRun.objects.select_for_update()
                .filter(pk=training_run_id)
                .first()
            )
            if locked_run is None:
                continue
            if locked_run.status != "running":
                continue
            if not locked_run.started_at or locked_run.started_at >= stale_deadline:
                continue

            locked_run.status = "failed"
            locked_run.completed_at = now_fn()
            locked_run.error_message = stale_error
            locked_run.post_run_status = "failed"
            locked_run.post_run_message = stale_error
            locked_run.post_run_warnings = []
            locked_run.execution_revision += 1
            locked_run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "post_run_status",
                    "post_run_message",
                    "post_run_warnings",
                    "config_snapshot",
                ]
            )
            cleaned += 1
    return cleaned


def run_training_task_delivery(
    *,
    training_run_id,
    expected_revision,
    execute_training_run_fn,
    finalize_training_run_post_run_fn,
    register_training_run_models_fn,
    training_execution_error_cls=None,
    logger_=None,
    now_fn=None,
):
    now_fn = now_fn or timezone.now
    logger_ = logger_ or logger
    with transaction.atomic():
        training_run = TrainingRun.objects.select_for_update().get(pk=training_run_id)
        if training_run.execution_revision != expected_revision:
            return {"training_run_id": training_run.id, "status": training_run.status}
        can_start = training_run.status == "queued" or (
            training_run.status == "failed"
            and training_run.error_message == TRAINING_PENDING_ENQUEUE_ERROR
        )
        if not can_start:
            return {"training_run_id": training_run.id, "status": training_run.status}

        training_run.status = "running"
        training_run.started_at = now_fn()
        training_run.error_message = ""
        training_run.post_run_status = "pending"
        training_run.post_run_message = ""
        training_run.post_run_warnings = []
        training_run.save(
            update_fields=[
                "status",
                "started_at",
                "error_message",
                "post_run_status",
                "post_run_message",
                "post_run_warnings",
            ]
        )

    try:
        execution_result = execute_training_run_fn(training_run)
        result = coerce_post_run_result(
            training_run=training_run,
            execution_result=execution_result,
            finalize_training_run_post_run_fn=finalize_training_run_post_run_fn,
        )
        return finalize_training_run_success(
            training_run_id=training_run_id,
            expected_revision=expected_revision,
            result=result,
            register_training_run_models_fn=register_training_run_models_fn,
            now_fn=now_fn,
        )
    except Exception as exc:
        failure_result = None
        post_run_cleanup_error = None
        with transaction.atomic():
            locked_run = TrainingRun.objects.select_for_update().get(pk=training_run_id)
            if locked_run.execution_revision != expected_revision:
                return {"training_run_id": locked_run.id, "status": locked_run.status}

            if training_execution_error_cls and isinstance(
                exc, training_execution_error_cls
            ):
                try:
                    failure_result = finalize_training_run_post_run_fn(
                        locked_run, exc.execution_result
                    )
                except Exception as post_run_exc:
                    post_run_cleanup_error = post_run_exc
                    logger_.exception(
                        "训练失败后的后处理清理失败: training_run_id=%s primary_error=%s",
                        training_run_id,
                        exc,
                    )
                else:
                    locked_run.log_path = (
                        failure_result.get("log_path") or locked_run.log_path
                    )
                    locked_run.artifact_paths = (
                        failure_result.get("artifact_paths")
                        or locked_run.artifact_paths
                    )

            locked_run.status = "failed"
            locked_run.completed_at = now_fn()
            locked_run.error_message = str(exc)
            locked_run.post_run_status = "failed"
            locked_run.post_run_message = str(exc)
            locked_run.post_run_warnings = (
                [f"训练失败后处理清理失败: {post_run_cleanup_error}"]
                if post_run_cleanup_error is not None
                else []
            )
            locked_run.save(
                update_fields=[
                    "status",
                    "completed_at",
                    "error_message",
                    "post_run_status",
                    "post_run_message",
                    "post_run_warnings",
                    "log_path",
                    "artifact_paths",
                ]
            )
        raise
