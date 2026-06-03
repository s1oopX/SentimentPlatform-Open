"""标注数据增量监控：当新增标注数据达到阈值时记录重训信号或自动提交训练。

实现思路：
1. 仅当系统配置 ``auto_retrain_enabled = True`` 时启用。
2. 以最近一次 TrainingRun 创建时间为基准，统计其后新增的、带分析师备注的
   AnalysisResult 条数。
3. 当增量达到 ``auto_retrain_threshold`` 时：
   - ``auto_retrain_mode = "signal"``（默认）：仅写入 OperationLog 提示。
   - ``auto_retrain_mode = "auto"``：自动提交一个训练任务。
4. 同一信号 / 提交 24 小时内只触发一次，避免冗余。
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.admin_panel.infra.automation.system_config import get_system_config_value
from apps.admin_panel.models import OperationLog, TrainingRun
from apps.analysis.models import AnalysisResult

logger = logging.getLogger(__name__)

# 复用现有 model_train 类型，避免引入新的 ACTION_CHOICES 迁移；用 detail 内的固定前缀标识。
AUTO_RETRAIN_LOG_ACTION = "model_train"
AUTO_RETRAIN_DETAIL_TAG = "[AUTO_RETRAIN_SIGNAL]"
AUTO_RETRAIN_SUBMIT_TAG = "[AUTO_RETRAIN_SUBMITTED]"
DEDUP_WINDOW_HOURS = 24


def get_auto_retrain_settings():
    enabled = bool(get_system_config_value("auto_retrain_enabled", False))
    mode = str(get_system_config_value("auto_retrain_mode", "signal") or "signal")
    threshold = int(get_system_config_value("auto_retrain_threshold", 5000) or 5000)
    return enabled, mode, threshold


def _resolve_cutoff_datetime():
    latest = (
        TrainingRun.objects.order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    if latest is not None:
        return latest
    return timezone.make_aware(timezone.datetime(1970, 1, 1))


def _count_new_annotations(cutoff):
    return (
        AnalysisResult.objects.filter(created_at__gt=cutoff)
        .exclude(Q(analyst_note__isnull=True) | Q(analyst_note__exact=""))
        .count()
    )


def _recently_triggered():
    """Check if a signal or auto-submit was already emitted within the dedup window."""
    threshold_time = timezone.now() - timedelta(hours=DEDUP_WINDOW_HOURS)
    return OperationLog.objects.filter(
        action=AUTO_RETRAIN_LOG_ACTION,
        created_at__gte=threshold_time,
    ).filter(
        Q(detail__startswith=AUTO_RETRAIN_DETAIL_TAG)
        | Q(detail__startswith=AUTO_RETRAIN_SUBMIT_TAG)
    ).exists()


def _write_signal_log(annotation_count, threshold):
    detail = (
        f"{AUTO_RETRAIN_DETAIL_TAG} 自动检测到 {annotation_count} 条新增标注"
        f"（阈值 {threshold}），建议管理员触发模型重新训练"
    )
    OperationLog.objects.create(
        user=None,
        action=AUTO_RETRAIN_LOG_ACTION,
        detail=detail,
        ip=None,
    )
    logger.info(
        "auto-retrain signal emitted: count=%s threshold=%s",
        annotation_count,
        threshold,
    )


def _auto_submit_training_run(annotation_count, threshold):
    """Create and enqueue a real training run using the latest successful run's config."""
    from apps.admin_panel.training_services import (
        create_training_run,
    )

    latest_succeeded = (
        TrainingRun.objects.filter(status="succeeded")
        .order_by("-created_at")
        .first()
    )
    if latest_succeeded is None:
        logger.warning("auto-retrain: no succeeded training run to clone config from")
        _write_signal_log(annotation_count, threshold)
        return None

    prev_snapshot = latest_succeeded.config_snapshot or {}
    prev_request = prev_snapshot.get("request", {})

    validated_data = {
        "name": f"自动重训 ({annotation_count} 条新增标注)",
        "task_type": latest_succeeded.task_type,
        "dataset_source": latest_succeeded.dataset_source,
        "dataset_ref": latest_succeeded.dataset_ref,
        "model_family": latest_succeeded.model_family,
        "candidate_models": list(latest_succeeded.candidate_models or []),
        "search_type": latest_succeeded.search_type,
        "split_strategy": latest_succeeded.split_strategy,
        "target_macro_f1": prev_request.get("target_macro_f1", 0.85),
        "max_length": prev_request.get("max_length", 256),
        "use_gpu": prev_request.get("use_gpu", False),
        "max_trials": prev_request.get("max_trials", 8),
        "cv_folds": prev_request.get("cv_folds", 3),
    }

    training_run = create_training_run(
        validated_data=validated_data,
        operator=None,
    )

    detail = (
        f"{AUTO_RETRAIN_SUBMIT_TAG} 自动提交训练任务 run-{training_run.id}"
        f"（{annotation_count} 条新增标注，阈值 {threshold}）"
    )
    OperationLog.objects.create(
        user=None,
        action=AUTO_RETRAIN_LOG_ACTION,
        detail=detail,
        ip=None,
    )
    logger.info(
        "auto-retrain submitted: run_id=%s count=%s threshold=%s",
        training_run.id,
        annotation_count,
        threshold,
    )
    return training_run


def check_auto_retrain_threshold():
    """主入口：被 Celery 任务调用，返回处理结果摘要。"""
    enabled, mode, threshold = get_auto_retrain_settings()
    if not enabled:
        return {"status": "disabled"}

    cutoff = _resolve_cutoff_datetime()
    annotation_count = _count_new_annotations(cutoff)

    if annotation_count < threshold:
        return {
            "status": "below_threshold",
            "count": annotation_count,
            "threshold": threshold,
            "cutoff": cutoff.isoformat(),
        }

    if _recently_triggered():
        return {
            "status": "already_signaled",
            "count": annotation_count,
            "threshold": threshold,
        }

    if mode == "auto":
        try:
            run = _auto_submit_training_run(annotation_count, threshold)
        except Exception:
            logger.exception("auto-retrain submission failed, falling back to signal")
            _write_signal_log(annotation_count, threshold)
            return {
                "status": "signal_fallback",
                "count": annotation_count,
                "threshold": threshold,
            }
        return {
            "status": "submitted",
            "training_run_id": run.id if run else None,
            "count": annotation_count,
            "threshold": threshold,
        }

    _write_signal_log(annotation_count, threshold)
    return {
        "status": "signaled",
        "count": annotation_count,
        "threshold": threshold,
    }
