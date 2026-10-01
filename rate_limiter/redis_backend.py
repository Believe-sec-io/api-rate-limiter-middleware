"""Optional Redis backend: a shared token bucket evaluated server side.

Several application processes must share one counter, so the whole
read-refill-decide-write cycle has to be atomic and must not trust the client
clock. It is therefore implemented as a single Lua script executed by Redis,
which uses the server's own ``TIME``. This is the standard way to build a
distributed rate limiter without a race.

Requires the optional dependency::

    pip install api-rate-limiter-middleware[redis]
"""

from __future__ import annotations

import math
from typing import Any, Optional

from .models import Decision

#: Atomic "refill then consume" evaluation. Returns
#: [allowed, tokens, retry_after, reset_after, capacity].
_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local now = redis.call('TIME')
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  ts = now_ms
end

local elapsed = now_ms - ts
if elapsed < 0 then elapsed = 0 end
tokens = math.min(capacity, tokens + (elapsed / 1000.0) * refill)

local allowed = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
end

local retry = 0
if allowed == 0 then
  retry = (cost - tokens) / refill
end
local reset = (capacity - tokens) / refill

redis.call('HSET', key, 'tokens', tostring(tokens), 'ts', tostring(now_ms))
redis.call('PEXPIRE', key, ttl)
return {allowed, tostring(tokens), tostring(retry), tostring(reset), tostring(capacity)}
"""


class RedisBackend:
    """Token-bucket backend shared by every process talking to the same Redis."""

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        *,
        capacity: float,
        refill_rate: float,
        prefix: str = "rate-limit:",
        ttl: Optional[float] = None,
        client: Any = None,
    ) -> None:
        try:
            import redis  # noqa: F401  (imported for the default client only)
        except ImportError as error:  # pragma: no cover - depends on environment
            raise ImportError(
                "the 'redis' package is required for RedisBackend: "
                "pip install api-rate-limiter-middleware[redis]"
            ) from error
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be greater than 0")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.prefix = prefix
        #: Idle buckets expire once the bucket would be full again, so a scan of
        #: the keyspace never grows without bound.
        default_ttl = math.ceil(self.capacity / self.refill_rate) + 1.0
        self.ttl_ms = int(round((ttl if ttl is not None else default_ttl) * 1000))
        if self.ttl_ms <= 0:
            raise ValueError("ttl must be greater than 0")
        self._client = client or redis.Redis.from_url(url, decode_responses=True)
        self._script = self._client.register_script(_SCRIPT)

    def _run(self, key: str, cost: float) -> Decision:
        raw = self._script(
            keys=[f"{self.prefix}{key}"],
            args=[self.capacity, self.refill_rate, cost, self.ttl_ms],
        )
        allowed, tokens, retry, reset, capacity = raw
        return Decision(
            allowed=bool(int(allowed)),
            key=key,
            limit=int(float(capacity)),
            remaining=int(float(tokens)),
            retry_after=float(retry),
            reset_after=float(reset),
        )

    def consume(self, key: str, cost: float = 1.0) -> Decision:
        if cost <= 0:
            raise ValueError("cost must be greater than 0")
        return self._run(key, cost)

    def peek(self, key: str, cost: float = 1.0) -> Decision:
        if cost <= 0:
            raise ValueError("cost must be greater than 0")
        return self._run(key, 0.0)

    def reset(self, key: str) -> None:
        """Forget the bucket of ``key`` (administrative helper)."""
        self._client.delete(f"{self.prefix}{key}")

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):  # pragma: no cover - client dependant
            close()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"RedisBackend(capacity={self.capacity}, refill_rate={self.refill_rate})"


__all__ = ["RedisBackend"]
