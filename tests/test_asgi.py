"""Tests of the ASGI middleware (driven by a tiny in-repo ASGI harness)."""

from __future__ import annotations

import asyncio

from helpers import FakeClock, header_value, http_scope, make_asgi_app, noop, run_asgi
from rate_limiter import ASGIRateLimitMiddleware, RateLimiter


def _app(limiter: RateLimiter, **kwargs) -> ASGIRateLimitMiddleware:
    return ASGIRateLimitMiddleware(make_asgi_app(), limiter=limiter, **kwargs)


def test_allowed_request_passes_with_rate_limit_headers():
    limiter = RateLimiter(capacity=5, refill_rate=1, time_source=FakeClock())
    messages = run_asgi(_app(limiter), http_scope())
    start = messages[0]
    assert start["status"] == 200
    assert header_value(start["headers"], "RateLimit-Limit") == "5"
    assert header_value(start["headers"], "RateLimit-Remaining") == "4"
    assert messages[-1]["body"] == b"ok"


def test_blocked_request_is_answered_with_429():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    app = _app(limiter)
    assert run_asgi(app, http_scope())[0]["status"] == 200

    messages = run_asgi(app, http_scope())
    assert messages[0]["status"] == 429
    assert header_value(messages[0]["headers"], "Retry-After") == "1"
    assert messages[1]["body"] == b'{"error":"rate limit exceeded"}'


def test_clients_are_limited_independently():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    app = _app(limiter, trust_forwarded_for=True)
    first = http_scope(headers=[(b"x-forwarded-for", b"1.1.1.1")])
    second = http_scope(headers=[(b"x-forwarded-for", b"2.2.2.2")])
    assert run_asgi(app, first)[0]["status"] == 200
    assert run_asgi(app, second)[0]["status"] == 200
    assert run_asgi(app, first)[0]["status"] == 429


def test_exempt_paths_bypass_the_limiter():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    app = _app(limiter, exempt_paths={"/health"})
    assert run_asgi(app, http_scope(path="/health"))[0]["status"] == 200
    assert run_asgi(app, http_scope(path="/health"))[0]["status"] == 200


def test_custom_cost_is_honoured():
    limiter = RateLimiter(capacity=10, refill_rate=1, time_source=FakeClock())
    messages = run_asgi(_app(limiter, cost=4), http_scope())
    assert header_value(messages[0]["headers"], "RateLimit-Remaining") == "6"


def test_non_http_scope_is_forwarded_untouched():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    seen = {}

    async def lifespan(scope, receive, send):
        seen["type"] = scope["type"]

    app = ASGIRateLimitMiddleware(lifespan, limiter=limiter)
    asyncio.run(app({"type": "lifespan"}, noop, noop))
    assert seen["type"] == "lifespan"


def test_default_limiter_is_built_from_capacity():
    app = ASGIRateLimitMiddleware(make_asgi_app(), capacity=3)
    assert app.limiter.capacity == 3
