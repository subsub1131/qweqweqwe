"""Direct local FastAPI serving: UI and API share port 8000."""
import unittest
from unittest.mock import patch

from tests import test_auth as fixture


class WebTests(unittest.TestCase):
    setUp = fixture.AuthTests.setUp
    tearDown = fixture.AuthTests.tearDown

    def test_backend_entry_redirects_to_frontend_without_forwarding_sensitive_query(self):
        with patch.object(fixture.settings, 'FRONTEND_URL', 'http://127.0.0.1:8080'):
            response = self.client.get('http://127.0.0.1:8000/?debug=1&code=private-code&token=private-token', follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers['location'], 'http://127.0.0.1:8080/?debug=1')

    def test_frontend_entry_does_not_redirect_to_itself(self):
        with patch.object(fixture.settings, 'FRONTEND_URL', 'http://127.0.0.1:8000'):
            response = self.client.get('http://127.0.0.1:8000/', follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="auth-form"', response.text)

    def test_root_serves_login_html_and_assets(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('id="auth-form"', response.text)
        for path, content_type in (('/app.js', 'javascript'), ('/styles.css', 'text/css')):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(content_type, response.headers['content-type'])

    def test_same_origin_prefixed_auth_flow(self):
        origin = 'http://127.0.0.1:8000'
        with patch.object(fixture.settings, 'FRONTEND_URL', origin):
            self.assertEqual(self.client.get('/api/auth/providers').status_code, 200)
            self.assertEqual(self.client.get('/api/auth/me').status_code, 401)
            response = self.client.post('/api/user/signUp', headers={'Origin': origin}, json={
                'userId': 'direct', 'userNm': 'Local', 'userPwd': 'test-password', 'email': 'local@example.com'})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(self.client.post('/api/user/login', headers={'Origin': origin}, json={
                'userId': 'direct', 'userPwd': 'test-password'}).status_code, 200)
            self.assertEqual(self.client.get('/api/auth/me').json()['userId'], 'direct')
            self.assertEqual(self.client.post('/api/auth/logout', headers={'Origin': origin}).status_code, 204)
            self.assertEqual(self.client.get('/api/auth/me').status_code, 401)

    def test_prefixed_validation_does_not_echo_password(self):
        response = self.client.post('/api/user/login', json={'userPwd': 'must-stay-private'})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('must-stay-private', response.text)

    def test_static_root_does_not_expose_project_files(self):
        for path in ('/.env', '/app/main.py', '/api/no-such-route'):
            self.assertEqual(self.client.get(path).status_code, 404)
