from django.conf import settings
from django.db import models


class TaskExecution(models.Model):
    """Persistent, security-conscious history for asynchronous work."""

    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('processing', '处理中'),
        ('retrying', '重试中'),
        ('succeeded', '已完成'),
        ('failed', '已失败'),
        ('cancelled', '已取消'),
    ]
    RETRYABLE_STATUSES = {'failed', 'cancelled'}

    task_id = models.CharField('任务 ID', max_length=255, unique=True)
    task_name = models.CharField('任务名称', max_length=255, db_index=True)
    request_id = models.CharField('请求 ID', max_length=100, blank=True, db_index=True)
    video = models.ForeignKey(
        'videos.Video',
        verbose_name='视频',
        related_name='task_executions',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='发起用户',
        related_name='task_executions',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    retry_of = models.ForeignKey(
        'self',
        verbose_name='重试来源',
        related_name='retry_attempts',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField('任务状态', max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    celery_state = models.CharField('Celery 状态', max_length=30, default='PENDING')
    progress = models.JSONField('进度信息', default=dict, blank=True)
    parameters = models.JSONField('安全重试参数', default=dict, blank=True)
    result_summary = models.JSONField('结果摘要', default=dict, blank=True)
    error_code = models.CharField('错误码', max_length=100, blank=True)
    error_message = models.CharField('安全错误提示', max_length=500, blank=True)
    retry_count = models.PositiveIntegerField('重试次数', default=0)
    retryable = models.BooleanField('允许重试', default=False)
    retry_dispatched_at = models.DateTimeField('重试派发时间', null=True, blank=True)
    queued_at = models.DateTimeField('入队时间', auto_now_add=True)
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    finished_at = models.DateTimeField('结束时间', null=True, blank=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['-queued_at']
        indexes = [
            models.Index(fields=['status', '-queued_at'], name='task_status_queued_idx'),
            models.Index(fields=['video', '-queued_at'], name='task_video_queued_idx'),
            models.Index(fields=['user', '-queued_at'], name='task_user_queued_idx'),
        ]
        verbose_name = '异步任务记录'
        verbose_name_plural = '异步任务记录'

    @property
    def can_retry(self):
        return (
            self.retryable
            and self.status in self.RETRYABLE_STATUSES
            and self.retry_dispatched_at is None
        )

    def __str__(self):
        return f'{self.task_name} ({self.task_id})'
