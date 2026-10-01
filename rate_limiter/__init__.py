"""api-rate-limiter-middleware: token-bucket rate limiting for ASGI and WSGI APIs.

Public surface::

    from rate_limiter import RateLimiter, TokenBucket
    from rate_limiter import ASGIRateLimitMiddleware, WSGIRateLimitMiddleware

    limiter = RateLimiter(capacity=60, refill_rate=1)   # burst 60, then 1/s
    app = ASGIRateLimitMiddleware(app, limiter=limiter)

Only the standard library is required. ``RedisBackend`` additionally needs the
optional ``redis`` package (``pip install api-rate-limiter-middleware[redis]``).
"""

from __future__ import annotations

from .asgi import RateLimitMiddleware as ASGIRateLimitMiddleware
from .backend import InMemoryBackend, RateLimitBackend
from .bucket import BucketState, TokenBucket
from .keys import (
    asgi_key_func,
    client_ip_from_environ,
    client_ip_from_scope,
    wsgi_key_func,
)
from .limiter import RateLimiter
from .models import Decision
from .redis_backend import RedisBackend
from .wsgi import RateLimitMiddleware as WSGIRateLimitMiddleware

__version__ = "1.0.0"

__all__ = [
    "ASGIRateLimitMiddleware",
    "BucketState",
    "Decision",
    "InMemoryBackend",
    "RateLimitBackend",
    "RateLimiter",
    "RedisBackend",
    "TokenBucket",
    "WSGIRateLimitMiddleware",
    "asgi_key_func",
    "client_ip_from_environ",
    "client_ip_from_scope",
    "wsgi_key_func",
    "__version__",
]
