"""自动数据集沉淀与重训触发。

规则：
1. 只统计尚未进入自动训练数据集的有效标注结果。
2. 高置信度结果自动视为有效标注；低置信度结果需分析师审核后才进入池子。
3. 每凑满阈值（默认 5000）条，保存为一个 HuggingFace Dataset。
4. 用这一个批次的数据集创建训练任务；真实训练由训练队列异步执行。
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from apps.admin_panel.infra.automation.system_config import get_system_config_value
from apps.admin_panel.models import OperationLog, TrainingRun
from apps.admin_panel.training_constants import (
    TASK_TYPE_CLASSICAL_COMPARE,
    TASK_TYPE_NEURAL_BASELINE_TRAIN,
    TASK_TYPE_TRANSFORMER_SEARCH,
    TASK_TYPE_TRANSFORMER_TRAIN,
    WORKSPACE_DATASET_SOURCE,
)
from apps.analysis.domain.review_rules import REVIEW_CONFIDENCE_THRESHOLD
from apps.analysis.models import AnalysisResult
from apps.users.models import User

logger = logging.getLogger(__name__)

AUTO_RETRAIN_LOG_ACTION = "model_train"
AUTO_RETRAIN_DETAIL_TAG = "[AUTO_RETRAIN_DATASET]"
AUTO_RETRAIN_SIGNAL_TAG = "[AUTO_RETRAIN_SIGNAL]"
AUTO_RETRAIN_ERROR_TAG = "[AUTO_RETRAIN_ERROR]"
AUTO_DATASET_ROOT_REF = "auto_retrain"
SENTIMENT_TO_DATASET_LABEL = {-1: 0, 0: 1, 1: 2}


def get_auto_retrain_settings():
    enabled = bool(get_system_config_value("auto_retrain_enabled", True))
    mode = str(get_system_config_value("auto_retrain_mode", "auto") or "auto").lower()
    if mode not in {"auto", "signal"}:
        mode = "auto"
    threshold = max(int(get_system_config_value("auto_retrain_threshold", 5000) or 5000), 1)
    max_batches = max(int(getattr(settings, "AUTO_RETRAIN_MAX_BATCHES_PER_CHECK", 3) or 3), 1)
    return enabled, mode, threshold, max_batches


def _eligible_unbatched_queryset():
    return (
        AnalysisResult.objects.select_related("comment", "user", "reviewed_by")
        .filter(training_dataset_ref="")
        .filter(Q(confidence__gte=REVIEW_CONFIDENCE_THRESHOLD) | Q(reviewed_at__isnull=False))
        .order_by("id")
    )


def _build_dataset_ref(*, first_result_id, last_result_id, now):
    timestamp = timezone.localtime(now).strftime("%Y%m%d_%H%M%S")
    return (
        f"{AUTO_DATASET_ROOT_REF}/batch_{first_result_id}_{last_result_id}_"
        f"{timestamp}_{uuid4().hex[:8]}"
    )


def _resolve_dataset_dir(dataset_ref):
    datasets_root = Path(
        getattr(settings, "TRAINING_DATASETS_ROOT", settings.MODEL_WORKSPACE_DIR)
    ).resolve()
    dataset_dir = (datasets_root / dataset_ref).resolve()
    dataset_dir.relative_to(datasets_root)
    return datasets_root, dataset_dir


def _result_to_dataset_row(result):
    final_sentiment = result.final_sentiment
    return {
        "text": result.comment.content,
        "label": SENTIMENT_TO_DATASET_LABEL[final_sentiment],
    }


def _save_results_as_dataset(*, results, dataset_ref, now):
    try:
        from datasets import Dataset
    except ImportError as exc:
        raise RuntimeError("服务端缺少 datasets 依赖，无法保存训练数据集") from exc

    _datasets_root, dataset_dir = _resolve_dataset_dir(dataset_ref)
    dataset_dir.parent.mkdir(parents=True, exist_ok=True)

    rows = [_result_to_dataset_row(result) for result in results]
    dataset = Dataset.from_dict(
        {
            "text": [row["text"] for row in rows],
            "label": [row["label"] for row in rows],
        }
    )
    dataset.save_to_disk(str(dataset_dir))

    label_counts = Counter(row["label"] for row in rows)
    result_ids = [result.id for result in results]
    metadata = {
        "dataset_ref": dataset_ref,
        "result_count": len(results),
        "result_min_id": min(result_ids),
        "result_max_id": max(result_ids),
        "result_ids": result_ids,
        "label_counts": {str(label): count for label, count in sorted(label_counts.items())},
        "generated_at": now.isoformat(),
        "source": "analysis_results",
    }
    (dataset_dir / "auto_retrain_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def _resolve_training_operator():
    return (
        User.objects.filter(role="admin", status=1).order_by("id").first()
        or User.objects.filter(is_superuser=True, status=1).order_by("id").first()
    )


def _latest_successful_training_run():
    return TrainingRun.objects.filter(status="succeeded").order_by("-created_at").first()


def _default_training_request(*, dataset_ref, result_count, now):
    return {
        "name": f"自动重训 {timezone.localtime(now).strftime('%Y%m%d %H:%M')} ({result_count}条)",
        "task_type": TASK_TYPE_CLASSICAL_COMPARE,
        "dataset_source": WORKSPACE_DATASET_SOURCE,
        "dataset_ref": dataset_ref,
        "model_family": "",
        "candidate_models": ["linear_svm", "logistic_regression"],
        "search_type": "random",
        "split_strategy": "auto_split",
        "target_macro_f1": 0.85,
        "max_length": 256,
        "use_gpu": False,
        "max_trials": 3,
        "cv_folds": 3,
    }


def _training_request_from_latest(*, latest_run, dataset_ref, result_count, now):
    if latest_run is None:
        return _default_training_request(
            dataset_ref=dataset_ref, result_count=result_count, now=now
        )

    prev_request = (latest_run.config_snapshot or {}).get("request", {}) or {}
    task_type = latest_run.task_type
    request = _default_training_request(
        dataset_ref=dataset_ref, result_count=result_count, now=now
    )
    request.update(
        {
            "task_type": task_type,
            "model_family": latest_run.model_family or prev_request.get("model_family") or "",
            "candidate_models": list(
                latest_run.candidate_models or prev_request.get("candidate_models") or []
            ),
            "search_type": latest_run.search_type or prev_request.get("search_type") or "",
            "target_macro_f1": prev_request.get("target_macro_f1", 0.85),
            "max_length": prev_request.get("max_length", 256),
            "use_gpu": bool(prev_request.get("use_gpu", False)),
            "max_trials": prev_request.get("max_trials", 8),
            "cv_folds": prev_request.get("cv_folds", 3),
        }
    )

    if task_type == TASK_TYPE_CLASSICAL_COMPARE:
        request["model_family"] = ""
        request["candidate_models"] = request["candidate_models"] or [
            "linear_svm",
            "logistic_regression",
        ]
        request["search_type"] = request["search_type"] or "random"
        request["use_gpu"] = False
    elif task_type == TASK_TYPE_NEURAL_BASELINE_TRAIN:
        request["model_family"] = ""
        request["candidate_models"] = request["candidate_models"] or ["textcnn"]
        request["search_type"] = ""
    elif task_type == TASK_TYPE_TRANSFORMER_TRAIN:
        request["model_family"] = request["model_family"] or "bert"
        request["candidate_models"] = []
        request["search_type"] = ""
        request["use_gpu"] = False
    elif task_type == TASK_TYPE_TRANSFORMER_SEARCH:
        request["model_family"] = request["model_family"] or "bert"
        request["candidate_models"] = []
        request["search_type"] = request["search_type"] or "random"
        request["use_gpu"] = False
    else:
        request = _default_training_request(
            dataset_ref=dataset_ref, result_count=result_count, now=now
        )

    request["split_strategy"] = "auto_split"
    request["name"] = request["name"][:120]
    return request


def _attach_auto_retrain_metadata(training_run, metadata):
    snapshot = dict(training_run.config_snapshot or {})
    snapshot["auto_retrain"] = dict(metadata)
    training_run.config_snapshot = snapshot
    training_run.save(update_fields=["config_snapshot"])


def _mark_results_as_batched(*, results, dataset_ref, now):
    result_ids = [result.id for result in results]
    return AnalysisResult.objects.filter(
        id__in=result_ids,
        training_dataset_ref="",
    ).update(
        training_dataset_ref=dataset_ref,
        training_dataset_at=now,
    )


def _write_dataset_log(*, metadata, training_run):
    detail = (
        f"{AUTO_RETRAIN_DETAIL_TAG} dataset_ref={metadata['dataset_ref']} "
        f"result_count={metadata['result_count']} "
        f"result_min_id={metadata['result_min_id']} "
        f"result_max_id={metadata['result_max_id']} "
        f"training_run=run-{training_run.id}"
    )
    OperationLog.objects.create(
        user=training_run.created_by,
        action=AUTO_RETRAIN_LOG_ACTION,
        detail=detail,
        ip=None,
    )


def _write_signal_log(*, pending_count, threshold):
    detail = (
        f"{AUTO_RETRAIN_SIGNAL_TAG} 自动检测到 {pending_count} 条可训练标注"
        f"（阈值 {threshold}），当前配置为 signal，仅记录提醒"
    )
    OperationLog.objects.create(
        user=None,
        action=AUTO_RETRAIN_LOG_ACTION,
        detail=detail,
        ip=None,
    )


def _write_error_log(message):
    OperationLog.objects.create(
        user=None,
        action=AUTO_RETRAIN_LOG_ACTION,
        detail=f"{AUTO_RETRAIN_ERROR_TAG} {message}",
        ip=None,
    )


def _create_training_for_dataset(*, dataset_ref, result_count, now, operator, create_training_run_fn):
    validated_data = _training_request_from_latest(
        latest_run=_latest_successful_training_run(),
        dataset_ref=dataset_ref,
        result_count=result_count,
        now=now,
    )
    return create_training_run_fn(validated_data=validated_data, operator=operator)


def _process_one_auto_retrain_batch(
    *,
    threshold,
    mode,
    save_dataset_fn,
    create_training_run_fn,
    resolve_operator_fn,
    now,
):
    pending_queryset = _eligible_unbatched_queryset()
    pending_count = pending_queryset.count()
    if pending_count < threshold:
        return {
            "status": "below_threshold",
            "count": pending_count,
            "threshold": threshold,
        }

    if mode == "signal":
        _write_signal_log(pending_count=pending_count, threshold=threshold)
        return {
            "status": "signaled",
            "count": pending_count,
            "threshold": threshold,
        }

    operator = resolve_operator_fn()
    if operator is None:
        _write_error_log("自动重训失败：没有可用的管理员账号作为训练任务创建者")
        return {
            "status": "missing_operator",
            "count": pending_count,
            "threshold": threshold,
        }

    results = list(pending_queryset[:threshold])
    dataset_ref = _build_dataset_ref(
        first_result_id=results[0].id,
        last_result_id=results[-1].id,
        now=now,
    )
    metadata = save_dataset_fn(results=results, dataset_ref=dataset_ref, now=now)
    training_run = _create_training_for_dataset(
        dataset_ref=dataset_ref,
        result_count=len(results),
        now=now,
        operator=operator,
        create_training_run_fn=create_training_run_fn,
    )
    _attach_auto_retrain_metadata(training_run, metadata)
    marked_count = _mark_results_as_batched(
        results=results,
        dataset_ref=dataset_ref,
        now=now,
    )
    _write_dataset_log(metadata=metadata, training_run=training_run)
    logger.info(
        "auto-retrain dataset saved and training submitted: dataset_ref=%s run_id=%s marked=%s",
        dataset_ref,
        training_run.id,
        marked_count,
    )
    return {
        "status": "submitted",
        "training_run_id": training_run.id,
        "dataset_ref": dataset_ref,
        "count": len(results),
        "marked_count": marked_count,
        "threshold": threshold,
    }


def check_auto_retrain_threshold(
    *,
    save_dataset_fn=None,
    create_training_run_fn=None,
    resolve_operator_fn=None,
    now_fn=None,
):
    """被 Celery Beat 调用：按阈值批量生成数据集并提交训练任务。"""
    enabled, mode, threshold, max_batches = get_auto_retrain_settings()
    if not enabled:
        return {"status": "disabled"}

    from apps.admin_panel.training_services import create_training_run

    save_dataset_fn = save_dataset_fn or _save_results_as_dataset
    create_training_run_fn = create_training_run_fn or create_training_run
    resolve_operator_fn = resolve_operator_fn or _resolve_training_operator
    now_fn = now_fn or timezone.now

    submitted_batches = []
    last_result = None
    for _index in range(max_batches):
        now = now_fn()
        try:
            result = _process_one_auto_retrain_batch(
                threshold=threshold,
                mode=mode,
                save_dataset_fn=save_dataset_fn,
                create_training_run_fn=create_training_run_fn,
                resolve_operator_fn=resolve_operator_fn,
                now=now,
            )
        except Exception as exc:
            logger.exception("auto-retrain batch processing failed")
            _write_error_log(f"自动重训失败：{exc}")
            return {
                "status": "failed",
                "error": str(exc),
                "submitted_batches": submitted_batches,
            }

        last_result = result
        if result["status"] != "submitted":
            break
        submitted_batches.append(result)

    if submitted_batches:
        return {
            "status": "submitted",
            "submitted_batches": submitted_batches,
            "remaining_count": _eligible_unbatched_queryset().count(),
            "threshold": threshold,
        }
    return last_result or {"status": "below_threshold", "count": 0, "threshold": threshold}


def build_auto_retrain_status():
    enabled, mode, threshold, max_batches = get_auto_retrain_settings()
    pending_count = _eligible_unbatched_queryset().count()
    progress_count = min(pending_count, threshold)
    remaining_to_next = max(threshold - progress_count, 0)
    progress_ratio = round(progress_count / threshold, 4) if threshold else 0

    batch_rows = list(
        AnalysisResult.objects.exclude(training_dataset_ref="")
        .values("training_dataset_ref")
        .annotate(
            result_count=Count("id"),
            result_min_id=Min("id"),
            result_max_id=Max("id"),
            generated_at=Max("training_dataset_at"),
        )
        .order_by("-generated_at")[:5]
    )
    dataset_refs = [row["training_dataset_ref"] for row in batch_rows]
    training_runs = {
        run.dataset_ref: run
        for run in TrainingRun.objects.filter(dataset_ref__in=dataset_refs).order_by("-created_at")
    }
    latest_operation = (
        OperationLog.objects.filter(action=AUTO_RETRAIN_LOG_ACTION)
        .filter(
            Q(detail__startswith=AUTO_RETRAIN_DETAIL_TAG)
            | Q(detail__startswith=AUTO_RETRAIN_SIGNAL_TAG)
            | Q(detail__startswith=AUTO_RETRAIN_ERROR_TAG)
        )
        .order_by("-created_at")
        .first()
    )

    batches = []
    for row in batch_rows:
        training_run = training_runs.get(row["training_dataset_ref"])
        batches.append(
            {
                "dataset_ref": row["training_dataset_ref"],
                "result_count": row["result_count"],
                "result_min_id": row["result_min_id"],
                "result_max_id": row["result_max_id"],
                "generated_at": row["generated_at"],
                "training_run": {
                    "id": training_run.id,
                    "name": training_run.name,
                    "status": training_run.status,
                    "record_id": f"run-{training_run.id}",
                }
                if training_run
                else None,
            }
        )

    return {
        "enabled": enabled,
        "mode": mode,
        "threshold": threshold,
        "max_batches_per_check": max_batches,
        "pending_count": pending_count,
        "progress_count": progress_count,
        "remaining_to_next": remaining_to_next,
        "progress_ratio": progress_ratio,
        "can_trigger_now": enabled and mode == "auto" and pending_count >= threshold,
        "batched_total": AnalysisResult.objects.exclude(training_dataset_ref="").count(),
        "batch_count": (
            AnalysisResult.objects.exclude(training_dataset_ref="")
            .values("training_dataset_ref")
            .distinct()
            .count()
        ),
        "recent_batches": batches,
        "latest_operation": {
            "detail": latest_operation.detail,
            "created_at": latest_operation.created_at,
        }
        if latest_operation
        else None,
    }


def queue_auto_retrain_check_best_effort():
    """提交一次异步阈值检查；失败时只记日志，不影响当前业务写入。"""

    def _enqueue():
        try:
            from apps.admin_panel.infra.training.tasks import (
                check_auto_retrain_threshold_task,
            )

            check_auto_retrain_threshold_task.delay()
        except Exception:
            logger.warning("failed to enqueue auto-retrain threshold check", exc_info=True)

    transaction.on_commit(_enqueue)
