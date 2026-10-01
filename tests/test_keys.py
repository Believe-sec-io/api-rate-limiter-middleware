"""Tests of the client-key extraction helpers."""

from __future__ import annotations

from rate_limiter import (
    asgi_key_func,
    client_ip_from_environ,
    client_ip_from_scope,
    wsgi_key_func,
)

FORWARDED = (b"x-forwarded-for", b"203.0.113.7, 10.0.0.1")


def test_scope_prefers_the_socket_client():
    scope = {"client": ("198.51.100.9", 5555), "headers": []}
    assert client_ip_from_scope(scope) == "198.51.100.9"


def test_scope_ignores_x_forwarded_for_by_default():
    scope = {"client": ("198.51.100.9", 1), "headers": [FORWARDED]}
    assert client_ip_from_scope(scope) == "198.51.100.9"


def test_scope_trusts_x_forwarded_for_first_hop():
    scope = {"client": ("198.51.100.9", 1), "headers": [FORWARDED]}
    assert client_ip_from_scope(scope, trust_forwarded_for=True) == "203.0.113.7"


def test_scope_without_client_is_unknown():
    assert client_ip_from_scope({"headers": []}) == "unknown"


def test_environ_uses_remote_addr():
    assert client_ip_from_environ({"REMOTE_ADDR": "10.1.2.3"}) == "10.1.2.3"


def test_environ_trusts_x_forwarded_for():
    environ = {"REMOTE_ADDR": "10.0.0.1", "HTTP_X_FORWARDED_FOR": "203.0.113.7, 10.0.0.1"}
    assert client_ip_from_environ(environ, trust_forwarded_for=True) == "203.0.113.7"


def test_environ_without_address_is_unknown():
    assert client_ip_from_environ({}) == "unknown"


def test_key_func_factories():
    assert asgi_key_func()({"client": ("1.1.1.1", 0), "headers": []}) == "1.1.1.1"
    assert wsgi_key_func()({"REMOTE_ADDR": "2.2.2.2"}) == "2.2.2.2"
    assert asgi_key_func(trust_forwarded_for=True)(
        {"client": ("1.1.1.1", 0), "headers": [FORWARDED]}
    ) == "203.0.113.7"
