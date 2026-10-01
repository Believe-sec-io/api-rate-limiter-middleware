"""Tests of the token-bucket primitive."""

from __future__ import annotations

import threading

import pytest

from helpers import FakeClock
from rate_limiter import TokenBucket


def test_starts_full():
    bucket = TokenBucket(5, 1, time_source=FakeClock())
    assert bucket.consume(5).allowed is True
    assert bucket.consume(1).allowed is False


def test_capacity_is_the_burst_size():
    bucket = TokenBucket(3, 1, time_source=FakeClock())
    allowed = [bucket.consume().allowed for _ in range(4)]
    assert allowed == [True, True, True, False]


def test_refill_over_time_and_cap():
    clock = FakeClock()
    bucket = TokenBucket(3, 1, time_source=clock)  # one token per second
    for _ in range(3):
        assert bucket.consume().allowed
    assert bucket.consume().allowed is False

    clock.advance(1)
    assert bucket.consume().allowed is True

    clock.advance(100)
    assert bucket.peek().remaining == 3  # never exceeds capacity


def test_retry_after_is_reported():
    clock = FakeClock()
    bucket = TokenBucket(1, 0.5, time_source=clock)  # one token every 2 seconds
    assert bucket.consume().allowed is True

    blocked = bucket.consume()
    assert blocked.allowed is False
    assert blocked.retry_after == pytest.approx(2.0)

    clock.advance(2)
    assert bucket.consume().allowed is True


def test_reset_after_counts_until_full():
    clock = FakeClock()
    bucket = TokenBucket(4, 1, time_source=clock)
    bucket.consume(3)
    assert bucket.peek(0.0 + 1).reset_after == pytest.approx(3.0)


def test_peek_does_not_spend_tokens():
    bucket = TokenBucket(2, 1, time_source=FakeClock())
    assert bucket.peek().remaining == 2
    assert bucket.peek().remaining == 2
    assert bucket.consume().remaining == 1


def test_cost_greater_than_one():
    bucket = TokenBucket(10, 1, time_source=FakeClock())
    assert bucket.consume(4).remaining == 6
    assert bucket.consume(7).allowed is False


def test_initial_tokens_and_refill_helper():
    bucket = TokenBucket(5, 1, initial_tokens=0, time_source=FakeClock())
    assert bucket.consume().allowed is False
    bucket.refill(2)
    assert bucket.consume().remaining == 1


def test_invalid_arguments():
    with pytest.raises(ValueError):
        TokenBucket(0, 1)
    with pytest.raises(ValueError):
        TokenBucket(1, 0)
    with pytest.raises(ValueError):
        TokenBucket(1, 1, initial_tokens=-1)
    bucket = TokenBucket(1, 1, time_source=FakeClock())
    with pytest.raises(ValueError):
        bucket.consume(0)


def test_thread_safety_never_overspends():
    # A frozen clock means no token is ever refilled during the test.
    bucket = TokenBucket(100, 1e-9, time_source=FakeClock())
    granted = []
    lock = threading.Lock()

    def worker() -> None:
        allowed = bucket.consume().allowed
        with lock:
            granted.append(allowed)

    threads = [threading.Thread(target=worker) for _ in range(250)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(granted) == 100
