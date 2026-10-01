"""Shared test helpers: a controllable clock and tiny ASGI/WSGI drivers.

No web framework and no HTTP client is used, so the suite stays standard-library
only and runs anywhere.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


class FakeClock:
    """A monotonic clock the tests move by hand."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


async def noop(*_args: Any, **_kwargs: Any) -> None:
    """An awaitable that does nothing (used as receive/send in ASGI tests)."""
    return None


# --------------------------------------------------------------------- ASGI
def make_asgi_app(
    status: int = 200,
    payload: bytes = b"ok",
    headers: Sequence[Tuple[bytes, bytes]] = (),
):
    """Build a minimal ASGI application."""

    async def app(scope: Mapping[str, Any], receive, send) -> None:
        await send({"type": "http.response.start", "status": status, "headers": list(headers)})
        await send({"type": "http.response.body", "body": payload})

    return app


def http_scope(
    path: str = "/",
    client: Tuple[str, int] = ("1.2.3.4", 1234),
    headers: Iterable[Tuple[bytes, bytes]] = (),
    method: str = "GET",
) -> Dict[str, Any]:
    """Build an ASGI ``http`` scope."""
    return {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": list(headers),
        "client": client,
        "server": ("testserver", 80),
        "scheme": "http",
    }


def run_asgi(app, scope: Mapping[str, Any], body: bytes = b"") -> List[Mapping[str, Any]]:
    """Drive an ASGI app once and return every message it sent."""
    messages: List[Mapping[str, Any]] = []
    state = {"consumed": False}

    async def receive() -> Mapping[str, Any]:
        if not state["consumed"]:
            state["consumed"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: Mapping[str, Any]) -> None:
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    return messages


# --------------------------------------------------------------------- WSGI
def make_wsgi_app(
    status: str = "200 OK",
    payload: bytes = b"ok",
    headers: Sequence[Tuple[str, str]] = (("Content-Type", "text/plain"),),
):
    """Build a minimal WSGI application."""

    def app(environ: Mapping[str, Any], start_response):
        start_response(status, list(headers))
        return [payload]

    return app


def wsgi_environ(path: str = "/", remote: str = "1.2.3.4", **extra: Any) -> Dict[str, Any]:
    """Build a WSGI ``environ``."""
    environ: Dict[str, Any] = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "REMOTE_ADDR": remote,
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.input": None,
    }
    environ.update(extra)
    return environ


def run_wsgi(app, environ: Mapping[str, Any]) -> Tuple[str, List[Tuple[str, str]], bytes]:
    """Drive a WSGI app once and return ``(status, headers, body)``."""
    captured: Dict[str, Any] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = list(headers)
        return lambda _data: None

    body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], body


# ------------------------------------------------------------------ helpers
def header_value(headers: Iterable[Tuple[Any, Any]], name: str) -> Any:
    """Case-insensitive header lookup, accepting ``bytes`` or ``str`` names."""
    wanted = name.lower()
    for key, value in headers:
        key_str = key.decode("latin-1") if isinstance(key, bytes) else key
        value_str = value.decode("latin-1") if isinstance(value, bytes) else value
        if key_str.lower() == wanted:
            return value_str
    return None
