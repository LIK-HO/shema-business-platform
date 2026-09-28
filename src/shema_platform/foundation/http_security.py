from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4


ASGIApp = Callable[[dict, Callable, Callable], Awaitable[None]]


class RequestBodyTooLarge(Exception):
    """Raised when an HTTP request body exceeds the configured security bound."""


class RequestBodySizeLimitMiddleware:
    """Hard request-body bound enforced before application parsing."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int = 1_048_576) -> None:
        if max_body_bytes < 1024:
            raise ValueError("max_body_bytes must be at least 1024")
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        headers = {
            key.lower(): value
            for key, value in scope.get("headers", ())
        }
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                declared_length = int(raw_length)
            except ValueError:
                declared_length = self._max_body_bytes + 1
            if declared_length > self._max_body_bytes:
                await self._send_too_large(send)
                return

        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message.get("type") == "http.request":
                total += len(message.get("body", b""))
                if total > self._max_body_bytes:
                    raise RequestBodyTooLarge
            return message

        try:
            await self._app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await self._send_too_large(send)

    async def _send_too_large(self, send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"x-correlation-id", str(uuid4()).encode("ascii")),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": (
                    b'{"code":"request_body_too_large",'
                    b'"message":"request body exceeds security limit"}'
                ),
            }
        )


def trusted_peer_identity(scope: dict) -> str:
    """Return only the direct ASGI peer; forwarded headers are intentionally ignored."""

    client = scope.get("client")
    if not client or not client[0]:
        raise ValueError("trusted peer identity is unavailable")
    return str(client[0])
