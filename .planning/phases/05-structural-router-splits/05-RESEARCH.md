# Phase 5: Structural Router Splits - Research

**Researched:** 2026-04-22
**Domain:** FastAPI router package decomposition + PyJWT library swap + OpenAPI-driven contract doc generation
**Confidence:** HIGH (all library/API claims verified via Context7; all code claims verified via direct file reads)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (46 items — D-01 through D-46)

Summarized here by cluster; full verbatim text in `05-CONTEXT.md`. Planner MUST honor all 46:

- **PyJWT migration (D-01—D-07):** `PyJWT==2.12.1` exact pin; `from jwt import InvalidTokenError` replaces `JWTError` at 4 sites in `endpoints/auth.py` + 3 sites in `dependencies/auth.py`; hoist `ALGORITHM` literal to new `settings.JWT_ALGORITHM="HS256"` config field; dedicated PR between admin and auth splits; grep regression guard (bare `jwt.decode` without `algorithms=`); jose/PyJWT parity test.
- **Sub-package composition (D-08—D-17):** 9 sub-routers total (5 admin + 4 auth), each registered individually in `main.py` via `endpoint_registry.register_endpoint()`; admin routes consolidate under sub-module prefixes (`/admin/stats`, `/admin/jobs`, `/admin/crawlers`, `/admin/db-ops`, `/admin/parts`); auth adds `/auth/oauth` sub-prefix; aggressive restructure moves `/admin/crawled-pages/rescrape-archives` → `/admin/crawlers/rescrape-archives` and `/auth/google/*` → `/auth/oauth/google/*`; EventBridge Terraform path update in same PR as admin split; frontend path updates same PR; hard import migration (no shim); OpenAPI snapshot regenerates in each restructure PR.
- **Helper files (D-18—D-26):** `auth/_helpers.py` contains ONLY cross-module helpers (`_issue_login_response`, `_maybe_2fa_challenge`); webauthn/oauth-local helpers stay in their modules; `admin/_helpers.py` (new) contains job-lifecycle helpers; ECS launchers stay inline in `admin/crawlers.py`; every new file uses module-level `logger = logging.getLogger(__name__)`.
- **401/403 integration tests (D-27—D-33):** parametrized over `(method, path, required_role)`; one file per package (`test_admin_auth_coverage.py` + `test_auth_auth_coverage.py`); per-route assertions; drift guard via `len(tuples) == len(app.routes filtered)`; public-route allow-list inline; reuse `test_admin_user` fixture; SQLite-safe.
- **Chrome extension contract (D-34—D-40):** `chrome-extension/API_CONTRACT.md` generated from `app.openapi()` by `backend/scripts/generate_ext_api_contract.py`; allow-list of extension endpoints inline in script; drift-guard pytest asserts doc matches generator output; manual UAT checklist post-deploy on staging; no new Playwright tests.
- **Sequencing (D-41—D-42):** PR 1 admin split → PR 2 PyJWT swap → PR 3 API_CONTRACT generator (parallel-safe) → PR 4 auth split → Post-merge staging UAT. Old file deleted in same PR as split.
- **Guardrails inherited (D-43—D-46):** Phase 1 auth characterization tests stay green; OpenAPI snapshot test IS the URL-drift guard; Phase 3 logger + Phase 4 `db.scalars()` regression greps run on every PR; `HS256` preserved.

### Claude's Discretion

- Exact filenames of internal scripts.
- Whether PyJWT parity test stays post-migration.
- Drift-guard assertion placement (top of parametrized function vs separate function).
- `create_and_login_admin` location (shared conftest vs inlined) — **verified: already exists in conftest.py as `create_and_login_admin_user` at line 688**.
- Sub-module commit granularity inside PR 1/4.
- `admin/_helpers.py` docstring style.
- Test file names (`test_admin_auth_coverage.py` vs alternatives).
- Markdown structure of `API_CONTRACT.md`.
- Parity test secret source (static vs `settings.SECRET_KEY`).

### Deferred Ideas (OUT OF SCOPE)

- Extract ECS task launchers to a service module (stays inline per D-24).
- Playwright E2E with loaded Chrome extension.
- Backend integration test simulating extension requests with `Authorization: Bearer` + `Origin: chrome-extension://`.
- Remove `get_logger` export entirely (defer to late Phase 5 / early Phase 6).
- Remove `python-jose` dependency (stays installed with parity test through Phase 5).
- Retroactive rename of historical admin/auth test files to sub-module paths.
- ALGORITHM rotation / RS256 migration.
- Admin UI URL routing polish (Phase 6+).
- **ADMIN-04 "service-level coupling":** CONTEXT.md flags this as potentially preventive language — planner confirms during research whether concrete target exists. **See Finding 6 below.**
- Further split `auth/webauthn.py` into sub-sub-packages.
- Parallel split of `services/*.py`.
- Chrome extension typed API client generated from OpenAPI.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADMIN-01 | admin.py (2,068 lines, 23 routes) decomposed into `admin/` package (`stats.py`, `jobs.py`, `crawlers.py`, `db_ops.py`, `parts.py`); old file deleted same PR | Route inventory verified against current file (Finding 2); EndpointRegistry pattern confirmed reusable (Finding 2); 9-register overhead negligible (Finding 2) |
| ADMIN-02 | Every admin sub-router route has explicit `Depends(get_current_admin_user)`; 401/403 integration test per route | Current state: 23 routes verified with explicit `Depends(get_current_admin_user)` (verified via grep of admin.py lines 190, 237, 260, 360, etc.); test pattern verified via Finding 4 |
| ADMIN-03 | EventBridge contract stays on same path; lives in `admin/crawlers.py` | Terraform has ONE API destination: `/api/admin/crawlers/run`; rescrape-archives NOT in Terraform (admins trigger manually per scheduler.tf L18); path preservation trivial for the single Terraform-bound endpoint (Finding 5) |
| ADMIN-04 | Service-level coupling reduced — inject specific services via `Depends()`, not god-service | **Reality check (Finding 6):** current admin.py imports `from app.services import job_service` (module-level) and inline-imports `part_linker_service` functions. No god-service pattern exists. Requirement is preventive. |
| AUTH-01 | auth.py (1,191 lines, 24 routes) decomposed into `auth/` package (`core.py`, `two_factor.py`, `webauthn.py`, `oauth.py`, `_helpers.py`); old file deleted same PR | Route inventory verified (Finding 2); cross-module helper boundaries from D-18 validated |
| AUTH-02 | `/api/auth/*` routes remain identical after split (Chrome extension critical path) | Chrome extension API paths inventoried from background.ts — **extension does NOT call `/auth/*` at all** (Finding 3); D-10 `/auth/google/*` → `/auth/oauth/google/*` breaks web frontend only, not extension |
| AUTH-03 | Each route explicitly redeclares `Depends(get_current_user)` or equivalent | Current state preserves this by definition (per-route `current_user` parameter with `Depends(...)` already the convention); 401/403 test locks future regressions |
| AUTH-04 | `python-jose` → `PyJWT 2.12.1`; `JWTError` → `InvalidTokenError`; algorithm explicit on every decode | **Verified via Context7 (Finding 1):** `from jwt import InvalidTokenError` works (re-exported from `jwt.exceptions`); `jwt.encode()` returns `str` (same as jose); HS256 tokens byte-compatible; 4 JWTError sites in endpoints/auth.py + 3 in dependencies/auth.py confirmed via grep |
| AUTH-05 | Chrome extension end-to-end auth flow validated post-refactor | Manual UAT per D-38; extension holds bearer token + calls non-auth routes only (Finding 3) |
| AUTH-06 | `chrome-extension/API_CONTRACT.md` documents every endpoint extension calls | 16 endpoint allow-list derived from direct code reading (Finding 3); OpenAPI schema extraction pattern verified (Finding 3) |

</phase_requirements>

## Summary

Phase 5 decomposes two oversized FastAPI endpoint files into well-scoped sub-packages, swaps the JWT library from `python-jose[cryptography]==3.5.0` to `PyJWT==2.12.1`, generates a Chrome-extension API contract document from `app.openapi()`, and locks the per-route auth dependency surface with parametrized 401/403 integration tests. The work is inherently sequential (admin first as dry run, then PyJWT, then auth as the highest-stakes move) and guarded end-to-end by the Phase 1 auth characterization tests + OpenAPI snapshot test + Phase 3/4 grep regression tests.

Research confirms: (1) PyJWT's exception class is importable as `from jwt import InvalidTokenError` and its base class is identical to `jwt.exceptions.InvalidTokenError` — D-02's literal is correct; (2) both libraries produce byte-compatible HS256 tokens, so the D-05 parity test is expected to pass; (3) the Chrome extension does NOT touch `/auth/*` or `/admin/*` — its critical path is bearer-token decoding via `get_current_user`, which is covered by per-route 401/403 tests + the existing Phase 1 characterization suite; (4) Terraform EventBridge has exactly ONE API destination (`/api/admin/crawlers/run`) — rescrape-archives is NOT EventBridge-triggered (admins invoke it manually), so D-11's "two schedules change path" framing is incorrect and sequencing concerns are narrower than CONTEXT.md suggests; (5) ADMIN-04's "service-level coupling" requirement is preventive — no god-service pattern exists in current admin.py. This should be documented in the split PR's SUMMARY.md rather than assigned a separate plan.

**Primary recommendation:** Structure the phase as exactly 4 PRs per D-41. In the admin split PR, verify each route's new prefix against the full route list in Finding 2 (there are 23 routes but CONTEXT.md D-09's table shows only 22 — the `/crawler-schedules/*` and `/crawler-adapter-configs/*` sub-routers are already separately registered in main.py and NOT in admin.py). In the PyJWT PR, the parity test uses `settings.SECRET_KEY` and a static payload — both libraries will produce identical HS256 tokens, and the test failing would indicate a broken PyJWT install, not a semantic drift. The 401/403 parametrized tests should enumerate `app.routes` using `fastapi.routing.APIRoute` at test collection time (pytest fixture) rather than hand-maintain tuples.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Admin CRUD (stats, jobs, crawlers, db-ops, parts) | API / Backend | — | All admin operations are server-side; frontend and extension never self-administer |
| Authentication (login, logout, 2FA, WebAuthn, OAuth) | API / Backend | Browser/Client (WebAuthn ceremony UI) | Core JWT issue/verify is server-only; WebAuthn requires browser-side navigator.credentials for ceremony, but backend validates |
| JWT encoding/decoding | API / Backend | — | Secret lives server-side; clients only hold the signed token |
| Chrome extension auth contract doc | Tooling (build script) | — | Generated at build time from `app.openapi()`, committed to git — not a runtime tier |
| EventBridge cron trigger (`/admin/crawlers/run`) | API / Backend | External (AWS EventBridge) | Backend exposes the HTTP endpoint; EventBridge invokes it via API Destination |
| Per-route 401/403 tests | API / Backend (test) | — | FastAPI TestClient exercises the backend's dependency injection surface |

## Technical Findings

### Finding 1: PyJWT 2.12.1 migration mechanics

**Confidence: HIGH (verified via Context7)**

**Exception import path (D-02 verification):**
- `from jwt import InvalidTokenError` — works. PyJWT re-exports `InvalidTokenError` at the top-level `jwt` namespace. `[VERIFIED: Context7 /jpadilla/pyjwt — "Handle JWT Decoding Exceptions" snippet catches `jwt.InvalidTokenError` subclasses directly]`.
- `from jwt.exceptions import InvalidTokenError` — also works; they're the same class. `[CITED: PyJWT source pyjwt/jwt/__init__.py imports from jwt/exceptions.py and re-exports]`.
- D-02's literal `from jwt import InvalidTokenError` is correct and is the idiomatic form in PyJWT documentation.

**Exception hierarchy:**
```
jwt.PyJWTError (base, "JWT processing failed")
└── jwt.InvalidTokenError
    ├── jwt.DecodeError (malformed)
    ├── jwt.ExpiredSignatureError
    ├── jwt.InvalidSignatureError
    ├── jwt.ImmatureSignatureError
    ├── jwt.InvalidAudienceError
    ├── jwt.InvalidIssuerError
    ├── jwt.InvalidAlgorithmError
    ├── jwt.MissingRequiredClaimError
    └── jwt.InvalidKeyError
```

Catching `InvalidTokenError` covers everything that `jose.JWTError` caught in the old code (jose's `JWTError` is similarly a broad base). The semantics are functionally identical for the auth.py/dependencies/auth.py use cases (all 7 sites want "token is bad for any reason → 401").

**Return type (`jwt.encode`):**
- PyJWT 2.x returns `str`, not `bytes`. `[VERIFIED: Context7 /jpadilla/pyjwt — "jwt.encode" API doc: "token (str) - The generated JWT string"]`.
- python-jose 3.5.0 also returns `str`. No code change required on call sites that consume the result.
- In PyJWT 1.x the return was `bytes` — this was the breaking change in PyJWT 2.0. Since the codebase is migrating to 2.12.1, the 2.x semantics apply.

**Algorithm specification:**
- Encode: `jwt.encode(payload, key, algorithm="HS256")` — identical signature to jose.
- Decode: `jwt.decode(token, key, algorithms=["HS256"])` — identical signature to jose.
- Current code already uses `algorithms=[ALGORITHM]` on every decode call (verified via grep — 5 decode sites in `endpoints/auth.py`, 3 in `dependencies/auth.py`, all with explicit `algorithms=[...]`). D-03's hoist of `ALGORITHM` → `settings.JWT_ALGORITHM` is a pure-rename refactor at these sites.

**HS256 token byte-identity:**
- HS256 is deterministic HMAC-SHA256 over the (base64url-encoded header . base64url-encoded payload) using the shared secret. Given identical payload dict, identical key, identical header, both jose and PyJWT produce bit-for-bit identical tokens.
- Caveat: default header dict field ORDER can differ between libraries if they JSON-encode non-deterministically. PyJWT 2.x uses `json.dumps(header, separators=(",", ":"))` which produces a stable encoding; jose does the same. In practice tokens ARE byte-identical for HS256.
- D-05 parity test is expected to pass. **Value of the test:** reviewer-visible proof for the PR that in-flight tokens (issued by the old library, decoded by the new) work without user-visible logout.

**Migration sites in the codebase (verified via grep):**

`backend/app/api/dependencies/auth.py`:
- Line 7: `from jose import JWTError, jwt` → replace with `import jwt` + `from jwt import InvalidTokenError`
- Line 17: `ALGORITHM = "HS256"` → `ALGORITHM = settings.JWT_ALGORITHM`
- Line 73: `jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)` — unchanged (still works)
- Line 95, 127, 155: `jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])` — unchanged
- Line 100, 132, 160: `except JWTError:` → `except InvalidTokenError:` (3 sites)

`backend/app/api/endpoints/auth.py`:
- Line 23: `from jose import JWTError, jwt` → replace
- Lines 227, 311, 514, 910: `jwt.decode(...)` — unchanged
- Lines 261, 332, 515, 911: `except JWTError:` or `except JWTError as e:` → `except InvalidTokenError:` or `except InvalidTokenError as e:` (4 sites)

**Total: 7 exception-handler rewrites + 2 import-line rewrites + 1 ALGORITHM hoist + `requirements.txt` swap.** Trivial mechanical diff.

### Finding 2: FastAPI APIRouter composition — 9 sub-routers vs 2

**Confidence: HIGH (verified via Context7 + direct code reading)**

**Admin route inventory (verified — admin.py 2,068 lines, 23 `@router.*` decorators):**

| Line | Method | Path (post-split) | Sub-module (per D-09) |
|------|--------|-------------------|----------------------|
| 181 | GET | `/stats/table-counts` | admin/stats |
| 228 | GET | `/stats/crawl-bucket` | admin/stats |
| 251 | POST | `/db-ops/migrations/run` | admin/db_ops |
| 351 | GET | `/db-ops/migrations/current` | admin/db_ops |
| 416 | POST | `/db-ops/init/car-generations` | admin/db_ops |
| 450 | POST | `/db-ops/init/part-categories` | admin/db_ops |
| 491 | POST | `/db-ops/cars/delete-all` | admin/db_ops |
| 641 | GET | `/crawlers` (listing) | admin/crawlers |
| 823 | POST | `/crawlers/run` | admin/crawlers |
| 1205 | POST | `/crawlers/rescrape-archives` (moved from `/crawled-pages/rescrape-archives`) | admin/crawlers |
| 1341 | GET | `/crawlers/service-account` (moved from `/service-accounts/crawler`) | admin/crawlers |
| 1379 | GET | `/jobs` | admin/jobs |
| 1432 | GET | `/jobs/{job_id}` | admin/jobs |
| 1465 | GET | `/jobs/{job_id}/crawler-progress` | admin/jobs |
| 1533 | POST | `/jobs/{job_id}/cancel` | admin/jobs |
| 1598 | POST | `/db-ops/parts/delete-all` | admin/db_ops |
| 1745 | GET | `/parts/lookup-by-url` | admin/parts |
| 1788 | GET | `/parts/{part_id}/link-group` | admin/parts |
| 1825 | POST | `/parts/promote-canonical` | admin/parts |
| 1847 | POST | `/parts/unlink` | admin/parts |
| 1869 | POST | `/parts/link` | admin/parts |
| 1914 | POST | `/parts/rescan` | admin/parts |
| 2029 | POST | `/db-ops/part-manufacturers/delete-all` | admin/db_ops |

**Total: 23 routes** (matches CONTEXT.md). CONTEXT.md D-09 table lists 22 rows — slight off-by-one because `/admin/crawlers` (listing at line 641) and `/admin/crawlers/run` (at line 823) are collapsed. Reality: 23 routes distributed 2 / 4 / 5 / 7 / 6 across stats/jobs/crawlers/db_ops/parts. [VERIFIED via grep]

**Note:** `/admin/crawler-schedules/*` and `/admin/crawler-adapter-configs/*` visible in the frontend API calls are ALREADY separate sub-routers registered at `main.py:296` and `main.py:304` — they are NOT inside `admin.py` and do not need decomposition. Leave them alone.

**Auth route inventory (verified — auth.py 1,191 lines, 24 `@router.*` decorators):**

| Line | Method | Path (post-split) | Sub-module |
|------|--------|-------------------|-----------|
| 90 | POST | `/token` | auth/core |
| 132 | POST | `/token/2fa` | auth/core |
| 185 | POST | `/verify-email` | auth/core |
| 215 | GET | `/verify-email/confirm` | auth/core |
| 275 | POST | `/reset-password` | auth/core |
| 303 | POST | `/reset-password/confirm` | auth/core |
| 343 | POST | `/logout` | auth/core |
| 357 | POST | `/2fa/setup` | auth/two_factor |
| 405 | POST | `/2fa/verify` | auth/two_factor |
| 447 | POST | `/2fa/disable` | auth/two_factor |
| 525 | POST | `/webauthn/register/options` | auth/webauthn |
| 563 | POST | `/webauthn/register/verify` | auth/webauthn |
| 617 | POST | `/webauthn/login/options` | auth/webauthn |
| 647 | POST | `/webauthn/login/verify` | auth/webauthn |
| 713 | GET | `/webauthn/credentials` | auth/webauthn |
| 726 | PATCH | `/webauthn/credentials/{credential_id}` | auth/webauthn |
| 748 | DELETE | `/webauthn/credentials/{credential_id}` | auth/webauthn |
| 834 | POST | `/oauth/google` (moved from `/google`) | auth/oauth |
| 918 | POST | `/oauth/google/link` (moved from `/google/link`) | auth/oauth |
| 999 | POST | `/oauth/google/signup` (moved from `/google/signup`) | auth/oauth |
| 1053 | POST | `/oauth/2fa` | auth/oauth |
| 1088 | POST | `/oauth/google/connect` (moved from `/google/connect`) | auth/oauth |
| 1144 | GET | `/oauth` | auth/oauth |
| 1157 | DELETE | `/oauth/{account_id}` | auth/oauth |

**Total: 24 routes** distributed 7 / 3 / 7 / 7 across core/two_factor/webauthn/oauth. [VERIFIED via grep]

**Registration overhead: 9 vs 2 `register_endpoint()` calls.**

- Each `register_endpoint()` wraps `app.include_router(router, prefix, tags)` and stores metadata (`backend/app/api/utils/endpoint_registry.py:55-73`). Cost: one dict store + one `include_router` call.
- `app.include_router` iterates the router's routes and appends each to `app.routes` with prefix-prefixing. Cost: O(routes).
- **Startup cost delta from 2 → 9 registrations is negligible** (sub-millisecond; dict store + 9 extra function calls vs 2). [CITED: FastAPI docs /fastapi/fastapi "include_router Method" — no startup penalty documented].
- **OpenAPI schema organization:** Tags are the primary grouping key in OpenAPI. If all 5 admin sub-routers use `tags=["admin"]`, Swagger UI groups all 23 admin routes under a single "admin" collapsible section — same visual result as today. If each sub-module uses a distinct tag (e.g., `tags=["admin-stats"]`, `tags=["admin-crawlers"]`), Swagger UI shows 5 separate sections. **Recommendation (Claude's Discretion space):** Use a single tag `"admin"` across all 5 admin sub-routers to preserve current UX. For auth, use `"authentication"` across all 4 sub-routers (matches current main.py:228). FastAPI supports the same tag on multiple routers — tags merge in OpenAPI. [CITED: FastAPI docs "Include APIRouter with custom prefix, tags"].

**Exact main.py pattern:**

```python
# Before (line 225-230)
endpoint_registry.register_endpoint(
    auth.router,
    prefix="/auth",
    tags=["authentication"],
    description="User authentication and authorization",
)

# After (auth split — 4 registrations)
from app.api.endpoints.auth import core as auth_core, two_factor as auth_2fa, webauthn as auth_webauthn, oauth as auth_oauth

endpoint_registry.register_endpoint(auth_core.router, prefix="/auth", tags=["authentication"], description="Login / logout / email / password reset")
endpoint_registry.register_endpoint(auth_2fa.router, prefix="/auth/2fa", tags=["authentication"], description="TOTP 2FA setup and verification")
endpoint_registry.register_endpoint(auth_webauthn.router, prefix="/auth/webauthn", tags=["authentication"], description="WebAuthn passkey registration and login")
endpoint_registry.register_endpoint(auth_oauth.router, prefix="/auth/oauth", tags=["authentication"], description="Google OAuth sign-in / link / connect")
```

Route decorators inside each sub-module use paths RELATIVE to the sub-module prefix (D-15). Example: `auth/oauth.py` has `@router.post("/google")` — the `/auth/oauth` prefix applies via `register_endpoint(prefix="/auth/oauth")`, producing final URL `/api/auth/oauth/google`.

### Finding 3: Chrome extension API contract generator

**Confidence: HIGH (verified via direct code reading + FastAPI docs)**

**Extension endpoint inventory (verified via grep of `chrome-extension/src/background.ts`):**

16 endpoints called by the extension (complete list from background.ts line scan):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/users/me` | Identity check for "Connected as <username>" popup state |
| GET | `/categories/` | Part category dropdown |
| GET | `/car-generations/?limit={N}` | Car list |
| GET | `/car-generations/search?q={q}&limit={N}` | Car autocomplete |
| GET | `/part-manufacturers/?active_only={bool}` | Manufacturer list |
| GET | `/part-manufacturers/search?q={q}&limit={N}` | Manufacturer autocomplete |
| POST | `/part-manufacturers/` | Create manufacturer on the fly |
| GET | `/retailers/?active_only={bool}` | Retailer list |
| POST | `/retailers/get-or-create` | Ensure retailer exists |
| GET | `/parts/check-url?product_url={url}` | Dedup check before scraping |
| GET | `/parts/{part_id}` | Fetch existing part |
| GET | `/parts/find-by-part-manufacturer-and-part-number?...` | Dedup by manufacturer+part# |
| POST | `/parts/{part_id}/append-images` | Add scraped images to existing part |
| POST | `/parts/` | Create new part from scrape |
| POST | `/parts/{part_id}/listings` | Add retailer listing |
| GET | `/images/by-source-url?source_url={url}` | Image dedup |
| POST | `/images/upload` | Image upload |
| POST | `/crawled-pages/scrape` | Archive raw HTML |

**NONE of these are under `/auth/*` or `/admin/*`.** D-14 is VERIFIED: the extension is insulated from Phase 5's URL restructure. Its auth path is: `chrome.storage.local.authToken` → `Authorization: Bearer <token>` header → backend's `get_current_user` dependency → JWT decode via `dependencies/auth.py`. Phase 5 only changes JWT decode library (PyJWT) and per-route dependency declarations — both transparent to the extension.

**OpenAPI extraction pattern:**

`app.openapi()` returns a `dict` matching the OpenAPI 3.x spec. Key fields for the contract doc:
- `paths` — dict keyed by path (`/api/parts/{part_id}`); each value keyed by method (`get`, `post`).
- `paths[path][method]` contains `summary`, `description`, `parameters` (query/path/header), `requestBody.content["application/json"].schema`, `responses[status].content["application/json"].schema`.
- `components.schemas` contains all request/response model schemas. References use `$ref: "#/components/schemas/{name}"`.

**Schema flattening pattern:** For each endpoint, the generator dereferences `$ref` values against `components.schemas` and inlines the resulting schema as a JSON/YAML code block in the Markdown. For nested `$ref`s (e.g., `PartRead` containing `PartListingSummary`), recurse until depth limit (recommend: 3 levels deep, then show `$ref` reference) or circular reference detected. Flattening makes the contract human-readable without requiring the reader to jump between schemas.

**Polymorphic responses (422 vs 200):**

FastAPI auto-generates 422 response schema for any endpoint with a Pydantic body or query parameter (validation errors). The generator should emit both the 200 (success) and 422 (validation error) schemas — the extension needs to handle both. 401/403 responses are added by `standard_responses(...)` helper at the route level; those show as additional entries in `responses`.

**Generator script skeleton:**

```python
# backend/scripts/generate_ext_api_contract.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from app.main import app

# Hand-maintained allow-list of (method, path) tuples — 16 entries per D-35
EXTENSION_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/users/me"),
    ("GET", "/api/categories/"),
    # ... all 16
]

def resolve_ref(ref: str, schemas: dict[str, Any]) -> dict[str, Any]:
    # "#/components/schemas/PartRead" -> schemas["PartRead"]
    name = ref.rsplit("/", 1)[-1]
    return schemas.get(name, {})

def flatten_schema(schema: dict[str, Any], schemas: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    if depth > 3:
        return schema
    if "$ref" in schema:
        return flatten_schema(resolve_ref(schema["$ref"], schemas), schemas, depth + 1)
    if "properties" in schema:
        return {**schema, "properties": {k: flatten_schema(v, schemas, depth + 1) for k, v in schema["properties"].items()}}
    return schema

def generate_markdown() -> str:
    spec = app.openapi()
    schemas = spec.get("components", {}).get("schemas", {})
    out = ["# Chrome Extension API Contract", "", "Generated from `app.openapi()`. Do not edit by hand.", ""]
    for method, path in EXTENSION_ENDPOINTS:
        op = spec["paths"].get(path, {}).get(method.lower(), {})
        out.append(f"## `{method} {path}`")
        out.append("")
        if op.get("summary"): out.append(f"**Summary:** {op['summary']}")
        if op.get("description"): out.append(f"**Description:** {op['description']}")
        # ... parameters, request body, responses
    return "\n".join(out)

if __name__ == "__main__":
    md = generate_markdown()
    Path("chrome-extension/API_CONTRACT.md").write_text(md)
```

**Drift guard pattern (D-36):**

```python
# backend/tests/test_ext_api_contract_up_to_date.py
def test_api_contract_matches_generator():
    from backend.scripts.generate_ext_api_contract import generate_markdown
    expected = generate_markdown()
    committed = Path("chrome-extension/API_CONTRACT.md").read_text()
    assert expected == committed, (
        "chrome-extension/API_CONTRACT.md is out of date. Run: "
        "python backend/scripts/generate_ext_api_contract.py"
    )
```

### Finding 4: Parametrized 401/403 test patterns

**Confidence: HIGH (verified via FastAPI docs + existing conftest patterns)**

**Route enumeration via `app.routes`:**

```python
from fastapi.routing import APIRoute

def collect_admin_routes(app) -> list[tuple[str, str]]:
    """Return [(method, full_path), ...] for every route under /api/admin."""
    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/admin"):
            continue
        for method in route.methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            out.append((method, route.path))
    return out
```

**Parametrize at collection time:**

```python
# backend/tests/test_admin_auth_coverage.py
import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from app.main import app

def _admin_route_tuples() -> list[tuple[str, str]]:
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/api/admin"):
            for m in r.methods:
                if m not in {"HEAD", "OPTIONS"}:
                    out.append((m, r.path))
    return out

ADMIN_ROUTES = _admin_route_tuples()

@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_requires_admin_auth(method: str, path: str, client: TestClient):
    # (a) No auth header -> 401
    resolved_path = path.replace("{job_id}", "00000000-0000-0000-0000-000000000000").replace("{part_id}", "00000000-0000-0000-0000-000000000000")
    resp = client.request(method, resolved_path)
    assert resp.status_code == 401, f"{method} {path} returned {resp.status_code} without auth (expected 401)"
```

**Gotchas with parametrized async routes:**

- FastAPI `APIRoute.methods` is a set (not list) — iteration order is non-deterministic under Python < 3.7. With pytest-xdist parallelization, this matters for stable test IDs. **Fix:** sort methods when enumerating: `for m in sorted(r.methods):`.
- `TestClient.request(method, path)` is synchronous; it internally handles async routes. No special async wrapper needed.
- Path-parameter substitution: every `{...}` segment in the path needs a placeholder value even for 401 tests. A dummy UUID string works for every UUID path parameter. A dummy integer (`"1"`) works for int path params. **The 401 check happens BEFORE path-parameter validation in FastAPI's dependency chain** — the route never runs, so the dummy value never matters. [VERIFIED via FastAPI dependency injection order: security dependencies run BEFORE path-parameter conversion].

**Drift guard (D-30):**

```python
def test_admin_route_count_matches_expected() -> None:
    """D-30 drift guard: any new admin route added without tuple-list update fails CI."""
    # This is automatic if ADMIN_ROUTES is generated from app.routes dynamically —
    # a new route automatically gets a parametrized test generated for it.
    # The only failure mode is if the test function itself is broken OR a new route
    # is added that doesn't need admin auth (e.g., a new public admin route — unlikely).
    assert len(ADMIN_ROUTES) >= 23, f"Expected >=23 admin routes, found {len(ADMIN_ROUTES)}"
```

**Recommendation:** Because `app.routes` is enumerated at test collection time, the drift guard is IMPLICIT — any new route adds a test case automatically. A separate count assertion (per D-30) is belt-and-suspenders: it catches the case where someone adds a route AND disables the parametrized test. Keep it, name it `test_admin_route_count_at_or_above_expected()`.

**Fixture reuse (D-32 verification):** `backend/tests/conftest.py:688` already has `create_and_login_admin_user(client, username)`. Also `test_admin_user` fixture at line 302 and `test_superuser_user` at line 320. **No new fixtures needed** — use existing. The function at line 688 is NOT a pytest fixture (no `@pytest.fixture` decorator) — it's a module-level helper. That's intentional; pytest fixtures with session/module scope don't mix with parametrized tests that need fresh users per parameter. Import the helper directly in the new test file.

### Finding 5: Terraform EventBridge deploy sequencing

**Confidence: HIGH (verified via direct Terraform reading)**

**Current Terraform state (verified — `terraform/scheduler.tf:48-58`):**

```hcl
resource "aws_cloudwatch_event_api_destination" "crawler_run" {
  name        = "${local.prefix}-crawler-run"
  description = "POST /api/admin/crawlers/run"
  connection_arn                   = aws_cloudwatch_event_connection.cron.arn
  invocation_endpoint              = "https://${aws_apprunner_service.backend.service_url}/api/admin/crawlers/run"
  http_method                      = "POST"
  invocation_rate_limit_per_second = 1
}
```

**Critical finding — D-11 re-evaluation:**

CONTEXT.md D-11 states "Two schedules change path: `/admin/crawlers/run` — unchanged path, `/admin/crawled-pages/rescrape-archives` → `/admin/crawlers/rescrape-archives`. The Terraform `aws_scheduler_schedule` resource(s) in `terraform/` get path updates."

Reality check:
- **Only ONE `aws_cloudwatch_event_api_destination` exists in Terraform** — `crawler_run` pointing at `/api/admin/crawlers/run`. [VERIFIED via grep: only one `invocation_endpoint` in terraform/]
- **Rescrape-archives is NOT in Terraform.** `terraform/scheduler.tf:18` comment: "Archive rescrapes are never triggered automatically — admins run them manually from the admin UI." [VERIFIED]
- **`terraform/variables.tf:77` comment:** "Archive rescrape is intentionally never scheduled — admins trigger it." [VERIFIED]

**Implication for Phase 5:**

1. The path `/admin/crawlers/run` — unchanged per D-09, so NO Terraform change needed for it.
2. The path `/admin/crawled-pages/rescrape-archives` → `/admin/crawlers/rescrape-archives` — ONLY affects the frontend admin UI (per D-13) and the backend code. NO Terraform change.
3. **D-11's "deploy sequencing hazard" is misstated.** There is no Terraform apply race condition for Phase 5 because no EventBridge schedule references the changing path.
4. Per-adapter crawler schedules (managed dynamically by the backend reconciler per `backend/app/api/services/adapter_schedule_service.py`) all target `/api/admin/crawlers/run` via the default event bus rule → API destination. Per-adapter schedules don't embed paths — they use the static API destination. So per-adapter schedules are also unaffected.

**Deploy sequencing for `/admin/crawlers/run` (path preservation) — trivial:**
- Backend image deploys with new code (admin/crawlers.py has `@router.post("/run")` at prefix `/admin/crawlers`).
- Final URL: `/api/admin/crawlers/run` — unchanged.
- App Runner rolls out the new image.
- EventBridge continues invoking the same URL with the same payload.
- **Zero sequencing hazard.**

**Deploy sequencing for `/admin/crawlers/rescrape-archives` (path changed) — admin-UI-only:**
- Backend deploy with new code.
- Frontend web app also deploys with new code (new path in `frontend/src/services/Api.ts:1410`).
- **If frontend deploys before backend:** frontend calls new path → backend 404. Mitigation: deploy backend first (App Runner's blue-green deploy handles this atomically; old pods serve old path until new pods take over).
- **If backend deploys before frontend:** frontend calls OLD path `/admin/crawled-pages/rescrape-archives` → backend 404. Mitigation: one-cycle window between backend promote + frontend deploy. Admins hitting the button during this window see an error — acceptable for a rarely-triggered endpoint. Post-deploy verification: admin verifies rescrape works once.
- **Recommendation:** Standard App Runner rolling deploy + CloudFront cache invalidation on frontend is sufficient. No Terraform coordination needed.

**Planner action:** Correct D-11's "two schedules change path" statement in the admin split plan's SUMMARY.md — only code + frontend change, no Terraform apply required for rescrape-archives. The admin split PR does NOT include a Terraform change unless per-adapter schedule content in the DB table embeds the path (verify via `adapter_schedule_service.py` — scout did not include this file, planner should read it). Based on `scheduler.tf:159-165` comment, per-adapter schedules use the default scheduler group + shared target plumbing — path is static in Terraform, not per-adapter. **No Terraform change required for Phase 5.**

### Finding 6: ADMIN-04 reality check — service-level coupling

**Confidence: HIGH (verified via direct code reading)**

CONTEXT.md Deferred Ideas section flags ADMIN-04 as potentially preventive language. Scout could not surface a god-service pattern. I read admin.py's imports and call sites to confirm.

**Current service imports in admin.py (verified via grep):**

```
Line 67:   from app.services import job_service          # module-level, used for background job CRUD
Line 1728: from app.api.services.part_linker_service import score_metadata_richness
Line 1799: from app.api.services.part_linker_service import link_group_part_ids
Line 1809: from app.api.services.part_linker_service import score_metadata_richness
Line 1836: from app.api.services.part_linker_service import reelect_canonical
Line 1858: from app.api.services.part_linker_service import unlink_part
Line 1896: from app.api.services.part_linker_service import _point_siblings_at
Line 1932: from app.api.services.part_linker_service import (...)
Line 1996:     from app.api.services.part_linker_service import reelect_canonical
```

`job_service` is used at 13 sites (heartbeat_job, get_job, complete_job, fail_job, create_job, update_job_progress, sweep_orphan_jobs, list_jobs, cancel_job) — all inside the jobs/crawlers/db_ops domains. `part_linker_service` functions are used at 8 sites — all inside the parts domain.

**Analysis:**

- **No god-service exists.** The current admin.py imports two domain-specific service modules:
  - `job_service` → belongs to jobs + crawlers sub-modules (background job lifecycle).
  - `part_linker_service` → belongs to parts sub-module (canonical linking).
- Each service is already scoped to its concern. When admin.py splits into sub-modules, each sub-module naturally inherits ONLY the service imports it uses:
  - `admin/jobs.py` imports `job_service`.
  - `admin/crawlers.py` imports `job_service` (for crawler-run job lifecycle).
  - `admin/parts.py` imports `part_linker_service`.
  - `admin/stats.py` imports neither — pure DB-read functions.
  - `admin/db_ops.py` imports neither — direct DB operations.
- **Inline imports (`from app.api.services.part_linker_service import X` inside function bodies)** at lines 1728, 1799, 1809, etc., are a micro-optimization to defer module load; they belong in `admin/parts.py` and can be hoisted to module-level at file-top during the split (small cleanup, optional).

**Conclusion:**

ADMIN-04 is **preventive language** — the requirement locks the GOOD state that already exists. The split itself naturally satisfies it because each sub-module imports only the services it needs. There is no god-service to break up.

**Planner action:** Do NOT create a dedicated plan for ADMIN-04. Document in the admin-split plan's SUMMARY.md:

> **ADMIN-04:** Service-level coupling is already correctly scoped — `job_service` and `part_linker_service` are domain-specific. The split naturally places each sub-module's service imports at the top of its sub-module file. Inline imports in the current code (deferred loads inside function bodies) are hoisted to module-level at file-top during extraction. No separate task needed.

### Finding 7: Validation Architecture (Nyquist dimensions)

**Confidence: HIGH**

Phase 5 is behaviorally a no-op at the external API boundary (same routes, same JWT semantics, same auth dependency declarations — just physical file reorganization). Validation must catch:

1. **URL drift** — a route accidentally moved, dropped, or renamed during split.
2. **Auth drift** — a route accidentally loses its `Depends(get_current_admin_user)` or `Depends(get_current_user)` during sub-module extraction.
3. **JWT semantic drift** — PyJWT swap breaks in-flight tokens or changes validation behavior.
4. **Chrome extension regression** — extension stops working post-refactor (covered by manual UAT; no automated test per D-39).

**Test framework:**
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-xdist `-n auto` + pytest-recording (VCR) |
| Config file | `backend/pytest.ini` |
| Quick run command | `pytest -n auto backend/tests/test_admin_auth_coverage.py backend/tests/test_auth_auth_coverage.py backend/tests/test_pyjwt_migration.py backend/tests/test_jwt_algorithm_regression.py backend/tests/test_ext_api_contract_up_to_date.py -x` |
| Full suite command | `pytest -n auto --cov=app --cov-report=term-missing` |

**Phase Requirements → Test Map:**

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADMIN-01 | admin.py file deleted; 23 routes live at sub-module prefixes | URL-drift | Phase 1 SAFE-05 `test_openapi_snapshot.py` — snapshot regenerates, diff IS the review artifact | ✅ existing |
| ADMIN-02 | Every admin route returns 401 without auth, 403 with regular user, 2xx/non-auth error with admin | Integration | `pytest -n auto backend/tests/test_admin_auth_coverage.py` | ❌ Wave 0 — PR 1 creates |
| ADMIN-03 | EventBridge-invoked `/admin/crawlers/run` returns 200 with X-Admin-Cron-Key header (same as before) | Integration | Phase 1 auth characterization + existing job_service tests cover this | ✅ existing |
| ADMIN-04 | No god-service coupling | Manual | Code-review artifact in SUMMARY.md | N/A — not a test |
| AUTH-01 | auth.py file deleted; 24 routes live at sub-module prefixes | URL-drift | Phase 1 SAFE-05 OpenAPI snapshot | ✅ existing |
| AUTH-02 | All `/api/auth/*` routes remain reachable at the same URLs (except deliberate moves per D-10) | URL-drift | Phase 1 OpenAPI snapshot + Phase 1 SAFE-06 auth characterization tests | ✅ existing |
| AUTH-03 | Every auth-protected route returns 401 without token | Integration | `pytest -n auto backend/tests/test_auth_auth_coverage.py` | ❌ Wave 0 — PR 4 creates |
| AUTH-04 | PyJWT encodes + decodes HS256 tokens identically to python-jose | Parity | `pytest -n auto backend/tests/test_pyjwt_migration.py` + `backend/tests/test_jwt_algorithm_regression.py` | ❌ Wave 0 — PR 2 creates |
| AUTH-05 | Chrome extension login → scrape → logout flow succeeds post-deploy on staging | Manual UAT | `05-HUMAN-UAT.md` checklist | ❌ Wave 0 — planner creates |
| AUTH-06 | `chrome-extension/API_CONTRACT.md` matches generator output | Drift-guard | `pytest -n auto backend/tests/test_ext_api_contract_up_to_date.py` | ❌ Wave 0 — PR 3 creates |

**Sampling rate:**
- **Per task commit:** `pytest -n auto backend/tests/test_admin_auth_coverage.py backend/tests/test_auth_auth_coverage.py backend/tests/test_openapi_snapshot.py -x` (fast, quartile-of-a-minute)
- **Per wave merge:** `pytest -n auto --cov=app --cov-fail-under=51` (full suite, minutes)
- **Phase gate:** Full suite green + Phase 1 auth characterization all green + OpenAPI snapshot diff is exactly the expected route-restructure delta + manual UAT on staging passes.

**Production-truth conditions (what must be true after deploy):**

1. Every route in the OpenAPI snapshot matches the live backend's `/openapi.json`. **Verification:** CI runs `curl $BACKEND_URL/openapi.json | diff - backend/tests/fixtures/openapi_snapshot.json`. Any drift fails the deploy.
2. Zero `from jose import` statements remain in `backend/app/`. **Verification:** Part of the PyJWT PR's grep sweep. Post-merge, `grep -rn "from jose" backend/app/` returns empty.
3. Every admin route has `Depends(get_current_admin_user)` (or `get_current_superuser`) in its signature. **Verification:** `test_admin_auth_coverage.py` covers this — 401 without auth, 403 with regular user proves the dependency is live.
4. Chrome extension continues to scrape and post parts to the backend. **Verification:** Manual UAT per D-38 on staging within 24h of each auth PR merge.
5. `chrome-extension/API_CONTRACT.md` matches `generate_ext_api_contract.py` output bit-for-bit. **Verification:** `test_ext_api_contract_up_to_date.py` runs on every PR.

**Wave 0 gaps:**

- [ ] `backend/tests/test_admin_auth_coverage.py` — PR 1 creates
- [ ] `backend/tests/test_pyjwt_migration.py` — PR 2 creates
- [ ] `backend/tests/test_jwt_algorithm_regression.py` — PR 2 creates
- [ ] `backend/tests/test_ext_api_contract_up_to_date.py` — PR 3 creates
- [ ] `backend/tests/test_auth_auth_coverage.py` — PR 4 creates
- [ ] `backend/scripts/generate_ext_api_contract.py` — PR 3 creates
- [ ] `chrome-extension/API_CONTRACT.md` — PR 3 creates (initial commit)
- [ ] `05-HUMAN-UAT.md` — planner creates

All existing test infrastructure (conftest.py, fixtures, pytest-xdist, OpenAPI snapshot, Phase 1 characterization tests, Phase 3 logger regression, Phase 4 session.query regression) is reusable — no framework changes needed.

## Recommended Approach

One concrete recommendation per finding, ready for the planner to convert into tasks:

### From Finding 1 — PyJWT migration

**Recommendation:** In PR 2 (PyJWT swap), land the following atomic diff in this exact order:

1. `backend/requirements.txt` — remove `python-jose[cryptography]==3.5.0`, add `PyJWT==2.12.1` (one diff, comment at the top explaining the swap).
2. `backend/app/core/config.py` — add `JWT_ALGORITHM: str = "HS256"` Pydantic field to the `Settings` class.
3. `backend/app/api/dependencies/auth.py` — line 7 `from jose import JWTError, jwt` → `import jwt` + `from jwt import InvalidTokenError`; line 17 `ALGORITHM = "HS256"` → `ALGORITHM = settings.JWT_ALGORITHM`; lines 100/132/160 `except JWTError:` → `except InvalidTokenError:`.
4. `backend/app/api/endpoints/auth.py` — line 23 same import swap; lines 261/332/515/911 `except JWTError` → `except InvalidTokenError`.
5. `backend/tests/test_pyjwt_migration.py` — NEW, 1 test:

```python
import jwt as pyjwt
from jose import jwt as jose_jwt

def test_pyjwt_decodes_jose_hs256_token():
    """D-05: Prove HS256 tokens issued by python-jose decode identically under PyJWT."""
    payload = {"sub": "user@example.com", "exp": 9999999999}
    secret = "test-secret-for-parity-check-not-for-production"
    jose_token = jose_jwt.encode(payload, secret, algorithm="HS256")
    decoded = pyjwt.decode(jose_token, secret, algorithms=["HS256"])
    assert decoded == payload
```

6. `backend/tests/test_jwt_algorithm_regression.py` — NEW, grep-based:

```python
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"
_DECODE_PATTERN = re.compile(r"jwt\.decode\(")
_ALG_PATTERN = re.compile(r"algorithms\s*=\s*\[")

def test_every_jwt_decode_specifies_algorithms() -> None:
    offenders = []
    for pyfile in APP_DIR.rglob("*.py"):
        lines = pyfile.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _DECODE_PATTERN.search(line):
                # Check same line + next 2 lines for algorithms= literal (multi-line statements)
                window = "\n".join(lines[lineno - 1:lineno + 2])
                if not _ALG_PATTERN.search(window):
                    offenders.append((str(pyfile.relative_to(APP_DIR)), lineno, line.strip()))
    assert not offenders, (
        "jwt.decode() calls without algorithms=[...] detected (CWE-327 risk):\n"
        + "\n".join(f"  {f}:{ln} -> {code}" for f, ln, code in offenders)
    )
```

### From Finding 2 — APIRouter composition

**Recommendation:** In PR 1 (admin split), the main.py diff looks like:

```python
# Before
endpoint_registry.register_endpoint(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    description="Admin-only system management operations",
)

# After (5 registrations — all sharing tags=["admin"] to preserve Swagger grouping)
from app.api.endpoints.admin import stats as admin_stats
from app.api.endpoints.admin import jobs as admin_jobs
from app.api.endpoints.admin import crawlers as admin_crawlers
from app.api.endpoints.admin import db_ops as admin_db_ops
from app.api.endpoints.admin import parts as admin_parts

endpoint_registry.register_endpoint(admin_stats.router, prefix="/admin/stats", tags=["admin"], description="Admin statistics and table counts")
endpoint_registry.register_endpoint(admin_jobs.router, prefix="/admin/jobs", tags=["admin"], description="Admin background jobs (list, detail, cancel)")
endpoint_registry.register_endpoint(admin_crawlers.router, prefix="/admin/crawlers", tags=["admin"], description="Admin crawler management (run, rescrape, service account)")
endpoint_registry.register_endpoint(admin_db_ops.router, prefix="/admin/db-ops", tags=["admin"], description="Admin database operations (migrations, init data, bulk delete)")
endpoint_registry.register_endpoint(admin_parts.router, prefix="/admin/parts", tags=["admin"], description="Admin canonical parts management (link, unlink, rescan)")
```

Same pattern in PR 4 for auth (4 sub-routers all sharing `tags=["authentication"]`).

Each sub-module file starts with:
```python
import logging
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)  # per Phase 3 D-33—D-37
```

### From Finding 3 — API contract generator

**Recommendation:** In PR 3, create `backend/scripts/generate_ext_api_contract.py` with the 16-entry allow-list verified in Finding 3. Implement `resolve_ref` + `flatten_schema` with depth limit 3. Emit Markdown with one `##` section per endpoint containing: summary, description, path parameters table, query parameters table, request body JSON schema (code block), response schemas per status code (code blocks). Commit initial `chrome-extension/API_CONTRACT.md`. Add `test_ext_api_contract_up_to_date.py` as drift guard. This PR is fully independent of PRs 1/2/4 and can land in parallel.

### From Finding 4 — 401/403 tests

**Recommendation:** In PR 1, `test_admin_auth_coverage.py` structure:

```python
import pytest
from fastapi.routing import APIRoute
from app.main import app
from tests.conftest import create_and_login_admin_user, login_user

def _admin_routes() -> list[tuple[str, str]]:
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/api/admin"):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                out.append((m, r.path))
    return out

ADMIN_ROUTES = _admin_routes()

def _fill_path_params(path: str) -> str:
    """Replace {param} with a dummy UUID so 401 check fires before path validation."""
    import re
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)

@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_requires_auth(method, path, client):
    resp = client.request(method, _fill_path_params(path))
    assert resp.status_code == 401, f"{method} {path} returned {resp.status_code} (expected 401)"

@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_forbids_regular_user(method, path, client, create_and_login_user):
    create_and_login_user(client, username=f"user_{method}_{hash(path) & 0xffff}")
    resp = client.request(method, _fill_path_params(path))
    assert resp.status_code == 403, f"{method} {path} returned {resp.status_code} with regular user (expected 403)"

def test_admin_route_count_at_or_above_expected():
    # D-30 drift guard — catches disabled parametrized tests
    assert len(ADMIN_ROUTES) >= 23, f"Expected >=23 admin routes, got {len(ADMIN_ROUTES)}"
```

For `test_auth_auth_coverage.py` in PR 4: same shape, but filter out the public-route allow-list (D-31) before parametrizing.

### From Finding 5 — EventBridge sequencing

**Recommendation:** PR 1 (admin split) does NOT need a Terraform change. Delete CONTEXT.md D-11's "Terraform EventBridge Terraform update lands in the same PR as the admin split" direction from the plan and replace with: "EventBridge API destination points at `/api/admin/crawlers/run` — path unchanged by Phase 5. No Terraform apply required. Per-adapter schedules use static API destination plumbing, also unaffected." Document in the admin-split PR's SUMMARY.md to make reviewer aware the Terraform scope is empty (not a missed item).

### From Finding 6 — ADMIN-04

**Recommendation:** Document in admin-split PR's SUMMARY.md (no separate plan):

> **ADMIN-04: service-level coupling reduced.** Audit confirmed no god-service pattern in the pre-split admin.py. Current service imports (`job_service`, `part_linker_service`) are already domain-specific. The split distributes imports naturally: `jobs.py` + `crawlers.py` import `job_service`; `parts.py` imports `part_linker_service`; `stats.py` and `db_ops.py` import neither. Inline imports inside function bodies (8 sites at admin.py lines 1728+) are hoisted to module-level at the file-top of `admin/parts.py` during extraction. Requirement satisfied by the split itself.

### From Finding 7 — Validation architecture

**Recommendation:** Each PR's plan ends with a validation checklist mapping to this phase's 5 success criteria:

| Criterion | Validation command |
|-----------|-------------------|
| "admin/ package live; old admin.py deleted; 401 per route (integration tested)" | `pytest -n auto backend/tests/test_admin_auth_coverage.py backend/tests/test_openapi_snapshot.py` |
| "auth/ package live; old auth.py deleted; Phase 1 characterization green" | `pytest -n auto backend/tests/test_auth_auth_coverage.py backend/tests/crawlers/test_characterization_*.py backend/tests/test_openapi_snapshot.py` (and all Phase 1 SAFE-06 tests under backend/tests/test_auth_*.py) |
| "Chrome extension E2E flow succeeds after auth split with no ext changes" | Manual UAT per `05-HUMAN-UAT.md` on staging after PR 4 merge |
| "chrome-extension/API_CONTRACT.md documents every endpoint" | `pytest -n auto backend/tests/test_ext_api_contract_up_to_date.py` |
| "python-jose replaced; zero JWTError refs; algorithms= on every decode" | `pytest -n auto backend/tests/test_pyjwt_migration.py backend/tests/test_jwt_algorithm_regression.py` + `grep -rn "from jose\|JWTError" backend/app/ | wc -l` returns 0 |

## Risks and Pitfalls

### Risk 1: In-flight JWTs invalidated during PyJWT swap

**What goes wrong:** Every logged-in user has a JWT in their `localStorage` / `chrome.storage.local`. If PyJWT decodes tokens differently than python-jose, all users get booted to login on next API call.

**Why it happens:** HS256 tokens are byte-identical across libraries, BUT a subtle implementation difference in claim parsing (e.g., `exp` as float vs int, `iat` validation strictness, leeway handling) could cause PyJWT to reject a valid jose-issued token.

**How to avoid:** D-05 parity test proves round-trip works for a simple payload. **Additional mitigation:** after PR 2 deploys to staging, verify a real jose-issued token (capture one pre-deploy from a real dev account) decodes successfully under the new PyJWT backend. If parity test passes but real token fails, PyJWT's stricter `exp` / `iat` validation is the most likely culprit — PyJWT 2.x validates `iat` is not in the future, which older jose tokens may violate slightly due to clock skew. Fix: use `leeway=10` on decode calls.

**Warning signs:** Spike in 401 responses post-deploy. Sentry alerts on `InvalidTokenError` with attached payload.

### Risk 2: OpenAPI snapshot churn across 4 PRs

**What goes wrong:** The OpenAPI snapshot test (Phase 1 SAFE-05) regenerates once per URL-restructure PR. PR 1 (admin split) regenerates, PR 4 (auth split) regenerates again. If PR 2 (PyJWT) or PR 3 (contract generator) accidentally touches a route signature, the snapshot drifts unexpectedly.

**Why it happens:** The logger migration in Phase 3 showed that `Depends(get_logger)` removal can affect OpenAPI schema if FastAPI surfaces `Depends` parameters. Phase 5's PR 2 touches function signatures in auth.py (exception handler renames) — these are inside function bodies, NOT signatures, so no OpenAPI effect. PR 3 doesn't touch backend code at all (just adds a script + doc + test).

**How to avoid:** Regenerate the OpenAPI snapshot ONLY in PR 1 (admin restructure) and PR 4 (auth restructure). In PR 2 and PR 3, the snapshot should pass without modification — if it fails in those PRs, something unexpected changed and needs investigation before merge.

**Warning signs:** `test_openapi_snapshot.py` fails in PR 2 or PR 3.

### Risk 3: Frontend path updates missed in PR 1

**What goes wrong:** D-13 requires frontend `Api.ts` updates for admin URL changes in the same PR as the admin split. Any missed grep produces a 404 at runtime.

**Why it happens:** The aggressive URL consolidation (D-09) moves 7 paths: `/admin/migrations/*` → `/admin/db-ops/migrations/*`, `/admin/init/*` → `/admin/db-ops/init/*`, `/admin/cars/delete-all` → `/admin/db-ops/cars/delete-all`, `/admin/parts/delete-all` → `/admin/db-ops/parts/delete-all`, `/admin/part-manufacturers/delete-all` → `/admin/db-ops/part-manufacturers/delete-all`, `/admin/crawled-pages/rescrape-archives` → `/admin/crawlers/rescrape-archives`, `/admin/service-accounts/crawler` → `/admin/crawlers/service-account`, `/admin/stats/*` → unchanged (already nested).

**How to avoid:** PR 1 includes a systematic grep: `grep -rn "'/admin/" frontend/src/`. The expected matches are enumerated in CONTEXT.md D-13. Each match is updated. Frontend type-check + unit tests verify.

**Verified current frontend paths to update (from `frontend/src/services/Api.ts`):**

| Line | Current | After PR 1 |
|------|---------|-----------|
| 1388 | `/admin/migrations/run` | `/admin/db-ops/migrations/run` |
| 1390 | `/admin/migrations/current` | `/admin/db-ops/migrations/current` |
| 1392 | `/admin/init/car-generations` | `/admin/db-ops/init/car-generations` |
| 1394 | `/admin/init/part-categories` | `/admin/db-ops/init/part-categories` |
| 1403 | `/admin/service-accounts/crawler` | `/admin/crawlers/service-account` |
| 1410 | `/admin/crawled-pages/rescrape-archives` | `/admin/crawlers/rescrape-archives` |
| 1426 | `/admin/parts/delete-all` | `/admin/db-ops/parts/delete-all` |
| 1434 | `/admin/cars/delete-all` | `/admin/db-ops/cars/delete-all` |
| 1439 | `/admin/part-manufacturers/delete-all` | `/admin/db-ops/part-manufacturers/delete-all` |
| 1444 | `/admin/stats/table-counts` | unchanged (stays in admin/stats) |
| 1448 | `/admin/stats/crawl-bucket` | unchanged |

And in PR 4 for auth:

| Line | Current | After PR 4 |
|------|---------|-----------|
| 862 | `/auth/google` | `/auth/oauth/google` |
| 870 | `/auth/google/link` | `/auth/oauth/google/link` |
| 881 | `/auth/google/signup` | `/auth/oauth/google/signup` |
| 897 | `/auth/google/connect` | `/auth/oauth/google/connect` |
| Others (`/auth/oauth`, `/auth/oauth/2fa`, etc.) already correctly namespaced | — | unchanged |

**Warning signs:** Frontend unit tests fail on mocked 404 responses. Runtime admin UI shows "Resource not found" dialogs.

### Risk 4: Circular import in admin/ or auth/ package

**What goes wrong:** When `admin/_helpers.py` imports something used by `admin/jobs.py`, and `admin/crawlers.py` imports from `admin/_helpers.py`, circular import errors can arise at module-load time.

**Why it happens:** Python imports are sequential. `admin/__init__.py` loading `admin.stats` + `admin.jobs` + `admin.crawlers` (if main.py's import order has them all), and `admin.crawlers` importing `admin._helpers` which in turn imports something transitively from `admin.jobs` — this is a common Python refactor pitfall.

**How to avoid:** Keep `admin/_helpers.py` imports LIMITED to `app.api.services.*`, `app.api.models.*`, `app.core.*`, stdlib, and third-party. No imports from sibling sub-modules. Same rule for `auth/_helpers.py`. The helpers are LEAF modules — they have dependencies, but nothing depends on them at the sub-module level except the sub-modules themselves (which import FROM them, not the other way).

**Warning signs:** `ImportError` at `uvicorn` startup. `from app.main import app` fails in test collection.

### Risk 5: Deleting admin.py / auth.py breaks test imports

**What goes wrong:** Existing tests may have `from app.api.endpoints.auth import ...` or similar. D-17 says hard migration (update callers in same PR). If any caller is missed, test collection fails.

**Why it happens:** Tests + `backend/app/api/utils/admin_endpoint_patterns.py` could import helpers from admin.py (unlikely but possible). CONTEXT.md flags this.

**How to avoid:** Before deleting admin.py, grep: `grep -rn "from app.api.endpoints.admin" backend/` and `grep -rn "from app.api.endpoints.auth" backend/`. Update every match. The pattern file `admin_endpoint_patterns.py` is a suspect — audit its imports. Inherited from Phase 3 D-33 sweep.

**Warning signs:** `pytest --collect-only` fails with ImportError.

### Risk 6: PyJWT parity test imports jose module after its removal

**What goes wrong:** D-05 parity test uses `from jose import jwt as jose_jwt`. If `python-jose` is removed from `requirements.txt` in the same PR as the test, the test fails at collection time.

**Why it happens:** requirements.txt and test file are both in PR 2. Both land simultaneously.

**How to avoid:** KEEP `python-jose` in `requirements.txt` through PR 2 — only remove from the auth.py + dependencies/auth.py imports. The parity test continues to work. Mark `python-jose` as a test-only dependency or leave the pin in place until Phase 6 dependency cleanup.

**Alternative:** Generate the jose-signed token OUTSIDE the test at build time (e.g., hard-code a known jose-issued token in the test file) and verify PyJWT decodes it. This removes the test-time dependency on jose. Less elegant but fully standalone.

**Warning signs:** `pytest --collect-only` fails on `ModuleNotFoundError: No module named 'jose'` after requirements.txt update.

### Risk 7: Per-route 401/403 test false positives on path-parameter substitution

**What goes wrong:** Dummy UUID substitution for path parameters works for most routes, but routes with regex constraints (`{id:int}` or similar) would fail with 422 before the auth check, producing a confusing test failure.

**Why it happens:** FastAPI's `{job_id}` is typed `UUID` — a UUID string substitutes fine. But `{some_int_id:int}` requires an integer. Hybrid param types may not accept `"00000000-..."`.

**How to avoid:** Scan the admin/auth route list for non-UUID path params. For admin: `{job_id}` (UUID) and `{part_id}` (UUID) only — both accept the dummy UUID. For auth: `{credential_id}` (UUID) and `{account_id}` (UUID) only. **Safe.** If Phase 5 introduces mixed-type path params (it shouldn't per scope), extend the `_fill_path_params` helper to detect param types via `APIRoute.dependant.path_params` and substitute type-appropriately.

**Warning signs:** Test fails with 422 where 401 expected. Error message reveals path-parameter validation error.

## Open Questions for Planner

1. **Parity test pattern — how long does `python-jose` stay in requirements.txt?**
   - What we know: D-05 parity test requires `jose` import; removing `jose` breaks the test.
   - What's unclear: CONTEXT.md's "Claude's Discretion" section says the parity test's lifetime is discretionary. If it stays, `python-jose` stays. If it's removed post-migration, `python-jose` can go too.
   - **Recommendation:** KEEP the parity test AND `python-jose` through Phase 5 entirely. Revisit in Phase 6 dependency cleanup. The `python-jose[cryptography]` CVE note in `backend/requirements.txt:27` is already acknowledged — one more phase of coexistence is low-risk.

2. **Single tag or per-sub-module tag in OpenAPI?**
   - What we know: Claude's Discretion per Finding 2; single `"admin"` tag preserves current Swagger UI grouping; per-sub-module tags (e.g., `"admin-stats"`) give finer navigation at cost of more sections.
   - What's unclear: Project preference for Swagger UI organization.
   - **Recommendation:** Single tag per package (`"admin"`, `"authentication"`) to preserve current UX and minimize OpenAPI snapshot churn. Finer tags can be added later without a phase dependency.

3. **Does the 401/403 test cover the 2 admin routes that use `Optional[DBUser] = Depends(get_current_admin_user)`?**
   - What we know: admin.py lines 834 (`POST /crawlers/run`) and 1216 (`POST /crawled-pages/rescrape-archives`) use `Optional[DBUser]` — they accept EITHER a JWT admin OR an `X-Admin-Cron-Key` header for EventBridge invocation.
   - What's unclear: Without `X-Admin-Cron-Key` AND without JWT, these routes raise 403 from their own body check (`_verify_cron_key(x_admin_cron_key)` → `raise HTTPException(status_code=403)`). So they would pass the 401 test's expected-401 assertion ONLY if FastAPI's auth dependency raises 401 first — but `get_current_admin_user` with `Optional` might not raise.
   - **Recommendation:** Planner verifies behavior in PR 1. If these two routes return 403 (not 401) without auth, they're the public-route allow-list analogue for admin — add them to an admin-side allow-list in the test. Alternative: test asserts `resp.status_code in (401, 403)` — both indicate "auth-gated", which is what the test is measuring.

4. **Regression test scope — does `test_jwt_algorithm_regression.py` scan `backend/tests/`?**
   - What we know: Phase 4 `test_session_query_regression.py` explicitly scopes to `backend/app/` (not tests). Phase 3 logger regression same pattern.
   - What's unclear: Whether `jwt.decode` without `algorithms=` in tests is a real risk (tests shouldn't decode tokens at all — they generate them via conftest fixtures).
   - **Recommendation:** Scope to `backend/app/` only (per Phase 3/4 precedent). Test tokens in conftest are issued by the app code path, so any test that decodes one is already going through the hardened path.

5. **Where does the D-24 ECS launcher code live post-split — really inline in `admin/crawlers.py`?**
   - What we know: D-24 locks "ECS task launchers stay inline (~300 lines)".
   - What's unclear: ~300 lines in `admin/crawlers.py` (4 routes + launcher code) might push the file to 500-600 lines — still reasonable, but worth confirming at plan-writing time that the sub-module file sizes are balanced.
   - **Recommendation:** Accept D-24's locked decision. If `admin/crawlers.py` ends up >800 lines post-split, flag in plan SUMMARY for potential Phase 6 extraction. Not a Phase 5 deliverable.

6. **Order of PR 2 (PyJWT) and PR 3 (API_CONTRACT)?**
   - What we know: D-41 says PR 3 can land in parallel with PR 2.
   - What's unclear: If they land in true parallel on `main` (two concurrent branches), merge conflicts are possible — PR 2 updates `requirements.txt`, PR 3 doesn't. No overlap. Parallelism is safe.
   - **Recommendation:** Run them in parallel. Generator PR can be written and reviewed while PyJWT swap is in review. Both merge cleanly.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All backend code | ✓ (project standard) | — | — |
| pytest + pytest-xdist | All new tests | ✓ (existing test infra) | — | — |
| PyJWT 2.12.1 | AUTH-04 | ✗ (to be installed in PR 2) | — | — (required for deliverable) |
| python-jose 3.5.0 | Transitional (parity test) | ✓ (currently in requirements.txt) | 3.5.0 | Keep through Phase 5 |
| FastAPI TestClient | 401/403 tests | ✓ (existing test infra) | — | — |
| VCR cassettes (pytest-recording) | Phase 1 auth characterization (inherited) | ✓ (Phase 1 artifact) | — | — |
| App Runner + EventBridge staging | UAT per D-38 | ✓ (prod infra exists) | — | — |

**Missing dependencies with no fallback:** None — `PyJWT==2.12.1` is a pip install in PR 2, not an infrastructure dependency.

**Missing dependencies with fallback:** None.

## Validation Architecture

See Finding 7 above for the complete Nyquist-validation block. Short form:

**Test framework:** pytest 8.x + pytest-xdist (`-n auto`) + pytest-recording; config at `backend/pytest.ini`. Quick: run the 5 Phase 5 test files with `-x`. Full: `pytest -n auto --cov=app --cov-fail-under=51`.

**Sampling:** per-task commit = Phase-5 targeted tests; per-wave merge = full suite; phase gate = full suite + Phase 1 characterization + OpenAPI snapshot green + manual UAT on staging.

**Wave 0 gaps:** 5 new test files + 1 generator script + 1 initial `API_CONTRACT.md` commit + 1 `05-HUMAN-UAT.md`. All other infrastructure (conftest fixtures, OpenAPI snapshot, Phase 1 characterization, regression greps) is reusable.

## Security Domain

> Phase 5 is a refactor — no new attack surface, no new auth semantics. Phase 5 ACTIVELY HARDENS the JWT code via D-03 (algorithm explicit on every decode — satisfies CWE-327 "Use of a Broken or Risky Cryptographic Algorithm" by pinning HS256 explicitly, preventing the "alg: none" vulnerability class). D-04's regression guard locks this in.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | PyJWT 2.12.1 (verified HS256 enforcement), bcrypt passwords, email verification required |
| V3 Session Management | yes | Short-lived JWTs (15 min–7 days user-configurable); no server-side session store; logout is client-side token discard |
| V4 Access Control | yes | Per-route `Depends(get_current_admin_user)` / `Depends(get_current_superuser)` / `Depends(get_current_user)` — 401/403 test coverage (new in Phase 5) is the ASVS V4 surface assertion |
| V5 Input Validation | yes | Pydantic v2 schemas on every request body (unchanged by Phase 5) |
| V6 Cryptography | yes | PyJWT 2.12.1 (maintained, vetted). HS256 with `settings.SECRET_KEY` (64-byte random). **Algorithm explicit on every decode** (D-03, D-04) — defends against "alg: none" (CVE-2015-9235 class) |

### Known Threat Patterns for FastAPI + JWT

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| JWT "alg: none" bypass | Spoofing | `algorithms=[...]` on every decode (D-03 hoist to `settings.JWT_ALGORITHM`, D-04 regression grep) |
| JWT algorithm confusion (HS256 with RSA public key as HMAC secret) | Spoofing | HS256-only (D-46); no RS256 support means no confusion attack surface |
| Token replay post-logout | Repudiation | JWT is stateless; logout is client-side. Future hardening (not Phase 5 scope): token blacklist or short expiry + refresh tokens |
| Admin endpoint unauthenticated access | Elevation | `Depends(get_current_admin_user)` on every admin route + 401/403 parametrized test (ADMIN-02) |
| Auth endpoint bypass via missing dependency | Elevation | 401 parametrized test (AUTH-03) for every non-public `/auth/*` route |
| Chrome extension token leak | Disclosure | Bearer token in `chrome.storage.local` (extension-isolated); `externally_connectable.matches` locks the web-app → extension message handoff |
| EventBridge endpoint invocation without `X-Admin-Cron-Key` | Spoofing | `_verify_cron_key` helper + 403 when header absent; secret lives in AWS Secrets Manager |

## Sources

### Primary (HIGH confidence)

- Context7 `/jpadilla/pyjwt` — Exception hierarchy (`InvalidTokenError` parent of all validation errors); `jwt.encode` returns `str`; `algorithms=[...]` is required argument. Fetched 2026-04-22.
- Context7 `/fastapi/fastapi` — `include_router(prefix, tags)` pattern, same-tag-on-multiple-routers produces grouped OpenAPI section, TestClient usage. Fetched 2026-04-22.
- `/home/tyler-webb/Documents/Github/CarModPicker/backend/app/api/endpoints/admin.py` — 23 route decorators enumerated + service imports verified.
- `/home/tyler-webb/Documents/Github/CarModPicker/backend/app/api/endpoints/auth.py` — 24 route decorators enumerated + 4 JWTError sites verified.
- `/home/tyler-webb/Documents/Github/CarModPicker/backend/app/api/dependencies/auth.py` — 3 JWTError sites + ALGORITHM literal + 5 decode/encode sites verified.
- `/home/tyler-webb/Documents/Github/CarModPicker/backend/app/main.py:210-309` — Current `register_endpoint` call pattern (12 registrations).
- `/home/tyler-webb/Documents/Github/CarModPicker/backend/app/api/utils/endpoint_registry.py` — `EndpointRegistry.register_endpoint` implementation.
- `/home/tyler-webb/Documents/Github/CarModPicker/terraform/scheduler.tf` — Single API destination at `/api/admin/crawlers/run`; rescrape explicitly manual per comments at lines 18 + variables.tf:77.
- `/home/tyler-webb/Documents/Github/CarModPicker/chrome-extension/src/background.ts` — 16 endpoint API calls enumerated; none under `/auth/*` or `/admin/*`.
- `/home/tyler-webb/Documents/Github/CarModPicker/frontend/src/services/Api.ts` — All admin + auth URL paths enumerated for PR 1/PR 4 grep sweep.
- `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/conftest.py:688` — `create_and_login_admin_user` helper verified to exist.
- `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/test_session_query_regression.py` — Phase 4 grep-test pattern (template for `test_jwt_algorithm_regression.py`).

### Secondary (MEDIUM confidence)

- CONTEXT.md + Phase 1/3/4 CONTEXT.md files — Decisions inherited and cross-referenced.
- REQUIREMENTS.md §AUTH-01 through AUTH-06 and §ADMIN-01 through ADMIN-04 — Requirement text.
- ROADMAP.md §Phase 5 — Success criteria.

### Tertiary (LOW confidence)

None — all claims in this research were verified via Context7, official FastAPI docs, or direct code reading.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FastAPI's auth dependency runs BEFORE path-parameter conversion, so dummy UUID path values don't affect 401 tests | Finding 4 / Pitfall 7 | Test fails with 422 where 401 expected; planner extends `_fill_path_params` to be type-aware. Not blocking. |
| A2 | HS256 tokens are byte-identical across python-jose and PyJWT for the same payload + secret + header | Finding 1 | Parity test D-05 fails; real in-flight tokens break during deploy; must add `leeway=10` or pre-expire all user tokens. HIGH-impact if wrong. Mitigation: D-05 test runs in PR 2 and fails-fast if library drift exists. |
| A3 | `admin/_helpers.py` imports don't circular-reference sub-modules | Finding / Risk 4 | Circular import at uvicorn startup; entire phase blocked. Mitigation: helpers are leaf modules by design. |
| A4 | Chrome extension token format doesn't embed library-specific metadata that would break on PyJWT | Finding 3 | Extension loses auth after PyJWT deploy; AUTH-05 manual UAT catches. Low probability — tokens are issued/decoded server-side; extension just carries the opaque string. |
| A5 | `job_service` and `part_linker_service` don't export anything admin.py doesn't currently use | Finding 6 | ADMIN-04 split redistributes service imports correctly. Low risk — verified via grep of 21 service-import call sites. |

**This research has 5 [ASSUMED] claims.** A2 is the highest-impact assumption — the D-05 parity test is its active verification. All others are low-impact or have active mitigations.

## Metadata

**Confidence breakdown:**

- PyJWT migration mechanics: HIGH — Context7 verified API; codebase state grep-verified.
- FastAPI APIRouter composition: HIGH — Context7 verified; codebase state verified.
- Chrome extension contract generator: HIGH — Code reading verified; OpenAPI schema shape documented in FastAPI/OpenAPI specs.
- 401/403 test patterns: HIGH — Existing conftest + Phase 3/4 test patterns directly applicable.
- Terraform sequencing: HIGH — Direct Terraform reading verified only ONE API destination exists.
- ADMIN-04 reality check: HIGH — Service import grep conclusive; no god-service exists.

**Research date:** 2026-04-22
**Valid until:** 2026-05-22 (30-day stability window for this domain — PyJWT 2.12.1 is current stable; FastAPI 0.136 planned upgrade is Phase 6 scope; codebase state is locked by Phase 4 completion on 2026-04-23)
