from django.utils import timezone

from apps.admin_panel.infra.automation.auto_retrain import (
    queue_auto_retrain_check_best_effort,
)
from apps.analysis.infra.audit_logs import write_operation_log


def update_analyst_comment(*, result, validated_data, user, client_ip=None):
    update_fields = []
    for field, value in validated_data.items():
        setattr(result, field, value)
        update_fields.append(field)
    if update_fields:
        result.reviewed_by = user
        result.reviewed_at = timezone.now()
        update_fields.extend(["reviewed_by", "reviewed_at"])
        result.save(update_fields=update_fields)

    write_operation_log(
        user=user,
        action="other",
        detail=f"更新分析师审核结果：{result.id}",
        ip=client_ip,
    )
    queue_auto_retrain_check_best_effort()
    return result


def delete_analyst_comment(*, result, user, client_ip=None):
    result_id = result.id
    result.delete()

    write_operation_log(
        user=user,
        action="other",
        detail=f"删除分析结果：{result_id}",
        ip=client_ip,
    )
