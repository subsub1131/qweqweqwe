"""Regressions from the final authentication review; all data is disposable."""
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import httpx
from tests.test_auth import AuthTests, User
from tests.test_kakao import KakaoTests
from app.models.social_account import SocialAccount


class SessionReviewTests(AuthTests):
    def test_deleted_local_id_reuse_rejects_old_session(self):
        idx = self.seed_local_user()
        self.assertEqual(self.login().status_code, 200)
        with self.sessions() as db:
            db.delete(db.get(User, idx))
            db.commit()
        # Even an identical user ID and password must belong to a new account.
        response = self.client.post('/user/signUp', json={
            'userId': 'tester', 'userNm': 'Replacement',
            'userPwd': 'correct-password', 'email': 'new@example.com'})
        self.assertEqual(response.status_code, 201)
        with self.sessions() as db:
            self.assertEqual(db.get(User, idx).userNm, 'Replacement')
        self.assertEqual(self.client.get('/auth/me').status_code, 401)

    def test_first_migrated_login_has_valid_binding(self):
        self.seed_local_user()
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.client.get('/auth/me').status_code, 200)

    def test_unbound_session_is_rejected(self):
        self.seed_local_user()
        self.client.cookies.set('token', self.signed_token())
        self.assertEqual(self.client.get('/auth/me').status_code, 401)

    def test_auth_validation_never_echoes_password(self):
        secret = 'credential-must-not-be-returned'
        cases = (
            ('/user/signUp', {'userId': 'x', 'userNm': 'X', 'userPwd': secret}),
            ('/user/signUp', {'userId': 'x', 'userNm': 'X', 'email': 'x@example.com', 'userPwd': {'secret': secret}}),
            ('/user/login', {'userPwd': secret}),
            ('/user/login', {'userId': 'x', 'userPwd': {'secret': secret}}),
        )
        for path, data in cases:
            with self.subTest(path=path, data_type=type(data['userPwd'])):
                response = self.client.post(path, json=data)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(secret, response.text)
                self.assertEqual(response.headers.get('cache-control'), 'no-store')


class KakaoReviewTests(KakaoTests):
    def test_deleted_social_id_reuse_rejects_old_session(self):
        router = self.module('api.routers.kakao')
        _, state = self.start()
        with patch.object(router, 'fetch_kakao_profile', return_value={'id': 123}):
            self.assertEqual(self.callback(state).status_code, 303)
        with self.sessions() as db:
            db.delete(db.get(SocialAccount, 1))
            db.commit()
            replacement = SocialAccount(provider='kakao', provider_user_id='456', display_name='Replacement')
            db.add(replacement)
            db.commit()
            self.assertEqual(replacement.id, 1)
        self.assertEqual(self.client.get('/auth/me').status_code, 401)

    def test_malformed_bearer_redirects_and_clears_state(self):
        service = self.module('app.services.kakao')
        real_client = httpx.AsyncClient
        for token in ('비밀토큰', 'bad\x00token', 'bad\x7ftoken'):
            _, state = self.start()
            calls = []
            def transport(request):
                calls.append(request)
                return httpx.Response(200, json={'access_token': token})
            with self.subTest(token=repr(token)), patch.object(service.httpx, 'AsyncClient',
                    side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs)):
                self.assert_error(self.callback(state), 'kakao_failed')
                self.assertEqual(len(calls), 1)


class FixtureReviewTests(unittest.TestCase):
    def test_fixture_import_restores_process_environment(self):
        script = """
import os
keys = ('DATABASE_URL', 'SECRET_KEY', 'FRONTEND_URL', 'COOKIE_SECURE')
before = {key: os.environ.get(key) for key in keys}
import tests.test_auth
assert before == {key: os.environ.get(key) for key in keys}, 'fixture leaked environment'
"""
        environment = dict(os.environ, DATABASE_URL='fixture-restoration-sentinel',
                           SECRET_KEY='environment-restoration-sentinel')
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(cls(name) for cls in
        (SessionReviewTests, KakaoReviewTests, FixtureReviewTests)
        for name in cls.__dict__ if name.startswith('test_'))
