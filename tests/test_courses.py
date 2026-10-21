"""Course demo contracts, using disposable SQLite authentication only."""
import unittest
from uuid import UUID
from unittest.mock import patch
from tests import test_auth as auth_fixture
from tests.test_auth import app, security

class CourseTests(unittest.TestCase):
    tearDown = auth_fixture.AuthTests.tearDown
    seed_local_user = auth_fixture.AuthTests.seed_local_user
    login = auth_fixture.AuthTests.login
    origin = {"Origin": "http://localhost:8080"}
    data = {"title": "새 강의", "description": "시연 설명", "category": "개발", "price": 12000, "duration_minutes": 90, "lesson_count": 6}

    def setUp(self):
        auth_fixture.AuthTests.setUp(self)
        try:
            from api.routers import courses
            from app.services.course_demo import CourseDemoRepository
        except ImportError:
            return
        replacement = patch.object(courses, "repository", CourseDemoRepository())
        replacement.start()
        self.addCleanup(replacement.stop)

    def authenticate(self):
        self.seed_local_user()
        self.assertEqual(self.login().status_code, 200)

    def test_public_catalog_and_detail(self):
        response = self.client.get("/api/courses")
        self.assertEqual(response.status_code, 200)
        courses = response.json()["items"]
        self.assertEqual(len(courses), 4)
        self.assertEqual(len({c["instructor"] for c in courses}), 1)
        self.assertEqual(set(courses[0]), {"id", "title", "description", "category", "price", "duration_minutes", "lesson_count", "instructor"})
        self.assertEqual(self.client.get(f'/api/courses/{courses[0]["id"]}').json(), courses[0])
        self.assertEqual(self.client.get("/api/courses/9999").status_code, 404)

    def test_private_routes_require_login(self):
        for path, data in (("/api/demo/courses", self.data), ("/api/demo/purchases", {"course_id": 1})):
            self.assertEqual(self.client.post(path, json=data, headers=self.origin).status_code, 401)
        self.assertEqual(self.client.get("/api/my/courses").status_code, 401)

    def test_mutations_require_configured_origin(self):
        self.authenticate()
        for path, data in (("/api/demo/courses", self.data), ("/api/demo/purchases", {"course_id": 1})):
            for headers in ({}, {"Origin": "https://attacker.example"}, {"Origin": "null"}):
                self.assertEqual(self.client.post(path, json=data, headers=headers).status_code, 403)

    def test_registration_is_visible_and_ids_increase(self):
        self.authenticate()
        first = self.client.post("/api/demo/courses", json=self.data, headers=self.origin)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["title"], "새 강의")
        second = self.client.post("/api/demo/courses", json=self.data, headers=self.origin)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["id"], first.json()["id"] + 1)
        self.assertEqual(self.client.get(f'/api/courses/{first.json()["id"]}').json(), first.json())
        self.assertEqual(len(self.client.get("/api/courses").json()["items"]), 6)

    def test_registration_validates_input(self):
        self.authenticate()
        for change in ({"title": " "}, {"description": ""}, {"category": " "}, {"price": -1}, {"price": 2.5}, {"price": True}, {"duration_minutes": 0}, {"lesson_count": 0}, {"id": 1}, {"instructor": "attacker"}):
            with self.subTest(change=change):
                self.assertEqual(self.client.post("/api/demo/courses", json={**self.data, **change}, headers=self.origin).status_code, 422)

    def test_purchase_is_idempotent_and_uses_server_course(self):
        self.authenticate()
        self.assertEqual(self.client.get("/api/my/courses").json(), {"items": []})
        course = self.client.get("/api/courses/1").json()
        first = self.client.post("/api/demo/purchases", json={"course_id": 1}, headers=self.origin)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(set(first.json()), {"id", "course", "demo"})
        UUID(first.json()["id"])
        self.assertTrue(first.json()["demo"])
        self.assertEqual(first.json()["course"], course)
        again = self.client.post("/api/demo/purchases", json={"course_id": 1}, headers=self.origin)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json(), first.json())
        mine = self.client.get("/api/my/courses")
        self.assertEqual(mine.json(), {"items": [course]})
        self.assertEqual(mine.headers.get("cache-control"), "no-store")

    def test_purchase_rejects_unknown_course_and_client_overrides(self):
        self.authenticate()
        self.assertEqual(self.client.post("/api/demo/purchases", json={"course_id": 9999}, headers=self.origin).status_code, 404)
        for data in ({"course_id": 1, "price": 0}, {"course_id": 1, "user_id": 2}, {"course_id": True}, {"course_id": -1}):
            self.assertEqual(self.client.post("/api/demo/purchases", json=data, headers=self.origin).status_code, 422)
        self.assertEqual(self.client.get("/api/my/courses").json(), {"items": []})

    def test_account_and_provider_purchase_isolation(self):
        self.authenticate()
        self.client.post("/api/demo/purchases", json={"course_id": 1}, headers=self.origin)
        self.seed_local_user(user_id="other")
        self.assertEqual(self.client.post("/user/login", json={"userId": "other", "userPwd": "correct-password"}).status_code, 200)
        self.assertEqual(self.client.get("/api/my/courses").json(), {"items": []})
        from app.models.social_account import SocialAccount
        with self.sessions() as db:
            social = SocialAccount(provider="kakao", provider_user_id="demo-social", display_name="Social")
            db.add(social)
            db.commit()
            token = security.create_session_token("kakao", social.id, security.session_account_binding("kakao", social))
        self.client.cookies.set("token", token)
        self.assertEqual(self.client.get("/api/my/courses").json(), {"items": []})
        self.assertEqual(self.client.post("/api/demo/purchases", json={"course_id": 1}, headers=self.origin).status_code, 201)

if __name__ == "__main__":
    unittest.main()
