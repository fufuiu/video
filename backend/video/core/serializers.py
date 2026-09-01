from rest_framework import serializers

from core.models import TaskExecution


class TaskExecutionSerializer(serializers.ModelSerializer):
    retry_of_task_id = serializers.CharField(source='retry_of.task_id', read_only=True)
    can_retry = serializers.BooleanField(read_only=True)

    class Meta:
        model = TaskExecution
        fields = [
            'id',
            'task_id',
            'task_name',
            'request_id',
            'video_id',
            'user_id',
            'retry_of_task_id',
            'status',
            'celery_state',
            'progress',
            'result_summary',
            'error_code',
            'error_message',
            'retry_count',
            'retryable',
            'can_retry',
            'retry_dispatched_at',
            'queued_at',
            'started_at',
            'finished_at',
            'updated_at',
        ]
        read_only_fields = fields
