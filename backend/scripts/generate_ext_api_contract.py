#!/usr/bin/env python3
"""
AUTH-06 + D-34—D-37: Chrome Extension API Contract Generator.

Generates ``chrome-extension/API_CONTRACT.md`` from ``app.openapi()`` for the
16 endpoints the extension calls. The inline ``EXTENSION_ENDPOINTS`` allow-list
is D-35 and mirrors ``chrome-extension/src/background.ts``; any change to it
requires regenerating the contract.

Usage:

    # Default — write to chrome-extension/API_CONTRACT.md:
    cd backend
    TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py

    # --stdout — emit Markdown to stdout (used by drift-guard test):
    cd backend
    TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout

The companion drift guard (``backend/tests/test_ext_api_contract_up_to_date.py``)
subprocess-invokes this script with ``--stdout`` and asserts the output matches
the committed .md. This avoids Python-level import of the script, whose
directory is not on ``sys.path`` for the test process.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "chrome-extension" / "API_CONTRACT.md"

EXTENSION_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/users/me"),
    ("GET", "/api/categories/"),
    ("GET", "/api/retailers"),
    ("POST", "/api/retailers/get-or-create"),
    ("GET", "/api/parts/check-url"),
    ("GET", "/api/parts/{part_id}"),
    ("GET", "/api/parts/find-by-part-manufacturer-and-part-number"),
    ("POST", "/api/parts/{part_id}/append-images"),
    ("POST", "/api/parts"),
    ("POST", "/api/parts/{part_id}/listings"),
    ("GET", "/api/part-manufacturers"),
    ("POST", "/api/part-manufacturers"),
    ("GET", "/api/car-generations"),
    ("GET", "/api/images/by-source-url"),
    ("POST", "/api/images/upload"),
    ("POST", "/api/images/fetch-from-url"),
    ("POST", "/api/crawled-pages/scrape"),
]


def resolve_ref(ref: str, schemas: dict[str, Any]) -> dict[str, Any]:
    """Resolve a JSON Schema $ref like ``#/components/schemas/PartRead`` to the schema dict."""
    name = ref.rsplit("/", 1)[-1]
    return schemas.get(name, {})


def flatten_schema(schema: dict[str, Any], schemas: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Inline ``$ref``-driven references up to depth 3 so the Markdown is human-readable."""
    if depth > 3:
        return schema
    if "$ref" in schema:
        return flatten_schema(resolve_ref(schema["$ref"], schemas), schemas, depth + 1)
    if "properties" in schema:
        return {
            **schema,
            "properties": {k: flatten_schema(v, schemas, depth + 1) for k, v in schema["properties"].items()},
        }
    return schema


def _schema_to_json_block(schema: dict[str, Any]) -> str:
    """Render a schema dict as a fenced JSON code block for readability."""
    return "```json\n" + json.dumps(schema, indent=2, sort_keys=True) + "\n```"


def generate_markdown() -> str:
    """Produce the full API_CONTRACT.md content as a string.

    Called from ``main()`` in both file-write and ``--stdout`` modes. The
    drift-guard test does NOT call this function directly — it invokes this
    script as a subprocess and captures stdout. See docstring at top for
    rationale.

    ``backend/`` is put on sys.path first so ``from app.main import app`` works
    regardless of cwd: running ``python scripts/generate_ext_api_contract.py``
    puts ``scripts/`` on sys.path[0], not ``backend/``. The app import is
    function-scope because TESTING=true and ENABLE_RATE_LIMITING=false must be
    set before ``app.main`` is imported.
    """
    backend_dir = str(Path(__file__).resolve().parents[1])
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from app.main import app  # noqa: PLC0415

    spec = app.openapi()
    schemas = spec.get("components", {}).get("schemas", {})
    out: list[str] = [
        "# Chrome Extension API Contract",
        "",
        "Generated from `app.openapi()`. Do not edit by hand.",
        "",
        "Regenerate:",
        "",
        "```",
        "cd backend",
        "TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py",
        "```",
        "",
        "---",
        "",
    ]

    for method, path in EXTENSION_ENDPOINTS:
        op = spec.get("paths", {}).get(path, {}).get(method.lower(), {})
        out.append(f"## `{method} {path}`")
        out.append("")
        if op.get("summary"):
            out.append(f"**Summary:** {op['summary']}")
            out.append("")
        if op.get("description"):
            out.append(f"**Description:** {op['description']}")
            out.append("")

        params = op.get("parameters", [])
        if params:
            out.append("**Parameters:**")
            out.append("")
            out.append("| Name | In | Required | Schema |")
            out.append("|------|----|----------|--------|")
            for p in params:
                name = p.get("name", "?")
                pin = p.get("in", "?")
                required = "yes" if p.get("required", False) else "no"
                schema = p.get("schema", {})
                schema_repr = schema.get("type", "") or "$ref"
                if "enum" in schema:
                    schema_repr += f" (enum: {schema['enum']})"
                out.append(f"| `{name}` | {pin} | {required} | {schema_repr} |")
            out.append("")

        req_body = op.get("requestBody")
        if req_body:
            content = req_body.get("content", {}).get("application/json", {})
            schema = content.get("schema", {})
            flat = flatten_schema(schema, schemas)
            out.append("**Request body (`application/json`):**")
            out.append("")
            out.append(_schema_to_json_block(flat))
            out.append("")

        responses = op.get("responses", {})
        if responses:
            out.append("**Responses:**")
            out.append("")
            for status_code in sorted(responses.keys()):
                resp = responses[status_code]
                out.append(f"- `{status_code}` — {resp.get('description', '')}")
                content = resp.get("content", {}).get("application/json", {})
                schema = content.get("schema")
                if schema:
                    flat = flatten_schema(schema, schemas)
                    out.append("")
                    out.append(_schema_to_json_block(flat))
                    out.append("")
            out.append("")

        out.append("---")
        out.append("")

    return "\n".join(out)


def main() -> None:
    """Write the generated contract to chrome-extension/API_CONTRACT.md, or to stdout.

    ``--stdout`` writes raw Markdown without ``print()``: a trailing newline
    would break the drift guard's byte-for-byte comparison.
    """
    parser = argparse.ArgumentParser(
        description="Generate Chrome Extension API Contract from app.openapi().",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help=(
            "Emit Markdown to stdout instead of writing "
            "chrome-extension/API_CONTRACT.md. Used by the drift-guard test to "
            "compare against the committed file."
        ),
    )
    args = parser.parse_args()

    md = generate_markdown()

    if args.stdout:
        sys.stdout.write(md)
    else:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(md, encoding="utf-8")
        print(f"Wrote {OUTPUT_PATH} ({len(md)} chars)")


if __name__ == "__main__":
    main()
