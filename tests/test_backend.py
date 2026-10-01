"""Tests of the in-memory backend."""

from __future__ import annotations

import pytest

from helpers import FakeClock
from rate_limiter import InMemoryBackend, RateLimitBackend


def test_satisfies_the_backend_contract():
    assert isinstance(InMemoryBackend(5, 1), RateLimitBackend)


def test_keys_are_isolated():
    backend = InMemoryBackend(2, 1, time_source=FakeClock())
    assert backend.consume("a").allowed is True
    assert backend.consume("a").allowed is True
    assert backend.consume("a").allowed is False
    assert backend.consume("b").allowed is True


def test_lru_eviction_and_forgetting():
    backend = InMemoryBackend(1, 1, max_keys=2, time_source=FakeClock())
    backend.consume("a")
    backend.consume("b")
    backend.consume("c")  # evicts the least recently used key, "a"
    assert backend.keys() == ["b", "c"]
    assert len(backend) == 2
    # The evicted key starts from a full bucket again.
    assert backend.consume("a").allowed is True


def test_peek_of_unknown_key_is_full_and_creates_nothing():
    backend = InMemoryBackend(5, 1, time_source=FakeClock())
    decision = backend.peek("nobody")
    assert decision.allowed is True
    assert decision.remaining == 5
    assert backend.keys() == []


def test_peek_does_not_consume():
    backend = InMemoryBackend(2, 1, time_source=FakeClock())
    backend.peek("a")
    backend.peek("a")
    assert backend.consume("a").remaining == 1
    assert backend.consume("a").remaining == 0


def test_invalid_arguments():
    with pytest.raises(ValueError):
        InMemoryBackend(5, 1, max_keys=0)
    with pytest.raises(ValueError):
        InMemoryBackend(5, 1).consume("a", 0)
    with pytest.raises(ValueError):
        InMemoryBackend(5, 1).peek("a", -1)


def test_close_clears_everything():
    backend = InMemoryBackend(5, 1, time_source=FakeClock())
    backend.consume("a")
    backend.close()
    assert len(backend) == 0
