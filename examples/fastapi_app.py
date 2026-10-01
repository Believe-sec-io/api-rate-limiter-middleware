"""Reference integration for FastAPI / Starlette.

Install a framework, then::

    pip install fastapi uvicorn
    uvicorn examples.fastapi_app:app --reload

Not imported by the test suite (it needs FastAPI installed); it is here as a
copy-paste starting point.
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from rate_limiter import ASGIRateLimitMiddleware, RateLimiter

app = FastAPI(title="rate-limited API")

#: One shared limiter: a burst of 100, then 10 requests/second per client IP.
limiter = RateLimiter(capacity=100, refill_rate=10)
app = ASGIRateLimitMiddleware(app, limiter=limiter, exempt_paths={"/health"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def index(request: Request) -> dict:
    client = request.client.host if request.client else "unknown"
    return {"ok": True, "remaining": limiter.peek(client).remaining}
