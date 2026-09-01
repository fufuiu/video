from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from core.errors import APIErrorResponseMiddleware, api_exception_handler
from core.task_lifecycle import (
    canonical_task_status,
    enqueue_task,
    report_task_progress,
    serialize_task_result,
)


class HealthEndpointTests(SimpleTestCase):
    def test_exception_handler_returns_stable_validation_error(self):
        request = APIRequestFactory().post('/api/videos/', {})
        request.request_id = 'req-test-validation'

        response = api_exception_handler(
            ValidationError({'title': ['此字段是必填项。']}),
            {'request': request},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
        self.assertEqual(response.data['error']['fields']['title'], ['此字段是必填项。'])
        self.assertEqual(response['X-Request-ID'], 'req-test-validation')

    def test_exception_handler_hides_unexpected_exception_details(self):
        request = APIRequestFactory().get('/api/videos/')
        request.request_id = 'req-test-internal'

        response = api_exception_handler(
            RuntimeError('database password must not leak'),
            {'request': request},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error']['code'], 'INTERNAL_SERVER_ERROR')
        self.assertNotIn('password', response.data['error']['message'])

    def test_request_id_is_returned_and_reused(self):
        response = self.client.get('/api/health/live/', HTTP_X_REQUEST_ID='demo-request-42')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Request-ID'], 'demo-request-42')

    def test_live_endpoint_does_not_require_dependencies(self):
        response = self.client.get('/api/health/live/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    @patch('core.health.cache')
    @patch('core.health.connection')
    def test_ready_endpoint_reports_healthy_dependencies(self, mock_connection, mock_cache):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        mock_connection.cursor.return_value.__enter__.return_value = cursor
        mock_cache._cache.get_client.return_value.ping.return_value = True

        response = self.client.get('/api/health/ready/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'status': 'ok',
            'checks': {
                'database': {'status': 'ok'},
                'cache': {'status': 'ok'},
            },
        })

    @patch('core.health.cache')
    @patch('core.health.connection')
    def test_ready_endpoint_returns_503_when_dependency_fails(self, mock_connection, mock_cache):
        mock_connection.cursor.side_effect = RuntimeError('database unavailable')
        mock_cache._cache.get_client.side_effect = RuntimeError('cache unavailable')

        response = self.client.get('/api/health/ready/')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'not_ready')
        self.assertEqual(response.json()['checks']['database']['error'], 'RuntimeError')
        self.assertEqual(response.json()['checks']['cache']['error'], 'RuntimeError')

    def test_legacy_auth_error_is_normalized(self):
        response = self.client.post('/api/auth/login/', {})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['success'])
        self.assertEqual(payload['error']['code'], 'VALIDATION_ERROR')
        self.assertEqual(payload['error']['message'], '请输入用户名和密码')
        self.assertEqual(payload['error']['request_id'], response['X-Request-ID'])

    def test_legacy_server_error_response_hides_internal_detail(self):
        request = APIRequestFactory().get('/api/videos/')
        request.request_id = 'req-legacy-500'

        def get_response(_request):
            from rest_framework.response import Response

            return Response(
                {'detail': 'database password must not leak'},
                status=500,
            )

        response = APIErrorResponseMiddleware(get_response)(request)

        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'INTERNAL_SERVER_ERROR')
        self.assertNotIn('password', response.data['error']['message'])
        self.assertEqual(response.data['error']['request_id'], 'req-legacy-500')

    def test_legacy_field_errors_are_preserved_in_stable_envelope(self):
        request = APIRequestFactory().post('/api/videos/', {})
        request.request_id = 'req-legacy-fields'

        def get_response(_request):
            from rest_framework.response import Response

            return Response(
                {'title': ['标题不能为空']},
                status=400,
            )

        response = APIErrorResponseMiddleware(get_response)(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
        self.assertEqual(response.data['error']['fields']['title'], ['标题不能为空'])
        self.assertEqual(response['X-Request-ID'], 'req-legacy-fields')

    def test_legacy_control_metadata_is_preserved_without_polluting_fields(self):
        request = APIRequestFactory().post('/api/auth/login/', {})
        request.request_id = 'req-captcha'

        def get_response(_request):
            from rest_framework.response import Response

            return Response(
                {'detail': '请输入验证码', 'show_captcha': True},
                status=400,
            )

        response = APIErrorResponseMiddleware(get_response)(request)

        self.assertEqual(response.data['error']['message'], '请输入验证码')
        self.assertEqual(response.data['error']['fields'], {})
        self.assertEqual(response.data['error']['meta'], {'show_captcha': True})

    def test_task_states_are_mapped_to_stable_product_states(self):
        self.assertEqual(canonical_task_status('PENDING'), 'pending')
        self.assertEqual(canonical_task_status('STARTED'), 'processing')
        self.assertEqual(canonical_task_status('RETRY'), 'retrying')
        self.assertEqual(canonical_task_status('SUCCESS'), 'succeeded')
        self.assertEqual(canonical_task_status('FAILURE'), 'failed')
        self.assertEqual(canonical_task_status('REVOKED'), 'cancelled')

    def test_task_dispatch_carries_request_and_video_context_in_headers(self):
        task = MagicMock()
        request = MagicMock(request_id='req-task-dispatch')

        enqueue_task(task, 42, request=request, target_video_id=42, language='zh')

        task.apply_async.assert_called_once()
        call = task.apply_async.call_args
        self.assertEqual(call.kwargs['args'], (42,))
        self.assertEqual(call.kwargs['kwargs'], {'language': 'zh'})
        self.assertEqual(call.kwargs['headers'], {
            'request_id': 'req-task-dispatch',
            'video_id': '42',
        })

    @patch('core.task_lifecycle.cache')
    def test_task_dispatch_deduplicates_before_publishing(self, mock_cache):
        task = MagicMock()
        mock_cache.get.return_value = 'task-existing'

        result = enqueue_task(task, 42, dedupe_key='video:42:process')

        self.assertEqual(result.id, 'task-existing')
        task.apply_async.assert_not_called()
        mock_cache.add.assert_not_called()

    @patch('core.task_lifecycle.cache')
    def test_first_deduplicated_dispatch_reserves_context_and_task_id(self, mock_cache):
        task = MagicMock()
        task.apply_async.return_value.id = 'task-new'
        mock_cache.get.return_value = None
        mock_cache.add.return_value = True

        result = enqueue_task(task, 42, target_video_id=42, dedupe_key='video:42:process')

        self.assertEqual(result.id, 'task-new')
        task.apply_async.assert_called_once()
        call = task.apply_async.call_args
        self.assertTrue(call.kwargs['task_id'])
        self.assertEqual(call.kwargs['headers']['video_id'], '42')
        self.assertEqual(call.kwargs['headers']['dedupe_key'], 'video:42:process')
        mock_cache.add.assert_called_once_with(
            'celery_task_dedupe:video:42:process',
            call.kwargs['task_id'],
            7200,
        )

    @patch('core.task_lifecycle.cache')
    def test_task_dispatch_reserves_dedupe_key_and_releases_on_publish_failure(self, mock_cache):
        task = MagicMock()
        task.apply_async.side_effect = RuntimeError('broker unavailable')
        mock_cache.get.return_value = None
        mock_cache.add.return_value = True

        with self.assertRaises(RuntimeError):
            enqueue_task(task, 42, dedupe_key='video:42:process')

        mock_cache.add.assert_called_once()
        mock_cache.delete.assert_called_once_with('celery_task_dedupe:video:42:process')

    def test_long_running_task_policies_are_explicit(self):
        from django.conf import settings

        policy = settings.CELERY_TASK_ANNOTATIONS['videos.tasks.process_video']

        self.assertEqual(policy['soft_time_limit'], 7200)
        self.assertEqual(policy['time_limit'], 7500)
        self.assertTrue(policy['acks_late'])
        self.assertTrue(policy['reject_on_worker_lost'])

    def test_task_status_serializer_hides_failure_details(self):
        result = MagicMock(
            id='task-failed',
            name='videos.tasks.process_video',
            state='FAILURE',
            info=RuntimeError('secret path'),
            result=RuntimeError('secret path'),
        )
        result.ready.return_value = True

        payload = serialize_task_result(result, target_video_id=42)

        self.assertEqual(payload['status'], 'failed')
        self.assertEqual(payload['video_id'], 42)
        self.assertEqual(payload['error']['code'], 'TASK_FAILED')
        self.assertNotIn('secret', payload['error']['message'])

    def test_task_progress_is_published_as_safe_metadata(self):
        task = MagicMock()
        task.request.headers = {'request_id': 'req-progress'}
        task.request.id = 'task-progress'

        report_task_progress(task, current=25, total=100, message='正在处理', target_video_id=42)

        task.update_state.assert_called_once_with(
            state='PROGRESS',
            meta={
                'current': 25,
                'total': 100,
                'percent': 25.0,
                'message': '正在处理',
                'video_id': 42,
                'request_id': 'req-progress',
            },
        )
