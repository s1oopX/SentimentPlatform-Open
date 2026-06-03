import logging

from apps.admin_panel.models import OperationLog

logger = logging.getLogger(__name__)


def create_operation_log(
    *, user, action, detail, ip, operation_log_model=None, logger_instance=None
):
    operation_log_model = operation_log_model or OperationLog
    logger_instance = logger_instance or logger

    try:
        operation_log_model.objects.create(
            user=user,
            action=action,
            detail=detail,
            ip=ip,
        )
    except Exception:
        logger_instance.exception(
            "admin_panel 操作日志写入失败: action=%s user_id=%s",
            action,
            getattr(user, "id", None),
        )


def create_operation_log_best_effort(
    *,
    detail,
    action="other",
    user=None,
    ip=None,
    operation_log_model=None,
    logger_instance=None,
):
    create_operation_log(
        user=user,
        action=action,
        detail=detail,
        ip=ip,
        operation_log_model=operation_log_model,
        logger_instance=logger_instance,
    )
