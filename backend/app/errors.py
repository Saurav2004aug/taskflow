"""Consistent JSON errors: every failure looks like {"error": "...", "fields": {...}?}."""

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, fields: dict | None = None,
                 headers: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.fields = fields
        self.headers = headers or {}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(e: ApiError):
        body = {"error": e.message}
        if e.fields:
            body["fields"] = e.fields
        return jsonify(body), e.status, e.headers

    @app.errorhandler(HTTPException)
    def handle_http_error(e: HTTPException):
        return jsonify({"error": e.description or e.name}), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e: Exception):
        app.logger.exception("unhandled error")
        return jsonify({"error": "Internal server error"}), 500
