import logging

from apps.admin_panel.models import OperationLog


logger = logging.getLogger(__name__)


def write_operation_log(*, user, action, detail, ip):
    try:
        OperationLog.objects.create(
            user=user,
            action=action,
            detail=detail,
            ip=ip,
        )
    except Exception:
        logger.exception(
            "操作日志写入失败: action=%s user_id=%s", action, getattr(user, "id", None)
        )
