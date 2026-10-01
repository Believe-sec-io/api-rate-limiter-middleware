"""Reference integration for Flask.

    pip install flask
    flask --app examples.flask_app run

Not imported by the test suite (it needs Flask installed); it is here as a
copy-paste starting point.
"""

from __future__ import annotations

from flask import Flask, jsonify

from rate_limiter import RateLimiter, WSGIRateLimitMiddleware

app = Flask(__name__)

#: A burst of 50, then 5 requests/second per client IP.
limiter = RateLimiter(capacity=50, refill_rate=5)
app.wsgi_app = WSGIRateLimitMiddleware(app.wsgi_app, limiter=limiter, exempt_paths={"/health"})


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/")
def index():
    return jsonify(ok=True)
