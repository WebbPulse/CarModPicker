"""The shutdown span flush webbpulse 0.22.0 installs is reachable on a built domain app.

CMP instruments conditionally inside `build_domain_app` rather than through
`webbpulse.http.create_app`, so the wrapper's reachability is a property of this
repo's own ordering: the lifespan has to be attached before `instrument_fastapi`
runs, and the middleware stack has to still be unbuilt. Driving a real ASGI
lifespan shutdown is what proves it, since a wrapper attached to the wrong object
still looks attached.
"""

from __future__ import annotations

import asyncio
from typing import Any, Iterator

import pytest

from app.composition import wiring
from app.composition.domains import DOMAINS

OTLP_ENDPOINT = "http://localhost:4318/v1/traces"


@pytest.fixture
def tracing_configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Put the builder on the branch that instruments, without exporting anything."""
    monkeypatch.setenv(wiring.OTLP_ENDPOINT_ENV, OTLP_ENDPOINT)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    monkeypatch.delenv("WEBBPULSE_OTEL_DISABLED", raising=False)
    monkeypatch.setattr(wiring, "_TRACING_CONFIGURED", True)
    yield


def _build(domain: str = "vehicles") -> Any:
    """One domain app with startup seeding stubbed out."""
    return wiring.build_domain_app(DOMAINS[domain], startup_tasks=lambda: None)


async def _drive_lifespan(app: Any) -> None:
    """Run the app's ASGI lifespan through startup and shutdown."""
    receive_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, str]:
        """Hand the protocol its next lifespan message."""
        return await receive_queue.get()

    async def send(message: dict[str, Any]) -> None:
        """Record what the protocol reports back."""
        sent.append(message)

    await receive_queue.put({"type": "lifespan.startup"})
    await receive_queue.put({"type": "lifespan.shutdown"})

    await app.router.lifespan({"type": "lifespan"}, receive, send)

    types = [message["type"] for message in sent]
    assert "lifespan.startup.complete" in types, sent
    assert "lifespan.shutdown.complete" in types, sent


def test_lifespan_shutdown_flushes_tracing_once(tracing_configured: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """An ASGI lifespan shutdown calls shutdown_tracing exactly once."""
    from webbpulse import otel

    calls: list[int | None] = []

    def record(timeout_millis: int | None = None) -> None:
        """Stand in for the real provider shutdown."""
        calls.append(timeout_millis)

    monkeypatch.setattr(otel, "shutdown_tracing", record)

    app = _build()
    assert app.router.lifespan_context.__qualname__.startswith("_wrap_lifespan_with_shutdown_flush"), (
        "the builder instrumented the app without wrapping its lifespan"
    )

    asyncio.run(_drive_lifespan(app))

    assert len(calls) == 1, f"expected one shutdown_tracing call, got {calls}"
    assert calls[0] == otel.resolve_shutdown_flush_timeout(None)


def test_an_uninstrumented_app_does_not_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    """With tracing unconfigured the builder leaves the lifespan alone."""
    from webbpulse import otel

    calls: list[int | None] = []
    monkeypatch.setattr(
        otel,
        "shutdown_tracing",
        lambda timeout_millis=None: calls.append(timeout_millis),
    )
    monkeypatch.setattr(wiring, "_TRACING_CONFIGURED", False)

    app = _build()
    assert not app.router.lifespan_context.__qualname__.startswith("_wrap_lifespan_with_shutdown_flush")

    asyncio.run(_drive_lifespan(app))

    assert calls == [], "an uninstrumented app shut tracing down anyway"


def test_the_flush_runs_after_the_apps_own_shutdown(tracing_configured: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """The flush happens after the app's own lifespan exit, not before it.

    Ordered from inside the builder's own lifespan rather than by re-wrapping the
    instrumented context, which would nest the observer on the wrong side.
    """
    from webbpulse import otel

    order: list[str] = []

    def check_signing_key(domains: Any) -> None:
        """Stand in for the real check and mark the app's lifespan entry."""
        order.append("app-startup")

    monkeypatch.setattr(wiring, "check_signing_key", check_signing_key)
    monkeypatch.setattr(wiring.settings, "RUN_STARTUP_TASKS", False, raising=False)

    def record(timeout_millis: int | None = None) -> None:
        """Mark the flush."""
        order.append("flush")

    monkeypatch.setattr(otel, "shutdown_tracing", record)

    app = _build()
    asyncio.run(_drive_lifespan(app))

    assert order == ["app-startup", "flush"], order
