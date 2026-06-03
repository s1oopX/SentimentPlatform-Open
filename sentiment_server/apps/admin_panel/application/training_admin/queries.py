import logging

from apps.admin_panel.application.errors import TrainingApplicationError
from apps.admin_panel.domain.rules.training_admin import (
    get_training_run_delete_state,
    get_training_run_action_state as build_training_run_action_state,
)
from apps.admin_panel.infra.selectors.training_admin import (
    TRAINING_COMPARISON_LIMIT,
    get_training_dashboard_totals,
    get_training_run_by_id,
    get_training_run_page,
    get_training_workflow_summary,
    list_recent_successful_training_runs,
    list_best_successful_training_runs,
    list_recent_training_runs,
)
from apps.admin_panel.infra.training.artifacts import (
    build_artifact_summaries,
    safe_artifact_value,
)
from apps.admin_panel.infra.runtime_registry.registry import (
    is_effectively_runtime_compatible,
    runtime_artifact_type,
    runtime_artifacts_complete,
)
from apps.admin_panel.infra.training.selectors import (
    build_registered_model_payloads,
    list_training_run_runtime_models,
    read_training_log_preview,
    resolve_runtime_activation_candidate,
    resolve_training_run_log_path,
)

logger = logging.getLogger(__name__)


def _build_training_run_note(training_run):
    if training_run.status == "failed" and training_run.error_message:
        return training_run.error_message
    if (
        training_run.post_run_status in {"warning", "failed"}
        and training_run.post_run_message
    ):
        return training_run.post_run_message
    if training_run.status == "queued":
        return "任务已提交到训练队列，等待 worker 执行。"
    if training_run.status == "running":
        return "任务正在训练 worker 中执行。"
    if training_run.status == "cancelled":
        return "任务已取消，不会继续执行或用于模型激活。"
    return ""


def _build_training_run_action_flags(training_run):
    action_state = build_training_run_action_state(
        status=training_run.status,
        task_type=training_run.task_type,
        post_run_status=training_run.post_run_status,
        has_activation_candidate=resolve_runtime_activation_candidate(
            training_run=training_run
        )
        is not None,
    )
    delete_state = get_training_run_delete_state(
        status=training_run.status,
        name=training_run.name,
    )
    return {
        "can_retry": action_state["can_retry"],
        "can_activate_model": action_state["can_activate_model"],
        "can_delete": delete_state["can_delete"],
    }


def _build_dataset_analysis(training_run):
    config_snapshot = dict(training_run.config_snapshot or {})
    request = dict(config_snapshot.get("request") or {})
    resolved_paths = dict(config_snapshot.get("resolved_paths") or {})
    metrics_snapshot = dict(training_run.metrics_snapshot or {})
    dataset = dict(config_snapshot.get("dataset") or {})
    rows = {
        "train": dataset.get("train_rows") or metrics_snapshot.get("train_rows"),
        "eval": dataset.get("eval_rows") or metrics_snapshot.get("eval_rows"),
        "test": dataset.get("test_rows") or metrics_snapshot.get("test_rows"),
    }
    preprocessing_stats = dict(
        config_snapshot.get("preprocessing_stats")
        or metrics_snapshot.get("preprocessing_stats")
        or {}
    )
    return {
        "dataset_source": training_run.dataset_source,
        "dataset_ref": training_run.dataset_ref,
        "split_strategy": request.get("split_strategy")
        or training_run.split_strategy
        or "pre_split",
        "target_macro_f1": request.get("target_macro_f1", 0.85),
        "paths": {
            key: value
            for key, value in resolved_paths.items()
            if key.endswith("_dataset_path") and value
        },
        "rows": rows,
        "label_distribution": dict(
            config_snapshot.get("label_distribution")
            or metrics_snapshot.get("label_distribution")
            or {}
        ),
        "preprocessing_stats": preprocessing_stats,
        "preprocessing_stats_available": bool(preprocessing_stats),
    }


def _build_model_incompatibility_reason(model, artifact_type, artifact_complete):
    if not is_effectively_runtime_compatible(model):
        if artifact_type == "unsupported":
            return "当前运行时暂不支持该模型产物格式"
        return "该模型记录标记为不兼容在线运行"
    if not artifact_complete:
        return "模型产物缺失或格式不完整"
    return ""


def _build_runtime_compatibility(training_run, action_state):
    registered_models = []
    for model in list_training_run_runtime_models(training_run):
        artifact_type = runtime_artifact_type(model.path)
        artifact_complete = runtime_artifacts_complete(model.path)
        registered_models.append(
            {
                "id": model.id,
                "name": model.name,
                "version": model.version,
                "model_type": model.model_type,
                "runtime_type": artifact_type,
                "artifact_complete": artifact_complete,
                "is_runtime_compatible": is_effectively_runtime_compatible(model),
                "is_active": model.is_active,
                "is_best_candidate": model.is_best_candidate,
                "file_label": safe_artifact_value(model.path),
                "incompatibility_reason": _build_model_incompatibility_reason(
                    model,
                    artifact_type,
                    artifact_complete,
                ),
            }
        )
    return {
        "can_activate_model": action_state["can_activate_model"],
        "activate_denied_reason": action_state["activate_denied_reason"],
        "registered_models": registered_models,
    }


def _build_quality_warnings(training_run, dataset_analysis, runtime_compatibility):
    warnings = []
    metrics_snapshot = dict(training_run.metrics_snapshot or {})
    target_macro_f1 = dataset_analysis["target_macro_f1"]
    macro_f1 = metrics_snapshot.get("macro_f1")
    if training_run.status == "failed" and training_run.error_message:
        warnings.append(training_run.error_message)
    for warning in training_run.post_run_warnings or []:
        if warning:
            warnings.append(str(warning))
    if macro_f1 is not None and target_macro_f1 is not None:
        try:
            if float(macro_f1) < float(target_macro_f1):
                warnings.append(
                    f"Macro-F1 {float(macro_f1):.4f} 低于目标 {float(target_macro_f1):.4f}"
                )
        except (TypeError, ValueError):
            pass
    for model in runtime_compatibility["registered_models"]:
        reason = model.get("incompatibility_reason")
        if reason:
            warnings.append(f"{model['name']}: {reason}")
    return list(dict.fromkeys(warnings))


def _training_run_record_id(training_run):
    return f"run-{training_run.id}"


def _normalize_training_run_record(training_run):
    return {
        "record_id": _training_run_record_id(training_run),
        "title": training_run.name,
        "source_type": "training_run",
        "workflow_type": training_run.task_type,
        "execution_mode": training_run.execution_mode,
        "status": training_run.status,
        "post_run_status": training_run.post_run_status,
        "post_run_message": training_run.post_run_message,
        "post_run_warnings": list(training_run.post_run_warnings or []),
        "execution_revision": training_run.execution_revision,
        "metric_highlights": dict(training_run.metrics_snapshot or {}),
        "artifact_summaries": build_artifact_summaries(
            training_run.artifact_paths or {}
        ),
        "has_log": bool(training_run.log_path),
        "log_filename": safe_artifact_value(training_run.log_path),
        "created_at": training_run.created_at.isoformat()
        if training_run.created_at
        else None,
        "note": _build_training_run_note(training_run),
        **_build_training_run_action_flags(training_run),
    }


def _build_training_run_detail(training_run):
    detail = _normalize_training_run_record(training_run)
    metrics_snapshot = dict(training_run.metrics_snapshot or {})
    action_state = build_training_run_action_state(
        status=training_run.status,
        task_type=training_run.task_type,
        post_run_status=training_run.post_run_status,
        has_activation_candidate=resolve_runtime_activation_candidate(
            training_run=training_run
        )
        is not None,
    )
    dataset_analysis = _build_dataset_analysis(training_run)
    runtime_compatibility = _build_runtime_compatibility(
        training_run,
        action_state,
    )
    return {
        **detail,
        "result_summary": {
            "workflow_type": training_run.task_type,
            "completed_at": training_run.completed_at.isoformat()
            if training_run.completed_at
            else None,
            "core_metrics": metrics_snapshot,
        },
        "leaderboard_preview": list(metrics_snapshot.get("leaderboard_preview", [])),
        "leaderboard_preview_count": len(
            metrics_snapshot.get("leaderboard_preview", [])
        ),
        "leaderboard_total_count": len(metrics_snapshot.get("leaderboard_preview", [])),
        "best_run_overview": metrics_snapshot.get("best_run_overview"),
        "confusion_matrix": metrics_snapshot.get("confusion_matrix"),
        "label_order": metrics_snapshot.get("label_order"),
        "loss_curve": metrics_snapshot.get("loss_curve", []),
        "error_message": training_run.error_message,
        "post_run_status": training_run.post_run_status,
        "post_run_message": training_run.post_run_message,
        "post_run_warnings": list(training_run.post_run_warnings or []),
        "dataset_source": training_run.dataset_source,
        "dataset_ref": training_run.dataset_ref,
        "has_log": bool(training_run.log_path),
        "log_filename": safe_artifact_value(training_run.log_path),
        "registered_models": build_registered_model_payloads(training_run),
        "dataset_analysis": dataset_analysis,
        "runtime_compatibility": runtime_compatibility,
        "quality_warnings": _build_quality_warnings(
            training_run,
            dataset_analysis,
            runtime_compatibility,
        ),
        "can_retry_post_run": action_state["can_retry_post_run"],
        "retry_post_run_denied_reason": action_state["retry_post_run_denied_reason"],
    }


def list_training_records(page=1, page_size=20):
    safe_page = max(int(page or 1), 1)
    safe_page_size = max(int(page_size or 20), 1)
    total_records, runs = get_training_run_page(
        page=safe_page, page_size=safe_page_size
    )
    items = [_normalize_training_run_record(run) for run in runs]
    return {
        "page": safe_page,
        "page_size": safe_page_size,
        "total_records": total_records,
        "returned_records": len(items),
        "items": items,
    }


def build_training_dashboard_payload():
    recent_runs = list_recent_training_runs()
    best_runs = list_best_successful_training_runs()
    workflow_summary = get_training_workflow_summary()
    return {
        "totals": get_training_dashboard_totals(),
        "workflow_summary": {
            "group_by": "task_type",
            "groups": [
                {
                    "group_value": item["task_type"],
                    "count": item["count"],
                }
                for item in workflow_summary
            ],
        },
        "recent_records": [_normalize_training_run_record(run) for run in recent_runs],
        "best_records": [_normalize_training_run_record(run) for run in best_runs],
    }


def build_training_comparison_payload():
    rows = []
    for run in list_recent_successful_training_runs(limit=TRAINING_COMPARISON_LIMIT):
        metrics = dict(run.metrics_snapshot or {})
        rows.append(
            {
                "record_id": _training_run_record_id(run),
                "subject_name": run.name,
                "source_type": "training_run",
                "execution_mode": run.execution_mode,
                "status": run.status,
                "macro_f1": metrics.get("macro_f1"),
                "accuracy": metrics.get("accuracy"),
                "negative_recall": metrics.get("negative_recall"),
            }
        )

    chart_base64 = ""
    macro_f1_results = {
        row["subject_name"]: row["macro_f1"]
        for row in rows
        if row.get("macro_f1") is not None
    }
    if macro_f1_results and len(macro_f1_results) >= 2:
        try:
            from ml_assets.workspace.evaluation.static_charts import (
                generate_model_comparison_chart,
            )

            chart_base64 = generate_model_comparison_chart(macro_f1_results)
        except Exception:
            logger.exception("训练对比图生成失败")

    return {
        "metric_key": "macro_f1",
        "row_count": len(rows),
        "top_metric_value": max((row.get("macro_f1") or 0 for row in rows), default=0),
        "rows": rows,
        "chart_base64": chart_base64,
    }


def get_training_record_detail(record_id):
    record_key = str(record_id or "")
    if not record_key.startswith("run-") or not record_key[4:].isdigit():
        return None
    training_run = get_training_run_by_id(int(record_key[4:]))
    return _build_training_run_detail(training_run) if training_run else None


def build_training_log_preview_payload(
    *,
    run_id,
    max_bytes=None,
    resolve_training_run_log_path_fn=None,
    read_training_log_preview_fn=None,
):
    resolve_training_run_log_path_fn = (
        resolve_training_run_log_path_fn or resolve_training_run_log_path
    )
    read_training_log_preview_fn = (
        read_training_log_preview_fn or read_training_log_preview
    )
    training_run = get_training_run_by_id(run_id)
    if not training_run:
        raise TrainingApplicationError("训练记录不存在", status_code=404)

    resolved_path = resolve_training_run_log_path_fn(training_run)
    if resolved_path is None:
        raise TrainingApplicationError("当前任务暂无日志文件", status_code=404)

    log_text, size_bytes, truncated = read_training_log_preview_fn(
        resolved_path,
        max_bytes=max_bytes,
    )
    return {
        "record_id": _training_run_record_id(training_run),
        "status": training_run.status,
        "post_run_status": training_run.post_run_status,
        "filename": resolved_path.name,
        "size_bytes": size_bytes,
        "truncated": truncated,
        "log_text": log_text,
    }


def build_training_log_download_metadata(
    *, run_id, resolve_training_run_log_path_fn=None
):
    resolve_training_run_log_path_fn = (
        resolve_training_run_log_path_fn or resolve_training_run_log_path
    )
    training_run = get_training_run_by_id(run_id)
    if not training_run:
        raise TrainingApplicationError("训练记录不存在", status_code=404)

    resolved_path = resolve_training_run_log_path_fn(training_run)
    if resolved_path is None:
        raise TrainingApplicationError("当前任务暂无日志文件", status_code=404)

    return {
        "path": resolved_path,
        "download_filename": f"训练日志_{training_run.id}.log",
        "content_type": "text/plain; charset=utf-8",
    }
