from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ai_service', '0003_update_risk_score_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='moderationresult',
            name='result',
            field=models.CharField(
                blank=True,
                choices=[
                    ('safe', '安全'),
                    ('unsafe', '不安全'),
                    ('uncertain', '待人工复核'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='moderationresult',
            name='human_decision',
            field=models.CharField(
                choices=[
                    ('pending', '未人工复核'),
                    ('confirmed_safe', '确认安全'),
                    ('false_positive', '确认误报'),
                    ('confirmed_violation', '确认违规'),
                ],
                db_index=True,
                default='pending',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='moderationresult',
            name='human_review_remark',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='moderationresult',
            name='human_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='moderationresult',
            name='human_reviewer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='human_moderation_reviews',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
