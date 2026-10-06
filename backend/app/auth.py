"""
Authentication: register, login, and the @require_auth decorator.

  * Passwords are hashed with scrypt (a deliberately slow, memory-hard hash)
    via Werkzeug. Plain text is never stored or logged.
  * Login returns a signed JWT (HS256). The API is stateless: each request
    proves who it is with `Authorization: Bearer <token>`, so no server-side
    session store is needed.
  * Login failures return the same message whether the email or the password
    was wrong. An unknown email still runs a password-hash check, so response
    timing doesn't reveal which emails are registered.
  * Auth endpoints are rate limited per IP to slow down password guessing.
"""

import re
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from psycopg import errors as pg_errors
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_conn
from .errors import ApiError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Hash of a random password, used to equalise timing for unknown emails.
_DUMMY_HASH = generate_password_hash("timing-equaliser-not-a-real-password")


def _public_user(row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"],
            "created_at": row["created_at"].isoformat()}


def issue_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=current_app.config["JWT_TTL_HOURS"]),
        "iss": "taskflow",
    }
    return jwt.encode(claims, current_app.config["JWT_SECRET"], algorithm="HS256")


def _rate_limit_by_ip() -> None:
    limiter = current_app.extensions["auth_limiter"]
    allowed, _, retry_after = limiter.check(request.remote_addr or "unknown")
    if not allowed:
        raise ApiError("Too many attempts. Please wait and try again.", 429,
                       headers={"Retry-After": str(max(1, round(retry_after)))})


def _json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.")
    return data


def require_auth(view):
    """Reject the request with 401 unless it carries a valid, unexpired token.
    On success, g.user_id holds the authenticated user's id."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ApiError("Missing bearer token.", 401)
        try:
            claims = jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"],
                                issuer="taskflow", options={"require": ["exp", "sub", "iat"]})
        except jwt.ExpiredSignatureError:
            raise ApiError("Session expired. Please log in again.", 401)
        except jwt.InvalidTokenError:
            raise ApiError("Invalid token.", 401)
        g.user_id = int(claims["sub"])

        limiter = current_app.extensions["api_limiter"]
        allowed, remaining, retry_after = limiter.check(f"user:{g.user_id}")
        if not allowed:
            raise ApiError("Rate limit exceeded. Slow down.", 429,
                           headers={"Retry-After": str(max(1, round(retry_after)))})
        g.rate_remaining = remaining
        return view(*args, **kwargs)
    return wrapped


@bp.post("/register")
def register():
    _rate_limit_by_ip()
    data = _json_body()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    fields = {}
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        fields["name"] = "Name is required (max 80 characters)."
    if not isinstance(email, str) or not EMAIL_RE.match(email.strip()) or len(email) > 254:
        fields["email"] = "Enter a valid email address."
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        fields["password"] = "Password must be 8-128 characters."
    if fields:
        raise ApiError("Please fix the highlighted fields.", 422, fields)

    try:
        with get_conn() as conn:
            user = conn.execute(
                """INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s)
                   RETURNING id, email, name, created_at""",
                (email.strip(), name.strip(), generate_password_hash(password)),
            ).fetchone()
    except pg_errors.UniqueViolation:
        raise ApiError("An account with this email already exists.", 409,
                       {"email": "Already registered."})
    return jsonify({"token": issue_token(user["id"]), "user": _public_user(user)}), 201


@bp.post("/login")
def login():
    _rate_limit_by_ip()
    data = _json_body()
    email, password = data.get("email"), data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        raise ApiError("Email and password are required.", 422)

    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, email, name, created_at, password_hash FROM users WHERE lower(email) = lower(%s)",
            (email.strip(),),
        ).fetchone()

    stored_hash = user["password_hash"] if user else _DUMMY_HASH
    if not check_password_hash(stored_hash, password) or user is None:
        raise ApiError("Invalid email or password.", 401)
    return jsonify({"token": issue_token(user["id"]), "user": _public_user(user)})


@bp.get("/me")
@require_auth
def me():
    with get_conn() as conn:
        user = conn.execute("SELECT id, email, name, created_at FROM users WHERE id = %s",
                            (g.user_id,)).fetchone()
    if user is None:  # account deleted after the token was issued
        raise ApiError("Account no longer exists.", 401)
    return jsonify({"user": _public_user(user)})
