"""Tests of the Decision HTTP representation."""

from __future__ import annotations

from rate_limiter import Decision
from rate_limiter.models import (
    LIMIT_HEADER,
    REMAINING_HEADER,
    RESET_HEADER,
    RETRY_AFTER_HEADER,
)


def test_allowed_decision_headers():
    decision = Decision(allowed=True, key="k", limit=10, remaining=4,
                        retry_after=0.0, reset_after=3.2)
    headers = decision.as_headers()
    assert headers[LIMIT_HEADER] == "10"
    assert headers[REMAINING_HEADER] == "4"
    assert headers[RESET_HEADER] == "4"  # ceil(3.2)
    assert RETRY_AFTER_HEADER not in headers
    assert decision.blocked is False


def test_blocked_decision_has_retry_after():
    decision = Decision(allowed=False, key="k", limit=10, remaining=0,
                        retry_after=2.5, reset_after=6.0)
    headers = decision.as_headers()
    assert headers[RETRY_AFTER_HEADER] == "3"  # ceil(2.5)
    assert decision.blocked is True


def test_retry_after_can_be_suppressed():
    decision = Decision(allowed=False, key="k", limit=1, remaining=0,
                        retry_after=1.0, reset_after=1.0)
    assert RETRY_AFTER_HEADER not in decision.as_headers(retry_after=False)


def test_retry_after_is_at_least_one_second():
    decision = Decision(allowed=False, key="k", limit=1, remaining=0,
                        retry_after=0.2, reset_after=0.2)
    assert decision.as_headers()[RETRY_AFTER_HEADER] == "1"
