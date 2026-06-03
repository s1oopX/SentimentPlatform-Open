from apps.admin_panel.models import OperationLog


def write_report_export_log(*, user, report_type, report_id, request_ip):
    return OperationLog.objects.create(
        user=user,
        action="export_report",
        detail=f"提交报告任务：{report_type} (report_id={report_id})",
        ip=request_ip,
    )


def write_report_download_log(*, report, user, request_ip):
    return OperationLog.objects.create(
        user=user,
        action="download_file",
        detail=f"下载报告：{report.id}",
        ip=request_ip,
    )
