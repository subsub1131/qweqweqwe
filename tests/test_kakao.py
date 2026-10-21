"""Kakao OAuth contract tests: disposable DB and no live Kakao traffic."""
import asyncio
import importlib
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import httpx
import jwt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from tests import test_auth as fixture
from app.models.social_account import SocialAccount

settings = fixture.settings


class KakaoTests(unittest.TestCase):
    setUp = fixture.AuthTests.setUp
    tearDown = fixture.AuthTests.tearDown

    def setUp(self):
        fixture.AuthTests.setUp(self)
        self.configuration = patch.multiple(settings, KAKAO_REST_API_KEY="test-rest-key", KAKAO_CLIENT_SECRET="", KAKAO_REDIRECT_URI="http://localhost:8000/auth/kakao/callback")
        self.configuration.start()
        self.addCleanup(self.configuration.stop)

    def module(self, name):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            self.fail(f"Required Kakao implementation missing: {name}")

    def start(self):
        response = self.client.get("/auth/kakao/login", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        return response, parse_qs(urlsplit(response.headers["location"]).query)["state"][0]

    def callback(self, state, **kwargs):
        return self.client.get("/auth/kakao/callback", params={"code": "test-code", "state": state, **kwargs}, follow_redirects=False)

    def assert_error(self, response, code):
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], f"http://localhost:8080/?auth_error={code}")
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        self.assertIn("kakao_oauth_state=", response.headers["set-cookie"])
        self.assertIn("Max-Age=0", response.headers["set-cookie"])
        self.assertNotIn("token", response.cookies)

    def test_provider_configuration_is_boolean_and_missing_keys_disable_login(self):
        for field, value in (("KAKAO_REST_API_KEY", ""), ("KAKAO_REST_API_KEY", "   "), ("KAKAO_REDIRECT_URI", ""), ("KAKAO_REDIRECT_URI", "javascript:alert(1)"), ("KAKAO_REDIRECT_URI", "https://user:pass@example.com/callback"), ("FRONTEND_URL", "javascript:alert(1)"), ("SECRET_KEY", ""), ("SECRET_KEY", "short")):
            with self.subTest(field=field, value=value), patch.object(settings, field, value):
                response = self.client.get("/auth/providers")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"kakao": {"enabled": False}})
                self.assertEqual(self.client.get("/auth/kakao/login", follow_redirects=False).status_code, 503)
        self.assertEqual(self.client.get("/auth/providers").json(), {"kakao": {"enabled": True}})

    def test_authorize_url_signed_state_cookie_and_secure_setting(self):
        with patch.object(settings, "COOKIE_SECURE", True):
            response, state = self.start()
        url = urlsplit(response.headers["location"])
        self.assertEqual(url.scheme + "://" + url.netloc + url.path, "https://kauth.kakao.com/oauth/authorize")
        self.assertEqual(parse_qs(url.query), {"client_id": ["test-rest-key"], "redirect_uri": ["http://localhost:8000/auth/kakao/callback"], "response_type": ["code"], "state": [state], "prompt": ["login"]})
        self.assertGreaterEqual(len(state), 43)
        cookie = response.headers["set-cookie"].lower()
        for expected in ("httponly", "secure", "samesite=lax", "max-age=600", "path=/"):
            self.assertIn(expected, cookie)
        claims = jwt.decode(response.cookies["kakao_oauth_state"], settings.SECRET_KEY, algorithms=["HS256"])
        self.assertEqual(claims["nonce"], state)
        self.assertEqual(claims["purpose"], "kakao_oauth_state")
        self.assertAlmostEqual(claims["exp"] - datetime.now(timezone.utc).timestamp(), 600, delta=5)
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_login_after_logout_requests_fresh_kakao_authentication(self):
        router = self.module("api.routers.kakao")
        _, first_state = self.start()
        with patch.object(router, "fetch_kakao_profile", return_value={"id": 123}):
            self.assertEqual(self.callback(first_state).status_code, 303)
        self.assertEqual(self.client.get("/auth/me").status_code, 200)
        self.assertEqual(self.client.post("/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        response = self.client.get("/api/auth/kakao/login", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(query.get("prompt"), ["login"])
        self.assertNotEqual(query["state"], [first_state])
        self.assertNotIn("login_hint", query)

    def test_missing_tampered_expired_and_session_state_never_exchange(self):
        router = self.module("api.routers.kakao")
        for case in ("missing", "tampered", "expired", "mismatch", "session", "missing_exp", "missing_query"):
            self.client.cookies.clear()
            if case != "missing":
                _, state = self.start()
            else:
                state = "unknown"
            if case == "tampered":
                self.client.cookies.set("kakao_oauth_state", "forged")
            elif case in {"expired", "missing_exp", "session"}:
                claims = {"purpose": "kakao_oauth_state", "nonce": state, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}
                if case == "missing_exp":
                    del claims["exp"]
                elif case == "session":
                    claims = {"sub": "local:1", "exp": 9999999999}
                self.client.cookies.set("kakao_oauth_state", jwt.encode(claims, settings.SECRET_KEY, algorithm="HS256"))
            with self.subTest(case=case), patch.object(router, "fetch_kakao_profile") as exchange:
                params = {"code": "test-code"}
                if case != "missing_query":
                    params["state"] = "different" if case == "mismatch" else state
                response = self.client.get("/auth/kakao/callback", params=params, follow_redirects=False)
                self.assert_error(response, "invalid_state")
                exchange.assert_not_called()

    def test_cancellation_and_missing_code_clear_state_without_exchange(self):
        router = self.module("api.routers.kakao")
        for params, expected in (({"error": "access_denied", "error_description": "private-detail"}, "kakao_cancelled"), ({"error": "server_error"}, "kakao_failed"), ({}, "kakao_failed")):
            _, state = self.start()
            with patch.object(router, "fetch_kakao_profile") as exchange:
                response = self.client.get("/auth/kakao/callback", params={"state": state, **params}, follow_redirects=False)
                self.assert_error(response, expected)
                exchange.assert_not_called()

    def test_success_defaults_profile_reuses_member_and_consumes_cookie(self):
        router = self.module("api.routers.kakao")
        for _ in range(2):
            _, state = self.start()
            with patch.object(router, "fetch_kakao_profile", return_value={"id": 12345678}):
                response = self.callback(state)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["location"], "http://localhost:8080/")
            self.assertEqual(response.headers.get("cache-control"), "no-store")
            self.assertTrue(any("Max-Age=0" in value and "kakao_oauth_state=" in value for value in response.headers.get_list("set-cookie")))
            self.assertEqual(self.client.get("/auth/me").json(), {"userId": "12345678", "userNm": "카카오 사용자", "email": None, "provider": "kakao"})
            with patch.object(router, "fetch_kakao_profile") as exchange:
                self.assert_error(self.callback(state), "invalid_state")
                exchange.assert_not_called()
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(SocialAccount)), 1)

    def test_profile_details_are_used_without_linking_local_email(self):
        router = self.module("api.routers.kakao")
        fixture.AuthTests.seed_local_user(self)
        _, state = self.start()
        profile = {"id": 42, "kakao_account": {"email": "tester@example.com", "profile": {"nickname": "카카오 별명"}}}
        with patch.object(router, "fetch_kakao_profile", return_value=profile):
            self.assertEqual(self.callback(state).status_code, 303)
        self.assertEqual(self.client.get("/auth/me").json(), {"userId": "42", "userNm": "카카오 별명", "email": "tester@example.com", "provider": "kakao"})

    def test_bad_profiles_do_not_create_accounts(self):
        router = self.module("api.routers.kakao")
        for profile in (None, [], {}, {"id": True}, {"id": -1}, {"id": "123"}, {"id": 1.5}, {"id": 2**63}, {"id": 1, "kakao_account": []}, {"id": 1, "kakao_account": {"profile": []}}):
            _, state = self.start()
            with self.subTest(profile=profile), patch.object(router, "fetch_kakao_profile", return_value=profile):
                self.assert_error(self.callback(state), "kakao_failed")
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(SocialAccount)), 0)

    def test_invalid_optional_fields_use_safe_defaults(self):
        router = self.module("api.routers.kakao")
        _, state = self.start()
        with patch.object(router, "fetch_kakao_profile", return_value={"id": 7, "kakao_account": {"email": {"bad": "value"}, "profile": {"nickname": 999}}}):
            self.assertEqual(self.callback(state).status_code, 303)
        self.assertEqual(self.client.get("/auth/me").json()["userNm"], "카카오 사용자")
        self.assertIsNone(self.client.get("/auth/me").json()["email"])

    def test_unavailable_config_callback_is_safe_and_clears_state(self):
        router = self.module("api.routers.kakao")
        _, state = self.start()
        with patch.object(settings, "KAKAO_REST_API_KEY", ""), patch.object(router, "fetch_kakao_profile") as exchange:
            self.assert_error(self.callback(state), "kakao_unavailable")
            exchange.assert_not_called()

    def test_provider_failures_never_leak_private_details(self):
        router = self.module("api.routers.kakao")
        service = self.module("app.services.kakao")
        for error in (service.KakaoUnavailable("private-token"), service.KakaoAuthenticationError("private-token")):
            _, state = self.start()
            with patch.object(router, "fetch_kakao_profile", side_effect=error):
                self.assert_error(self.callback(state), "kakao_unavailable" if isinstance(error, service.KakaoUnavailable) else "kakao_failed")

    def test_unique_conflict_rolls_back_and_returns_winning_account(self):
        router = self.module("api.routers.kakao")
        with self.sessions() as db:
            def concurrent_commit():
                with self.sessions() as winner_db:
                    winner = SocialAccount(provider="kakao", provider_user_id="99", display_name="Winner")
                    winner_db.add(winner)
                    winner_db.commit()
                raise IntegrityError("duplicate", {}, Exception())
            with patch.object(db, "commit", side_effect=concurrent_commit):
                account = router.get_or_create_account(db, {"id": 99})
            self.assertEqual(account.display_name, "Winner")
            self.assertEqual(account.provider_user_id, "99")
            self.assertEqual(db.scalar(select(func.count()).select_from(SocialAccount)), 1)

    def test_exchange_uses_form_bearer_timeout_and_optional_secret(self):
        service = self.module("app.services.kakao")
        real_client = httpx.AsyncClient
        for secret in ("", "test-secret"):
            requests = []
            def transport(request):
                requests.append(request)
                if len(requests) == 1:
                    return httpx.Response(200, json={"access_token": "private-token", "token_type": "bearer", "expires_in": 21599})
                return httpx.Response(200, json={"id": 123})
            with patch.object(settings, "KAKAO_CLIENT_SECRET", secret), patch.object(service.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs)) as factory:
                self.assertEqual(asyncio.run(service.fetch_kakao_profile("test-code")), {"id": 123})
            self.assertEqual(factory.call_args.kwargs["timeout"], 10.0)
            self.assertEqual(str(requests[0].url), "https://kauth.kakao.com/oauth/token")
            self.assertEqual(requests[0].method, "POST")
            self.assertIn("application/x-www-form-urlencoded", requests[0].headers["content-type"])
            expected = {"grant_type": ["authorization_code"], "client_id": ["test-rest-key"], "redirect_uri": ["http://localhost:8000/auth/kakao/callback"], "code": ["test-code"]}
            if secret:
                expected["client_secret"] = [secret]
            self.assertEqual(parse_qs(requests[0].content.decode()), expected)
            self.assertEqual(str(requests[1].url), "https://kapi.kakao.com/v2/user/me")
            self.assertEqual(requests[1].headers["authorization"], "Bearer private-token")

    def test_exchange_handles_http_network_and_malformed_responses(self):
        service = self.module("app.services.kakao")
        real_client = httpx.AsyncClient
        cases = ((400, {"error": "invalid_grant"}, False), (500, {}, False), (200, {}, False), (200, [], False), (200, {"access_token": 123}, False), (200, {"access_token": "private-token"}, True))
        for status, payload, profile_failure in cases:
            calls = []
            def transport(request):
                calls.append(request)
                return httpx.Response(500 if profile_failure and len(calls) == 2 else status, json=payload)
            with self.subTest(status=status, payload=payload), patch.object(service.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs)):
                with self.assertRaises((service.KakaoUnavailable, service.KakaoAuthenticationError)):
                    asyncio.run(service.fetch_kakao_profile("test-code"))
        for failure in (httpx.ReadTimeout("private-detail"), None):
            def transport(request):
                if failure:
                    raise failure
                return httpx.Response(200, content=b"not-json")
            with patch.object(service.httpx, "AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs)):
                with self.assertRaises((service.KakaoUnavailable, service.KakaoAuthenticationError)):
                    asyncio.run(service.fetch_kakao_profile("test-code"))


if __name__ == "__main__":
    unittest.main()
