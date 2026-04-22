---
phase: 05-structural-router-splits
plan: 04
type: execute
wave: 3
depends_on:
  - 05-02-pyjwt-migration
  - 05-03-api-contract-generator
files_modified:
  - backend/app/api/endpoints/auth/__init__.py
  - backend/app/api/endpoints/auth/_helpers.py
  - backend/app/api/endpoints/auth/core.py
  - backend/app/api/endpoints/auth/two_factor.py
  - backend/app/api/endpoints/auth/webauthn.py
  - backend/app/api/endpoints/auth/oauth.py
  - backend/app/api/endpoints/auth.py
  - backend/app/main.py
  - backend/tests/test_auth_auth_coverage.py
  - backend/tests/fixtures/openapi_snapshot.json
  - frontend/src/services/Api.ts
autonomous: true
requirements:
  - AUTH-01
  - AUTH-02
  - AUTH-03
user_setup: []

must_haves:
  truths:
    - "POST /api/auth/token still returns 200 for valid credentials (public-route allow-list D-31)"
    - "POST /api/auth/logout returns 401 without auth and succeeds with valid JWT (auth-gated; covered by coverage test)"
    - "POST /api/auth/2fa/setup, /auth/2fa/verify, /auth/2fa/disable are reachable at post-split prefix and require auth"
    - "All 7 WebAuthn routes reachable at /api/auth/webauthn/* (credentials list/delete auth-gated; login/options and login/verify public per D-31)"
    - "POST /api/auth/oauth/google is reachable (moved from /auth/google per D-10); Google link/signup/connect similarly moved"
    - "backend/app/api/endpoints/auth.py no longer exists; all 24 routes served from auth/ sub-package per D-10"
    - "Frontend Api.ts calls updated to new /auth/oauth/google/* paths; Chrome extension untouched (D-14)"
    - "OpenAPI snapshot regenerated; diff matches 4 Google OAuth URL moves per D-10"
    - "Phase 1 auth characterization tests stay green (7 happy-path flows — D-43 guardrail)"
  artifacts:
    - path: "backend/app/api/endpoints/auth/__init__.py"
      provides: "Auth package init (empty or single-line docstring per D-08)"
    - path: "backend/app/api/endpoints/auth/_helpers.py"
      provides: "_issue_login_response + _maybe_2fa_challenge (D-18 cross-module helpers only)"
      contains: "logger = logging.getLogger"
    - path: "backend/app/api/endpoints/auth/core.py"
      provides: "7 routes: /token, /token/2fa, /verify-email, /verify-email/confirm, /reset-password, /reset-password/confirm, /logout"
    - path: "backend/app/api/endpoints/auth/two_factor.py"
      provides: "3 routes: /setup, /verify, /disable (at prefix /auth/2fa)"
    - path: "backend/app/api/endpoints/auth/webauthn.py"
      provides: "7 routes + challenge-token helpers (D-19)"
    - path: "backend/app/api/endpoints/auth/oauth.py"
      provides: "7 routes + Google-specific helpers (D-20)"
    - path: "backend/tests/test_auth_auth_coverage.py"
      provides: "Parametrized 401 coverage over protected /api/auth routes + public-route allow-list per D-31"
  key_links:
    - from: "backend/app/main.py"
      to: "backend/app/api/endpoints/auth/{core,two_factor,webauthn,oauth}"
      via: "endpoint_registry.register_endpoint(sub.router, prefix='/auth/<name>', tags=['authentication'])"
      pattern: "register_endpoint\\(auth_(core|2fa|webauthn|oauth)\\.router"
    - from: "backend/app/api/endpoints/auth/oauth.py"
      to: "backend/app/api/endpoints/auth/_helpers.py"
      via: "from app.api.endpoints.auth._helpers import _issue_login_response, _maybe_2fa_challenge"
      pattern: "from app\\.api\\.endpoints\\.auth\\._helpers import"
    - from: "backend/tests/test_auth_auth_coverage.py"
      to: "app.routes filtered by /api/auth prefix"
      via: "PUBLIC_ROUTES allow-list + APIRoute enumeration"
      pattern: "PUBLIC_ROUTES\\s*=\\s*\\{"
---

<objective>
Decompose backend/app/api/endpoints/auth.py (1,191 lines, 24 routes) into a 6-file auth/ sub-package per D-10, delete the old file, register 4 sub-routers in main.py, aggressively restructure `/auth/google/*` → `/auth/oauth/google/*`, migrate frontend Google OAuth URL paths, create the parametrized 401 coverage test with public-route allow-list, and regenerate the OpenAPI snapshot.

Purpose: Close AUTH-01, AUTH-02, AUTH-03. This is the highest-stakes refactor in the milestone; it lands after PyJWT (Plan 02 — modern library) and API_CONTRACT (Plan 03 — reviewer can verify auth claims against split code per D-37). Phase 1 auth characterization tests (7 happy-path flows per D-43) are the end-to-end guardrail.

Output: 4 auth sub-router files + _helpers.py + __init__.py + parametrized 401 coverage test + updated main.py registrations + migrated frontend Google OAuth paths + regenerated OpenAPI snapshot + confirmation Chrome extension flow still works via AUTH-05 UAT (checklist created in Plan 03, to be executed post-deploy).
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
@.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md
@CLAUDE.md

# Source file being decomposed (MUST READ during extraction — post-PR-2 PyJWT-swapped state)
@backend/app/api/endpoints/auth.py

# Dependencies consumed by the new sub-package
@backend/app/api/dependencies/auth.py
@backend/app/api/utils/endpoint_decorators.py
@backend/app/api/utils/response_patterns.py

# Reference for the split shape (already a clean sub-router)
@backend/app/api/endpoints/crawler_schedules.py

# Main registration point
@backend/app/main.py

# Fixtures reused by the coverage test
@backend/tests/conftest.py

# Admin-side coverage test created in Plan 01 (sibling template for auth coverage test)
@backend/tests/test_admin_auth_coverage.py

# OpenAPI snapshot shape + regeneration command
@backend/tests/test_openapi_snapshot.py

<interfaces>
<!-- Auth routes inventory (VERIFIED in RESEARCH.md Finding 2, 24 routes) -->

From backend/app/api/endpoints/auth.py (post-PyJWT, pre-split):
| Line | Method | Current path            | Target prefix       | Target relative path      | Sub-module     |
|------|--------|-------------------------|---------------------|---------------------------|----------------|
| 90   | POST   | /token                  | /auth               | /token                    | core           |
| 132  | POST   | /token/2fa              | /auth               | /token/2fa                | core           |
| 185  | POST   | /verify-email           | /auth               | /verify-email             | core           |
| 215  | GET    | /verify-email/confirm   | /auth               | /verify-email/confirm     | core           |
| 275  | POST   | /reset-password         | /auth               | /reset-password           | core           |
| 303  | POST   | /reset-password/confirm | /auth               | /reset-password/confirm   | core           |
| 343  | POST   | /logout                 | /auth               | /logout                   | core           |
| 357  | POST   | /2fa/setup              | /auth/2fa           | /setup                    | two_factor     |
| 405  | POST   | /2fa/verify             | /auth/2fa           | /verify                   | two_factor     |
| 447  | POST   | /2fa/disable            | /auth/2fa           | /disable                  | two_factor     |
| 525  | POST   | /webauthn/register/options   | /auth/webauthn | /register/options   | webauthn       |
| 563  | POST   | /webauthn/register/verify    | /auth/webauthn | /register/verify    | webauthn       |
| 617  | POST   | /webauthn/login/options      | /auth/webauthn | /login/options      | webauthn       |
| 647  | POST   | /webauthn/login/verify       | /auth/webauthn | /login/verify       | webauthn       |
| 713  | GET    | /webauthn/credentials        | /auth/webauthn | /credentials        | webauthn       |
| 726  | PATCH  | /webauthn/credentials/{credential_id} | /auth/webauthn | /credentials/{credential_id} | webauthn |
| 748  | DELETE | /webauthn/credentials/{credential_id} | /auth/webauthn | /credentials/{credential_id} | webauthn |
| 834  | POST   | /google                 | /auth/oauth         | /google                   | oauth          |
| 918  | POST   | /google/link            | /auth/oauth         | /google/link              | oauth          |
| 999  | POST   | /google/signup          | /auth/oauth         | /google/signup            | oauth          |
| 1053 | POST   | /oauth/2fa              | /auth/oauth         | /2fa                      | oauth          |
| 1088 | POST   | /google/connect         | /auth/oauth         | /google/connect           | oauth          |
| 1144 | GET    | /oauth                  | /auth/oauth         | /                         | oauth          |
| 1157 | DELETE | /oauth/{account_id}     | /auth/oauth         | /{account_id}             | oauth          |

**Total: 7 / 3 / 7 / 7 = 24 routes distributed core/two_factor/webauthn/oauth.**

Helpers from auth.py that move to auth/_helpers.py (D-18, lines 813-832):
  _issue_login_response, _maybe_2fa_challenge

WebAuthn-local helpers stay in auth/webauthn.py (D-19, lines 492-522):
  WEBAUTHN_REGISTER_PURPOSE, WEBAUTHN_LOGIN_PURPOSE, _b64url_encode, _b64url_decode,
  _build_challenge_token, _decode_challenge_token

OAuth-local helpers stay in auth/oauth.py (D-20, lines 770-810 + 908-915):
  GOOGLE_LINK_PURPOSE, GOOGLE_SIGNUP_PURPOSE, OAUTH_2FA_PURPOSE, GOOGLE_PROVIDER,
  _ensure_google_enabled, _verify_google_or_400, _suggest_username, _decode_purpose_token

**Planner decision per PATTERNS.md §9 Open Question (OAUTH_2FA_PURPOSE / GOOGLE_PROVIDER):**
Choose option (a) — duplicate the minimal constants in `auth/_helpers.py` (OAUTH_2FA_PURPOSE = "oauth_2fa", GOOGLE_PROVIDER = "google") so `_maybe_2fa_challenge` is self-contained without importing back from oauth.py. oauth.py keeps its own copies (source-of-truth for OAuth flows). Trade: one-line duplication of two string constants vs circular-import risk.

Public auth routes (D-31 — D-10 paths after move) — MUST match the PUBLIC_ROUTES allow-list in test_auth_auth_coverage.py:
```
("POST", "/api/auth/token")
("POST", "/api/auth/token/2fa")
("POST", "/api/auth/verify-email")
("GET",  "/api/auth/verify-email/confirm")
("POST", "/api/auth/reset-password")
("POST", "/api/auth/reset-password/confirm")
("POST", "/api/auth/oauth/google")
("POST", "/api/auth/oauth/google/signup")
("POST", "/api/auth/oauth/google/link")
("POST", "/api/auth/oauth/2fa")
("POST", "/api/auth/webauthn/login/options")
("POST", "/api/auth/webauthn/login/verify")
```

Post-PyJWT imports (Pattern G in PATTERNS.md):
```python
import jwt
from jwt import InvalidTokenError

from app.api.dependencies.auth import (
    ALGORITHM,
    create_access_token,
    get_access_token_expires_delta_for_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
```

From backend/app/main.py — current single registration (VERIFIED lines 225-230):
```python
endpoint_registry.register_endpoint(
    auth.router,
    prefix="/auth",
    tags=["authentication"],
    description="User authentication and authorization",
)
```
REPLACE with 4 sub-router registrations (PATTERNS.md §19).

Frontend Google OAuth paths to update (from RESEARCH.md Risk 3 — VERIFIED):
| Api.ts line | Current                   | Target                            |
|-------------|---------------------------|-----------------------------------|
| 862         | `'/auth/google'`          | `'/auth/oauth/google'`            |
| 870         | `'/auth/google/link'`     | `'/auth/oauth/google/link'`       |
| 881         | `'/auth/google/signup'`   | `'/auth/oauth/google/signup'`     |
| 897         | `'/auth/google/connect'`  | `'/auth/oauth/google/connect'`    |
(Paths `/auth/oauth`, `/auth/oauth/2fa`, `/auth/oauth/{id}` already use the new /oauth prefix in Api.ts — unchanged.)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create auth/ sub-package skeleton + _helpers.py (D-18) + coverage test scaffold with public-route allow-list</name>
  <files>
    backend/app/api/endpoints/auth/__init__.py,
    backend/app/api/endpoints/auth/_helpers.py,
    backend/app/api/endpoints/auth/core.py,
    backend/app/api/endpoints/auth/two_factor.py,
    backend/app/api/endpoints/auth/webauthn.py,
    backend/app/api/endpoints/auth/oauth.py,
    backend/tests/test_auth_auth_coverage.py
  </files>
  <read_first>
    - backend/app/api/endpoints/auth.py (full file — source-of-truth for extraction; post-PyJWT-swap state)
    - backend/app/api/endpoints/crawler_schedules.py (reference sub-router shape)
    - backend/tests/test_admin_auth_coverage.py (sibling created in Plan 01 — reuse shape)
    - backend/tests/conftest.py (module-level helpers: create_and_login_user at line 368, login_user at 356)
    - .planning/phases/05-structural-router-splits/05-PATTERNS.md (Sections 6-10, 13 — auth imports + route move templates + _helpers + coverage test template)
    - .planning/phases/05-structural-router-splits/05-CONTEXT.md D-18, D-19, D-20, D-31
  </read_first>
  <behavior>
    - `python -c "from app.api.endpoints.auth import core, two_factor, webauthn, oauth, _helpers"` succeeds.
    - `auth/_helpers.py` is a LEAF module (Risk 4): no imports from auth/core, auth/two_factor, auth/webauthn, auth/oauth.
    - `auth/_helpers.py` contains `_issue_login_response` and `_maybe_2fa_challenge` (copied verbatim from auth.py:813-832) + the duplicated constants `OAUTH_2FA_PURPOSE = "oauth_2fa"` and `GOOGLE_PROVIDER = "google"` per the planner decision.
    - `test_auth_auth_coverage.py` exists with parametrized test + PUBLIC_ROUTES allow-list of 12 tuples per D-31.
    - Pre-Task-2, the sub-router files have empty routers (routes added in Task 2). Coverage test count guard fails until Task 2 wires main.py.
  </behavior>
  <action>
**Step A — Create `backend/app/api/endpoints/auth/__init__.py`** (one-line docstring per D-08):
```python
"""Auth endpoint sub-package — sub-routers registered individually in main.py (D-08)."""
```

**Step B — Create `backend/app/api/endpoints/auth/_helpers.py`** per D-18 + planner decision. Copy the body of `_issue_login_response` + `_maybe_2fa_challenge` verbatim from `backend/app/api/endpoints/auth.py:813-832`. Also duplicate the two string constants referenced by `_maybe_2fa_challenge`:

```python
"""Cross-module auth helpers shared across sub-routers (D-18).

Used by core.py (login, 2FA login), oauth.py (Google sign-in, Google signup),
two_factor.py (2FA verify login). Leaf module — NO sibling sub-module imports
(Risk 4 mitigation). OAUTH_2FA_PURPOSE + GOOGLE_PROVIDER constants duplicated
here (matched verbatim in auth/oauth.py) to keep this module self-contained.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from app.api.dependencies.auth import (
    create_access_token,
    get_access_token_expires_delta_for_user,
)
from app.api.models.user import User as DBUser
from app.api.schemas.user import UserRead

logger = logging.getLogger(__name__)

# Duplicated from auth/oauth.py per planner decision (PATTERNS.md §9 Open Question):
# option (a) — duplicate constants to keep _helpers.py a leaf module.
# Source-of-truth for OAuth flows remains auth/oauth.py; any future change to
# these string values must update BOTH files (low-risk: string literals change rarely).
OAUTH_2FA_PURPOSE = "oauth_2fa"
GOOGLE_PROVIDER = "google"


def _issue_login_response(user: DBUser) -> dict[str, str | UserRead]:
    """Build the login response payload (access_token + user metadata)."""
    # TODO: copy verbatim body from auth.py:813-822
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=expires_delta)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


def _maybe_2fa_challenge(user: DBUser) -> Optional[dict[str, str | bool]]:
    """If user has TOTP enabled, mint an otp_token bound to them and return the challenge payload.

    Source: auth.py:823-832 — copy body verbatim, using the duplicated OAUTH_2FA_PURPOSE
    + GOOGLE_PROVIDER constants above.
    """
    # TODO: copy verbatim body from auth.py:823-832
    raise NotImplementedError("Copy body from auth.py:823-832 during extraction")
```

Before exiting this task, the `NotImplementedError` placeholder MUST be replaced with the verbatim body from `auth.py:823-832`. Read those lines, paste the body, verify imports match, run `python -c "from app.api.endpoints.auth._helpers import _issue_login_response, _maybe_2fa_challenge"`.

**Step C — Create 4 sub-router files** with empty routers and correct imports per PATTERNS.md §6. Template for each (adapt imports per sub-module scope):
```python
"""<Sub-module purpose — one-line>."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    ALGORITHM,
    create_access_token,
    get_access_token_expires_delta_for_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.api.models.user import User as DBUser
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()
```

Sub-module docstrings (first line):
- `core.py`: "Authentication core endpoints: token issuance, email verification, password reset, logout."
- `two_factor.py`: "TOTP 2FA endpoints: setup, verify, disable (all auth-gated)."
- `webauthn.py`: "WebAuthn passkey endpoints: register/login ceremonies + credentials management."
- `oauth.py`: "Google OAuth endpoints: sign-in, signup, link, connect, 2FA, account list/delete."

For `oauth.py`: include the Google-specific constants and helpers (D-20 — stays local):
```python
GOOGLE_LINK_PURPOSE = "google_link"
GOOGLE_SIGNUP_PURPOSE = "google_signup"
OAUTH_2FA_PURPOSE = "oauth_2fa"       # Duplicated in _helpers.py per planner decision
GOOGLE_PROVIDER = "google"             # Duplicated in _helpers.py per planner decision

# Also copy verbatim from auth.py:770-810 + 908-915:
# _ensure_google_enabled, _verify_google_or_400, _suggest_username, _decode_purpose_token
```
Leave the helper bodies as NotImplementedError placeholders; Task 2 copies them verbatim along with the routes.

For `webauthn.py`: include the WebAuthn-local constants + helpers (D-19 — stays local):
```python
WEBAUTHN_REGISTER_PURPOSE = "webauthn_register"
WEBAUTHN_LOGIN_PURPOSE = "webauthn_login"

# Also copy verbatim from auth.py:492-522:
# _b64url_encode, _b64url_decode, _build_challenge_token, _decode_challenge_token
```
Task 2 copies bodies verbatim (important: `_decode_challenge_token` already uses `except InvalidTokenError:` because PyJWT swap landed in Plan 02 — NOT `except JWTError`).

**Step D — Create `backend/tests/test_auth_auth_coverage.py`** per PATTERNS.md §13 + D-31 public-route allow-list:
```python
"""AUTH-03 regression: every protected route under /api/auth requires a valid JWT.

Public auth routes (login, email verify, reset, Google sign-in, WebAuthn login
ceremonies) are excluded via the PUBLIC_ROUTES allow-list below — any new public
route is a deliberate review-gated addition.

D-30 drift guard: count-at-or-above check catches a disabled parametrized test
or a route removal without test update.
"""

from __future__ import annotations

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

# D-31: Intentionally public (no auth dependency), post-D-10 URL restructure.
PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("POST", "/api/auth/token"),
    ("POST", "/api/auth/token/2fa"),
    ("POST", "/api/auth/verify-email"),
    ("GET", "/api/auth/verify-email/confirm"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/reset-password/confirm"),
    ("POST", "/api/auth/oauth/google"),          # D-10: moved from /auth/google
    ("POST", "/api/auth/oauth/google/signup"),   # D-10: moved from /auth/google/signup
    ("POST", "/api/auth/oauth/google/link"),     # D-10: moved from /auth/google/link
    ("POST", "/api/auth/oauth/2fa"),
    # WebAuthn login challenges are pre-auth — user isn't logged in yet
    ("POST", "/api/auth/webauthn/login/options"),
    ("POST", "/api/auth/webauthn/login/verify"),
}


def _protected_auth_routes() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/api/auth"):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                if (m, r.path) not in PUBLIC_ROUTES:
                    out.append((m, r.path))
    return out


AUTH_PROTECTED_ROUTES = _protected_auth_routes()


def _fill_path_params(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


@pytest.mark.parametrize("method,path", AUTH_PROTECTED_ROUTES)
def test_auth_route_requires_token(method: str, path: str, client: TestClient) -> None:
    resp = client.request(method, _fill_path_params(path))
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code} (expected 401)"


def test_auth_protected_route_count_at_or_above_expected() -> None:
    # 24 total auth routes - 12 public = 12 protected. Tight drift guard: any disabled
    # parametrized test or silently-deleted route immediately trips CI.
    assert len(AUTH_PROTECTED_ROUTES) >= 12, (
        f"Too few protected auth routes: {len(AUTH_PROTECTED_ROUTES)} (expected >=12). "
        f"Check PUBLIC_ROUTES allow-list drift or accidental route removal."
    )


def test_public_routes_still_return_non_401() -> None:
    """Public routes must NOT return 401 on unauthenticated hit (they may return 422 for
    bad body, 400 for missing data, 404 for invalid token, etc. — but NEVER 401)."""
    client = TestClient(app)
    for method, path in sorted(PUBLIC_ROUTES):
        resolved = _fill_path_params(path)
        resp = client.request(method, resolved)
        assert resp.status_code != 401, (
            f"Public route {method} {path} returned 401 — auth dep leaked in! "
            f"Remove Depends(get_current_user) or move to PUBLIC_ROUTES allow-list."
        )
```
  </action>
  <verify>
    <automated>cd backend && python -c "from app.api.endpoints.auth import core, two_factor, webauthn, oauth, _helpers; print('import ok')"</automated>
    <automated>test -f backend/app/api/endpoints/auth/__init__.py && test -f backend/app/api/endpoints/auth/_helpers.py && test -f backend/app/api/endpoints/auth/core.py && test -f backend/app/api/endpoints/auth/two_factor.py && test -f backend/app/api/endpoints/auth/webauthn.py && test -f backend/app/api/endpoints/auth/oauth.py && test -f backend/tests/test_auth_auth_coverage.py</automated>
    <automated>cd backend && grep -c "^logger = logging.getLogger(__name__)" app/api/endpoints/auth/_helpers.py app/api/endpoints/auth/core.py app/api/endpoints/auth/two_factor.py app/api/endpoints/auth/webauthn.py app/api/endpoints/auth/oauth.py | awk -F: '$2!=1 {exit 1}'</automated>
    <automated>cd backend && grep -q "def _issue_login_response" app/api/endpoints/auth/_helpers.py && grep -q "def _maybe_2fa_challenge" app/api/endpoints/auth/_helpers.py</automated>
    <automated>cd backend && python -c "from app.api.endpoints.auth._helpers import _issue_login_response, _maybe_2fa_challenge; print('leaf helpers ok')"</automated>
    <automated>cd backend && grep -rn "from app.api.endpoints.auth\.\(core\|two_factor\|webauthn\|oauth\)" app/api/endpoints/auth/_helpers.py ; test $? -eq 1</automated>
    <automated>cd backend && grep -c '("POST", "/api/auth/oauth/google")' tests/test_auth_auth_coverage.py</automated>
    <automated>grep -q "raise NotImplementedError" backend/app/api/endpoints/auth/_helpers.py ; test $? -eq 1</automated>
    <automated>cd backend && python -c "from app.api.endpoints.auth._helpers import _maybe_2fa_challenge; import inspect; src = inspect.getsource(_maybe_2fa_challenge); assert 'NotImplementedError' not in src"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/app/api/endpoints/auth/__init__.py` exits 0
    - `test -f backend/app/api/endpoints/auth/_helpers.py` exits 0
    - `test -f backend/app/api/endpoints/auth/core.py` exits 0
    - `test -f backend/app/api/endpoints/auth/two_factor.py` exits 0
    - `test -f backend/app/api/endpoints/auth/webauthn.py` exits 0
    - `test -f backend/app/api/endpoints/auth/oauth.py` exits 0
    - `test -f backend/tests/test_auth_auth_coverage.py` exits 0
    - `cd backend && python -c "from app.api.endpoints.auth import core, two_factor, webauthn, oauth, _helpers"` exits 0
    - `grep -c "^logger = logging.getLogger(__name__)" backend/app/api/endpoints/auth/*.py` reports `1` for EACH of: _helpers.py, core.py, two_factor.py, webauthn.py, oauth.py
    - `grep -q "def _issue_login_response" backend/app/api/endpoints/auth/_helpers.py` exits 0
    - `grep -q "def _maybe_2fa_challenge" backend/app/api/endpoints/auth/_helpers.py` exits 0
    - `grep -rn "from app.api.endpoints.auth\.\(core\|two_factor\|webauthn\|oauth\)" backend/app/api/endpoints/auth/_helpers.py` returns exit code 1 (leaf module per Risk 4)
    - `grep -c '("POST", "/api/auth/oauth/google")' backend/tests/test_auth_auth_coverage.py` outputs at least `1` (PUBLIC_ROUTES includes the post-D-10 path)
    - `cd backend && python -c "from app.api.endpoints.auth._helpers import _issue_login_response, _maybe_2fa_challenge"` exits 0 (import succeeds — note: Python does NOT execute function bodies at import, so this alone does NOT prove the placeholder has been replaced; see next criterion)
    - NotImplementedError placeholder has been REPLACED with the verbatim `_maybe_2fa_challenge` body from `auth.py:823-832`. Verify via: `grep -q "raise NotImplementedError" backend/app/api/endpoints/auth/_helpers.py; test $? -eq 1` — grep exits 0 if the text IS found, 1 if NOT found; we want NOT-found (exit code 1) to prove the placeholder is gone
    - Runtime sanity: `cd backend && python -c "from app.api.endpoints.auth._helpers import _maybe_2fa_challenge; import inspect; src = inspect.getsource(_maybe_2fa_challenge); assert 'NotImplementedError' not in src, 'placeholder still present'; assert 'OAUTH_2FA_PURPOSE' in src or 'otp_token' in src, 'body appears empty/stubbed'"` exits 0 (confirms the function body was actually copied, not just the signature)
  </acceptance_criteria>
  <done>Sub-package directory + 7 files created, _helpers.py contains the 2 cross-module helpers verbatim + duplicated constants, sub-router files import cleanly with empty routers, coverage test scaffolded with 12-entry PUBLIC_ROUTES allow-list.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extract 24 auth routes into sub-router files (with D-10 /auth/oauth/google/* restructure) + wire main.py + delete auth.py + regenerate OpenAPI snapshot</name>
  <files>
    backend/app/api/endpoints/auth/core.py,
    backend/app/api/endpoints/auth/two_factor.py,
    backend/app/api/endpoints/auth/webauthn.py,
    backend/app/api/endpoints/auth/oauth.py,
    backend/app/api/endpoints/auth.py,
    backend/app/main.py,
    backend/tests/fixtures/openapi_snapshot.json
  </files>
  <read_first>
    - backend/app/api/endpoints/auth.py (source-of-truth — ALL 1,191 lines; post-PyJWT-swap state)
    - backend/app/main.py (lines 1-40 for imports, 225-230 for auth registration)
    - backend/tests/test_openapi_snapshot.py (regeneration command for step F)
    - .planning/phases/05-structural-router-splits/05-PATTERNS.md (Sections 6-9, 19 — route move templates + Google OAuth restructure + main.py pattern)
    - .planning/phases/05-structural-router-splits/05-RESEARCH.md Finding 2 table (route→sub-module map)
    - .planning/phases/05-structural-router-splits/05-RESEARCH.md Risk 5 (test import audit)
  </read_first>
  <behavior>
    - After extraction, `pytest -n auto backend/tests/test_auth_auth_coverage.py` passes (at least 12 parametrized cases + count guard + public-route non-401 check).
    - Phase 1 auth characterization tests (7 happy-path flows per D-43) STAY GREEN — the end-to-end guardrail.
    - `pytest -n auto backend/tests/test_openapi_snapshot.py` passes AFTER regeneration.
    - Phase 3 logger + Phase 4 session.query + Phase 3 Pydantic v1 regression guards all stay green.
    - AUTH-04 regression guards (`test_jwt_algorithm_regression.py`, `test_pyjwt_migration.py`) stay green (no JWT regressions from the split).
    - `python -c "from app.api.endpoints import auth"` FAILS with ModuleNotFoundError (old file deleted per REQ-AUTH-01).
    - `/api/auth/oauth/google` is reachable; `/api/auth/google` returns 404 (D-10 move).
    - `/api/auth/token` still reachable (unchanged per D-10 core); `/api/auth/logout` still reachable + auth-gated.
  </behavior>
  <action>
**Step A — Extract the 24 routes into the 4 sub-router files** using the Finding 2 table in `<interfaces>`. For each route in auth.py:
1. Identify target sub-module + target relative path per the table.
2. Copy the full `@router.*` decorator + handler function body VERBATIM into the target sub-module file.
3. REWRITE the decorator path relative to the sub-module's mount prefix (D-15):
   - Example: `@router.post("/token")` in auth.py → `@router.post("/token")` in auth/core.py (prefix `/auth`, unchanged).
   - Example: `@router.post("/2fa/setup")` in auth.py → `@router.post("/setup")` in auth/two_factor.py (prefix `/auth/2fa` strips `/2fa`).
   - Example: `@router.post("/webauthn/register/options")` in auth.py → `@router.post("/register/options")` in auth/webauthn.py (prefix `/auth/webauthn` strips `/webauthn`).
   - **D-10 AGGRESSIVE MOVES (Google OAuth restructure):**
     - `@router.post("/google")` → in auth/oauth.py as `@router.post("/google")` (prefix `/auth/oauth` — final URL: `/api/auth/oauth/google`, moved from `/api/auth/google`).
     - `@router.post("/google/link")` → in auth/oauth.py as `@router.post("/google/link")` (final: `/api/auth/oauth/google/link`).
     - `@router.post("/google/signup")` → in auth/oauth.py as `@router.post("/google/signup")` (final: `/api/auth/oauth/google/signup`).
     - `@router.post("/google/connect")` → in auth/oauth.py as `@router.post("/google/connect")` (final: `/api/auth/oauth/google/connect`).
   - `/oauth/2fa` → `@router.post("/2fa")` in auth/oauth.py (prefix `/auth/oauth`, final: `/api/auth/oauth/2fa` — UNCHANGED).
   - `/oauth` (GET list) → `@router.get("/")` in auth/oauth.py (prefix `/auth/oauth`, final: `/api/auth/oauth` — UNCHANGED).
   - `/oauth/{account_id}` (DELETE) → `@router.delete("/{account_id}")` in auth/oauth.py (final: `/api/auth/oauth/{account_id}` — UNCHANGED).
4. PRESERVE per-route `current_user: DBUser = Depends(get_current_user)` verbatim — AUTH-03 literal. Do NOT add `Depends(get_current_user)` to public routes (D-31 allow-list — /token, /verify-email, /reset-password, /oauth/google, /oauth/google/signup, /oauth/google/link, /oauth/2fa, /webauthn/login/*).
5. DO NOT add, remove, or re-order decorator arguments (preserves OpenAPI snapshot shape except for path moves).

**Sub-module-specific extras:**

`auth/webauthn.py`: Copy verbatim from auth.py:
- `WEBAUTHN_REGISTER_PURPOSE`, `WEBAUTHN_LOGIN_PURPOSE` (module-level constants) — D-19.
- `_b64url_encode`, `_b64url_decode` (lines 496-505) — D-19.
- `_build_challenge_token`, `_decode_challenge_token` (lines 506-522) — D-19. **Verify `_decode_challenge_token` uses `except InvalidTokenError:` (post-PR-2 swap) — NOT `except JWTError`.**

`auth/oauth.py`: Copy verbatim:
- `GOOGLE_LINK_PURPOSE`, `GOOGLE_SIGNUP_PURPOSE`, `OAUTH_2FA_PURPOSE`, `GOOGLE_PROVIDER` (module-level constants) — D-20.
- `_ensure_google_enabled`, `_verify_google_or_400`, `_suggest_username` (lines 770-810) — D-20.
- `_decode_purpose_token` (lines 908-915) — D-20. **Verify it uses `except InvalidTokenError:`.**
- Add module-level import: `from app.api.endpoints.auth._helpers import _issue_login_response, _maybe_2fa_challenge`.

`auth/core.py`: `_issue_login_response` and `_maybe_2fa_challenge` are imported from `auth/_helpers.py` (Task 1 already copied them there).

`auth/two_factor.py`: Add `from app.api.endpoints.auth._helpers import _issue_login_response` (used by `/2fa/verify` route to issue final login token).

**Pattern reminder:** every sub-module file uses `logger = logging.getLogger(__name__)` per D-26 (already set in Task 1). Use `db.scalars(select(...))` — NOT `db.query(...)` (Phase 4 grep guard; Pattern B). Keep `standard_responses(...)` helpers on every route (Pattern D). Keep `ResponsePatterns.raise_*` call style for error responses (Pattern E).

**Step B — Update `backend/app/main.py`:** Replace the single `auth.router` registration (lines 225-230) with 4 sub-router registrations. Also update imports: replace `from .api.endpoints import auth` (or wherever `auth` is imported from endpoints) with per-sub-module imports.

Exact imports block update (find existing `from .api.endpoints import` line with `auth` in the tuple — REMOVE `auth` from that tuple):
```python
from .api.endpoints.auth import (
    core as auth_core,
    oauth as auth_oauth,
    two_factor as auth_2fa,
    webauthn as auth_webauthn,
)
```

Exact replacement at lines 225-230 (per PATTERNS.md §19):
```python
endpoint_registry.register_endpoint(
    auth_core.router,
    prefix="/auth",
    tags=["authentication"],
    description="Authentication core (login, token refresh, email verify, password reset, logout)",
)
endpoint_registry.register_endpoint(
    auth_2fa.router,
    prefix="/auth/2fa",
    tags=["authentication"],
    description="TOTP 2FA setup and management",
)
endpoint_registry.register_endpoint(
    auth_webauthn.router,
    prefix="/auth/webauthn",
    tags=["authentication"],
    description="WebAuthn passkey registration and login",
)
endpoint_registry.register_endpoint(
    auth_oauth.router,
    prefix="/auth/oauth",
    tags=["authentication"],
    description="Google OAuth sign-in, link, connect, and account management",
)
```

**Step C — Delete `backend/app/api/endpoints/auth.py`** per REQ-AUTH-01 "old file deleted in same PR".

**Step D — Audit test imports** per Risk 5:
```bash
grep -rn "from app.api.endpoints.auth import" backend/tests/ backend/app/
```
For each match, rewrite the import to the correct sub-module (based on which function/class is imported). For example:
- `from app.api.endpoints.auth import router` — DELETE (router is no longer exported; use the sub-routers).
- `from app.api.endpoints.auth import some_helper` — rewrite to `from app.api.endpoints.auth.<sub> import some_helper` where `<sub>` is where the helper moved.

**Step E — Verify no regression guards break:**
```bash
cd backend
grep -rn "db\.query\|session\.query\|self\.db\.query" app/api/endpoints/auth/ && exit 1 || true
grep -rn "Depends(get_logger)" app/api/endpoints/auth/ && exit 1 || true
grep -rn "from jose" app/api/endpoints/auth/ && exit 1 || true
grep -rn "JWTError" app/api/endpoints/auth/ && exit 1 || true
```

**Step F — Regenerate OpenAPI snapshot** (per D-44 / Phase 1 D-26 convention):
```bash
cd backend
TESTING=true ENABLE_RATE_LIMITING=false python -c "
import json
from app.main import app
from pathlib import Path
out = Path('tests/fixtures/openapi_snapshot.json')
out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + '\n')
print('regenerated', out)
"
```
(Or use the canonical regeneration script the project provides — read `backend/tests/test_openapi_snapshot.py` to find it.)

**Step G — Regenerate API_CONTRACT.md** (AUTH-06 drift — route signatures may have changed subtly due to path moves, even though the 16 extension endpoints themselves are untouched):
```bash
cd backend
TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py
```
If the contract file drifts, commit the regenerated version. The contract's drift-guard test will pass on the new committed content.

**Step H — Run full validation:**
```bash
cd backend
pytest -n auto tests/test_auth_auth_coverage.py -x
pytest -n auto tests/test_openapi_snapshot.py tests/test_ext_api_contract_up_to_date.py -x
pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x
pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x

# Phase 1 D-43 guardrail — characterization tests MUST stay green
pytest -n auto -k "auth and characterization" -x

# Full backend suite sanity
pytest -n auto --cov=app --cov-fail-under=51 2>&1 | tail -20
```

If characterization tests fail: most likely cause is a missed `Depends(get_current_user)` on a route that should be auth-gated, OR a route moved incorrectly (e.g., forgot to strip a sub-module prefix). Cross-reference the test failure against the route table in `<interfaces>` and fix.
  </action>
  <verify>
    <automated>cd backend && pytest -n auto tests/test_auth_auth_coverage.py -x</automated>
    <automated>cd backend && pytest -n auto tests/test_openapi_snapshot.py tests/test_ext_api_contract_up_to_date.py -x</automated>
    <automated>cd backend && pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x</automated>
    <automated>cd backend && pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x</automated>
    <automated>cd backend && pytest -n auto -k "auth and characterization" -x 2>&1 | tail -30</automated>
    <automated>test ! -f backend/app/api/endpoints/auth.py</automated>
    <automated>cd backend && python -c "from app.main import app; from fastapi.routing import APIRoute; paths = sorted({r.path for r in app.routes if isinstance(r, APIRoute) and r.path.startswith('/api/auth')}); print('\n'.join(paths)); assert '/api/auth/oauth/google' in paths; assert '/api/auth/oauth/google/signup' in paths; assert '/api/auth/oauth/google/link' in paths; assert '/api/auth/oauth/google/connect' in paths; assert '/api/auth/google' not in paths, 'old path leaked!'"</automated>
    <automated>cd backend && grep -rn "db\.query\|session\.query" app/api/endpoints/auth/ ; test $? -eq 1</automated>
    <automated>cd backend && grep -rn "from jose\|JWTError" app/api/endpoints/auth/ ; test $? -eq 1</automated>
    <automated>cd backend && grep -rn "from app.api.endpoints.auth import" backend/ 2>/dev/null | grep -v "endpoints\.auth\.\(core\|two_factor\|webauthn\|oauth\|_helpers\)" ; test $? -eq 1</automated>
  </verify>
  <acceptance_criteria>
    - `test ! -f backend/app/api/endpoints/auth.py` exits 0 (old file deleted per REQ-AUTH-01)
    - `cd backend && pytest -n auto tests/test_auth_auth_coverage.py -x` exits 0
    - `cd backend && pytest -n auto tests/test_openapi_snapshot.py -x` exits 0
    - `cd backend && pytest -n auto tests/test_ext_api_contract_up_to_date.py -x` exits 0 (contract regenerated if needed)
    - `cd backend && pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x` exits 0
    - `cd backend && pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x` exits 0
    - `cd backend && pytest -n auto -k "auth and characterization" -x` exits 0 (D-43 end-to-end guardrail green)
    - `cd backend && python -c "from app.main import app; from fastapi.routing import APIRoute; paths = {r.path for r in app.routes if isinstance(r, APIRoute) and r.path.startswith('/api/auth')}; assert '/api/auth/oauth/google' in paths and '/api/auth/oauth/google/signup' in paths and '/api/auth/oauth/google/link' in paths and '/api/auth/oauth/google/connect' in paths and '/api/auth/google' not in paths"` exits 0
    - `grep -rn "db\.query\|session\.query" backend/app/api/endpoints/auth/` returns exit code 1
    - `grep -rn "from jose\|JWTError" backend/app/api/endpoints/auth/` returns exit code 1 (PyJWT swap preserved in new files)
    - `grep -rn "from app.api.endpoints.auth import" backend/ | grep -v "endpoints\.auth\.\(core\|two_factor\|webauthn\|oauth\|_helpers\)"` returns exit code 1 (D-17 hard-migration)
    - At least 24 routes under `/api/auth` in `app.routes` (verify via Python one-liner inspection)
    - OpenAPI snapshot regenerated and reviewer confirms diff is exactly the 4 Google OAuth path moves
  </acceptance_criteria>
  <done>All 24 auth routes served from the sub-package, auth.py deleted, main.py registers 4 sub-routers, Google OAuth paths moved to /auth/oauth/google/*, OpenAPI snapshot + API_CONTRACT regenerated, parametrized 401 tests pass, Phase 1 characterization tests stay green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Migrate frontend Google OAuth URL literals per D-13 (post-auth-split paths)</name>
  <files>
    frontend/src/services/Api.ts
  </files>
  <read_first>
    - frontend/src/services/Api.ts (Google OAuth URL literals at lines 862, 870, 881, 897 per Finding 2 / Risk 3)
    - .planning/phases/05-structural-router-splits/05-RESEARCH.md (Risk 3 second table — verified delta map for PR 4)
  </read_first>
  <behavior>
    - 4 frontend URL literals update: `/auth/google` → `/auth/oauth/google`, `/auth/google/link` → `/auth/oauth/google/link`, `/auth/google/signup` → `/auth/oauth/google/signup`, `/auth/google/connect` → `/auth/oauth/google/connect`.
    - `/auth/oauth/*` paths already using `/oauth/` prefix (like `/auth/oauth/2fa`, `/auth/oauth`, `/auth/oauth/{id}`) are UNCHANGED.
    - `/auth/token`, `/auth/verify-email`, `/auth/reset-password`, `/auth/logout`, `/auth/2fa/*`, `/auth/webauthn/*` are UNCHANGED.
    - `cd frontend && npm run type-check` exits 0.
    - `cd frontend && npm test -- --run` exits 0.
    - `grep -rn "'/auth/google[^/]" frontend/src/` returns exit code 1 (no old `/auth/google` literals remain; the `[^/]` guard avoids matching `/auth/google/...` paths that also need updating).
    - More precise: `grep -rnE "'/auth/google(/(link|signup|connect))?'" frontend/src/` returns exit code 1 after migration.
  </behavior>
  <action>
Edit `frontend/src/services/Api.ts`. Do EXACT-string replacements for these 4 lines (verified in RESEARCH.md Risk 3):

| Old literal                  | New literal                            |
|------------------------------|----------------------------------------|
| `'/auth/google'`             | `'/auth/oauth/google'`                 |
| `'/auth/google/link'`        | `'/auth/oauth/google/link'`            |
| `'/auth/google/signup'`      | `'/auth/oauth/google/signup'`          |
| `'/auth/google/connect'`     | `'/auth/oauth/google/connect'`         |

DO NOT touch other `/auth/*` literals. If the file contains helper functions that construct paths via template strings (e.g., `\`/auth/google/${param}\``), audit those patterns separately and rewrite to `\`/auth/oauth/google/${param}\``.

After the edit, run:
```bash
cd frontend
npm run type-check
npm test -- --run
```

Then the final guard grep:
```bash
grep -rnE "'/auth/google(/(link|signup|connect))?'" frontend/src/
```
This MUST return exit code 1 (no old literals remain). If it returns matches, migrate those too.

**Sanity check — Chrome extension is NOT affected** (D-14 re-confirmed):
```bash
grep -rn "/auth/" chrome-extension/src/
```
This MUST return empty OR only `/auth/token` / other public routes (not Google OAuth paths). The extension doesn't call Google OAuth — it receives an already-issued bearer token from the web app via `chrome.runtime.sendMessage`.
  </action>
  <verify>
    <automated>cd frontend && npm run type-check</automated>
    <automated>cd frontend && npm test -- --run 2>&1 | tail -40</automated>
    <automated>grep -rnE "'/auth/google(/(link|signup|connect))?'" frontend/src/ ; test $? -eq 1</automated>
    <automated>grep -q "'/auth/oauth/google'" frontend/src/services/Api.ts</automated>
    <automated>grep -q "'/auth/oauth/google/link'" frontend/src/services/Api.ts</automated>
    <automated>grep -q "'/auth/oauth/google/signup'" frontend/src/services/Api.ts</automated>
    <automated>grep -q "'/auth/oauth/google/connect'" frontend/src/services/Api.ts</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "'/auth/oauth/google'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/auth/oauth/google/link'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/auth/oauth/google/signup'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/auth/oauth/google/connect'" frontend/src/services/Api.ts` exits 0
    - `grep -rnE "'/auth/google(/(link|signup|connect))?'" frontend/src/` returns exit code 1 (no old literals)
    - `cd frontend && npm run type-check` exits 0
    - `cd frontend && npm test -- --run` exits 0
    - Chrome extension source has no Google OAuth URL references (D-14 preserved): `grep -rnE "/auth/(google|oauth)" chrome-extension/src/` returns exit code 1 (empty)
  </acceptance_criteria>
  <done>Frontend Api.ts uses the post-split Google OAuth paths; type-check + tests green; grep audit confirms zero stragglers; Chrome extension is confirmed untouched per D-14.</done>
</task>

</tasks>

<deferred>
## Deferred / documented-only

- **Further split of auth/webauthn.py (7 routes, ~400 lines) into sub-sub-packages:** CONTEXT.md Deferred Ideas — not a Phase 5 deliverable; file size is reasonable post-split.
- **Retroactive rename of historical test files:** CONTEXT.md Deferred Ideas.
- **Playwright E2E for Chrome extension:** D-39. Manual UAT per 05-HUMAN-UAT.md (created in Plan 03) is the post-deploy validation for AUTH-05.
- **Removing python-jose dependency:** Kept through Phase 5 for parity test (Risk 6). Removal in Phase 6.
- **Removing `get_logger` export:** Phase 3 D-36 defers to "late Phase 5 / early Phase 6". After this plan merges, run `grep -rn "from app.core.logging import get_logger" backend/app/` — if zero callers, open a follow-up for Phase 6.
- **UAT execution (AUTH-05):** The 5-step checklist in 05-HUMAN-UAT.md runs POST-DEPLOY on staging, not during this plan's execution. Plan 04 ends with the checklist ready; post-deploy UAT closes the phase.
</deferred>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Unauthenticated HTTP → /api/auth/* public routes | Login, signup, reset endpoints must remain public per D-31 |
| Unauthenticated HTTP → /api/auth/* protected routes | logout, 2FA management, webauthn credentials, oauth connect/list/delete must require JWT |
| Chrome extension bearer token → FastAPI get_current_user | Extension holds JWT in chrome.storage.local; passes via Authorization header; NEVER calls /auth/* or /admin/* (D-14 / Finding 3) |
| Web frontend → Google OAuth paths | Paths MOVE /auth/google/* → /auth/oauth/google/*; frontend updates in same PR |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-04-01 | Elevation of Privilege | Auth-protected route loses `Depends(get_current_user)` during sub-module extraction (characterization test regression) | mitigate | Task 2 preserves per-route `current_user: DBUser = Depends(get_current_user)` verbatim when copying each route. `test_auth_auth_coverage.py` (created Task 1) parametrizes over `app.routes` filtered by `/api/auth` and asserts 401 without auth for EVERY non-public route. Drift guard D-30 catches deleted tests. Phase 1 auth characterization tests (D-43) are the end-to-end guardrail — 7 happy-path flows MUST stay green. |
| T-05-04-02 | Information Disclosure | Public-route allow-list (D-31) drifts — a formerly-public route accidentally requires auth, blocking new signups/logins | mitigate | Task 1 creates `test_public_routes_still_return_non_401` in the coverage test. Every route in PUBLIC_ROUTES is asserted to NOT return 401 without auth. Any regression fails CI immediately. The allow-list is a named set; adding a route requires code review. |
| T-05-04-03 | Spoofing | `get_current_user` bypass due to wrong-dependency import in a new sub-module file (e.g., accidentally importing `get_optional_current_user`) | mitigate | Task 2 copies route handlers verbatim; the import from `app.api.dependencies.auth` is explicit at file top (Pattern G in PATTERNS.md). Coverage test `test_auth_route_requires_token` catches any 2xx/403 where 401 is expected. Manual Plan 04 code review inspects each `Depends(...)` declaration. |
| T-05-04-04 | Denial of Service | Google OAuth path move breaks web-app login flow (frontend calls old path → 404) | mitigate | Task 3 updates all 4 Google OAuth literals in Api.ts. Post-migration grep `grep -rnE "'/auth/google(/(link|signup|connect))?'" frontend/src/` returns empty. Chrome extension DOES NOT use Google OAuth paths (D-14, Finding 3) — it receives an already-issued bearer token from the web app. Zero extension changes needed. |
| T-05-04-05 | Spoofing | Circular import in auth/_helpers.py → uvicorn startup fails | mitigate | Task 1 enforces `auth/_helpers.py` imports ONLY from stdlib + third-party + app.api.dependencies.auth + app.api.models + app.api.schemas. The OAUTH_2FA_PURPOSE / GOOGLE_PROVIDER constants are DUPLICATED in _helpers.py (planner decision per PATTERNS.md §9) to avoid importing from oauth.py. Risk 4 mitigation verified by acceptance criteria grep: `grep -rn "from app.api.endpoints.auth\.(core|two_factor|webauthn|oauth)" backend/app/api/endpoints/auth/_helpers.py` returns exit 1. |
| T-05-04-06 | Tampering | In-flight Chrome extension tokens invalidated post-auth-split deploy (extension still holds old-format token) | mitigate | Phase 1 characterization tests (D-43) + PyJWT parity test (Plan 02) together prove token format is library-compatible. Per D-14, the extension calls `/users/me` on next action — this triggers `get_current_user` which decodes the bearer token. If decode fails (unlikely — token format is byte-identical across jose/PyJWT per Finding 1), the extension gets a 401 and prompts re-auth. AUTH-05 UAT (05-HUMAN-UAT.md Step 4) validates this flow end-to-end on staging before phase gate. |
</threat_model>

<verification>
```bash
# Per-plan green
cd backend
pytest -n auto tests/test_auth_auth_coverage.py tests/test_openapi_snapshot.py tests/test_ext_api_contract_up_to_date.py tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x

# Phase 3 + Phase 4 inherited guards
pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x

# Phase 1 D-43 end-to-end guardrail
pytest -n auto -k "auth and characterization" -x

# Frontend
cd ../frontend
npm run type-check
npm test -- --run

# Old-file deletion + hard-migration audit
test ! -f ../backend/app/api/endpoints/auth.py
grep -rn "from app.api.endpoints.auth import" ../backend/ | grep -v "endpoints\.auth\.\(core\|two_factor\|webauthn\|oauth\|_helpers\)"  # exit 1 expected

# Chrome extension untouched (D-14)
grep -rnE "/auth/(google|oauth)" ../chrome-extension/src/  # exit 1 expected (empty)
```

**Post-deploy** (after this plan lands on main + staging deploys):
Execute the 5-step AUTH-05 UAT checklist from `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md`. Only after all 5 steps pass does the phase gate close.
</verification>

<success_criteria>
1. `backend/app/api/endpoints/auth.py` does NOT exist; 24 routes served from `backend/app/api/endpoints/auth/{core,two_factor,webauthn,oauth}.py`.
2. `pytest -n auto backend/tests/test_auth_auth_coverage.py` exits 0 — every protected auth route returns 401 without JWT; every public route returns non-401.
3. Phase 1 auth characterization tests (7 happy-path flows per D-43) stay green — the end-to-end guardrail.
4. OpenAPI snapshot regenerated; diff matches the 4 intentional Google OAuth path moves per D-10.
5. `chrome-extension/API_CONTRACT.md` regenerated if drifted; drift-guard test passes.
6. Frontend Google OAuth paths (4 literals) migrated; type-check + tests green; zero stragglers on grep.
7. AUTH-04 regression guards (test_pyjwt_migration.py + test_jwt_algorithm_regression.py) stay green (no JWT regressions introduced by the split).
8. Chrome extension is untouched (D-14); AUTH-05 UAT checklist ready in 05-HUMAN-UAT.md for post-deploy execution.
</success_criteria>

<output>
After completion, create `.planning/phases/05-structural-router-splits/05-04-SUMMARY.md` with:
- Routes extracted per sub-module (counts: 7/3/7/7 = 24)
- OpenAPI snapshot delta summary (4 Google OAuth path moves per D-10)
- API_CONTRACT.md regeneration note (if it drifted)
- Phase 1 characterization pass confirmation (D-43 guardrail)
- Link to 05-HUMAN-UAT.md for post-deploy UAT execution (AUTH-05)
- Chrome extension untouched confirmation (D-14)
- Post-merge instruction: execute the 5-step staging UAT and record results in 05-HUMAN-UAT.md
</output>
