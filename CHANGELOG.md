# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-01

### Added

* **`TokenBucket`** — a thread-safe, monotonic token-bucket primitive
  (`capacity` = burst size, `refill_rate` = tokens/second). `consume` is atomic
  and never blocks: it reports whether the request is allowed and, when it is
  not, the `retry_after` delay.
* **`RateLimiter`** — the policy facade (`capacity`, `refill_rate`,
  `default_cost`, pluggable `backend`). Default policy is "`capacity` requests
  per minute".
* **`ASGIRateLimitMiddleware`** — plain ASGI 3 middleware (works with FastAPI,
  Starlette, Quart, …) that answers rejected requests with `429` and adds the
  `RateLimit-*` headers to successful ones.
* **`WSGIRateLimitMiddleware`** — plain WSGI middleware (Flask, Django, …) with
  the same behaviour.
* **Backends** — `InMemoryBackend` (per-process, LRU-bounded) and, optionally,
  `RedisBackend` (shared across processes, atomic Lua token bucket using the
  Redis server clock).
* **Key extraction** — client IP from an ASGI scope or a WSGI environ, with
  opt-in `X-Forwarded-For` support.
* **Headers** — `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`
  (IETF draft) and `Retry-After` on rejections.
* 49 standard-library tests (1 optional Redis test), a GitHub Actions workflow
  running them on Linux and Windows with Python 3.9, 3.12 and 3.13, and a
  dependency-free demo (`examples/demo_stdlib.py`).

### Security

* `X-Forwarded-For` is never trusted by default: a forged header would let any
  client pick someone else's bucket.
* The in-memory backend is bounded (`max_keys`) and the Redis backend expires
  idle keys, so neither can be turned into an unbounded memory sink.

[1.0.0]: https://github.com/Believe-sec-io/api-rate-limiter-middleware/releases/tag/v1.0.0
