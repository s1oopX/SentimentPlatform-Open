from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysisresult",
            name="analysis_channel",
            field=models.CharField(
                choices=[("single", "单条分析"), ("batch", "批量分析")],
                db_index=True,
                default="single",
                max_length=20,
                verbose_name="分析渠道",
            ),
        ),
        migrations.AddField(
            model_name="analysisresult",
            name="analysis_session_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="分析会话ID",
            ),
        ),
        migrations.AddField(
            model_name="analysisresult",
            name="analysis_source_name",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="分析来源名称",
            ),
        ),
    ]
