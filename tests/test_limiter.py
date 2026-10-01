"""Tests of the RateLimiter facade."""

from __future__ import annotations

import pytest

from helpers import FakeClock
from rate_limiter import RateLimiter


def test_default_refill_is_per_minute():
    limiter = RateLimiter(capacity=60)
    assert limiter.refill_rate == pytest.approx(1.0)


def test_check_consumes_and_reports():
    limiter = RateLimiter(capacity=2, refill_rate=1, time_source=FakeClock())
    assert limiter.check("a").allowed is True
    assert limiter.check("a").allowed is True
    assert limiter.check("a").blocked is True


def test_custom_default_cost_and_per_call_cost():
    limiter = RateLimiter(capacity=5, refill_rate=1, default_cost=2, time_source=FakeClock())
    assert limiter.check("a").remaining == 3  # cost 2 by default
    assert limiter.check("a", cost=3).remaining == 0
    assert limiter.check("a").blocked is True


def test_peek_does_not_consume():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    limiter.peek("a")
    assert limiter.check("a").allowed is True


def test_key_is_stringified():
    limiter = RateLimiter(capacity=1, refill_rate=1, time_source=FakeClock())
    assert limiter.check(42).key == "42"


def test_invalid_configuration():
    with pytest.raises(ValueError):
        RateLimiter(capacity=0)
    with pytest.raises(ValueError):
        RateLimiter(capacity=10, refill_rate=-1)
    with pytest.raises(ValueError):
        RateLimiter(capacity=10, default_cost=0)


def test_close_is_safe():
    limiter = RateLimiter(capacity=1, time_source=FakeClock())
    limiter.check("a")
    limiter.close()
