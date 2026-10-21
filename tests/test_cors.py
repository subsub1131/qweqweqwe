"""Browser calls backend directly from the configured frontend origin."""
import unittest
from tests import test_auth as fixture


class DirectCorsTests(unittest.TestCase):
    setUp = fixture.AuthTests.setUp
    tearDown = fixture.AuthTests.tearDown

    def test_preflight_allows_frontend_credentials_and_request_id(self):
        response = self.client.options('/api/user/login', headers={
            'Origin': fixture.settings.FRONTEND_URL,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type,x-request-id'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['access-control-allow-origin'], fixture.settings.FRONTEND_URL)
        self.assertEqual(response.headers['access-control-allow-credentials'], 'true')

    def test_response_exposes_only_metadata_header_to_allowed_origin(self):
        response = self.client.get('/api/auth/me', headers={'Origin': fixture.settings.FRONTEND_URL})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get('access-control-allow-origin'), fixture.settings.FRONTEND_URL)
        self.assertIn('x-request-id', response.headers.get('access-control-expose-headers', '').lower())

    def test_other_origin_is_not_allowed(self):
        response = self.client.options('/api/user/login', headers={
            'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'POST'})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('access-control-allow-origin', response.headers)
