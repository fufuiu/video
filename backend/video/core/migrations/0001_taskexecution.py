import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('videos', '0015_add_taken_down_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskExecution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_id', models.CharField(max_length=255, unique=True, verbose_name='任务 ID')),
                ('task_name', models.CharField(db_index=True, max_length=255, verbose_name='任务名称')),
                ('request_id', models.CharField(blank=True, db_index=True, max_length=100, verbose_name='请求 ID')),
                ('status', models.CharField(choices=[('pending', '等待中'), ('processing', '处理中'), ('retrying', '重试中'), ('succeeded', '已完成'), ('failed', '已失败'), ('cancelled', '已取消')], db_index=True, default='pending', max_length=20, verbose_name='任务状态')),
                ('celery_state', models.CharField(default='PENDING', max_length=30, verbose_name='Celery 状态')),
                ('progress', models.JSONField(blank=True, default=dict, verbose_name='进度信息')),
                ('parameters', models.JSONField(blank=True, default=dict, verbose_name='安全重试参数')),
                ('result_summary', models.JSONField(blank=True, default=dict, verbose_name='结果摘要')),
                ('error_code', models.CharField(blank=True, max_length=100, verbose_name='错误码')),
                ('error_message', models.CharField(blank=True, max_length=500, verbose_name='安全错误提示')),
                ('retry_count', models.PositiveIntegerField(default=0, verbose_name='重试次数')),
                ('retryable', models.BooleanField(default=False, verbose_name='允许重试')),
                ('retry_dispatched_at', models.DateTimeField(blank=True, null=True, verbose_name='重试派发时间')),
                ('queued_at', models.DateTimeField(auto_now_add=True, verbose_name='入队时间')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='开始时间')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='结束时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('retry_of', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='retry_attempts', to='core.taskexecution', verbose_name='重试来源')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_executions', to=settings.AUTH_USER_MODEL, verbose_name='发起用户')),
                ('video', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_executions', to='videos.video', verbose_name='视频')),
            ],
            options={
                'verbose_name': '异步任务记录',
                'verbose_name_plural': '异步任务记录',
                'ordering': ['-queued_at'],
            },
        ),
        migrations.AddIndex(
            model_name='taskexecution',
            index=models.Index(fields=['status', '-queued_at'], name='task_status_queued_idx'),
        ),
        migrations.AddIndex(
            model_name='taskexecution',
            index=models.Index(fields=['video', '-queued_at'], name='task_video_queued_idx'),
        ),
        migrations.AddIndex(
            model_name='taskexecution',
            index=models.Index(fields=['user', '-queued_at'], name='task_user_queued_idx'),
        ),
    ]
