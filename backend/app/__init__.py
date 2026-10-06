"""
TaskFlow API: application factory.

    create_app()         reads configuration from environment variables
    create_app({...})    overrides for tests

In production the same Flask process also serves the built React app
(frontend/dist), so the site and API share one origin: no CORS setup, and one
service to deploy.
"""

import os
import secrets
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auth, db, tasks
from .errors import ApiError, register_error_handlers
from .ratelimit import RateLimiter

DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.json.sort_keys = False  # keep response fields in a readable order
    env = os.environ
    app.config.update(
        DATABASE_URL=env.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/taskflow"),
        JWT_SECRET=env.get("JWT_SECRET", ""),
        JWT_TTL_HOURS=int(env.get("JWT_TTL_HOURS", 24)),
        AUTH_RATE_CAPACITY=int(env.get("AUTH_RATE_CAPACITY", 10)),     # 10 attempts burst,
        AUTH_RATE_PER_SEC=float(env.get("AUTH_RATE_PER_SEC", 10 / 60)),  # then 10 per minute per IP
        API_RATE_CAPACITY=int(env.get("API_RATE_CAPACITY", 120)),
        API_RATE_PER_SEC=float(env.get("API_RATE_PER_SEC", 5)),
        TRUSTED_PROXIES=int(env.get("TRUSTED_PROXIES", 0)),  # set to 1 behind Render/Heroku/nginx
        FRONTEND_DIST=env.get("FRONTEND_DIST", str(DEFAULT_DIST)),
        RUN_MIGRATIONS=env.get("RUN_MIGRATIONS", "1") == "1",
        MAX_CONTENT_LENGTH=64 * 1024,  # no request body needs more than 64 KB
    )
    if overrides:
        app.config.update(overrides)

    if not app.config["JWT_SECRET"]:
        if env.get("FLASK_ENV") == "production" or env.get("RENDER"):
            raise RuntimeError("JWT_SECRET must be set in production")
        # Dev convenience: a random secret means tokens don't survive restarts.
        app.config["JWT_SECRET"] = secrets.token_urlsafe(32)
        app.logger.warning("JWT_SECRET not set; using a random development secret")

    if app.config["TRUSTED_PROXIES"]:
        # Use the real client IP from X-Forwarded-For (needed for per-IP rate limits).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["TRUSTED_PROXIES"],
                                x_proto=app.config["TRUSTED_PROXIES"])

    clock = app.config.get("RATE_LIMIT_CLOCK")
    kw = {"clock": clock} if clock else {}
    app.extensions["auth_limiter"] = RateLimiter(app.config["AUTH_RATE_CAPACITY"],
                                                 app.config["AUTH_RATE_PER_SEC"], **kw)
    app.extensions["api_limiter"] = RateLimiter(app.config["API_RATE_CAPACITY"],
                                                app.config["API_RATE_PER_SEC"], **kw)

    if app.config["RUN_MIGRATIONS"]:
        applied = db.migrate(app.config["DATABASE_URL"])
        if applied:
            app.logger.warning("applied migrations: %s", ", ".join(applied))
    db.init_pool(app.config["DATABASE_URL"])

    register_error_handlers(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(tasks.bp)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    @app.get("/health")
    def health():
        try:
            with db.get_conn() as conn:
                conn.execute("SELECT 1")
        except Exception:
            return jsonify({"status": "degraded", "database": "unreachable"}), 503
        return jsonify({"status": "ok", "database": "ok"})

    @app.route("/api/<path:_unused>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def api_not_found(_unused):
        raise ApiError("Endpoint not found.", 404)

    # ---- single-page app: serve files from frontend/dist, fall back to index.html
    dist = Path(app.config["FRONTEND_DIST"])

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path):
        if not (dist / "index.html").exists():
            return jsonify({"message": "TaskFlow API is running. Build the frontend to serve the UI."})
        if path and (dist / path).is_file():
            resp = send_from_directory(dist, path)
            if path.startswith("assets/"):  # content-hashed filenames: cache forever
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        resp = send_from_directory(dist, "index.html")
        resp.headers["Cache-Control"] = "no-cache"  # always pick up new deploys
        return resp

    return app
