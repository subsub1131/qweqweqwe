"""Authentication contract tests; never load the user's .env or database."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

_test_environment = {
    "DATABASE_URL": "sqlite://",
    "SECRET_KEY": "test-only-secret-key-for-disposable-tests-with-at-least-sixty-four-bytes",
    "FRONTEND_URL": "http://localhost:8080", "COOKIE_SECURE": "false",
}

import jwt
import pydantic_settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_settings_config = pydantic_settings.SettingsConfigDict
def _without_dotenv(**kwargs):
    kwargs["env_file"] = None
    return _settings_config(**kwargs)

with patch.dict(os.environ, _test_environment), patch.object(pydantic_settings, "SettingsConfigDict", side_effect=_without_dotenv):
    from app.main import app
    from app.core import security
    from app.core.config import settings
    from app.db.database import Base, get_db
    from app.models.user import User


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        def override_db():
            with self.sessions() as session:
                yield session
        app.dependency_overrides[get_db] = override_db
        # Legacy login uses SessionLocal directly: keep the RED run disposable too.
        self.legacy_db = patch("api.routers.users.SessionLocal", self.sessions, create=True)
        self.legacy_db.start()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.legacy_db.stop()
        self.engine.dispose()

    def seed_local_user(self, user_id="tester", password="correct-password"):
        with self.sessions() as db:
            user = User(userNm="테스터", userId=user_id, userPwd=password, email="tester@example.com")
            db.add(user)
            db.commit()
            return user.idx

    def login(self, password="correct-password", **kwargs):
        return self.client.post("/user/login", json={"userId": "tester", "userPwd": password}, **kwargs)

    def signed_token(self, **claims):
        payload = {"sub": "local:1", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
        payload.update(claims)
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def test_wrong_password_is_rejected(self):
        self.seed_local_user()
        response = self.login("incorrect-password")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("token", response.cookies)

    def test_unknown_user_is_rejected(self):
        self.assertEqual(self.login().status_code, 401)

    def test_signup_hashes_password_and_filters_response(self):
        response = self.client.post("/user/signUp", json={"userId": "tester", "userNm": "테스터", "userPwd": "correct-password", "email": "tester@example.com"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"userId": "tester", "userNm": "테스터", "email": "tester@example.com"})
        with self.sessions() as db:
            stored = db.scalar(select(User)).userPwd
        self.assertTrue(stored.startswith("scrypt$"))
        self.assertTrue(security.verify_password("correct-password", stored))

    def test_duplicate_signup_is_conflict(self):
        self.seed_local_user()
        response = self.client.post("/user/signUp", json={"userId": "tester", "userNm": "Other", "userPwd": "password", "email": "other@example.com"})
        self.assertEqual(response.status_code, 409)

    def test_successful_plaintext_login_migrates_and_sets_session(self):
        idx = self.seed_local_user()
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"userId": "tester", "userNm": "테스터", "email": "tester@example.com"})
        cookie = response.headers["set-cookie"].lower()
        for expected in ("httponly", "samesite=lax", "path=/", "max-age=1800"):
            self.assertIn(expected, cookie)
        payload = jwt.decode(response.cookies["token"], settings.SECRET_KEY, algorithms=["HS256"])
        self.assertEqual(payload["sub"], f"local:{idx}")
        self.assertAlmostEqual(payload["exp"] - datetime.now(timezone.utc).timestamp(), 1800, delta=5)
        with self.sessions() as db:
            self.assertTrue(db.get(User, idx).userPwd.startswith("scrypt$"))

    def test_failed_plaintext_login_does_not_migrate(self):
        idx = self.seed_local_user()
        self.login("wrong")
        with self.sessions() as db:
            self.assertEqual(db.get(User, idx).userPwd, "correct-password")

    def test_hash_roundtrip_random_salt_and_wrong_password(self):
        self.assertTrue(callable(getattr(security, "hash_password", None)), "hash_password helper missing")
        first = security.hash_password("비밀번호")
        self.assertNotEqual(first, security.hash_password("비밀번호"))
        self.assertTrue(security.verify_password("비밀번호", first))
        self.assertFalse(security.verify_password("different", first))

    def test_damaged_hashes_fail_closed_even_when_used_as_password(self):
        self.assertTrue(callable(getattr(security, "verify_password", None)), "verify_password helper missing")
        for stored in ("scrypt$broken", "scrypt$32768$8$1$00$00", "scrypt$16384$8$1$not-hex$not-hex", "scrypt$16384$8$1$00$00", "$2b$broken", "argon2$broken", "pbkdf2_sha256$broken"):
            with self.subTest(stored=stored):
                self.assertFalse(security.verify_password(stored, stored))

    def test_hashed_password_login(self):
        self.assertTrue(callable(getattr(security, "hash_password", None)), "hash_password helper missing")
        self.seed_local_user(password=security.hash_password("correct-password"))
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.login("wrong").status_code, 401)

    def test_me_returns_minimal_local_profile_without_cache(self):
        self.seed_local_user()
        self.login()
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"userId": "tester", "userNm": "테스터", "email": "tester@example.com", "provider": "local"})
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_me_rejects_missing_and_invalid_tokens(self):
        self.seed_local_user()
        values = (None, "bad-token", self.signed_token(exp=datetime.now(timezone.utc) - timedelta(seconds=1)), self.signed_token(sub="local:0"), self.signed_token(sub="local:abc"), self.signed_token(sub="local:1:2"), self.signed_token(sub="unknown:1"), self.signed_token(sub="local:01"), self.signed_token(sub="local:-1"))
        for value in values:
            self.client.cookies.clear()
            if value:
                self.client.cookies.set("token", value)
            with self.subTest(token=value):
                self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_unauthenticated_me_is_not_cacheable(self):
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_social_identity_is_unique_per_provider(self):
        from app.models.social_account import SocialAccount
        from sqlalchemy.exc import IntegrityError
        with self.sessions() as db:
            db.add(SocialAccount(provider="kakao", provider_user_id="same-member", display_name="One"))
            db.commit()
            db.add(SocialAccount(provider="kakao", provider_user_id="same-member", display_name="Two"))
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_invalid_session_subjects_cannot_be_issued(self):
        for provider, account_id in (("other", 1), ("local", 0), ("local", -1), ("local", True), ("local", "1"), ("local", 2**63)):
            with self.subTest(provider=provider, account_id=account_id):
                with self.assertRaises(ValueError):
                    security.create_session_token(provider, account_id, "0" * 64)

    def test_me_rejects_missing_exp_wrong_signature_and_algorithm(self):
        self.seed_local_user()
        tokens = (jwt.encode({"sub": "local:1"}, settings.SECRET_KEY, algorithm="HS256"), jwt.encode({"sub": "local:1", "exp": 9999999999}, "wrong-key-with-at-least-thirty-two-bytes", algorithm="HS256"), jwt.encode({"sub": "local:1", "exp": 9999999999}, settings.SECRET_KEY, algorithm="HS384"))
        for value in tokens:
            self.client.cookies.set("token", value)
            self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_deleted_member_cannot_use_session(self):
        idx = self.seed_local_user()
        self.login()
        with self.sessions() as db:
            db.delete(db.get(User, idx))
            db.commit()
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_origin_mismatch_blocks_auth_mutations(self):
        self.seed_local_user()
        for path, data in (("/user/login", {"userId": "tester", "userPwd": "correct-password"}), ("/user/signUp", {"userId": "new", "userNm": "New", "userPwd": "password", "email": "new@example.com"}), ("/auth/logout", None)):
            response = self.client.post(path, json=data, headers={"Origin": "https://attacker.example"})
            self.assertEqual(response.status_code, 403)

    def test_configured_origin_is_allowed(self):
        self.seed_local_user()
        self.assertEqual(self.login(headers={"Origin": "http://localhost:8080"}).status_code, 200)

    def test_logout_expires_cookie(self):
        self.seed_local_user()
        self.login()
        response = self.client.post("/auth/logout")
        self.assertEqual(response.status_code, 204)
        self.assertIn("Max-Age=0", response.headers["set-cookie"])
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_secure_cookie_setting(self):
        self.assertTrue(hasattr(settings, "COOKIE_SECURE"), "COOKIE_SECURE setting missing")
        self.seed_local_user()
        with patch.object(settings, "COOKIE_SECURE", True, create=True):
            self.assertIn("; secure", self.login().headers["set-cookie"].lower())

    def test_unsafe_signing_keys_fail_clearly_without_migrating(self):
        idx = self.seed_local_user()
        for key in ("", "short", "my-secret-key-for-jwk-must-be-32-bytes-or-more"):
            with patch.object(settings, "SECRET_KEY", key):
                response = self.login()
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("token", response.cookies)
        with self.sessions() as db:
            self.assertEqual(db.get(User, idx).userPwd, "correct-password")

    def test_social_session_is_separate_from_local_id(self):
        self.assertTrue(callable(getattr(security, "create_session_token", None)), "session helper missing")
        from app.models.social_account import SocialAccount
        self.seed_local_user()
        with self.sessions() as db:
            social = SocialAccount(provider="kakao", provider_user_id="kakao-member", display_name="카카오 사용자", email=None)
            db.add(social)
            db.commit()
            token = security.create_session_token("kakao", social.id, security.session_account_binding("kakao", social))
        self.client.cookies.set("token", token)
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"userId": "kakao-member", "userNm": "카카오 사용자", "email": None, "provider": "kakao"})


if __name__ == "__main__":
    unittest.main()
