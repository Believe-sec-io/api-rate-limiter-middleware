"""Tests of the WSGI middleware (driven by a tiny in-repo WSGI harness)."""

from __future__ import annotations

from helpers import FakeClock, header_value, make_wsgi_app, run_wsgi, wsgi_environ
from rate_limiter import RateLimiter, WSGIRateLimitMiddleware


def _app(limiter: RateLimiter, **kwargs) -> WSGIRateLimitMiddleware:
    return WSGIRateLimitMiddleware(make_wsgi_app(), limiter=limiter, **kwargs)


def test_allowed_request_passes_with_rate_limit_headers():
    limiter = RateLimiter(capacity=5, refill_rate=1, time_source=FakeClock())
    status, headers, body = run_wsgi(_app(limiter), wsgi_environ())
    assert status == "200 OK"
    assert header_value(headers, "RateLimit-Limit") == "5"
    assert header_value(headers, "RateLimit-Remaining") == "4"
    assert body == b"ok"


def test_blocked_request_is_answered_with_429():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    app = _app(limiter)
    assert run_wsgi(app, wsgi_environ())[0] == "200 OK"

    status, headers, body = run_wsgi(app, wsgi_environ())
    assert status == "429 Too Many Requests"
    assert header_value(headers, "Retry-After") == "1"
    assert header_value(headers, "Content-Type") == "application/json"
    assert b"rate limit exceeded" in body


def test_clients_are_limited_independently():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    app = _app(limiter)
    assert run_wsgi(app, wsgi_environ(remote="1.1.1.1"))[0] == "200 OK"
    assert run_wsgi(app, wsgi_environ(remote="2.2.2.2"))[0] == "200 OK"
    assert run_wsgi(app, wsgi_environ(remote="1.1.1.1"))[0] == "429 Too Many Requests"


def test_exempt_paths_bypass_the_limiter():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    app = _app(limiter, exempt_paths={"/health"})
    assert run_wsgi(app, wsgi_environ(path="/health"))[0] == "200 OK"
    assert run_wsgi(app, wsgi_environ(path="/health"))[0] == "200 OK"


def test_trust_forwarded_for_selects_the_client():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    app = _app(limiter, trust_forwarded_for=True)
    env_a = wsgi_environ(remote="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.7")
    env_b = wsgi_environ(remote="10.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.8")
    assert run_wsgi(app, env_a)[0] == "200 OK"
    assert run_wsgi(app, env_b)[0] == "200 OK"
    assert run_wsgi(app, env_a)[0] == "429 Too Many Requests"


def test_default_limiter_is_built_from_capacity():
    app = WSGIRateLimitMiddleware(make_wsgi_app(), capacity=7)
    assert app.limiter.capacity == 7
