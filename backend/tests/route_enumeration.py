from __future__ import annotations

from app.main import app

_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "TRACE"})


def schema_routes() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path, operations in app.openapi().get("paths", {}).items():
        for method in sorted(operations):
            normalized = method.upper()
            if normalized in _HTTP_METHODS:
                out.append((normalized, path))
    return out
