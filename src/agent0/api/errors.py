from __future__ import annotations

import base64
import binascii
import logging
import time
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def error_response(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_response(
            exc.status_code, _HTTP_CODES.get(exc.status_code, "http_error"), str(exc.detail), exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo `input`: a rejected secret value would otherwise come back in the body.
        msg = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors()
        )
        return error_response(422, "validation_error", msg)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return error_response(500, "internal_error", "internal server error")


def encode_cursor(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> str:
    try:
        return base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError):
        raise ApiError(400, "invalid_cursor", "cursor is not valid") from None


def decode_offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        offset = int(decode_cursor(cursor))
    except ValueError:
        raise ApiError(400, "invalid_cursor", "cursor is not valid") from None
    if offset < 0:
        raise ApiError(400, "invalid_cursor", "cursor is not valid")
    return offset


def paginate(items: list[Any], limit: int, cursor: str | None, mapper: Callable[[Any], Any] = lambda x: x):
    offset = decode_offset(cursor)
    chunk = items[offset : offset + limit]
    more = offset + limit < len(items)
    return {
        "items": [mapper(i) for i in chunk],
        "next_cursor": encode_cursor(str(offset + limit)) if more else None,
    }


class RateLimiter:
    def __init__(self, limit: int = 20, window: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, list[float]] = {}

    def check(self, key: str) -> None:
        now = self._clock()
        hits = [t for t in self._hits.get(key, []) if now - t < self.window]
        if len(hits) >= self.limit:
            self._hits[key] = hits
            raise ApiError(429, "rate_limited", "too many requests", {"Retry-After": str(int(self.window))})
        hits.append(now)
        self._hits[key] = hits
