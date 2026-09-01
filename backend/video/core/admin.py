from django.contrib import admin

from .models import TaskExecution


@admin.register(TaskExecution)
class TaskExecutionAdmin(admin.ModelAdmin):
    list_display = [
        'task_id',
        'task_name',
        'status',
        'video',
        'user',
        'retry_count',
        'queued_at',
    ]
    list_filter = ['status', 'retryable', 'task_name', 'queued_at']
    search_fields = ['task_id', 'request_id', 'task_name', 'video__title', 'user__username']
    readonly_fields = [
        'task_id',
        'task_name',
        'request_id',
        'video',
        'user',
        'retry_of',
        'status',
        'celery_state',
        'progress',
        'parameters',
        'result_summary',
        'error_code',
        'error_message',
        'retry_count',
        'retryable',
        'retry_dispatched_at',
        'queued_at',
        'started_at',
        'finished_at',
        'updated_at',
    ]
