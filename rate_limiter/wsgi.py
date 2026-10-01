"""WSGI middleware: works with Flask, Django, Bottle, Pyramid, ...

It follows the classic WSGI middleware pattern: on a rejection it answers
``429`` directly, otherwise it wraps ``start_response`` to append the
``RateLimit-*`` headers to whatever the application produced.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, MutableMapping, Optional

from .keys import wsgi_key_func
from .limiter import RateLimiter
from .models import DEFAULT_REJECTION_BODY

Environ = MutableMapping[str, Any]
StartResponse = Callable[..., Callable[[bytes], None]]
App = Callable[[Environ, StartResponse], Iterable[bytes]]


class RateLimitMiddleware:
    """Reject requests that exhaust their token bucket with a ``429``."""

    def __init__(
        self,
        app: App,
        *,
        limiter: Optional[RateLimiter] = None,
        capacity: float = 60,
        refill_rate: Optional[float] = None,
        key_func: Optional[Callable[[Environ], str]] = None,
        trust_forwarded_for: bool = False,
        cost: float = 1.0,
        exempt_paths: Iterable[str] = (),
        body: bytes = DEFAULT_REJECTION_BODY,
        content_type: str = "application/json",
        status: str = "429 Too Many Requests",
    ) -> None:
        self.app = app
        self.limiter = limiter or RateLimiter(capacity=capacity, refill_rate=refill_rate)
        self.key_func = key_func or wsgi_key_func(trust_forwarded_for=trust_forwarded_for)
        self.cost = float(cost)
        self.exempt_paths = frozenset(exempt_paths)
        self.body = body
        self.content_type = content_type
        self.status = status

    def __call__(self, environ: Environ, start_response: StartResponse) -> Iterable[bytes]:
        if environ.get("PATH_INFO") in self.exempt_paths:
            return self.app(environ, start_response)

        decision = self.limiter.check(self.key_func(environ), cost=self.cost)
        if decision.blocked:
            return self._reject(start_response, decision)

        extra = list(decision.as_headers().items())

        def start_response_with_headers(status, headers, exc_info=None):
            return start_response(status, list(headers) + extra, exc_info)

        return self.app(environ, start_response_with_headers)

    def _reject(self, start_response: StartResponse, decision) -> Iterable[bytes]:
        headers = list(decision.as_headers().items())
        headers.append(("Content-Type", self.content_type))
        headers.append(("Content-Length", str(len(self.body))))
        start_response(self.status, headers)
        return [self.body]


__all__ = ["RateLimitMiddleware"]
