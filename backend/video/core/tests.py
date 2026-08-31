from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


class HealthEndpointTests(SimpleTestCase):
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

# Create your tests here.
