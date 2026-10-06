from datetime import datetime, timedelta, timezone

import jwt

from base import SECRET, ApiTestCase
from app import db


class TestRegister(ApiTestCase):
    def test_register_returns_token_and_user(self):
        r = self.client.post("/api/auth/register",
                             json={"email": "Aman@Example.com", "password": "correct-horse", "name": " Aman "})
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertEqual(body["user"]["name"], "Aman")
        self.assertEqual(body["user"]["email"], "Aman@Example.com")
        self.assertNotIn("password_hash", body["user"])
        claims = jwt.decode(body["token"], SECRET, algorithms=["HS256"], issuer="taskflow")
        self.assertEqual(claims["sub"], str(body["user"]["id"]))

    def test_password_is_hashed_not_stored(self):
        self.register(password="my-plain-password")
        with db.get_conn() as conn:
            stored = conn.execute("SELECT password_hash FROM users").fetchone()["password_hash"]
        self.assertNotIn("my-plain-password", stored)
        self.assertTrue(stored.startswith("scrypt:"))

    def test_validation_errors_are_per_field(self):
        r = self.client.post("/api/auth/register", json={"email": "not-an-email", "password": "short", "name": ""})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(r.get_json()["fields"]), {"email", "password", "name"})

    def test_duplicate_email_is_case_insensitive(self):
        self.register(email="aman@example.com")
        r = self.client.post("/api/auth/register",
                             json={"email": "AMAN@example.COM", "password": "another-pass", "name": "X"})
        self.assertEqual(r.status_code, 409)

    def test_non_json_body(self):
        r = self.client.post("/api/auth/register", data="nope", content_type="text/plain")
        self.assertEqual(r.status_code, 400)


class TestLogin(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.register(email="aman@example.com", password="correct-horse")

    def test_login_success_any_email_case(self):
        r = self.client.post("/api/auth/login", json={"email": "AMAN@example.com", "password": "correct-horse"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.get_json())

    def test_wrong_password_and_unknown_email_look_identical(self):
        wrong_pw = self.client.post("/api/auth/login", json={"email": "aman@example.com", "password": "nope-nope"})
        unknown = self.client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope"})
        self.assertEqual(wrong_pw.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong_pw.get_json(), unknown.get_json())  # no account enumeration

    def test_brute_force_is_rate_limited_per_ip(self):
        codes = [self.client.post("/api/auth/login", json={"email": "aman@example.com", "password": f"guess-{i}"}).status_code
                 for i in range(12)]
        # 1 token was spent on register in setUp; 9 guesses allowed, then 429
        self.assertEqual(codes[:9], [401] * 9)
        self.assertEqual(set(codes[9:]), {429})
        r = self.client.post("/api/auth/login", json={"email": "aman@example.com", "password": "correct-horse"})
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)
        self.clock.t += 60  # the bucket refills over time
        r = self.client.post("/api/auth/login", json={"email": "aman@example.com", "password": "correct-horse"})
        self.assertEqual(r.status_code, 200)


class TestTokens(ApiTestCase):
    def test_me(self):
        headers = self.register(name="Aman")
        r = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(r.get_json()["user"]["name"], "Aman")

    def test_missing_or_malformed_header(self):
        for headers in ({}, {"Authorization": "Token abc"}, {"Authorization": "Bearer"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def _token(self, secret=SECRET, algorithm="HS256", **overrides):
        now = datetime.now(timezone.utc)
        claims = {"sub": "1", "iat": now, "exp": now + timedelta(hours=1), "iss": "taskflow", **overrides}
        return jwt.encode(claims, secret, algorithm=algorithm)

    def test_rejects_expired_forged_and_unsigned_tokens(self):
        self.register()
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        bad_tokens = {
            "expired": self._token(exp=past),
            "wrong secret": self._token(secret="attacker-secret-attacker-secret-1234"),
            "wrong issuer": self._token(iss="someone-else"),
            "alg none": jwt.encode({"sub": "1", "iss": "taskflow"}, None, algorithm="none"),
            "garbage": "not.a.jwt",
        }
        for name, token in bad_tokens.items():
            with self.subTest(name):
                r = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(r.status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {self._token()}"}).status_code, 200)

    def test_token_for_deleted_account(self):
        headers = self.register()
        with db.get_conn() as conn:
            conn.execute("DELETE FROM users")
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)
