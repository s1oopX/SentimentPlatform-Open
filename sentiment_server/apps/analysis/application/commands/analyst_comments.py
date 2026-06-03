from apps.analysis.infra.audit_logs import write_operation_log


def update_analyst_comment(*, result, validated_data, user, client_ip=None):
    update_fields = []
    for field, value in validated_data.items():
        setattr(result, field, value)
        update_fields.append(field)
    if update_fields:
        result.save(update_fields=update_fields)

    write_operation_log(
        user=user,
        action="other",
        detail=f"更新分析备注：{result.id}",
        ip=client_ip,
    )
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
