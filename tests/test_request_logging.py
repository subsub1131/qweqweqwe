"""Request correlation and metadata-only diagnostics."""
import json
import logging
import unittest
from uuid import UUID, uuid4
from unittest.mock import patch

from tests import test_auth as fixture


class RequestLoggingTests(unittest.TestCase):
    setUp = fixture.AuthTests.setUp
    tearDown = fixture.AuthTests.tearDown

    def test_payment_paths_keep_metadata_without_raw_ids_or_query(self):
        from app.core.request_logging import safe_path
        self.assertEqual(safe_path('/api/payments/webhook?signature=private'), '/api/payments/webhook')
        self.assertEqual(safe_path('/api/payments/confirm?paymentId=private'), '/api/payments/confirm')
        self.assertEqual(safe_path('/api/courses/123?token=private'), '/api/courses/{course_id}')

    def test_response_and_log_share_request_id_without_credentials(self):
        request_id = str(uuid4())
        secret = 'private-password-never-log'
        with self.assertLogs('qwer.http', level='INFO') as logs:
            response = self.client.post('/api/user/login?token=private-query',
                json={'userId': 'private-account', 'userPwd': secret},
                headers={'X-Request-ID': request_id, 'Cookie': 'token=private-cookie',
                         'Authorization': 'Bearer private-bearer'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get('x-request-id'), request_id)
        record = json.loads(logs.records[-1].getMessage())
        self.assertEqual(record['request_id'], request_id)
        self.assertEqual(record['path'], '/api/user/login')
        self.assertEqual(record['method'], 'POST')
        self.assertEqual(record['status'], 401)
        self.assertGreaterEqual(record['duration_ms'], 0)
        for value in (secret, 'private-query', 'private-cookie', 'private-bearer', 'private-account'):
            self.assertNotIn(value, '\n'.join(logs.output))

    def test_untrusted_request_id_and_path_are_not_logged(self):
        with self.assertLogs('qwer.http', level='INFO') as logs:
            response = self.client.get('/private-path-value?code=private-code',
                                       headers={'X-Request-ID': 'private-header'})
        UUID(response.headers['x-request-id'])
        self.assertNotIn('private-', '\n'.join(logs.output))
        self.assertEqual(json.loads(logs.records[-1].getMessage())['path'], '[unmatched]')

    def test_oauth_callback_logs_safe_failure_result_only(self):
        with patch.object(fixture.settings, 'KAKAO_REST_API_KEY', 'test-key'), \
             patch.object(fixture.settings, 'KAKAO_REDIRECT_URI', 'http://localhost:8000/callback'), \
             self.assertLogs('qwer.http', level='INFO') as logs:
            response = self.client.get('/api/auth/kakao/callback?code=private-code&state=private-state',
                                       follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        record = json.loads(logs.records[-1].getMessage())
        self.assertEqual(record['auth_result'], 'invalid_state')
        self.assertNotIn('private-', '\n'.join(logs.output))

    def test_uvicorn_access_filter_drops_raw_url_and_query(self):
        from app.core.request_logging import SafeAccessFilter
        record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s - "%s %s HTTP/%s" %d',
            ('127.0.0.1', 'GET', '/api/auth/kakao/callback?code=private-code&state=private-state', '1.1', 303), None)
        self.assertTrue(SafeAccessFilter().filter(record))
        self.assertNotIn('private-', record.getMessage())
