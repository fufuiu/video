from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from core.errors import APIErrorResponseMiddleware, api_exception_handler


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
