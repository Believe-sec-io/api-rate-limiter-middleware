#!/usr/bin/env python3
"""Dependency-free demo of the token bucket: no framework, no HTTP server.

Run it directly::

    python examples/demo_stdlib.py

It shows a burst being absorbed, then a request being rejected with the delay to
wait, then the bucket refilling.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rate_limiter import RateLimiter  # noqa: E402  (after sys.path tweak)


def main() -> int:
    limiter = RateLimiter(capacity=5, refill_rate=1.0)  # burst 5, then 1/s
    print(
        f"policy: burst={limiter.capacity:.0f}, "
        f"sustained={limiter.refill_rate:.1f} token/s, key=203.0.113.7\n"
    )
    print(f"{'#':>2}  {'decision':<8} {'remaining':>9} {'retry-after':>12}")
    print("-" * 36)
    for index in range(1, 9):
        decision = limiter.check("203.0.113.7")
        verdict = "allow" if decision.allowed else "block"
        retry = "-" if decision.allowed else f"{decision.retry_after:.2f}s"
        print(f"{index:>2}  {verdict:<8} {decision.remaining:>9} {retry:>12}")
        if index == 6:
            print("\n... sleeping 2 seconds so two tokens come back ...\n")
            time.sleep(2)
    limiter.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
