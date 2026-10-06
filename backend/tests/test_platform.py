"""Health check, error format, security headers, SPA serving, migrations."""
import tempfile
import threading
from pathlib import Path

from base import SECRET, TEST_DB, ApiTestCase
from app import create_app, db


class TestPlatform(ApiTestCase):
    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual((r.status_code, r.get_json()["database"]), (200, "ok"))

    def test_unknown_api_route_is_json_404(self):
        r = self.client.get("/api/nope")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["error"], "Endpoint not found.")

    def test_security_headers(self):
        r = self.client.get("/health")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_oversized_body_rejected(self):
        h = self.register()
        r = self.client.post("/api/tasks", json={"title": "x", "description": "y" * 100_000}, headers=h)
        self.assertEqual(r.status_code, 413)

    def test_migrations_are_idempotent_and_safe_to_run_concurrently(self):
        errors = []

        def run():
            try:
                db.migrate(TEST_DB)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=run) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        with db.get_conn() as conn:
            n = conn.execute("SELECT count(*) AS n FROM schema_migrations").fetchone()["n"]
        self.assertEqual(n, len(list(db.MIGRATIONS_DIR.glob("*.sql"))))


class TestSpaServing(ApiTestCase):
    def test_serves_built_frontend_with_fallback_and_caching(self):
        with tempfile.TemporaryDirectory() as dist:
            Path(dist, "index.html").write_text("<div id=root></div>")
            Path(dist, "assets").mkdir()
            Path(dist, "assets", "app-abc123.js").write_text("console.log(1)")
            app = create_app({"TESTING": True, "DATABASE_URL": TEST_DB, "JWT_SECRET": SECRET,
                              "FRONTEND_DIST": dist, "RUN_MIGRATIONS": False})
            c = app.test_client()
            asset = c.get("/assets/app-abc123.js")
            self.assertIn("immutable", asset.headers["Cache-Control"])
            asset.close()
            for path in ("/", "/board", "/some/deep/link"):  # client-side routes -> index.html
                r = c.get(path)
                self.assertIn(b"id=root", r.data)
                self.assertEqual(r.headers["Cache-Control"], "no-cache")
                r.close()
            self.assertEqual(c.get("/api/unknown").status_code, 404)  # API 404s are not swallowed
            db.init_pool(TEST_DB)  # restore the shared pool for other tests
