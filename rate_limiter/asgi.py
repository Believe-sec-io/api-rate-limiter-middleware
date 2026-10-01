"""ASGI middleware: works with any ASGI app (Starlette, FastAPI, Quart, ...).

It is a plain ASGI 3 callable, so it adds no dependency on a framework. When a
request is allowed the response is left untouched except for the ``RateLimit-*``
headers; when it is rejected the middleware answers ``429`` itself and never
calls the wrapped application.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Iterable, Mapping, Optional

from .keys import asgi_key_func
from .limiter import RateLimiter
from .models import DEFAULT_REJECTION_BODY

Message = Mapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
App = Callable[[Mapping[str, Any], Receive, Send], Awaitable[None]]


def _encode(headers: Mapping[str, str]) -> "list[tuple[bytes, bytes]]":
    return [(name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in headers.items()]


class RateLimitMiddleware:
    """Reject ``http`` requests that exhaust their token bucket with a ``429``."""

    def __init__(
        self,
        app: App,
        *,
        limiter: Optional[RateLimiter] = None,
        capacity: float = 60,
        refill_rate: Optional[float] = None,
        key_func: Optional[Callable[[Mapping[str, Any]], str]] = None,
        trust_forwarded_for: bool = False,
        cost: float = 1.0,
        exempt_paths: Iterable[str] = (),
        body: bytes = DEFAULT_REJECTION_BODY,
        content_type: str = "application/json",
    ) -> None:
        self.app = app
        self.limiter = limiter or RateLimiter(capacity=capacity, refill_rate=refill_rate)
        self.key_func = key_func or asgi_key_func(trust_forwarded_for=trust_forwarded_for)
        self.cost = float(cost)
        self.exempt_paths = frozenset(exempt_paths)
        self.body = body
        self.content_type = content_type

    async def __call__(self, scope: Mapping[str, Any], receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or scope.get("path") in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        decision = self.limiter.check(self.key_func(scope), cost=self.cost)
        if decision.blocked:
            await self._reject(send, decision)
            return

        extra = _encode(decision.as_headers())

        async def send_with_headers(message: Message) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or ()) + extra
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)

    async def _reject(self, send: Send, decision) -> None:
        headers = _encode(decision.as_headers())
        headers.append((b"content-type", self.content_type.encode("latin-1")))
        headers.append((b"content-length", str(len(self.body)).encode("latin-1")))
        await send({"type": "http.response.start", "status": 429, "headers": headers})
        await send({"type": "http.response.body", "body": self.body})


__all__ = ["RateLimitMiddleware"]
