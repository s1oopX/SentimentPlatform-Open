from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0003_analysis_result_review_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysisresult",
            name="training_dataset_ref",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=255,
                verbose_name="自动训练数据集引用",
            ),
        ),
        migrations.AddField(
            model_name="analysisresult",
            name="training_dataset_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="加入自动训练数据集时间"
            ),
        ),
    ]
