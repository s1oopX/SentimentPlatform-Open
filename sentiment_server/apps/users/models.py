from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    """自定义用户管理器，以 email 为主键替代 username。"""

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("邮箱不能为空")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # User.save() 用 role/status 覆盖 is_staff/is_active，
        # 默认 role="user" 会把 is_staff 改回 False，导致 superuser 无法登录 /admin/。
        # 这里显式同步 role 与 status，让 save() 的覆盖结果与 superuser 语义一致。
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("status", 1)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    用户模型
    角色：user(普通用户), analyst(分析师), admin(管理员)
    """

    ROLE_CHOICES = (
        ("user", "普通用户"),
        ("analyst", "分析师"),
        ("admin", "管理员"),
    )

    STATUS_CHOICES = (
        (0, "禁用"),
        (1, "启用"),
    )

    # 移除 username 字段，使用邮箱作为登录标识
    username = None
    first_name = None
    last_name = None

    email = models.EmailField("邮箱", unique=True)
    phone = models.CharField("手机号", max_length=20, blank=True, default="")
    nickname = models.CharField(
        "昵称", max_length=50, blank=True, null=True, help_text="用户昵称，用于前端显示"
    )
    role = models.CharField(
        "角色", max_length=20, choices=ROLE_CHOICES, default="user", db_index=True
    )
    status = models.SmallIntegerField("状态", choices=STATUS_CHOICES, default=1)
    avatar = models.ImageField("头像", upload_to="avatars/", blank=True, null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    # 设置邮箱为登录字段
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"
        verbose_name = "用户"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.is_active = self.status == 1

        # Keep is_staff in sync with role so that Django admin access
        # (is_staff) and the application-level admin role stay consistent.
        self.is_staff = self.role == "admin"

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if "status" in update_fields or "is_active" in update_fields:
                update_fields.update({"status", "is_active"})
            if "role" in update_fields or "is_staff" in update_fields:
                update_fields.update({"role", "is_staff"})
            kwargs["update_fields"] = list(update_fields)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class EmailVerificationCode(models.Model):
    """
    邮箱验证码模型
    """

    email = models.EmailField("邮箱")
    code = models.CharField("验证码哈希", max_length=128)
    purpose = models.CharField(
        "用途", max_length=20, default="register"
    )  # register, reset_password
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    delivered_at = models.DateTimeField("投递时间", blank=True, null=True)
    used = models.BooleanField("已使用", default=False)
    failed_attempts = models.PositiveSmallIntegerField("失败尝试次数", default=0)
    last_attempt_at = models.DateTimeField("最后尝试时间", blank=True, null=True)

    class Meta:
        db_table = "email_verification_codes"
        verbose_name = "邮箱验证码"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["email", "purpose", "used"], name="evc_email_purpose_used"
            ),
        ]

    def __str__(self):
        return f"{self.email}: [hashed]"

    def is_valid_code(self):
        """检查验证码是否有效（5 分钟有效期）"""
        from django.utils import timezone
        from datetime import timedelta

        return not self.used and (timezone.now() - self.created_at) < timedelta(
            minutes=5
        )
