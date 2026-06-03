from django.db import models
from apps.users.models import User


class ReportStatus(models.TextChoices):
    PENDING_ENQUEUE = "pending_enqueue", "待入队"
    PENDING = "pending", "生成中"
    PROCESSING = "processing", "处理中"
    COMPLETED = "completed", "已完成"
    FAILED = "failed", "失败"


class Report(models.Model):
    """
    分析报告表
    """

    TYPE_CHOICES = (
        ("single", "单次分析报告"),
        ("batch", "批量分析报告"),
        ("daily", "日报"),
        ("weekly", "周报"),
        ("monthly", "月报"),
    )

    FORMAT_CHOICES = (
        ("pdf", "PDF"),
        ("excel", "Excel"),
        ("csv", "CSV"),
    )

    STATUS_CHOICES = ReportStatus.choices

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reports", verbose_name="用户"
    )
    report_type = models.CharField("报告类型", max_length=20, choices=TYPE_CHOICES)
    report_format = models.CharField(
        "报告格式", max_length=20, choices=FORMAT_CHOICES, default="pdf"
    )
    status = models.CharField(
        "状态",
        max_length=20,
        choices=STATUS_CHOICES,
        default=ReportStatus.PENDING_ENQUEUE,
    )
    file_path = models.CharField("文件路径", max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField("文件大小 (字节)", default=0)
    start_date = models.DateField("开始日期", blank=True, null=True)
    end_date = models.DateField("结束日期", blank=True, null=True)
    request_params = models.JSONField("请求参数", blank=True, null=True)
    summary = models.JSONField("报告摘要", blank=True, null=True)
    enqueue_attempts = models.PositiveIntegerField("入队尝试次数", default=0)
    last_enqueue_attempt_at = models.DateTimeField(
        "最近一次入队尝试时间", null=True, blank=True
    )
    last_enqueue_error = models.TextField("最近一次入队错误", blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    completed_at = models.DateTimeField("完成时间", blank=True, null=True)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    processing_token = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "reports"
        verbose_name = "分析报告"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "created_at"], name="reports_status_created"
            ),
        ]

    def __str__(self):
        return f"Report {self.id} - {self.user.email}"
