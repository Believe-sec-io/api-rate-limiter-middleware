"""Extraction of the rate-limit key from an ASGI scope or a WSGI environ.

Everything keys on the client identity. Behind a reverse proxy the socket peer
is the proxy, so the real client is only available through ``X-Forwarded-For``.
Trusting that header is a security decision: it is opt-in
(``trust_forwarded_for=True``) because a client can forge it when the app is
reachable directly.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, MutableMapping

UNKNOWN_CLIENT = "unknown"


def _first_hop(value: str) -> str:
    """Return the left-most address of a comma separated forwarding chain."""
    return value.split(",")[0].strip()


def client_ip_from_scope(
    scope: Mapping[str, Any], *, trust_forwarded_for: bool = False
) -> str:
    """Client address of an ASGI ``scope`` (``http``)."""
    if trust_forwarded_for:
        for name, value in scope.get("headers") or ():
            if name == b"x-forwarded-for":
                ip = _first_hop(value.decode("latin-1"))
                if ip:
                    return ip
    client = scope.get("client")
    if client:
        return str(client[0])
    return UNKNOWN_CLIENT


def client_ip_from_environ(
    environ: MutableMapping[str, Any], *, trust_forwarded_for: bool = False
) -> str:
    """Client address of a WSGI ``environ``."""
    if trust_forwarded_for:
        ip = _first_hop(str(environ.get("HTTP_X_FORWARDED_FOR", "")))
        if ip:
            return ip
    return str(environ.get("REMOTE_ADDR") or UNKNOWN_CLIENT)


def asgi_key_func(
    *, trust_forwarded_for: bool = False
) -> Callable[[Mapping[str, Any]], str]:
    """Build a ``scope -> key`` callable for the ASGI middleware."""

    def key(scope: Mapping[str, Any]) -> str:
        return client_ip_from_scope(scope, trust_forwarded_for=trust_forwarded_for)

    return key


def wsgi_key_func(
    *, trust_forwarded_for: bool = False
) -> Callable[[MutableMapping[str, Any]], str]:
    """Build an ``environ -> key`` callable for the WSGI middleware."""

    def key(environ: MutableMapping[str, Any]) -> str:
        return client_ip_from_environ(environ, trust_forwarded_for=trust_forwarded_for)

    return key


__all__ = [
    "UNKNOWN_CLIENT",
    "asgi_key_func",
    "client_ip_from_environ",
    "client_ip_from_scope",
    "wsgi_key_func",
]
