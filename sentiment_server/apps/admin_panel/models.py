from django.conf import settings
from django.db import models
from apps.users.models import User

from apps.admin_panel.training_constants import (
    DATASET_SOURCE_CHOICES,
    SPLIT_STRATEGY_CHOICES,
    TRAINING_POST_RUN_STATUS_CHOICES,
    TRAINING_STATUS_CHOICES,
    TRAINING_TASK_TYPE_CHOICES,
)


class OperationLog(models.Model):
    """
    操作日志表
    """

    ACTION_CHOICES = (
        ("login", "登录"),
        ("logout", "登出"),
        ("register", "注册"),
        ("change_password", "修改密码"),
        ("reset_password", "重置密码"),
        ("analyze_single", "单条评论分析"),
        ("analyze_batch", "批量评论分析"),
        ("export_report", "导出报告"),
        ("upload_file", "上传文件"),
        ("download_file", "下载文件"),
        ("create_user", "创建用户"),
        ("update_user", "更新用户"),
        ("delete_user", "删除用户"),
        ("model_train", "模型训练"),
        ("delete_training", "删除训练"),
        ("model_switch", "模型切换"),
        ("other", "其他"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="operation_logs",
        verbose_name="用户",
        blank=True,
        null=True,
    )
    action = models.CharField("操作类型", max_length=50, choices=ACTION_CHOICES)
    detail = models.TextField("操作详情", blank=True, null=True)
    ip = models.GenericIPAddressField("IP 地址", blank=True, null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "operation_logs"
        verbose_name = "操作日志"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user_id"]),
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.created_at}"


class TrainingRun(models.Model):
    """
    训练任务记录表
    """

    name = models.CharField(max_length=120)
    task_type = models.CharField(max_length=40, choices=TRAINING_TASK_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=TRAINING_STATUS_CHOICES, default="queued"
    )
    dataset_source = models.CharField(max_length=30, choices=DATASET_SOURCE_CHOICES)
    dataset_ref = models.CharField(max_length=255)
    model_family = models.CharField(max_length=40, blank=True, default="")
    candidate_models = models.JSONField(default=list, blank=True)
    search_type = models.CharField(max_length=20, blank=True, default="")
    split_strategy = models.CharField(
        max_length=20, choices=SPLIT_STRATEGY_CHOICES, default="pre_split"
    )
    config_snapshot = models.JSONField(default=dict, blank=True)
    metrics_snapshot = models.JSONField(default=dict, blank=True)
    artifact_paths = models.JSONField(default=dict, blank=True)
    log_path = models.CharField(max_length=255, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    post_run_status = models.CharField(
        max_length=20,
        choices=TRAINING_POST_RUN_STATUS_CHOICES,
        default="pending",
    )
    post_run_message = models.TextField(blank=True, default="")
    post_run_warnings = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "training_runs"
        verbose_name = "训练任务"
        verbose_name_plural = verbose_name
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["task_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.task_type}/{self.status})"

    @property
    def execution_mode(self):
        """训练执行方式：celery 或 manual"""
        return "manual"

    @property
    def execution_revision(self):
        """训练执行版本号"""
        try:
            value = int((self.config_snapshot or {}).get("execution_revision", 1))
        except (TypeError, ValueError):
            return 1
        return max(value, 1)

    @execution_revision.setter
    def execution_revision(self, value):
        try:
            normalized = max(int(value), 1)
        except (TypeError, ValueError):
            normalized = 1
        snapshot = dict(self.config_snapshot or {})
        snapshot["execution_revision"] = normalized
        self.config_snapshot = snapshot
