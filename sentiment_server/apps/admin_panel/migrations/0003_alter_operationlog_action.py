from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="operationlog",
            name="action",
            field=models.CharField(
                choices=[
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
                ],
                max_length=50,
                verbose_name="操作类型",
            ),
        ),
    ]
