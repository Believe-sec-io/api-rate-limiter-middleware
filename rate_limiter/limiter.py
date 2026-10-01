"""The :class:`RateLimiter` binds a policy (capacity, refill) to a backend."""

from __future__ import annotations

import time
from typing import Optional

from .backend import InMemoryBackend, RateLimitBackend
from .bucket import TimeSource
from .models import Decision

#: Requests allowed in a burst when neither ``capacity`` nor ``refill_rate`` is set.
DEFAULT_CAPACITY = 60

#: Window used to derive the refill rate from the capacity (60 requests / minute).
DEFAULT_WINDOW_SECONDS = 60.0


class RateLimiter:
    """A ready-to-use limiter: pick a policy, get a backend for free.

    ``capacity`` is the burst size and ``refill_rate`` the sustained rate
    (tokens per second). When ``refill_rate`` is omitted it is derived so that
    ``capacity`` tokens are refilled every ``DEFAULT_WINDOW_SECONDS`` seconds,
    i.e. the familiar "60 requests per minute".
    """

    def __init__(
        self,
        *,
        capacity: float = DEFAULT_CAPACITY,
        refill_rate: Optional[float] = None,
        backend: Optional[RateLimitBackend] = None,
        max_keys: int = 10_000,
        default_cost: float = 1.0,
        time_source: TimeSource = time.monotonic,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        if refill_rate is None:
            refill_rate = capacity / DEFAULT_WINDOW_SECONDS
        if refill_rate <= 0:
            raise ValueError("refill_rate must be greater than 0")
        if default_cost <= 0:
            raise ValueError("default_cost must be greater than 0")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.default_cost = float(default_cost)
        self._backend: RateLimitBackend = backend or InMemoryBackend(
            self.capacity,
            self.refill_rate,
            max_keys=max_keys,
            time_source=time_source,
        )

    def check(self, key: str, cost: Optional[float] = None) -> Decision:
        """Spend the request's cost for ``key`` and return the decision."""
        return self._backend.consume(str(key), self.default_cost if cost is None else cost)

    def peek(self, key: str, cost: Optional[float] = None) -> Decision:
        """Observe the state of ``key`` without spending anything."""
        return self._backend.peek(str(key), self.default_cost if cost is None else cost)

    def close(self) -> None:
        """Release the backend (a no-op for the in-memory one)."""
        self._backend.close()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"RateLimiter(capacity={self.capacity}, refill_rate={self.refill_rate}, "
            f"backend={type(self._backend).__name__})"
        )


__all__ = ["DEFAULT_CAPACITY", "DEFAULT_WINDOW_SECONDS", "RateLimiter"]
