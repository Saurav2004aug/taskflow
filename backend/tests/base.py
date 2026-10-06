"""
Shared test setup. Tests run against a REAL PostgreSQL database (not SQLite,
not mocks), so constraints, indexes and SQL behave exactly as in production.

    TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/taskflow_test

Every test starts from empty tables.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db  # noqa: E402
from app.ratelimit import RateLimiter  # noqa: E402

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/taskflow_test")
SECRET = "test-secret-key-that-is-long-enough-for-hs256"


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class ApiTestCase(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.clock = FakeClock()
        cls.app = create_app({
            "TESTING": True,
            "DATABASE_URL": TEST_DB,
            "JWT_SECRET": SECRET,
            "FRONTEND_DIST": "/nonexistent",
            "RATE_LIMIT_CLOCK": cls.clock,
        })

    @classmethod
    def tearDownClass(cls):
        db.close_pool()

    def setUp(self):
        with db.get_conn() as conn:
            conn.execute("TRUNCATE users, tasks RESTART IDENTITY CASCADE")
        cfg = self.app.config
        # fresh rate-limit buckets for every test
        self.app.extensions["auth_limiter"] = RateLimiter(cfg["AUTH_RATE_CAPACITY"], cfg["AUTH_RATE_PER_SEC"], self.clock)
        self.app.extensions["api_limiter"] = RateLimiter(cfg["API_RATE_CAPACITY"], cfg["API_RATE_PER_SEC"], self.clock)
        self.client = self.app.test_client()

    # ---- helpers ----

    def register(self, email="aman@example.com", password="correct-horse", name="Aman"):
        r = self.client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
        self.assertEqual(r.status_code, 201, r.get_json())
        return {"Authorization": f"Bearer {r.get_json()['token']}"}

    def create(self, headers, **body):
        body.setdefault("title", "A task")
        r = self.client.post("/api/tasks", json=body, headers=headers)
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()
