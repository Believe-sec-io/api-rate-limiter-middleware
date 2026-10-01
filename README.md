# api-rate-limiter-middleware

[![CI](https://github.com/Believe-sec-io/api-rate-limiter-middleware/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Believe-sec-io/api-rate-limiter-middleware/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Token-bucket rate limiting for ASGI and WSGI APIs — a reusable core, an in-memory backend and an optional Redis backend, with no runtime dependency.**

A token bucket is the right shape for an API: ``capacity`` sets how big a burst
you tolerate and ``refill_rate`` how much sustained traffic you accept. This
package gives you that primitve, exposes it as middleware for any ASGI or WSGI
app (FastAPI, Starlette, Flask, Django, Bottle…), and answers the rejected
requests with a proper ``429`` plus the standard ``RateLimit-*`` headers.

## Installation

```bash
pip install api-rate-limiter-middleware            # core + in-memory backend
pip install "api-rate-limiter-middleware[redis]"   # optional Redis backend
```

The core and the in-memory backend use **only the standard library**. Something
to note: nothing is required at runtime for the common case.

## Quickstart — ASGI (FastAPI / Starlette)

```python
from fastapi import FastAPI
from rate_limiter import ASGIRateLimitMiddleware, RateLimiter

app = FastAPI()

# 60 requests allowed in a burst, then 1 request per second, per client.
app = ASGIRateLimitMiddleware(app, limiter=RateLimiter(capacity=60, refill_rate=1))

@app.get("/")
def read_root():
    return {"ok": True}
```

Because it is a plain ASGI 3 callable, it also wraps a Starlette app, a Quart
app, or any other ASGI callable without a framework-specific adapter.

## Quickstart — WSGI (Flask / Django)

```python
from flask import Flask
from rate_limiter import WSGIRateLimitMiddleware, RateLimiter

app = Flask(__name__)

@app.get("/")
def index():
    return {"ok": True}

# A friendly burst of 10, refilled at 0.5 token/s, keyed on the client IP.
app.wsgi_app = WSGIRateLimitMiddleware(app.wsgi_app, capacity=10, refill_rate=0.5)
```

For Django, wrap the callable in your WSGI entry point:

```python
application = WSGIRateLimitMiddleware(get_wsgi_application(), capacity=100, refill_rate=2)
```

## Responses

| Situation | Status | Headers |
| --- | --- | --- |
| Request allowed | untouched | `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` |
| Request rejected | `429 Too Many Requests` | the three above **+** `Retry-After` (whole seconds) |

```http
HTTP/1.1 429 Too Many Requests
RateLimit-Limit: 60
RateLimit-Remaining: 0
RateLimit-Reset: 1
Retry-After: 1
Content-Type: application/json

{"error":"rate limit exceeded"}
```

## Configuration

Both middlewares accept the same keyword arguments:

| Argument | Default | Meaning |
| --- | --- | --- |
| `limiter` | built from `capacity`/`refill_rate` | A ready-made `RateLimiter` (share one instance across middlewares) |
| `capacity` | `60` | Burst size: the maximum number of tokens in the bucket |
| `refill_rate` | `capacity / 60` | Tokens per second (so the default is “60 per minute”) |
| `key_func` | client IP | `scope -> str` for ASGI, `environ -> str` for WSGI |
| `trust_forwarded_for` | `False` | Key on `X-Forwarded-For` instead of the socket peer |
| `cost` | `1.0` | Tokens charged per request (cheap vs. expensive endpoints) |
| `exempt_paths` | `()` | Paths that never consume a token (`/health`, `/metrics`) |
| `body` / `content_type` / `status` | JSON `429` | Customise the rejection response |

A shared limiter lets several routes (or several middlewares) draw from the same
budget:

```python
limiter = RateLimiter(capacity=100, refill_rate=5)
app = ASGIRateLimitMiddleware(app, limiter=limiter)
```

Charge expensive endpoints more:

```python
cost = 10 if request.url.path.startswith("/reports") else 1
decision = limiter.check(client_ip, cost=cost)
```

## How the token bucket works

The bucket holds at most `capacity` tokens and gains `refill_rate` tokens per
second. A request spends `cost` tokens when enough are available; otherwise it is
rejected and told how long to wait:

```
retry_after = (cost - tokens) / refill_rate     # seconds until it fits
```

* `capacity=60, refill_rate=1` → a burst of 60, then a steady 1 req/s.
* `capacity=1, refill_rate=0.2` → a strict one request every 5 seconds.

The clock is `time.monotonic`, so it never jumps backwards when the wall clock
is adjusted, and no call ever blocks: callers are told *when* to retry instead of
being put to sleep.

## The Redis backend (multi-process)

The in-memory backend is per process. When several workers (gunicorn, uvicorn
`--workers`, Kubernetes replicas…) must share one budget, use `RedisBackend`. The
whole read-refill-decide-write cycle runs as a single Lua script executed **on
the Redis server**, using the server’s own clock, so it is atomic and immune to
clock skew between pods:

```python
from rate_limiter import RateLimiter, RedisBackend, ASGIRateLimitMiddleware

backend = RedisBackend("redis://localhost:6379/0", capacity=100, refill_rate=10)
app = ASGIRateLimitMiddleware(app, limiter=RateLimiter(capacity=100, refill_rate=10, backend=backend))
```

Idle buckets expire on their own (TTL = time to refill from empty), so the key
space does not grow without bound.

## Security notes

* **`X-Forwarded-For` is opt-in.** A client can forge that header, so it is only
  trusted when you set `trust_forwarded_for=True` — i.e. when you *know* a
  reverse proxy strips and sets it.
* **The in-memory backend is LRU-bounded** (`max_keys`, default 10 000) so a
  flood of spoofed IPs cannot exhaust memory.
* **The Redis script never trusts the client clock**, which is what makes the
  distributed limiter correct across machines.

## Architecture

```
rate_limiter/
  bucket.py         TokenBucket — the thread-safe token-bucket primitive
  models.py         Decision + RateLimit-* / Retry-After headers
  keys.py           client key extraction (ASGI scope, WSGI environ, XFF)
  backend.py        RateLimitBackend protocol + InMemoryBackend (LRU)
  redis_backend.py  RedisBackend — atomic Lua token bucket (optional)
  limiter.py        RateLimiter — policy + backend
  asgi.py           ASGIRateLimitMiddleware  (plain ASGI 3)
  wsgi.py           WSGIRateLimitMiddleware  (plain WSGI)
```

## Tests

```bash
pip install -e ".[dev]"
python -m pytest --cov=rate_limiter --cov-report=term-missing
```

The suite is standard-library only: the ASGI and WSGI middlewares are driven by
tiny in-repo servers, and the token bucket is tested with an injected clock (no
`sleep`). The Redis tests run only when `RATE_LIMITER_REDIS_URL` is set, and are
skipped otherwise. `examples/demo_stdlib.py` is a runnable, dependency-free demo:

```bash
python examples/demo_stdlib.py
```

## License

[MIT](LICENSE) © 2026 Believe.

