import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0002_analysis_session_metadata"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="analysisresult",
            name="corrected_sentiment",
            field=models.SmallIntegerField(
                blank=True,
                choices=[(1, "积极"), (0, "中性"), (-1, "消极")],
                db_index=True,
                null=True,
                verbose_name="人工修正情感类别",
            ),
        ),
        migrations.AddField(
            model_name="analysisresult",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="审核时间"),
        ),
        migrations.AddField(
            model_name="analysisresult",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_analysis_results",
                to=settings.AUTH_USER_MODEL,
                verbose_name="审核人",
            ),
        ),
    ]
