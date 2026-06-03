from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from apps.users.models import User


class Comment(models.Model):
    """
    评论记录表
    """

    content = models.TextField("评论内容")
    project_name = models.CharField(
        "项目名称", max_length=100, blank=True, default="", db_index=True
    )
    score = models.DecimalField(
        "评分", max_digits=3, decimal_places=1, blank=True, null=True
    )
    comment_time = models.DateTimeField("评论时间", blank=True, null=True)
    category = models.CharField("商品/服务类别", max_length=100, blank=True, null=True)
    source = models.CharField("数据来源", max_length=100, blank=True, null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "comments"
        verbose_name = "评论"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["comment_time"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.content[:50] if self.content else f"Comment {self.id}"


class AnalysisResult(models.Model):
    """
    情感分析结果表
    """

    SENTIMENT_CHOICES = (
        (1, "积极"),
        (0, "中性"),
        (-1, "消极"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="analysis_results",
        verbose_name="用户",
        db_index=False,
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="analysis_results",
        verbose_name="评论",
    )
    sentiment = models.SmallIntegerField("情感类别", choices=SENTIMENT_CHOICES)
    confidence = models.DecimalField("置信度", max_digits=5, decimal_places=4)
    keywords = models.JSONField("关键情感词", blank=True, null=True)
    analyst_note = models.TextField("分析备注", blank=True, null=True)
    is_priority = models.BooleanField("是否重点关注", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "analysis_results"
        verbose_name = "分析结果"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user_id", "created_at"], name="analysis_user_created"
            ),
            models.Index(fields=["sentiment"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.comment.content[:20]} - {self.get_sentiment_display()}"


class Model(models.Model):
    """
    模型信息表
    """

    name = models.CharField("模型名称", max_length=100)
    version = models.CharField("版本号", max_length=50)
    model_type = models.CharField("模型类型", max_length=50)
    metrics = models.JSONField("性能指标", blank=True, null=True)
    path = models.CharField("模型文件路径", max_length=255, unique=True)
    is_active = models.BooleanField("是否启用", default=False)
    source_run = models.ForeignKey(
        "admin_panel.TrainingRun",
        on_delete=models.SET_NULL,
        related_name="registered_models",
        verbose_name="来源训练任务",
        blank=True,
        null=True,
    )
    registered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="registered_models",
        verbose_name="登记人",
        blank=True,
        null=True,
    )
    activated_at = models.DateTimeField("激活时间", blank=True, null=True)
    is_best_candidate = models.BooleanField("是否最佳候选", default=False)
    is_runtime_compatible = models.BooleanField("是否兼容运行时", default=True)
    artifact_summary = models.JSONField("产物摘要", blank=True, null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "models"
        verbose_name = "模型"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} v{self.version}"

    def activate(self):
        """激活当前模型，同时停用其他模型"""
        from apps.admin_panel.infra.runtime_registry.registry import (
            runtime_artifacts_complete,
        )

        with transaction.atomic():
            # Acquire the model-table locks in a deterministic order so concurrent
            # activations serialize cleanly instead of deadlocking on lock upgrades.
            list(
                Model.objects.select_for_update()
                .filter(Q(is_active=True) | Q(pk=self.pk))
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            locked_model = Model.objects.get(pk=self.pk)
            if not runtime_artifacts_complete(locked_model.path):
                raise ValueError("当前运行时模型文件不完整")

            Model.objects.filter(is_active=True).exclude(pk=locked_model.pk).update(
                is_active=False
            )

            locked_model.is_active = True
            locked_model.activated_at = timezone.now()
            locked_model.save(update_fields=["is_active", "activated_at"])

            self.is_active = locked_model.is_active
            self.activated_at = locked_model.activated_at

    @classmethod
    def get_active_model(cls):
        """获取当前激活的模型"""
        return cls.objects.filter(is_active=True).first()
