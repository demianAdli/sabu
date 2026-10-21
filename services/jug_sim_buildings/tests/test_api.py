"""
Sabu project
jug_sim_buildings package
test_api module
Verify HTTP contracts and request correlation.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import unittest
from unittest.mock import patch

from sabu_chassis.logging.context import get_request_id, set_request_id

from jug_sim_buildings.api import create_app


class TestFoundationAPI(unittest.TestCase):
    def setUp(self):
        logging_patch = patch('jug_sim_buildings.api.configure_service_logging')
        logging_patch.start()
        self.addCleanup(logging_patch.stop)
        original_id = get_request_id()
        self.addCleanup(set_request_id, original_id)
        set_request_id('outer-context')
        self.app = create_app({'TESTING': True, 'API_TITLE': 'Test API'})
        self.client = self.app.test_client()

    def test_health_delegates_to_application_and_is_documented(self):
        result = {'service': 'jug_sim_buildings', 'status': 'ok'}
        with patch('jug_sim_buildings.resources.health.get_health',
                   return_value=result) as health:
            response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, result)
        health.assert_called_once_with()
        spec = self.client.get('/openapi.json')
        self.assertEqual(spec.status_code, 200)
        self.assertEqual(spec.json['info']['title'], 'Test API')
        self.assertIn('get', spec.json['paths']['/health'])
        schema = spec.json['components']['schemas']['HealthResponse']
        self.assertEqual(set(schema['required']), {'service', 'status'})
        self.assertEqual(self.client.get('/swagger-ui').status_code, 200)

    def test_correlation_header_precedence_and_context_restoration(self):
        for headers, expected in (
                ({'X-Request-ID': 'request', 'X-Correlation-ID': 'correlation'},
                 'request'),
                ({'X-Correlation-ID': 'correlation'}, 'correlation'),
                ({'X-Request-ID': '', 'X-Correlation-ID': 'fallback'},
                 'fallback')):
            with self.subTest(headers=headers):
                observed = []

                def health():
                    observed.append(get_request_id())
                    return {'service': 'jug_sim_buildings', 'status': 'ok'}

                with patch('jug_sim_buildings.resources.health.get_health',
                           side_effect=health):
                    response = self.client.get('/health', headers=headers)
                self.assertEqual(response.headers['X-Request-ID'], expected)
                self.assertEqual(observed, [expected])
                self.assertEqual(get_request_id(), 'outer-context')

    def test_generated_ids_do_not_leak_between_requests(self):
        first = self.client.get('/health').headers['X-Request-ID']
        self.assertEqual(get_request_id(), 'outer-context')
        second = self.client.get('/health').headers['X-Request-ID']
        self.assertRegex(first, r'^[0-9a-f]{16}$')
        self.assertRegex(second, r'^[0-9a-f]{16}$')
        self.assertNotEqual(first, second)
        self.assertEqual(get_request_id(), 'outer-context')

    def test_http_errors_preserve_status_and_correlation(self):
        for method, path, status in (
                ('get', '/missing', 404), ('post', '/health', 405)):
            with self.subTest(status=status):
                response = getattr(self.client, method)(
                    path, headers={'X-Request-ID': 'http-error'})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers['X-Request-ID'], 'http-error')
                self.assertEqual(get_request_id(), 'outer-context')

    def test_unexpected_errors_are_logged_without_exposing_details(self):
        with patch('jug_sim_buildings.resources.health.get_health',
                   side_effect=RuntimeError('private failure')):
            with patch('jug_sim_buildings.api.logger') as logger:
                response = self.client.get(
                    '/health', headers={'X-Request-ID': 'failed-request'})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Internal Server Error'})
        self.assertEqual(response.headers['X-Request-ID'], 'failed-request')
        self.assertEqual(get_request_id(), 'outer-context')
        logger.exception.assert_called_once_with('unhandled_exception')
        access = logger.info.call_args.kwargs['extra']
        self.assertEqual(access['status'], 500)
        self.assertEqual(access['method'], 'GET')
        self.assertEqual(access['path'], '/health')
        self.assertGreaterEqual(access['latency_ms'], 0)


if __name__ == '__main__':
    unittest.main()
