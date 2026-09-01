import logging

from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import TaskExecution
from core.permissions import IsProjectAdmin
from core.serializers import TaskExecutionSerializer
from core.task_lifecycle import retry_task_execution


logger = logging.getLogger(__name__)


class TaskExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """Administrator task history and controlled retry operations."""

    permission_classes = [permissions.IsAuthenticated, IsProjectAdmin]
    serializer_class = TaskExecutionSerializer

    def get_queryset(self):
        queryset = TaskExecution.objects.select_related('video', 'user', 'retry_of')
        task_status = self.request.query_params.get('status')
        task_name = self.request.query_params.get('task_name')
        video_id = self.request.query_params.get('video_id')
        search = self.request.query_params.get('search')

        if task_status:
            queryset = queryset.filter(status=task_status)
        if task_name:
            queryset = queryset.filter(task_name=task_name)
        if video_id:
            queryset = queryset.filter(video_id=video_id)
        if search:
            queryset = queryset.filter(
                Q(task_id__icontains=search)
                | Q(request_id__icontains=search)
                | Q(video__title__icontains=search)
                | Q(user__username__icontains=search)
            )
        return queryset

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        execution = self.get_object()
        try:
            result = retry_task_execution(execution, request=request)
        except ValueError as exc:
            return Response(
                {'error': {'code': 'TASK_RETRY_NOT_ALLOWED', 'message': str(exc)}},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.exception('administrator task retry dispatch failed task_id=%s', execution.task_id)
            return Response(
                {'error': {'code': 'TASK_RETRY_UNAVAILABLE', 'message': '任务重试暂时不可用，请稍后再试'}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                'message': '任务重试已提交',
                'task_id': result.id,
                'retry_of': execution.task_id,
            },
            status=status.HTTP_202_ACCEPTED,
        )
