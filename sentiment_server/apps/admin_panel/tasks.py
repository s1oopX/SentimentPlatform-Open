import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import OperationalError, InterfaceError
from django.utils import timezone

from apps.admin_panel.infra.audit_logs import create_operation_log_best_effort
from apps.admin_panel.infra.tasks.cleanup import (
    cleanup_expired_verification_codes_task_logic,
)
from apps.admin_panel.models import OperationLog

# Celery autodiscover_tasks() 只会 import <app>.tasks，
# 训练相关 @shared_task 定义在 apps.admin_panel.infra.training.tasks 中。
# 这里显式 import 该模块，确保 worker 启动时训练任务能注册到任务表。
from apps.admin_panel.infra.training import tasks as _training_tasks  # noqa: F401

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.admin_panel.tasks.cleanup_operation_logs_task",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=30,
)
def cleanup_operation_logs_task():
    retention_days = getattr(settings, "OPERATION_LOG_RETENTION_DAYS", 180)
    cutoff = timezone.now() - timedelta(days=int(retention_days))
    deleted_count, _ = OperationLog.objects.filter(created_at__lt=cutoff).delete()
    if deleted_count:
        create_operation_log_best_effort(
            detail=f"自动清理 {deleted_count} 条过期操作日志（保留 {retention_days} 天）",
            logger_instance=logger,
        )
    return {"deleted_count": deleted_count}


@shared_task(
    name="apps.admin_panel.tasks.cleanup_expired_verification_codes_task",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=30,
)
def cleanup_expired_verification_codes_task():
    return cleanup_expired_verification_codes_task_logic()
