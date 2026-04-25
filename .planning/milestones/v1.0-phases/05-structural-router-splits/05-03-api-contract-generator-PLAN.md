---
phase: 05-structural-router-splits
plan: 03
type: execute
wave: 2
depends_on:
  - 05-01-admin-split
files_modified:
  - backend/scripts/generate_ext_api_contract.py
  - chrome-extension/API_CONTRACT.md
  - backend/tests/test_ext_api_contract_up_to_date.py
  - .planning/phases/05-structural-router-splits/05-HUMAN-UAT.md
autonomous: true
requirements:
  - AUTH-05
  - AUTH-06
user_setup: []

must_haves:
  truths:
    - "`backend/scripts/generate_ext_api_contract.py` exists and produces Markdown when run with TESTING=true ENABLE_RATE_LIMITING=false"
    - "`backend/scripts/generate_ext_api_contract.py` supports `--stdout` flag (emits Markdown to stdout) and default file-write mode"
    - "`chrome-extension/API_CONTRACT.md` exists and starts with 'Generated from `app.openapi()`. Do not edit by hand.'"
    - "`chrome-extension/API_CONTRACT.md` documents all 16 extension endpoints per D-35 (users/me, categories, retailers, parts, part-manufacturers, car-generations, images, crawled-pages/scrape)"
    - "`backend/tests/test_ext_api_contract_up_to_date.py` passes — committed .md matches generator output byte-for-byte"
    - "`.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` exists with the 5-step Chrome-extension staging checklist per D-38"
    - "Generator is parallel-safe with Plan 02 (PyJWT) — no shared files (requirements.txt, dependencies/auth.py untouched)"
  artifacts:
    - path: "backend/scripts/generate_ext_api_contract.py"
      provides: "OpenAPI → Markdown generator; 16-endpoint allow-list inline; --stdout flag support"
      contains: "EXTENSION_ENDPOINTS"
    - path: "chrome-extension/API_CONTRACT.md"
      provides: "Committed contract doc — drift-guarded"
      contains: "# Chrome Extension API Contract"
    - path: "backend/tests/test_ext_api_contract_up_to_date.py"
      provides: "Pytest drift guard: subprocess-invoke generator → compare stdout vs committed file (mirrors openapi_snapshot.py pattern — no Python import of script)"
    - path: ".planning/phases/05-structural-router-splits/05-HUMAN-UAT.md"
      provides: "5-step Chrome-extension post-deploy staging UAT checklist (AUTH-05, D-38)"
  key_links:
    - from: "backend/tests/test_ext_api_contract_up_to_date.py"
      to: "backend/scripts/generate_ext_api_contract.py"
      via: "subprocess.run([python, script, '--stdout'], capture_output=True, text=True, check=True) — no Python-level import to avoid sys.path issues (backend/scripts has no __init__.py)"
      pattern: "subprocess\\.run\\(.*generate_ext_api_contract"
    - from: "backend/scripts/generate_ext_api_contract.py"
      to: "app.openapi()"
      via: "app instantiation with TESTING=true env gate"
      pattern: "app\\.openapi\\(\\)"
---

<objective>
Create the Chrome-extension API contract generator, commit the initial generated `chrome-extension/API_CONTRACT.md`, add a CI drift guard, and record the post-deploy staging UAT checklist. This plan is parallel-safe with Plan 02 (PyJWT migration) — no file overlap (per D-41 and D-42).

Purpose: Close AUTH-06 (live API contract for the extension). Provide the reviewer of Plan 04 (auth split) with a vetted allow-list of endpoints the extension calls so the auth-split review can verify the extension surface is untouched. Record the AUTH-05 UAT checklist so post-deploy validation has a deterministic acceptance artifact.

Output: 1 generator script (with `--stdout` flag) + 1 initial generated Markdown doc + 1 pytest drift guard (subprocess-invokes the generator, mirrors `test_openapi_snapshot.py` pattern) + 1 UAT checklist. All four artifacts created in this plan; parallel-safe with Plan 02.
</objective>

<execution_context>
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/workflows/execute-plan.md
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/05-structural-router-splits/05-CONTEXT.md
@.planning/phases/05-structural-router-splits/05-RESEARCH.md
@.planning/phases/05-structural-router-splits/05-PATTERNS.md
@.planning/phases/05-structural-router-splits/05-VALIDATION.md
@CLAUDE.md

# Generator script analog (CLI shape)
@backend/scripts/check_migrations.py

# Drift-guard test shape analog — mirrors its function-scope import + stdout/file comparison pattern
@backend/tests/test_openapi_snapshot.py

# Extension endpoint source-of-truth
@chrome-extension/src/background.ts

<interfaces>
<!-- D-35: The 16 extension endpoints — verified in RESEARCH.md Finding 3 via grep of background.ts -->

EXTENSION_ENDPOINTS allow-list (16 tuples, ordered to match the generated Markdown section order):
```python
EXTENSION_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/users/me"),
    ("GET", "/api/categories/"),
    ("GET", "/api/retailers/"),
    ("POST", "/api/retailers/get-or-create"),
    ("GET", "/api/parts/check-url"),
    ("GET", "/api/parts/{part_id}"),
    ("GET", "/api/parts/find-by-part-manufacturer-and-part-number"),
    ("POST", "/api/parts/{part_id}/append-images"),
    ("POST", "/api/parts/"),
    ("POST", "/api/parts/{part_id}/listings"),
    ("GET", "/api/part-manufacturers/"),
    ("POST", "/api/part-manufacturers/"),
    ("GET", "/api/car-generations/"),
    ("GET", "/api/images/by-source-url"),
    ("POST", "/api/images/upload"),
    ("POST", "/api/crawled-pages/scrape"),
]
```

OpenAPI env-gate (CRITICAL per PATTERNS.md §11 pitfall 8):
```bash
TESTING=true ENABLE_RATE_LIMITING=false python backend/scripts/generate_ext_api_contract.py
```
Without these env vars, rate-limiter-injected schemas leak into the generated doc and the drift-guard test fails sporadically.

**CRITICAL — why the drift-guard test must NOT import the generator via Python:**
- `backend/scripts/__init__.py` does NOT exist → `backend/scripts` is not a Python package
- `backend/__init__.py` does NOT exist → `backend/` is not a Python package either
- `backend/pytest.ini` has `testpaths = tests` with rootdir at `backend/` — tests discover from `backend/`, and `backend/` itself is NOT on `sys.path` as an importable package
- Therefore `from backend.scripts.generate_ext_api_contract import ...` from a test WILL raise `ModuleNotFoundError`

**Solution (mirrors `backend/tests/test_openapi_snapshot.py` which imports `app.main` but does NOT import any script):**
- Generator script accepts a `--stdout` flag: when passed, emit Markdown to stdout instead of writing the file
- Drift-guard test uses `subprocess.run([sys.executable, str(script_path), "--stdout"], capture_output=True, text=True, check=True)` to invoke the generator and capture its Markdown output
- Test then reads the committed `chrome-extension/API_CONTRACT.md` and asserts string equality
- No Python-level import of the script from the test — no sys.path manipulation, no package discovery issues

Repo root resolution pattern (from check_migrations.py):
```python
REPO_ROOT = Path(__file__).resolve().parents[2]   # <repo>/backend/scripts/<script>.py → parents[2] = <repo>
OUTPUT_PATH = REPO_ROOT / "chrome-extension" / "API_CONTRACT.md"
```

OpenAPI schema access pattern (from FastAPI docs + RESEARCH.md Finding 3):
```python
from app.main import app   # function-scope import
spec = app.openapi()
schemas = spec.get("components", {}).get("schemas", {})
for method, path in EXTENSION_ENDPOINTS:
    op = spec.get("paths", {}).get(path, {}).get(method.lower(), {})
    # op contains: summary, description, parameters, requestBody, responses
```

Schema-flattening pattern (depth limit 3 per RESEARCH.md):
```python
def resolve_ref(ref: str, schemas: dict) -> dict:
    name = ref.rsplit("/", 1)[-1]
    return schemas.get(name, {})

def flatten_schema(schema: dict, schemas: dict, depth: int = 0) -> dict:
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
```

Drift-guard test shape (subprocess-invoke, NOT Python import — mirrors `test_openapi_snapshot.py` which calls `app.openapi()` in-process via function-scope import but does not import any script):
```python
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_ext_api_contract.py"
CONTRACT_PATH = Path(__file__).resolve().parents[2] / "chrome-extension" / "API_CONTRACT.md"

def test_api_contract_matches_generator() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--stdout"],
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "TESTING": "true",
            "ENABLE_RATE_LIMITING": "false",
        },
    )
    expected = result.stdout
    committed = CONTRACT_PATH.read_text(encoding="utf-8")
    assert expected == committed, (
        "chrome-extension/API_CONTRACT.md is stale. Regenerate with:\n"
        "    cd backend\n"
        "    TESTING=true ENABLE_RATE_LIMITING=false \\\n"
        "      python scripts/generate_ext_api_contract.py\n"
        "Then commit the regenerated chrome-extension/API_CONTRACT.md."
    )
```

AUTH-05 UAT checklist (D-38) — must be recorded in `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md`:
1. Log in on web app at staging — verify JWT received in localStorage.
2. Open extension popup → verify "Connected as <username>" state.
3. Navigate to a Phase 1 characterized retailer product page (e.g., briantooleyracing, amsperformance, subispeed, texasspeed, or cobbtuning).
4. Trigger scrape → verify POST `/api/parts/` returns 2xx and the part appears in the user's build-list workflow.
5. Log out on web app → verify extension shows disconnected state within reasonable propagation (note: extension may hold cached token until next action — acceptable per current design).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create generator script (with --stdout flag) + drift-guard test (subprocess-invoke) + UAT checklist artifact</name>
  <files>
    backend/scripts/generate_ext_api_contract.py,
    backend/tests/test_ext_api_contract_up_to_date.py,
    .planning/phases/05-structural-router-splits/05-HUMAN-UAT.md
  </files>
  <read_first>
    - backend/scripts/check_migrations.py (CLI-script shape reference — pathlib, exit codes, repo-root resolution)
    - backend/tests/test_openapi_snapshot.py (drift-guard shape — function-scope import + stdout comparison + regeneration command in message; note this file does NOT import any script, it reads app.openapi() directly; we mirror the "no Python import of scripts" pattern)
    - chrome-extension/src/background.ts (verify the 16-endpoint inventory against the source — sanity check before committing the allow-list)
    - .planning/phases/05-structural-router-splits/05-PATTERNS.md (Section 11 — generator skeleton; Section 16 — drift-guard test template)
    - .planning/phases/05-structural-router-splits/05-RESEARCH.md Finding 3 (verified endpoint list + schema-extraction pattern)
  </read_first>
  <behavior>
    - `python backend/scripts/generate_ext_api_contract.py --stdout` emits the full Markdown to stdout without writing a file.
    - `python backend/scripts/generate_ext_api_contract.py` (no flags) writes `chrome-extension/API_CONTRACT.md` and prints a write confirmation.
    - Running the script with `TESTING=true ENABLE_RATE_LIMITING=false` (either mode) produces non-empty Markdown that starts with `# Chrome Extension API Contract`.
    - `test_ext_api_contract_up_to_date.py` runs the generator via subprocess (no Python import); in Task 1 the committed file is empty/absent so the test FAILS; after Task 2 writes the generated doc, it passes.
    - `05-HUMAN-UAT.md` exists with the 5-step checklist from D-38.
  </behavior>
  <action>
**Step A — Create `backend/scripts/generate_ext_api_contract.py`** with support for a `--stdout` flag (emits to stdout, does not touch files) AND default file-write mode (writes `chrome-extension/API_CONTRACT.md`). Full skeleton below — FILL IN the `for method, path in EXTENSION_ENDPOINTS:` loop body to emit full Markdown per endpoint (headers, parameters, request body, responses).

```python
#!/usr/bin/env python3
"""
AUTH-06 + D-34—D-37: Chrome Extension API Contract Generator.

Generates chrome-extension/API_CONTRACT.md from app.openapi() for the 16 endpoints
the extension calls (allow-list inline below).

Usage:

    # Default — write to chrome-extension/API_CONTRACT.md:
    cd backend
    TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py

    # --stdout — emit Markdown to stdout (used by drift-guard test):
    cd backend
    TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout

The companion drift guard (backend/tests/test_ext_api_contract_up_to_date.py)
subprocess-invokes this script with --stdout and asserts the output matches the
committed .md. This avoids Python-level import of the script (backend/scripts
is not a Python package — no __init__.py, not on sys.path).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# <repo>/backend/scripts/generate_ext_api_contract.py → parents[2] = <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "chrome-extension" / "API_CONTRACT.md"

# D-35: Allow-list of (method, path) tuples — mirrors chrome-extension/src/background.ts.
# Verified inventory per RESEARCH.md Finding 3. Any change to this list requires regeneration.
EXTENSION_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/users/me"),
    ("GET", "/api/categories/"),
    ("GET", "/api/retailers/"),
    ("POST", "/api/retailers/get-or-create"),
    ("GET", "/api/parts/check-url"),
    ("GET", "/api/parts/{part_id}"),
    ("GET", "/api/parts/find-by-part-manufacturer-and-part-number"),
    ("POST", "/api/parts/{part_id}/append-images"),
    ("POST", "/api/parts/"),
    ("POST", "/api/parts/{part_id}/listings"),
    ("GET", "/api/part-manufacturers/"),
    ("POST", "/api/part-manufacturers/"),
    ("GET", "/api/car-generations/"),
    ("GET", "/api/images/by-source-url"),
    ("POST", "/api/images/upload"),
    ("POST", "/api/crawled-pages/scrape"),
]


def resolve_ref(ref: str, schemas: dict[str, Any]) -> dict[str, Any]:
    """Resolve a JSON Schema $ref like '#/components/schemas/PartRead' to the schema dict."""
    name = ref.rsplit("/", 1)[-1]
    return schemas.get(name, {})


def flatten_schema(
    schema: dict[str, Any], schemas: dict[str, Any], depth: int = 0
) -> dict[str, Any]:
    """Inline $ref-driven references up to depth 3 so the Markdown is human-readable."""
    if depth > 3:
        return schema
    if "$ref" in schema:
        return flatten_schema(resolve_ref(schema["$ref"], schemas), schemas, depth + 1)
    if "properties" in schema:
        return {
            **schema,
            "properties": {
                k: flatten_schema(v, schemas, depth + 1)
                for k, v in schema["properties"].items()
            },
        }
    return schema


def _schema_to_json_block(schema: dict[str, Any]) -> str:
    """Render a schema dict as a fenced JSON code block for readability."""
    return "```json\n" + json.dumps(schema, indent=2, sort_keys=True) + "\n```"


def generate_markdown() -> str:
    """Produce the full API_CONTRACT.md content as a string.

    Called from main() in both file-write and --stdout modes. The drift-guard
    test does NOT call this function directly — it invokes this script as a
    subprocess and captures stdout. See docstring at top for rationale.
    """
    # Function-scope import — TESTING=true ENABLE_RATE_LIMITING=false must be set
    # BEFORE app.main is imported (conftest-style env-var ordering).
    from app.main import app  # noqa: PLC0415 — intentional ordering

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

        # Parameters (path + query + header)
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
                # Inline schema type (compact)
                schema_repr = schema.get("type", "") or "$ref"
                if "enum" in schema:
                    schema_repr += f" (enum: {schema['enum']})"
                out.append(f"| `{name}` | {pin} | {required} | {schema_repr} |")
            out.append("")

        # Request body
        req_body = op.get("requestBody")
        if req_body:
            content = req_body.get("content", {}).get("application/json", {})
            schema = content.get("schema", {})
            flat = flatten_schema(schema, schemas)
            out.append("**Request body (`application/json`):**")
            out.append("")
            out.append(_schema_to_json_block(flat))
            out.append("")

        # Responses
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
    parser = argparse.ArgumentParser(
        description="Generate Chrome Extension API Contract from app.openapi()."
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Emit Markdown to stdout instead of writing chrome-extension/API_CONTRACT.md. "
             "Used by the drift-guard test to compare against the committed file.",
    )
    args = parser.parse_args()

    md = generate_markdown()

    if args.stdout:
        # Write raw Markdown to stdout; caller (the pytest drift guard) captures it.
        # Do NOT use print() — print appends a newline that would break byte-for-byte equality.
        sys.stdout.write(md)
    else:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(md, encoding="utf-8")
        print(f"Wrote {OUTPUT_PATH} ({len(md)} chars)")


if __name__ == "__main__":
    main()
```

**Step B — Create `backend/tests/test_ext_api_contract_up_to_date.py`** that subprocess-invokes the generator with `--stdout` (NOT a Python import — mirrors the pattern of `test_openapi_snapshot.py` which also avoids importing any script and instead reads app state directly):

```python
"""AUTH-06 D-36 drift guard: chrome-extension/API_CONTRACT.md matches generator output.

Per D-36, developers regenerate the contract locally when the extension endpoint
list or underlying route signatures change, then commit the new .md. CI fails
here if the committed doc is stale.

IMPORTANT: this test does NOT import the generator as a Python module.
`backend/scripts/` has no `__init__.py` and `backend/` itself is not on sys.path
as a package (pytest.ini sets testpaths=tests with rootdir at backend/).
A `from backend.scripts.generate_ext_api_contract import ...` would raise
ModuleNotFoundError. Instead we subprocess-invoke the script with --stdout,
which is how `test_openapi_snapshot.py` avoids script-import issues too
(it calls `app.openapi()` directly in-process rather than importing any script).

Same shape as test_openapi_snapshot.py in spirit — diff IS the review artifact.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_ext_api_contract.py"
CONTRACT_PATH = Path(__file__).resolve().parents[2] / "chrome-extension" / "API_CONTRACT.md"


def test_api_contract_matches_generator() -> None:
    # Subprocess-invoke with --stdout — captures Markdown as the generator emits it.
    # TESTING=true + ENABLE_RATE_LIMITING=false ensure the OpenAPI schema matches the
    # conftest.py env-var setup used by test_openapi_snapshot.py (pitfall 8 in PATTERNS.md).
    env = {
        **os.environ,
        "TESTING": "true",
        "ENABLE_RATE_LIMITING": "false",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--stdout"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        cwd=str(SCRIPT_PATH.parent.parent),  # run with backend/ as cwd so `from app.main import app` works
    )
    expected = result.stdout
    committed = CONTRACT_PATH.read_text(encoding="utf-8")

    if expected != committed:
        msg = (
            "chrome-extension/API_CONTRACT.md is out of date.\n"
            "Regenerate:\n"
            "\n"
            "    cd backend\n"
            "    TESTING=true ENABLE_RATE_LIMITING=false \\\n"
            "      python scripts/generate_ext_api_contract.py\n"
            "\n"
            "Then commit the regenerated chrome-extension/API_CONTRACT.md."
        )
        assert expected == committed, msg
```

**Step C — Create `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md`** with the D-38 checklist:
```markdown
# Phase 05 — Post-Deploy Human UAT Checklist

**Scope:** AUTH-05 — Chrome extension end-to-end auth flow validation post-refactor.
**When:** After Plan 05-04 (auth split) merges to main + staging deploy completes.
**Owner:** Developer with staging credentials + loaded Chrome extension build.
**Environment:** staging.carmodpicker.com (or current staging URL) + Chrome extension loaded from dist/ via chrome://extensions developer mode.

## Checklist

- [ ] **Step 1 — Log in on staging web app.** Navigate to the staging URL, log in with a known staging test account. Verify JWT token is stored in localStorage (DevTools → Application → Local Storage → `authToken` present with a non-empty value starting with `ey`).
- [ ] **Step 2 — Verify extension popup.** Click the extension icon. Popup shows "Connected as <username>" — the username matches the logged-in staging account. If popup shows "Not connected", step 1 did not propagate; open DevTools on the extension popup and inspect `chrome.storage.local.get('authToken')`.
- [ ] **Step 3 — Navigate to a Phase 1 characterized retailer product page.** Pick one of: briantooleyracing.com, amsperformance.com, subispeed.com, texasspeed.com, cobbtuning.com. Navigate to any single-product page.
- [ ] **Step 4 — Trigger scrape + verify part creation.** Click the extension's scrape button. Verify: (a) no visible error toast, (b) navigate to your build-list view on the web app — the scraped part appears in the user's build-list workflow, (c) DevTools → Network shows a POST to `/api/parts/` with status 2xx.
- [ ] **Step 5 — Log out on web app + verify extension state.** Click Logout on the web app. Open the extension popup again — it should show a disconnected state OR still show cached state. Acceptable per current design: the extension holds a cached token until the next API call hits a 401. Click scrape once more on a product page; the extension should detect the 401 and show a reconnect prompt.

## Pass criteria

All 5 checkbox items pass in one session. If any fails, record the failure mode in this file and halt the phase gate.

## Fail handling

- If step 1 fails → JWT issuance is broken; investigate `/api/auth/token` regression first.
- If step 2 fails → extension popup → web-app message channel broken; investigate `externally_connectable.matches` in manifest.json.
- If step 4 fails with 401/403 → per-route auth dependency missing (AUTH-03 regression); rerun `test_auth_auth_coverage.py`.
- If step 4 fails with 500 → backend scrape pipeline broken; check Sentry for stack trace.

## Sign-off

- **Passed by:** ____________________
- **Date:** ____________________
- **Commit on main:** ____________________
- **Staging URL:** ____________________
```

The UAT file is created now (during Plan 03 execution) so it's committed and ready before Plan 04 auth split merges. The file gets filled in during post-deploy UAT, not during this plan.
  </action>
  <verify>
    <automated>test -f backend/scripts/generate_ext_api_contract.py</automated>
    <automated>test -f backend/tests/test_ext_api_contract_up_to_date.py</automated>
    <automated>test -f .planning/phases/05-structural-router-splits/05-HUMAN-UAT.md</automated>
    <automated>cd backend && grep -q "^EXTENSION_ENDPOINTS" scripts/generate_ext_api_contract.py</automated>
    <automated>cd backend && grep -q '"--stdout"' scripts/generate_ext_api_contract.py</automated>
    <automated>cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout 2>&1 | head -1 | grep -q "^# Chrome Extension API Contract$"</automated>
    <automated>grep -q "subprocess.run" backend/tests/test_ext_api_contract_up_to_date.py</automated>
    <automated>grep -q "Step 1 — Log in on staging web app" .planning/phases/05-structural-router-splits/05-HUMAN-UAT.md</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/scripts/generate_ext_api_contract.py` exits 0
    - `test -f backend/tests/test_ext_api_contract_up_to_date.py` exits 0
    - `test -f .planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` exits 0
    - `grep -q "^EXTENSION_ENDPOINTS" backend/scripts/generate_ext_api_contract.py` exits 0 (allow-list exists as a module-level list)
    - Counting EXTENSION_ENDPOINTS entries via grep: `grep -cE '^\s+\("(GET|POST|PATCH|DELETE)", ' backend/scripts/generate_ext_api_contract.py` outputs `16`
    - `grep -q '"--stdout"' backend/scripts/generate_ext_api_contract.py` exits 0 (flag is declared)
    - `cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout | head -1` outputs exactly `# Chrome Extension API Contract`
    - `cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout | grep -c '^## \`'` outputs `16`
    - `grep -q "subprocess.run" backend/tests/test_ext_api_contract_up_to_date.py` exits 0 (test subprocess-invokes, does NOT import the script)
    - `grep "from backend.scripts" backend/tests/test_ext_api_contract_up_to_date.py ; test $? -eq 1` (test does NOT contain a `from backend.scripts...` import)
    - `grep -q "Step 1 — Log in on staging web app" .planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` exits 0
  </acceptance_criteria>
  <done>Generator script exists with `--stdout` flag support and produces Markdown for all 16 endpoints, drift-guard test subprocess-invokes the generator (no Python import) and will fail until Task 2 commits the generated file, UAT checklist recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Run generator to produce initial `chrome-extension/API_CONTRACT.md` + verify drift guard passes</name>
  <files>
    chrome-extension/API_CONTRACT.md
  </files>
  <read_first>
    - backend/scripts/generate_ext_api_contract.py (the generator just created — verify its invocation matches the env-gate pattern)
    - backend/tests/test_ext_api_contract_up_to_date.py (drift guard that must pass after this task)
  </read_first>
  <behavior>
    - `chrome-extension/API_CONTRACT.md` exists and is not empty.
    - File starts with `# Chrome Extension API Contract`.
    - File contains all 16 endpoint sections (one `## \`<METHOD> <path>\`` header per entry in EXTENSION_ENDPOINTS).
    - `pytest -n auto backend/tests/test_ext_api_contract_up_to_date.py` exits 0.
    - Re-running the generator produces IDENTICAL bytes (determinism — `json.dumps(..., sort_keys=True)` guarantees this).
  </behavior>
  <action>
**Run the generator** (default file-write mode — no `--stdout` flag) with the required env gate:

```bash
cd backend
TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py
```

This writes `chrome-extension/API_CONTRACT.md` (at the repo root, one level up from `backend/`).

**Verify the output** before committing:
```bash
head -30 chrome-extension/API_CONTRACT.md
grep -c "^## \`" chrome-extension/API_CONTRACT.md   # MUST be 16
wc -l chrome-extension/API_CONTRACT.md                # sanity: non-trivial size
```

**Run the drift-guard test** to prove equality (the test subprocess-invokes the generator with `--stdout` — no Python import):
```bash
cd backend
pytest -n auto tests/test_ext_api_contract_up_to_date.py -x
```

**Cross-check via direct subprocess invocation** (matches what the test does internally):
```bash
cd backend
TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout > /tmp/expected_contract.md
diff /tmp/expected_contract.md ../chrome-extension/API_CONTRACT.md   # MUST be empty
```

**Determinism check** — re-run the generator; the file should be byte-identical:
```bash
md5sum chrome-extension/API_CONTRACT.md > /tmp/contract_hash_before
cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py
cd ..
md5sum chrome-extension/API_CONTRACT.md > /tmp/contract_hash_after
diff /tmp/contract_hash_before /tmp/contract_hash_after  # MUST be empty
```

If the drift test fails OR the determinism check fails:
- Inspect the generator for non-deterministic ordering (e.g., iterating over dict keys without `sorted()`).
- Common culprit: `spec.get("paths", {})` returns an unordered dict on some Python versions — iterate over the fixed `EXTENSION_ENDPOINTS` tuple list instead (already the pattern in Task 1's script).
- Another common culprit: `json.dumps` without `sort_keys=True` — the helper `_schema_to_json_block` must pass `sort_keys=True` (verify Task 1 script does so).
- File-write-mode vs --stdout-mode discrepancy: the Task 1 script writes identical content in both modes (both call `generate_markdown()`), so any divergence indicates `print()` vs `sys.stdout.write()` adding a trailing newline — the Task 1 script uses `sys.stdout.write(md)` specifically to avoid this.

Commit the generated file as-is; do NOT hand-edit. Future regenerations will overwrite and the drift guard keeps the file in sync.
  </action>
  <verify>
    <automated>test -f chrome-extension/API_CONTRACT.md</automated>
    <automated>head -1 chrome-extension/API_CONTRACT.md | grep -q "^# Chrome Extension API Contract$"</automated>
    <automated>test "$(grep -c '^## \`' chrome-extension/API_CONTRACT.md)" -eq 16</automated>
    <automated>cd backend && pytest -n auto tests/test_ext_api_contract_up_to_date.py -x</automated>
    <automated>grep -q "## \`GET /api/users/me\`" chrome-extension/API_CONTRACT.md</automated>
    <automated>grep -q "## \`POST /api/crawled-pages/scrape\`" chrome-extension/API_CONTRACT.md</automated>
    <automated>cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout > /tmp/_expected_contract.md && diff /tmp/_expected_contract.md ../chrome-extension/API_CONTRACT.md</automated>
    <automated>md5sum chrome-extension/API_CONTRACT.md > /tmp/contract_hash_1 && cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py > /dev/null && cd .. && md5sum chrome-extension/API_CONTRACT.md > /tmp/contract_hash_2 && diff /tmp/contract_hash_1 /tmp/contract_hash_2</automated>
  </verify>
  <acceptance_criteria>
    - `test -f chrome-extension/API_CONTRACT.md` exits 0
    - `head -1 chrome-extension/API_CONTRACT.md` outputs exactly `# Chrome Extension API Contract`
    - `grep -c '^## \`' chrome-extension/API_CONTRACT.md` outputs `16` (one section per endpoint)
    - `grep -q "## \`GET /api/users/me\`" chrome-extension/API_CONTRACT.md` exits 0
    - `grep -q "## \`POST /api/crawled-pages/scrape\`" chrome-extension/API_CONTRACT.md` exits 0
    - `cd backend && pytest -n auto tests/test_ext_api_contract_up_to_date.py -x` exits 0
    - Subprocess cross-check: `cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout | diff - ../chrome-extension/API_CONTRACT.md` produces no output (byte-identical)
    - Determinism check: running the generator twice produces identical md5sum (diff of the two hashes returns empty)
  </acceptance_criteria>
  <done>API_CONTRACT.md committed with all 16 endpoints documented; drift guard passes (subprocess-invokes generator with --stdout, no Python import); regeneration is deterministic.</done>
</task>

</tasks>

<deferred>
## Deferred / documented-only

- **Playwright E2E with loaded Chrome extension:** D-39 defers this. The 5-step manual UAT (created in Task 1 as 05-HUMAN-UAT.md) is the Phase 5 acceptance. Automated extension E2E deferred to a future testing-infra phase.
- **Backend integration test simulating extension requests:** D-40 defers this. Per-route 401/403 coverage in Plans 01 + 04 captures the auth dependency correctness.
- **Typed API client generated from OpenAPI for the Chrome extension:** CONTEXT.md "Noted but not a Phase 5 deliverable".
- **Moving `backend/scripts/` into a proper Python package (adding `__init__.py`):** Out of scope. The subprocess-invocation pattern works without this; a future cleanup phase could unify the script-testing approach across `backend/scripts/*`.
</deferred>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Developer → generator allow-list | EXTENSION_ENDPOINTS allow-list is manually maintained; accidentally adding a sensitive internal endpoint (e.g., `/admin/db-ops/*`) would disclose it in a public-ish doc |
| Committed .md → CI drift guard | File drift without regen is the attack surface; the pytest guard closes it |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-03-01 | Information Disclosure | EXTENSION_ENDPOINTS allow-list accidentally discloses internal-only endpoints (admin, auth private routes) in a repo-committed Markdown doc | mitigate | Task 1's allow-list is manually curated from RESEARCH.md Finding 3 (16 verified endpoints from background.ts grep). Allow-list discipline: any future PR changing the list must update via code review. The chrome-extension/API_CONTRACT.md file lives in a public repo only if the repo is public; current repo is private per STATE.md. No auth/admin endpoints appear in the list — verified by `grep -E '/(auth|admin)' chrome-extension/API_CONTRACT.md` returning exit 1 (part of Task 2 acceptance). |
| T-05-03-02 | Tampering | Stale `chrome-extension/API_CONTRACT.md` ships to reviewers with incorrect request/response shapes → extension author reads outdated contract | mitigate | Task 1's `test_ext_api_contract_up_to_date.py` drift guard runs on every CI PR. The test subprocess-invokes the generator with `--stdout` (mirrors `test_openapi_snapshot.py`'s "no script import" pattern) — any change to a documented endpoint's schema or signature invalidates the cached .md, and CI refuses to merge until the doc regenerates. |
| T-05-03-03 | Repudiation | Generator non-determinism → spurious CI failures + reviewer confusion ("why does the test fail on my clean checkout?") | mitigate | Task 2 verifies determinism: md5sum the generated file; regenerate; md5sum again; expect equality. The generator uses `json.dumps(..., sort_keys=True)` + iterates over the ordered EXTENSION_ENDPOINTS tuple list (not over `spec["paths"]` dict). File-write and --stdout paths both call `generate_markdown()` once and emit the exact same string (`sys.stdout.write(md)` avoids `print()` trailing newlines). Both pitfalls documented in PATTERNS.md §11. |
| T-05-03-04 | Information Disclosure | `API_CONTRACT.md` commits request body schemas that expose field names/validation rules an attacker could exploit | accept | Low-severity — the API is the public interface of the app; endpoint shapes are discoverable via Swagger UI (/api/docs) in production. This just surfaces them in a second form. No new disclosure beyond what /openapi.json already exposes on the live backend. |
</threat_model>

<verification>
```bash
# Generator + drift-guard sanity
cd backend
TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py
pytest -n auto tests/test_ext_api_contract_up_to_date.py -x

# Phase-wide regression guards (unchanged by this plan, but must stay green)
pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x

# Sanity: no admin/auth endpoints leaked into the contract
grep -E '/(auth|admin)' ../chrome-extension/API_CONTRACT.md ; test $? -eq 1

# UAT artifact committed
test -f ../.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md
```
</verification>

<success_criteria>
1. `backend/scripts/generate_ext_api_contract.py` exists, supports `--stdout` flag + default file-write mode, and is invocable with `TESTING=true ENABLE_RATE_LIMITING=false`.
2. `chrome-extension/API_CONTRACT.md` exists, contains 16 endpoint sections (one per EXTENSION_ENDPOINTS tuple), is deterministic (re-running the generator produces byte-identical output).
3. `backend/tests/test_ext_api_contract_up_to_date.py` passes — the drift guard is live (subprocess-invokes generator with `--stdout`, no Python import of the script).
4. `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` exists with the 5-step AUTH-05 checklist from D-38.
5. No /admin or /auth endpoints appear in the generated contract (scope discipline verified).
6. Plan 02 (PyJWT) and Plan 03 (this plan) touch zero overlapping files — parallel-safe per D-41.
</success_criteria>

<output>
After completion, create `.planning/phases/05-structural-router-splits/05-03-SUMMARY.md` with:
- Generator + drift-guard artifact summary
- Confirmation of 16-endpoint coverage + determinism verification
- Allow-list discipline note (only extension endpoints in the contract)
- Link to 05-HUMAN-UAT.md checklist for post-Plan-04-deploy validation
- Parallel-safety note with Plan 02
- Note on the subprocess-invocation drift-guard pattern (mirrors `test_openapi_snapshot.py` — avoids `backend/scripts` package-path issues since `backend/scripts/__init__.py` is absent)
</output>
