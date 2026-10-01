"""Public result type of a rate-limit decision, and its HTTP representation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

#: Header names advertised by the middleware (IETF ``RateLimit`` fields draft).
LIMIT_HEADER = "RateLimit-Limit"
REMAINING_HEADER = "RateLimit-Remaining"
RESET_HEADER = "RateLimit-Reset"
RETRY_AFTER_HEADER = "Retry-After"

#: Default body returned by the middlewares when a request is rejected.
DEFAULT_REJECTION_BODY = b'{"error":"rate limit exceeded"}'


@dataclass(frozen=True)
class Decision:
    """The verdict for one request against one bucket.

    ``limit`` and ``remaining`` are whole tokens because they end up in HTTP
    headers; ``retry_after`` / ``reset_after`` are floats in seconds so callers
    can sleep with the precision the token bucket actually has.
    """

    allowed: bool
    key: str
    limit: int
    remaining: int
    retry_after: float
    reset_after: float

    @property
    def blocked(self) -> bool:
        """Convenience negation of :attr:`allowed`."""
        return not self.allowed

    def as_headers(self, *, retry_after: bool = True) -> Dict[str, str]:
        """Render the decision as response headers.

        ``RateLimit-*`` are always present; ``Retry-After`` is only meaningful
        on a rejection, so it is added there and only there.
        """
        headers = {
            LIMIT_HEADER: str(self.limit),
            REMAINING_HEADER: str(self.remaining),
            RESET_HEADER: str(max(0, int(math.ceil(self.reset_after)))),
        }
        if retry_after and not self.allowed:
            headers[RETRY_AFTER_HEADER] = str(max(1, int(math.ceil(self.retry_after))))
        return headers


__all__ = [
    "DEFAULT_REJECTION_BODY",
    "LIMIT_HEADER",
    "REMAINING_HEADER",
    "RESET_HEADER",
    "RETRY_AFTER_HEADER",
    "Decision",
]
