"""The token-bucket primitive: a thread-safe, monotonic, dependency-free core.

A bucket starts full (``capacity`` tokens) and refills continuously at
``refill_rate`` tokens per second, never exceeding ``capacity``. ``capacity`` is
therefore the burst size and ``refill_rate`` the sustained throughput:
``capacity=60, refill_rate=1`` allows a burst of 60 requests and then one request
per second.

The bucket never sleeps and never blocks: it only reports whether a request is
allowed *now* and, when it is not, how long the caller should wait. That is what
makes it a building block for both middlewares and for a distributed backend.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

#: A monotonic clock. Injectable so the tests never depend on wall-clock time.
TimeSource = Callable[[], float]


@dataclass(frozen=True)
class BucketState:
    """Outcome of a (possibly hypothetical) consumption."""

    allowed: bool
    limit: float
    remaining: float
    #: Seconds to wait before ``cost`` tokens are available (``0`` when allowed).
    retry_after: float
    #: Seconds until the bucket is full again.
    reset_after: float


class TokenBucket:
    """A single token bucket, safe to share between threads."""

    __slots__ = ("_capacity", "_refill_rate", "_tokens", "_updated", "_lock", "_now")

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        *,
        initial_tokens: float = None,  # type: ignore[assignment]
        time_source: TimeSource = time.monotonic,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be greater than 0")
        self._capacity = float(capacity)
        self._refill_rate = float(refill_rate)
        self._now = time_source
        start = self._capacity if initial_tokens is None else min(float(initial_tokens), self._capacity)
        if start < 0:
            raise ValueError("initial_tokens must not be negative")
        self._tokens = start
        self._updated = self._now()
        self._lock = threading.Lock()

    # --------------------------------------------------------------- properties
    @property
    def capacity(self) -> float:
        """Maximum number of tokens the bucket can hold (the burst size)."""
        return self._capacity

    @property
    def refill_rate(self) -> float:
        """Tokens added per second (the sustained rate)."""
        return self._refill_rate

    # ------------------------------------------------------------------- intern
    def _accrue(self, now: float) -> None:
        """Add the tokens earned since the last update (caller holds the lock)."""
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
            self._updated = now

    def _state(self, allowed: bool, cost: float) -> BucketState:
        missing = max(0.0, cost - self._tokens)
        retry_after = 0.0 if allowed else missing / self._refill_rate
        reset_after = (self._capacity - self._tokens) / self._refill_rate
        return BucketState(
            allowed=allowed,
            limit=self._capacity,
            remaining=self._tokens,
            retry_after=retry_after,
            reset_after=reset_after,
        )

    # ------------------------------------------------------------------ public
    def consume(self, cost: float = 1.0) -> BucketState:
        """Try to take ``cost`` tokens atomically and report the outcome."""
        if cost <= 0:
            raise ValueError("cost must be greater than 0")
        with self._lock:
            now = self._now()
            self._accrue(now)
            allowed = self._tokens >= cost
            if allowed:
                self._tokens -= cost
            return self._state(allowed, cost)

    def peek(self, cost: float = 1.0) -> BucketState:
        """Report what :meth:`consume` would do, without spending any token."""
        if cost <= 0:
            raise ValueError("cost must be greater than 0")
        with self._lock:
            now = self._now()
            self._accrue(now)
            return self._state(self._tokens >= cost, cost)

    def refill(self, tokens: float) -> None:
        """Add ``tokens`` explicitly (used by tests and administrative credits)."""
        with self._lock:
            self._accrue(self._now())
            self._tokens = min(self._capacity, self._tokens + max(0.0, tokens))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"TokenBucket(capacity={self._capacity}, refill_rate={self._refill_rate}, "
            f"tokens={self._tokens:.3f})"
        )


__all__ = ["BucketState", "TokenBucket", "TimeSource"]
