"""Tests of the optional Redis backend.

They only run when Redis is reachable: set ``RATE_LIMITER_REDIS_URL`` (for
example ``redis://localhost:6379/15``) and install the extra
(``pip install .[redis]``). Otherwise the whole module is skipped, so the
default ``pytest`` run stays dependency-free.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("redis", reason="the optional 'redis' package is not installed")
pytestmark = pytest.mark.skipif(
    not os.environ.get("RATE_LIMITER_REDIS_URL"),
    reason="set RATE_LIMITER_REDIS_URL to run the Redis integration tests",
)

from rate_limiter import RedisBackend  # noqa: E402  (after the skip guards)

URL = os.environ.get("RATE_LIMITER_REDIS_URL", "redis://localhost:6379/15")


def _backend(capacity: float = 2, refill_rate: float = 1.0) -> RedisBackend:
    return RedisBackend(URL, capacity=capacity, refill_rate=refill_rate,
                        prefix="pytest-rate-limit:")


def test_consume_then_block():
    backend = _backend()
    backend.reset("client")
    try:
        assert backend.consume("client").allowed is True
        assert backend.consume("client").allowed is True
        assert backend.consume("client").blocked is True
        assert backend.peek("client").blocked is True
    finally:
        backend.reset("client")
        backend.close()


def test_keys_are_isolated():
    backend = _backend()
    backend.reset("a")
    backend.reset("b")
    try:
        assert backend.consume("a").allowed is True
        assert backend.consume("a").allowed is True
        assert backend.consume("a").blocked is True
        assert backend.consume("b").allowed is True
    finally:
        backend.reset("a")
        backend.reset("b")
        backend.close()


def test_invalid_arguments():
    with pytest.raises(ValueError):
        RedisBackend(URL, capacity=0, refill_rate=1)
    with pytest.raises(ValueError):
        RedisBackend(URL, capacity=1, refill_rate=1).consume("a", 0)
