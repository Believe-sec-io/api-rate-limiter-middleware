"""Storage backends: where the buckets live and how a decision is produced.

A backend turns ``(key, cost)`` into a :class:`~rate_limiter.models.Decision`.
The in-memory backend keeps one :class:`~rate_limiter.bucket.TokenBucket` per key
and evicts the least recently used ones; :class:`~rate_limiter.redis_backend.RedisBackend`
implements the same contract for several processes.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import List, Protocol, runtime_checkable

from .bucket import BucketState, TimeSource, TokenBucket
from .models import Decision


@runtime_checkable
class RateLimitBackend(Protocol):
    """The contract every backend must satisfy."""

    def consume(self, key: str, cost: float = 1.0) -> Decision:
        """Spend ``cost`` tokens for ``key`` and return the decision."""

    def peek(self, key: str, cost: float = 1.0) -> Decision:
        """Return what :meth:`consume` would decide, without spending tokens."""

    def close(self) -> None:
        """Release any resource held by the backend."""


def _to_decision(key: str, state: BucketState) -> Decision:
    """Adapt a :class:`BucketState` to the public :class:`Decision`."""
    return Decision(
        allowed=state.allowed,
        key=key,
        limit=int(state.limit),
        remaining=int(state.remaining),
        retry_after=state.retry_after,
        reset_after=state.reset_after,
    )


class InMemoryBackend:
    """Per-process backend backed by an LRU map of token buckets."""

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        *,
        max_keys: int = 10_000,
        time_source: TimeSource = time.monotonic,
    ) -> None:
        if max_keys <= 0:
            raise ValueError("max_keys must be greater than 0")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.max_keys = int(max_keys)
        self._now = time_source
        self._buckets: "OrderedDict[str, TokenBucket]" = OrderedDict()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------- intern
    def _bucket(self, key: str) -> TokenBucket:
        """Return the bucket of ``key``, creating it and evicting if needed.

        The caller must hold :attr:`_lock`.
        """
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(self.capacity, self.refill_rate, time_source=self._now)
            self._buckets[key] = bucket
        else:
            self._buckets.move_to_end(key)
        while len(self._buckets) > self.max_keys:
            self._buckets.popitem(last=False)
        return bucket

    # ------------------------------------------------------------------ public
    def consume(self, key: str, cost: float = 1.0) -> Decision:
        if cost <= 0:
            raise ValueError("cost must be greater than 0")
        with self._lock:
            bucket = self._bucket(key)
        return _to_decision(key, bucket.consume(cost))

    def peek(self, key: str, cost: float = 1.0) -> Decision:
        if cost <= 0:
            raise ValueError("cost must be greater than 0")
        with self._lock:
            bucket = self._buckets.get(key)
        if bucket is None:
            full = int(self.capacity)
            return Decision(True, key, full, full, 0.0, 0.0)
        return _to_decision(key, bucket.peek(cost))

    def keys(self) -> List[str]:
        """Current keys, most recently used last (introspection/testing)."""
        with self._lock:
            return list(self._buckets)

    def close(self) -> None:
        with self._lock:
            self._buckets.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buckets)


__all__ = ["InMemoryBackend", "RateLimitBackend"]
