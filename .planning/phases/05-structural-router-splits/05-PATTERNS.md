# Phase 5: Structural Router Splits - Pattern Map

**Mapped:** 2026-04-22
**Files analyzed:** 28 (16 new + 1 new doc + 5 modified backend + 1 modified frontend + 1 modified terraform + 4 misc)
**Analogs found:** 28 / 28

---

## File Classification

### Backend — NEW files (endpoint sub-routers)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `backend/app/api/endpoints/admin/__init__.py` | package-init | import-aggregation | `backend/app/api/endpoints/__init__.py` (empty) | exact |
| `backend/app/api/endpoints/admin/stats.py` | controller | request-response (read-only) | `backend/app/api/endpoints/admin.py` (current stats routes, lines 181-248) | exact-self |
| `backend/app/api/endpoints/admin/jobs.py` | controller | CRUD | `backend/app/api/endpoints/admin.py` (current jobs routes, lines 1379-1596) | exact-self |
| `backend/app/api/endpoints/admin/crawlers.py` | controller | event-driven (EventBridge) + background-task | `backend/app/api/endpoints/admin.py` (current crawlers routes, lines 641-1371) | exact-self |
| `backend/app/api/endpoints/admin/db_ops.py` | controller | CRUD + subprocess | `backend/app/api/endpoints/admin.py` (current migrations/init/delete-all routes, lines 251-640, 1598-1718, 2029-2068) | exact-self |
| `backend/app/api/endpoints/admin/parts.py` | controller | CRUD | `backend/app/api/endpoints/admin.py` (current parts routes, lines 1719-2028) | exact-self |
| `backend/app/api/endpoints/admin/_helpers.py` | utility | module-level helpers | `backend/app/api/endpoints/admin.py` (_stamp_heartbeat/_heartbeat_loop/_get_superadmin_emails/_notify_job_completion, lines 88-136) | exact-self |
| `backend/app/api/endpoints/auth/__init__.py` | package-init | import-aggregation | `backend/app/api/endpoints/__init__.py` (empty) | exact |
| `backend/app/api/endpoints/auth/core.py` | controller | request-response | `backend/app/api/endpoints/auth.py` (login/verify/reset/logout routes, lines 90-352) | exact-self |
| `backend/app/api/endpoints/auth/two_factor.py` | controller | request-response (auth-gated) | `backend/app/api/endpoints/auth.py` (2FA routes, lines 357-486) | exact-self |
| `backend/app/api/endpoints/auth/webauthn.py` | controller | request-response (challenge-token) | `backend/app/api/endpoints/auth.py` (webauthn routes + helpers, lines 492-774) | exact-self |
| `backend/app/api/endpoints/auth/oauth.py` | controller | request-response (OAuth2 federated) | `backend/app/api/endpoints/auth.py` (google/oauth routes + helpers, lines 770-1191) | exact-self |
| `backend/app/api/endpoints/auth/_helpers.py` | utility | cross-module helpers | `backend/app/api/endpoints/auth.py` (_issue_login_response/_maybe_2fa_challenge, lines 813-832) | exact-self |

### Backend — NEW files (scripts + tests)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `backend/scripts/generate_ext_api_contract.py` | script | transform (openapi → markdown) | `backend/scripts/check_migrations.py` | role-match (both are CLI scripts with exit codes + pathlib) |
| `backend/tests/test_admin_auth_coverage.py` | test | parametrized integration | `backend/tests/test_session_query_regression.py` + `backend/tests/auth/test_characterization_login.py` | composite (regression-guard + integration patterns) |
| `backend/tests/test_auth_auth_coverage.py` | test | parametrized integration | `backend/tests/test_admin_auth_coverage.py` (created in same phase) | exact (sibling) |
| `backend/tests/test_pyjwt_migration.py` | test | parity check | `backend/tests/test_pydantic_v1_regression.py` | role-match (dependency migration proof test) |
| `backend/tests/test_jwt_algorithm_regression.py` | test | grep-based regression | `backend/tests/test_session_query_regression.py` | exact (same grep-guard shape) |
| `backend/tests/test_ext_api_contract_up_to_date.py` | test | drift guard (file equality) | `backend/tests/test_openapi_snapshot.py` | exact (same shape: run generator → diff file) |

### Frontend / Docs / Terraform / Other

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `chrome-extension/API_CONTRACT.md` | doc (generated) | output-only | N/A (first of its kind) | no-analog |
| `backend/app/api/dependencies/auth.py` (MODIFIED) | dependency/utility | JWT decode | itself (in-place edit) | self |
| `backend/app/core/config.py` (MODIFIED) | config | Pydantic settings | itself — existing fields (`ACCESS_TOKEN_EXPIRE_MINUTES` line 33, `SECRET_KEY` line 29) | exact-self |
| `backend/app/main.py` (MODIFIED) | app-factory | router registration | itself — existing `register_endpoint(admin.router, prefix="/admin", ...)` line 280-285 | exact-self |
| `backend/requirements.txt` (MODIFIED) | dep-manifest | package pin swap | itself — current line `python-jose[cryptography]==3.5.0` | exact-self |
| `frontend/src/services/Api.ts` (MODIFIED) | api-client | URL rewrite | itself — existing admin/auth path constants | exact-self |
| `terraform/scheduler.tf` (MAYBE-MODIFIED — see Finding 5) | infra | API destination path | itself — `crawler_run` resource | exact-self |

---

## Pattern Assignments

### 1. Admin sub-router files (stats.py, jobs.py, crawlers.py, db_ops.py, parts.py)

**Analog:** `backend/app/api/endpoints/admin.py` + `backend/app/api/endpoints/crawler_schedules.py` (a clean reference sub-router that already lives at `/admin/crawler-schedules` prefix).

**Imports pattern** (copy from `backend/app/api/endpoints/crawler_schedules.py:1-40`):
```python
"""<Module purpose docstring — one line summary, blank line, longer prose>."""

from __future__ import annotations

import logging
from typing import ...
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.<...> import <...> as DB<...>
from app.api.schemas.<...> import <...>
from app.api.services import <job_service | part_linker_service>  # only if needed
from app.api.utils.endpoint_decorators import standard_responses
from app.db.session import get_db

logger = logging.getLogger(__name__)  # Phase 3 D-33—D-37 (REQUIRED)
router = APIRouter()
```

**Route decorator pattern** (copy from `backend/app/api/endpoints/admin.py:181-225` — `/stats/table-counts`):
```python
@router.get(
    "/table-counts",                                   # D-15: RELATIVE path (prefix applied at main.py)
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Supplemental table and polymorphic vote/report counts",
        forbidden=True,
    ),
)
async def get_admin_table_counts(
    current_user: DBUser = Depends(get_current_admin_user),   # ADMIN-02: explicit per-route
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """<docstring>"""
    _ = current_user                                   # Common idiom when user is unused inside body
    ...
```

**Route move template** (one concrete example showing what "move this route" means — from `admin.py:181` to `admin/stats.py`):

Before (in current `admin.py`):
```python
@router.get(
    "/stats/table-counts",
    ...
)
async def get_admin_table_counts(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ...
```

After (in `admin/stats.py`):
```python
@router.get(
    "/table-counts",                                   # prefix dropped — /admin/stats now applied in main.py
    ...
)
async def get_admin_table_counts(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ...
```

**Admin URL prefix map (D-09) — where each route lives after split:**

| Sub-module | Prefix in main.py | Relative paths in the file |
|------------|-------------------|----------------------------|
| `admin/stats.py` | `/admin/stats` | `/table-counts` (GET), `/crawl-bucket` (GET) |
| `admin/jobs.py` | `/admin/jobs` | `/` (GET), `/{job_id}` (GET), `/{job_id}/crawler-progress` (GET), `/{job_id}/cancel` (POST) |
| `admin/crawlers.py` | `/admin/crawlers` | `/` (GET listing), `/run` (POST), `/rescrape-archives` (POST), `/service-account` (GET) |
| `admin/db_ops.py` | `/admin/db-ops` | `/migrations/run` (POST), `/migrations/current` (GET), `/init/car-generations` (POST), `/init/part-categories` (POST), `/cars/delete-all` (POST), `/parts/delete-all` (POST), `/part-manufacturers/delete-all` (POST) |
| `admin/parts.py` | `/admin/parts` | `/lookup-by-url` (GET), `/{part_id}/link-group` (GET), `/promote-canonical` (POST), `/unlink` (POST), `/link` (POST), `/rescan` (POST) |

---

### 2. `backend/app/api/endpoints/admin/crawlers.py` (special: Optional admin + cron-key dual auth)

**Analog:** `admin.py:823-906` (`run_crawlers_endpoint`). Special pattern — accepts EITHER JWT admin OR `X-Admin-Cron-Key` header.

**Dual-auth route pattern** (copy from `admin.py:823-851`):
```python
@router.post(
    "/run",
    response_model=Dict[str, Any],
    responses=standard_responses(success_description="Crawler job started", forbidden=True),
)
async def run_crawlers_endpoint(
    body: CrawlerRunRequest,
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_current_admin_user),   # Optional = allows unauth if cron key valid
    x_admin_cron_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    is_scheduled = _verify_cron_key(x_admin_cron_key)
    if not is_scheduled and current_user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    ...
```

**Planner note (Open Question 3 from RESEARCH.md):** These two routes (`/run`, `/rescrape-archives`) will return 403 (not 401) when called without any auth because `get_current_admin_user` with `Optional` doesn't raise 401. The 401/403 parametrized test must accept `in (401, 403)` for these two routes OR carry an explicit allow-list.

**`_verify_cron_key` helper pattern** (copy verbatim from `admin.py:139-147`):
```python
def _verify_cron_key(x_admin_cron_key: Optional[str]) -> bool:
    """Return True if the provided key matches CRON_SECRET_KEY (constant-time compare)."""
    expected = settings.CRON_SECRET_KEY
    if not expected or not x_admin_cron_key:
        return False
    return secrets.compare_digest(expected, x_admin_cron_key)
```

**ECS launchers (D-24 stay-inline):** Keep `_launch_ecs_crawler_task` (admin.py:665-756), `_run_crawlers_in_process` (admin.py:757-820), `_launch_ecs_rescrape_task` (admin.py:1081-1141), `_run_rescrape_in_process` (admin.py:1142-1204) verbatim in `admin/crawlers.py`. No extraction.

---

### 3. `backend/app/api/endpoints/admin/_helpers.py`

**Analog:** `admin.py:88-136` (heartbeat + superadmin notify helpers). Move verbatim.

**Contents to extract** (copy from `admin.py:88-136`):
```python
"""Background-job lifecycle helpers shared across admin sub-routers.

Mirrors the auth/_helpers.py pattern for package consistency (D-21).
Used by crawlers.py (crawler-run job) and potentially db_ops.py (migrations/run).
Leaf module: no sibling-sub-module imports (Risk 4 mitigation).
"""

from __future__ import annotations

import asyncio
import logging
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.core.email import send_job_report_email
from app.core.worker_identity import WORKER_INSTANCE_ID
from app.db.session import SessionLocal
from app.services import job_service

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_SEC = 15


def _stamp_heartbeat(job_id: UUID) -> None:
    """Write a single heartbeat row. Runs in a thread to keep the event loop free."""
    db = SessionLocal()
    try:
        job_service.heartbeat_job(db, job_id, WORKER_INSTANCE_ID)
    finally:
        db.close()


async def _heartbeat_loop(job_id: UUID, interval: float = _HEARTBEAT_INTERVAL_SEC) -> None:
    """Periodically refresh a job's last_heartbeat_at ..."""
    # ... body from admin.py:97-110


def _get_superadmin_emails(db: Session) -> List[str]:
    users = db.scalars(
        select(DBUser.email).where(DBUser.is_superuser.is_(True), DBUser.disabled.is_(False))
    ).all()
    return list(users)


def _notify_job_completion(job_id: UUID) -> None:
    # ... body from admin.py:119-136
```

**Convention reminder (Risk 4 — circular imports):** `admin/_helpers.py` must NOT import from `admin/crawlers.py`, `admin/jobs.py`, etc. Only imports from `app.api.services.*`, `app.api.models.*`, `app.core.*`, stdlib, third-party.

---

### 4. `backend/app/api/endpoints/admin/db_ops.py` (special: `_get_alembic_directory` + `_init_result`)

**Analog:** `admin.py:150-179` (path resolution) + `admin.py:411-414` (result shape).

**Keep inline** per D-23 — these helpers are used ONLY by migration/init endpoints:

```python
# From admin.py:150-179
def _get_alembic_directory() -> str:
    """Get the directory containing alembic.ini."""
    if os.path.exists("/app/alembic.ini"):
        return "/app"
    ...


# From admin.py:411-414
def _init_result(success: bool, message: str) -> Dict[str, Any]:
    return {"success": success, "message": message}
```

**Imports that admin/db_ops.py needs (from the imports admin.py currently uses for db-ops routes):**
```python
import os
import subprocess  # nosec B404
import threading
from typing import Any, Dict

from app.api.models.car_generation import CarGeneration as DBCar
from app.api.models.category import Category as DBCategory
from app.core.init_cars import init_car_generations
from app.core.init_categories import init_part_categories
# + routing imports (FastAPI, sqlalchemy) same as other sub-routers
```

---

### 5. `backend/app/api/endpoints/admin/parts.py` (special: `_first_listing_for` + `_link_group_member`)

**Analog:** `admin.py:1719-1743` (parts helpers).

**Keep inline** per D-25. Concrete excerpt from `admin.py:1719-1743`:
```python
def _first_listing_for(db: Session, part_id: UUID) -> Optional[DBPartListing]:
    return db.scalars(
        select(DBPartListing).where(DBPartListing.part_id == part_id)
        .order_by(DBPartListing.created_at.asc())
    ).first()


def _link_group_member(db: Session, part: DBPart, canonical_id: UUID) -> CanonicalLinkGroupMember:
    ...
```

**Import hoisting opportunity (Finding 6):** The 8 inline `from app.api.services.part_linker_service import X` lines scattered across `admin.py:1728, 1799, 1809, 1836, 1858, 1896, 1932, 1996` should hoist to module-level at the top of `admin/parts.py`:
```python
from app.api.services.part_linker_service import (
    _point_siblings_at,
    link_group_part_ids,
    reelect_canonical,
    score_metadata_richness,
    unlink_part,
)
```

---

### 6. Auth sub-router files (core.py, two_factor.py, webauthn.py, oauth.py)

**Analog:** `backend/app/api/endpoints/auth.py` (entire file — extraction targets).

**Imports pattern** (copy from `auth.py:1-87`, filtered per sub-module):
```python
"""<Sub-module purpose>."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
import jwt                                     # POST-PR 2 (PyJWT)
from jwt import InvalidTokenError              # POST-PR 2 (PyJWT)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    ALGORITHM,                                 # now reads settings.JWT_ALGORITHM (D-07)
    create_access_token,
    get_access_token_expires_delta_for_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.api.models.user import User as DBUser
from app.api.schemas.auth import ...
from app.api.schemas.user import UserRead
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)                  # Phase 3 D-33—D-37 REQUIRED
router = APIRouter()
```

**Auth URL prefix map (D-10):**

| Sub-module | Prefix in main.py | Relative paths in the file |
|------------|-------------------|----------------------------|
| `auth/core.py` | `/auth` | `/token` (POST), `/token/2fa` (POST), `/verify-email` (POST), `/verify-email/confirm` (GET), `/reset-password` (POST), `/reset-password/confirm` (POST), `/logout` (POST) |
| `auth/two_factor.py` | `/auth/2fa` | `/setup` (POST), `/verify` (POST), `/disable` (POST) |
| `auth/webauthn.py` | `/auth/webauthn` | `/register/options` (POST), `/register/verify` (POST), `/login/options` (POST), `/login/verify` (POST), `/credentials` (GET), `/credentials/{credential_id}` (PATCH + DELETE) |
| `auth/oauth.py` | `/auth/oauth` | `/google` (POST), `/google/signup` (POST), `/google/link` (POST), `/google/connect` (POST), `/2fa` (POST), `/` (GET list), `/{account_id}` (DELETE) |

**Route move template** (example — `auth.py:357` → `auth/two_factor.py`):

Before:
```python
@router.post("/2fa/setup", response_model=TOTPSetupResponse)
async def setup_2fa(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TOTPSetupResponse:
    ...
```

After (now at prefix `/auth/2fa`):
```python
@router.post("/setup", response_model=TOTPSetupResponse)        # /2fa prefix stripped
async def setup_2fa(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TOTPSetupResponse:
    ...
```

**Route move template for `auth/oauth.py` — `/google` → `/oauth/google` (D-10 aggressive restructure):**

Before (`auth.py:834`):
```python
@router.post("/google")
async def google_sign_in(...):
    ...
```

After (in `auth/oauth.py`, prefix now `/auth/oauth`):
```python
@router.post("/google")     # final URL: /api/auth/oauth/google
async def google_sign_in(...):
    ...
```

---

### 7. `backend/app/api/endpoints/auth/webauthn.py` (local helpers stay)

**Analog:** `auth.py:492-522` (challenge-token helpers).

**Keep inline** per D-19. Move verbatim:
```python
WEBAUTHN_REGISTER_PURPOSE = "webauthn_register"
WEBAUTHN_LOGIN_PURPOSE = "webauthn_login"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _build_challenge_token(purpose: str, challenge: bytes, user_id: str | None = None) -> str:
    ...


def _decode_challenge_token(token: str, expected_purpose: str) -> tuple[bytes, str | None]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:                       # POST-PR 2: was `except JWTError`
        ResponsePatterns.raise_bad_request("Invalid or expired challenge")
    ...
```

**Post-PyJWT swap note:** Line 515 of current `auth.py` has `except JWTError:` — becomes `except InvalidTokenError:` in `auth/webauthn.py` (already swapped because auth split lands AFTER PyJWT PR per D-41).

---

### 8. `backend/app/api/endpoints/auth/oauth.py` (Google-specific helpers stay local)

**Analog:** `auth.py:770-810` (Google helpers) + `auth.py:908-915` (`_decode_purpose_token`).

**Keep local** per D-20. Move verbatim:
```python
GOOGLE_LINK_PURPOSE = "google_link"
GOOGLE_SIGNUP_PURPOSE = "google_signup"
OAUTH_2FA_PURPOSE = "oauth_2fa"
GOOGLE_PROVIDER = "google"


def _ensure_google_enabled() -> None:
    if not settings.google_oauth_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")


def _verify_google_or_400(id_token_str: str, nonce: str, logger: logging.Logger) -> GoogleIdentity:
    ...


def _suggest_username(email: str, db: Session) -> str:
    ...


def _decode_purpose_token(token: str, expected_purpose: str) -> dict[str, Any]:
    ...
```

**Cross-module imports required:** `auth/oauth.py` imports from `auth/_helpers.py`:
```python
from app.api.endpoints.auth._helpers import _issue_login_response, _maybe_2fa_challenge
```

---

### 9. `backend/app/api/endpoints/auth/_helpers.py`

**Analog:** `auth.py:813-832` (`_issue_login_response`, `_maybe_2fa_challenge`).

**Move verbatim** per D-18:
```python
"""Cross-module auth helpers shared across sub-routers.

Used by core.py (login, 2FA login), oauth.py (Google sign-in/signup),
two_factor.py (2FA verify login). Leaf module: no sibling-sub-module imports.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from app.api.dependencies.auth import create_access_token, get_access_token_expires_delta_for_user
from app.api.models.user import User as DBUser
from app.api.schemas.user import UserRead

logger = logging.getLogger(__name__)

# Note: OAUTH_2FA_PURPOSE / GOOGLE_PROVIDER remain in oauth.py (D-20).
# _maybe_2fa_challenge references them via conditional import OR re-imports minimally here.
# The canonical approach: import the constants from oauth.py IF _maybe_2fa_challenge stays
# cross-module, OR inline the constants here. Planner decides during implementation.


def _issue_login_response(user: DBUser) -> dict[str, str | UserRead]:
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=expires_delta)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


def _maybe_2fa_challenge(user: DBUser) -> Optional[dict[str, str | bool]]:
    """If user has TOTP enabled, mint an otp_token bound to them and return the challenge payload."""
    # See auth.py:823-831 for verbatim body — needs OAUTH_2FA_PURPOSE + GOOGLE_PROVIDER constants.
    ...
```

**Planner decision point (Open Question — see CONTEXT.md D-18/D-20):** `_maybe_2fa_challenge` currently references `OAUTH_2FA_PURPOSE` and `GOOGLE_PROVIDER` — constants declared in oauth.py at current `auth.py:771-772`. Either (a) duplicate the constants in `_helpers.py`, (b) import from `oauth.py` (requires the helper to live lower than oauth.py in the import graph — risky), or (c) hoist the constants to `_helpers.py` and have `oauth.py` import them back.

---

### 10. `backend/app/api/endpoints/admin/__init__.py` and `backend/app/api/endpoints/auth/__init__.py`

**Analog:** `backend/app/api/endpoints/__init__.py` (currently empty).

**Content (both files):** Empty or one-line docstring. Router mounting happens in `main.py` per D-08, not in `__init__.py`.

```python
"""Admin endpoint sub-package — sub-routers registered individually in main.py (D-08)."""
```

---

### 11. `backend/scripts/generate_ext_api_contract.py` (NEW)

**Analog:** `backend/scripts/check_migrations.py` (role-match: CLI script with pathlib, exit codes, run from repo root).

**Script skeleton** (copy structure from `check_migrations.py:1-40` adapted for openapi):
```python
#!/usr/bin/env python3
"""
AUTH-06 + D-34—D-37: Chrome Extension API Contract Generator.

Generates chrome-extension/API_CONTRACT.md from app.openapi() for the 16 endpoints
the extension calls (allow-list inline below).

Regenerate when extension endpoint list changes OR when route signatures change:

    cd backend
    python scripts/generate_ext_api_contract.py

The companion drift guard (backend/tests/test_ext_api_contract_up_to_date.py)
asserts the committed .md matches generator output on every CI run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# <repo>/backend/scripts/generate_ext_api_contract.py -> parents[2] = <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "chrome-extension" / "API_CONTRACT.md"

# Allow-list of (method, path) tuples — mirrors chrome-extension/src/background.ts
# endpoint inventory per Finding 3 of 05-RESEARCH.md.
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
    name = ref.rsplit("/", 1)[-1]
    return schemas.get(name, {})


def flatten_schema(schema: dict[str, Any], schemas: dict[str, Any], depth: int = 0) -> dict[str, Any]:
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


def generate_markdown() -> str:
    # TESTING=true ENABLE_RATE_LIMITING=false must be set (see test_openapi_snapshot.py rationale)
    from app.main import app  # function-scope import for env-var ordering

    spec = app.openapi()
    schemas = spec.get("components", {}).get("schemas", {})
    out: list[str] = [
        "# Chrome Extension API Contract",
        "",
        "Generated from `app.openapi()`. Do not edit by hand.",
        "Regenerate: `python backend/scripts/generate_ext_api_contract.py`",
        "",
    ]
    for method, path in EXTENSION_ENDPOINTS:
        op = spec.get("paths", {}).get(path, {}).get(method.lower(), {})
        out.append(f"## `{method} {path}`")
        out.append("")
        if op.get("summary"):
            out.append(f"**Summary:** {op['summary']}")
        if op.get("description"):
            out.append(f"**Description:** {op['description']}")
        # parameters (path/query), request body, responses — one section each
        ...
    return "\n".join(out)


if __name__ == "__main__":
    md = generate_markdown()
    OUTPUT_PATH.write_text(md, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
```

**OpenAPI env gate (CRITICAL — lifted from `test_openapi_snapshot.py:14-17` pitfall 8):** Script MUST be run with `TESTING=true ENABLE_RATE_LIMITING=false` so conftest-style env ordering applies and rate-limiter schemas don't leak into output. Add this as a comment at the script top.

---

### 12. `backend/tests/test_admin_auth_coverage.py` (NEW, parametrized)

**Analog:** `backend/tests/test_session_query_regression.py` (grep-guard shape) + `backend/tests/auth/test_characterization_login.py` (integration patterns).

**Full file template** (assembled from RESEARCH.md Finding 4 recommendation + existing conftest fixtures):
```python
"""ADMIN-02 regression: every route under /api/admin requires admin auth.

D-27—D-30: parametrized over (method, path) extracted from app.routes at
collection time. Per-route assertions:
  (a) no auth header -> 401 (or 403 for dual-auth routes)
  (b) regular-user token -> 403

D-30 drift guard: count-at-or-above check catches a disabled parametrized
test or a route removal without test update. Combined with SAFE-05 OpenAPI
snapshot the drift surface is fully covered.
"""

from __future__ import annotations

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

# Routes that use Optional[DBUser] admin dep + X-Admin-Cron-Key header and
# return 403 (not 401) on bare requests. See admin.py:831-851 pattern.
# If the route must be called by an unauthenticated EventBridge request with
# valid CRON_SECRET_KEY, it accepts 401|403 on missing-both case.
DUAL_AUTH_ROUTES = {
    ("POST", "/api/admin/crawlers/run"),
    ("POST", "/api/admin/crawlers/rescrape-archives"),
}


def _admin_routes() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/api/admin"):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                out.append((m, r.path))
    return out


ADMIN_ROUTES = _admin_routes()


def _fill_path_params(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_requires_auth(method: str, path: str, client: TestClient) -> None:
    resp = client.request(method, _fill_path_params(path))
    if (method, path) in DUAL_AUTH_ROUTES:
        assert resp.status_code in (401, 403), f"{method} {path} -> {resp.status_code}"
    else:
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_forbids_regular_user(method: str, path: str, client: TestClient) -> None:
    from tests.conftest import create_and_login_user, login_user

    # Fresh user per parametrized test — parametrize-in-test-ids unique suffix.
    username = f"cov_user_{method}_{abs(hash(path)) & 0xFFFF}"
    create_and_login_user(client, username=username)
    token = login_user(client, username)
    resp = client.request(method, _fill_path_params(path), headers={"Authorization": f"Bearer {token}"})
    # 403 for admin-guarded routes; admin-guarded routes invoked with JWT should never return 401
    assert resp.status_code == 403, f"{method} {path} with regular user -> {resp.status_code}"


def test_admin_route_count_at_or_above_expected() -> None:
    # D-30 drift guard
    assert len(ADMIN_ROUTES) >= 23, f"Expected >=23 admin routes (post-split), got {len(ADMIN_ROUTES)}"
```

**Fixture reuse** (from `conftest.py:688` + `conftest.py:356` + `conftest.py:368`):
- `create_and_login_user(client, username)` — module-level helper, NOT a fixture. Import directly. (`conftest.py:368`)
- `login_user(client, username)` — returns Bearer token string. (`conftest.py:356`)
- `create_and_login_admin_user(client, username)` — module-level helper for admin user; available for positive-path (2xx) assertion extension. (`conftest.py:688`)

---

### 13. `backend/tests/test_auth_auth_coverage.py` (NEW, parametrized)

**Analog:** `test_admin_auth_coverage.py` (sibling — just created). Filter by `/api/auth/*` prefix and exclude public routes.

**Template** (D-31 public allow-list inline):
```python
"""AUTH-03 regression: every protected route under /api/auth requires a valid JWT.

Public auth routes (login, email verify, reset, Google sign-in) are excluded
via the PUBLIC_ROUTES allow-list below — any new public route is a deliberate
review-gated addition.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

# D-31: Intentionally public (no auth dependency)
PUBLIC_ROUTES = {
    ("POST", "/api/auth/token"),
    ("POST", "/api/auth/token/2fa"),
    ("POST", "/api/auth/verify-email"),
    ("GET", "/api/auth/verify-email/confirm"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/reset-password/confirm"),
    ("POST", "/api/auth/oauth/google"),        # D-10: moved from /auth/google
    ("POST", "/api/auth/oauth/google/signup"),
    ("POST", "/api/auth/oauth/google/link"),
    ("POST", "/api/auth/oauth/2fa"),
    # WebAuthn login/options + login/verify are pre-auth challenges — user isn't logged in yet
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


@pytest.mark.parametrize("method,path", AUTH_PROTECTED_ROUTES)
def test_auth_route_requires_token(method: str, path: str, client: TestClient) -> None:
    import re
    resolved = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)
    resp = client.request(method, resolved)
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


def test_auth_protected_route_count_at_or_above_expected() -> None:
    # 24 total auth routes - 12 public = 12 protected (actual may differ slightly)
    assert len(AUTH_PROTECTED_ROUTES) >= 8, f"Too few protected auth routes: {len(AUTH_PROTECTED_ROUTES)}"
```

---

### 14. `backend/tests/test_pyjwt_migration.py` (NEW, parity)

**Analog:** `backend/tests/test_pydantic_v1_regression.py` (role-match — library-migration proof test).

**Full file** (from RESEARCH.md Finding 1 recommendation):
```python
"""AUTH-04 D-05: HS256 token parity between python-jose (old) and PyJWT (new).

Proves a token issued by the old library decodes identically under the new.
HS256 is deterministic HMAC — byte-compatible across libraries. This test
is the reviewer-visible safety check for the PyJWT swap PR.

Lifetime discretion: keep post-migration as a safeguard against future
library-swap regressions, OR delete alongside python-jose dependency in
Phase 6 cleanup. See CONTEXT.md "Claude's Discretion".
"""

from __future__ import annotations

import jwt as pyjwt
from jose import jwt as jose_jwt

from app.core.config import settings


def test_pyjwt_decodes_jose_hs256_token() -> None:
    """Round-trip: jose encode -> PyJWT decode -> payload match."""
    payload = {"sub": "user@example.com", "exp": 9999999999}
    secret = settings.SECRET_KEY or "test-secret-for-parity-check"

    jose_token = jose_jwt.encode(payload, secret, algorithm="HS256")
    decoded = pyjwt.decode(jose_token, secret, algorithms=["HS256"])

    assert decoded == payload


def test_pyjwt_and_jose_produce_identical_hs256_tokens() -> None:
    """Byte-identity assertion — both libraries produce the same string for HS256."""
    payload = {"sub": "bob", "exp": 9999999999}
    secret = "test-secret-deterministic"

    pyjwt_token = pyjwt.encode(payload, secret, algorithm="HS256")
    jose_token = jose_jwt.encode(payload, secret, algorithm="HS256")

    assert pyjwt_token == jose_token
```

---

### 15. `backend/tests/test_jwt_algorithm_regression.py` (NEW, grep)

**Analog:** `backend/tests/test_session_query_regression.py` (EXACT shape — same grep-guard pattern; Phase 4 D-09).

**Full file** (mirror session.query regression guard exactly, adapted for `jwt.decode`):
```python
"""AUTH-04 D-04 regression: every jwt.decode() call MUST specify algorithms=[].

Scoped to backend/app/ per Phase 3/4 precedent (test_session_query_regression.py).
Guards against the CWE-327 / "alg: none" vulnerability class — if a future PR
adds a bare jwt.decode(token, key) call, this test fails at CI.

Companion tests: test_session_query_regression.py, test_pydantic_v1_regression.py,
test_logger_migration_regression.py.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

_DECODE_PATTERN = re.compile(r"\bjwt\.decode\(")
_ALG_PATTERN = re.compile(r"algorithms\s*=\s*\[")


def test_every_jwt_decode_specifies_algorithms() -> None:
    offenders: list[tuple[str, int, str]] = []
    for pyfile in APP_DIR.rglob("*.py"):
        lines = pyfile.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _DECODE_PATTERN.search(line):
                # Check same line + next 2 lines (multi-line statements)
                window = "\n".join(lines[lineno - 1:lineno + 2])
                if not _ALG_PATTERN.search(window):
                    offenders.append((str(pyfile.relative_to(APP_DIR)), lineno, line.strip()))
    assert not offenders, (
        "jwt.decode() calls without algorithms=[...] detected (CWE-327 risk):\n"
        + "\n".join(f"  {f}:{ln} -> {code}" for f, ln, code in offenders)
    )
```

---

### 16. `backend/tests/test_ext_api_contract_up_to_date.py` (NEW, drift-guard)

**Analog:** `backend/tests/test_openapi_snapshot.py` (EXACT shape — run generator, diff committed file, provide regeneration command in the assertion message).

**Full file** (mirror test_openapi_snapshot.py structure):
```python
"""AUTH-06 D-36 drift guard: chrome-extension/API_CONTRACT.md matches generator output.

Per D-36, developers regenerate the contract locally when the extension endpoint
list or underlying route signatures change, then commit the new .md. CI fails
here if the committed doc is stale.

Same shape as test_openapi_snapshot.py — diff IS the review artifact.
"""

from __future__ import annotations

from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "chrome-extension" / "API_CONTRACT.md"


def test_api_contract_matches_generator() -> None:
    # Function-scope import — same ordering constraint as test_openapi_snapshot.py
    from backend.scripts.generate_ext_api_contract import generate_markdown

    expected = generate_markdown()
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

---

### 17. `backend/app/api/dependencies/auth.py` (MODIFIED)

**Current state** (verified excerpts):

Line 7 (`dependencies/auth.py:7`):
```python
from jose import JWTError, jwt
```

Line 17 (`dependencies/auth.py:17`):
```python
ALGORITHM = "HS256"
```

Lines 100, 132, 160 — three `except JWTError:` sites.

**Delta (PR 2 — PyJWT swap):**

- Line 7: `from jose import JWTError, jwt` → `import jwt` + `from jwt import InvalidTokenError` (D-02).
- Line 17: `ALGORITHM = "HS256"` → `ALGORITHM = settings.JWT_ALGORITHM` (D-03, D-07).
- Lines 100, 132, 160: `except JWTError:` → `except InvalidTokenError:` (3 sites).

**Key convention:** The module-level `ALGORITHM` constant is KEPT (D-07 explicit) — sibling code (`auth.py`, `webauthn`, `oauth`) imports it via `from app.api.dependencies.auth import ALGORITHM` at `auth.py:42`. Renaming to `JWT_ALGORITHM` or removing would cascade; the scope stays `ALGORITHM = settings.JWT_ALGORITHM`.

---

### 18. `backend/app/core/config.py` (MODIFIED)

**Analog (same-file):** Existing Pydantic field `ACCESS_TOKEN_EXPIRE_MINUTES: int = 60` at line 33.

**Delta:** Add one field after line 36:
```python
# JWT algorithm — PyJWT swap (AUTH-04 D-03). HS256 preserved per D-46.
JWT_ALGORITHM: str = Field(
    default="HS256",
    description="Algorithm used to sign + verify JWTs. Must match on encode and decode.",
)
```

Place in the "# JWT Auth" section (after `ACCESS_TOKEN_EXPIRE_MINUTES_MAX` at line 36). Follow the `Field(default=..., description=...)` convention used by every other field in the file (e.g., `SECRET_KEY` at line 29).

---

### 19. `backend/app/main.py` (MODIFIED)

**Current state** (`main.py:279-285` — single admin registration):
```python
# Admin endpoint
endpoint_registry.register_endpoint(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    description="Admin-only system management operations",
)
```

**Current state** (`main.py:225-230` — single auth registration):
```python
endpoint_registry.register_endpoint(
    auth.router,
    prefix="/auth",
    tags=["authentication"],
    description="User authentication and authorization",
)
```

**Delta — replace 2 registrations with 9** (from RESEARCH.md Finding 2 recommendation, D-08):

For admin (PR 1):
```python
# Replace `from .api.endpoints import ... admin ...` with sub-package imports.
# main.py:9-31 currently imports `admin`; after PR 1, import each sub-module individually.

from .api.endpoints.admin import (
    crawlers as admin_crawlers,
    db_ops as admin_db_ops,
    jobs as admin_jobs,
    parts as admin_parts,
    stats as admin_stats,
)

# (replacing lines 279-285)
endpoint_registry.register_endpoint(
    admin_stats.router,
    prefix="/admin/stats",
    tags=["admin"],
    description="Admin statistics (table counts, crawl bucket)",
)
endpoint_registry.register_endpoint(
    admin_jobs.router,
    prefix="/admin/jobs",
    tags=["admin"],
    description="Admin background job listing, detail, cancel",
)
endpoint_registry.register_endpoint(
    admin_crawlers.router,
    prefix="/admin/crawlers",
    tags=["admin"],
    description="Admin crawler management (run, rescrape archives, service account)",
)
endpoint_registry.register_endpoint(
    admin_db_ops.router,
    prefix="/admin/db-ops",
    tags=["admin"],
    description="Admin database operations (migrations, init data, bulk delete)",
)
endpoint_registry.register_endpoint(
    admin_parts.router,
    prefix="/admin/parts",
    tags=["admin"],
    description="Admin canonical parts management (link, unlink, rescan)",
)
```

For auth (PR 4):
```python
from .api.endpoints.auth import (
    core as auth_core,
    oauth as auth_oauth,
    two_factor as auth_2fa,
    webauthn as auth_webauthn,
)

# (replacing lines 225-230)
endpoint_registry.register_endpoint(
    auth_core.router,
    prefix="/auth",
    tags=["authentication"],
    description="Login / logout / email / password reset",
)
endpoint_registry.register_endpoint(
    auth_2fa.router,
    prefix="/auth/2fa",
    tags=["authentication"],
    description="TOTP 2FA setup and verification",
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
    description="Google OAuth sign-in / link / connect",
)
```

**Tag convention (Open Question 2 resolution from RESEARCH.md):** Use single tag per package (`"admin"` for all admin sub-modules; `"authentication"` for all auth sub-modules) to preserve current Swagger UI grouping. Do NOT use per-sub-module tags — FastAPI merges routers sharing a tag, and this minimizes OpenAPI snapshot churn.

---

### 20. `backend/requirements.txt` (MODIFIED)

**Current state** (verified — `requirements.txt:24-28`):
```
# Note: python-jose depends on ecdsa (CVE-2024-23342), but this is not exploitable
# in this codebase as we use HS256 (HMAC) algorithm, not ECDSA-based algorithms.
# The ecdsa maintainers have indicated no plans to fix this vulnerability.
python-jose[cryptography]==3.5.0
```

**Delta (PR 2 — D-06):**
- Add `PyJWT==2.12.1` line.
- KEEP `python-jose[cryptography]==3.5.0` through Phase 5 (see Risk 6 in RESEARCH.md). The parity test (`test_pyjwt_migration.py`) imports jose.
- Removal of `python-jose` is deferred to Phase 6 dependency cleanup.

Result:
```
# PyJWT — primary JWT library (AUTH-04, Phase 5 D-06).
PyJWT==2.12.1

# python-jose — KEPT through Phase 5 for test_pyjwt_migration.py parity assertion.
# Scheduled for removal in Phase 6 dependency cleanup.
# Note: python-jose depends on ecdsa (CVE-2024-23342), but this is not exploitable
# in this codebase as we use HS256 (HMAC) algorithm, not ECDSA-based algorithms.
python-jose[cryptography]==3.5.0
```

---

### 21. `frontend/src/services/Api.ts` (MODIFIED)

**Analog (same-file):** Existing `adminApi` object at `Api.ts:1387-1450+` uses plain string path literals.

**Delta map (PR 1 — admin, D-13):** From RESEARCH.md Risk 3 verified table:

| Api.ts line | Current literal | Target literal (PR 1) |
|-------------|-----------------|-----------------------|
| 1388 | `'/admin/migrations/run'` | `'/admin/db-ops/migrations/run'` |
| 1390 | `'/admin/migrations/current'` | `'/admin/db-ops/migrations/current'` |
| 1392 | `'/admin/init/car-generations'` | `'/admin/db-ops/init/car-generations'` |
| 1394 | `'/admin/init/part-categories'` | `'/admin/db-ops/init/part-categories'` |
| 1403 | `'/admin/service-accounts/crawler'` | `'/admin/crawlers/service-account'` |
| 1410 | `'/admin/crawled-pages/rescrape-archives'` | `'/admin/crawlers/rescrape-archives'` |
| 1426 | `'/admin/parts/delete-all'` | `'/admin/db-ops/parts/delete-all'` |
| 1434 | `'/admin/cars/delete-all'` | `'/admin/db-ops/cars/delete-all'` |
| 1439 | `'/admin/part-manufacturers/delete-all'` | `'/admin/db-ops/part-manufacturers/delete-all'` |
| 1444, 1448 | `/admin/stats/*` | unchanged |
| 1401, 1405 | `/admin/crawlers`, `/admin/crawlers/run` | unchanged |
| `/admin/jobs/*` | (unchanged) | unchanged |

**Delta map (PR 4 — auth, D-13):**

| Api.ts line | Current literal | Target literal (PR 4) |
|-------------|-----------------|-----------------------|
| 862 | `'/auth/google'` | `'/auth/oauth/google'` |
| 870 | `'/auth/google/link'` | `'/auth/oauth/google/link'` |
| 881 | `'/auth/google/signup'` | `'/auth/oauth/google/signup'` |
| 897 | `'/auth/google/connect'` | `'/auth/oauth/google/connect'` |
| 892 | `'/auth/oauth/2fa'` | unchanged (already correct) |
| 898 | `'/auth/oauth'` | unchanged |
| 900 | `` `/auth/oauth/${id}` `` | unchanged |

**Validation:** `cd frontend && npm run type-check && npm test` after the delta. Grep guard pre-commit: `grep -rn "'/admin/migrations\|'/admin/init\|'/admin/service-accounts\|'/admin/crawled-pages/rescrape-archives\|'/admin/cars/delete-all\|'/admin/parts/delete-all\|'/admin/part-manufacturers/delete-all" frontend/src/` must return empty after PR 1. Analogous grep for `/auth/google(?!/oauth)` after PR 4.

---

### 22. `terraform/scheduler.tf` (MAYBE-MODIFIED — see Finding 5 reality check)

**Analog (same-file):** `terraform/scheduler.tf:48-58`:
```hcl
resource "aws_cloudwatch_event_api_destination" "crawler_run" {
  name                             = "${local.prefix}-crawler-run"
  description                      = "POST /api/admin/crawlers/run"
  connection_arn                   = aws_cloudwatch_event_connection.cron.arn
  invocation_endpoint              = "https://${aws_apprunner_service.backend.service_url}/api/admin/crawlers/run"
  http_method                      = "POST"
  invocation_rate_limit_per_second = 1
}
```

**Delta — RESEARCH.md Finding 5 correction of CONTEXT.md D-11:**
- `/api/admin/crawlers/run` — unchanged path → **NO Terraform change needed**.
- `/api/admin/crawled-pages/rescrape-archives` → `/api/admin/crawlers/rescrape-archives` — admin-UI-only endpoint, **NOT in Terraform** (scheduler.tf:18 comment: "Archive rescrapes are never triggered automatically — admins run them manually from the admin UI").

**Planner action:** The admin-split PR SUMMARY.md should call out that Terraform is NOT modified. Do NOT plan a Terraform task. If per-adapter schedules at `backend/app/api/services/adapter_schedule_service.py` turn out to embed paths (unverified), re-evaluate.

---

### 23. `chrome-extension/API_CONTRACT.md` (NEW, generated)

**Analog:** None (first of its kind in this repo). Structure decided by the generator script (D-35).

**No hand-authored content.** The file is the output of `backend/scripts/generate_ext_api_contract.py` committed to git; CI's drift-guard test asserts equality between the generator output and the committed file.

**Convention:** File starts with a generator-authored header noting "Generated from `app.openapi()`. Do not edit by hand." (see script template above).

---

## Shared Patterns (apply to ALL new files in auth/ and admin/ packages)

### Pattern A: Module-level logger (Phase 3 D-33—D-37)

**Source:** `backend/app/api/endpoints/crawler_schedules.py:14, 39`
**Apply to:** Every new `.py` file in `backend/app/api/endpoints/admin/` and `backend/app/api/endpoints/auth/`.

```python
import logging
...
logger = logging.getLogger(__name__)
```

**Regression guard:** `backend/tests/test_logger_migration_regression.py` fails CI on any `Depends(get_logger)` reintroduction in `backend/app/`.

---

### Pattern B: SQLAlchemy 2.0 `db.scalars(select(...))` (Phase 4 D-06—D-11)

**Source:** `backend/app/api/dependencies/auth.py:103` + `backend/app/api/endpoints/admin.py:115, 203, 206, 871, 1763-1767`
**Apply to:** Every DB read in the new sub-router files. No `db.query(...)` or `session.query(...)` calls.

Simple example (`dependencies/auth.py:103`):
```python
user = db.scalars(select(DBUser).where(DBUser.username == token_data.username)).first()
```

Aggregate example (`admin.py:203`):
```python
vote_rows = db.execute(select(DBVote.entity_type, func.count(DBVote.id)).group_by(DBVote.entity_type)).all()
```

**Regression guard:** `backend/tests/test_session_query_regression.py` fails CI on any `.query(` reintroduction in `backend/app/`.

---

### Pattern C: Per-route auth dependency (AUTH-03, ADMIN-02)

**Source:** `backend/app/api/endpoints/admin.py:190` (admin route) + `backend/app/api/endpoints/auth.py:358, 408, 449, 528` (auth-gated route).

Admin route:
```python
async def <route_handler>(
    current_user: DBUser = Depends(get_current_admin_user),   # REQUIRED on every admin route
    db: Session = Depends(get_db),
) -> ...:
    ...
```

Auth-gated (user) route:
```python
async def <route_handler>(
    request: <RequestSchema>,
    current_user: DBUser = Depends(get_current_user),         # REQUIRED on every protected auth route
    db: Session = Depends(get_db),
) -> ...:
    ...
```

**Regression guard:** `backend/tests/test_admin_auth_coverage.py` + `backend/tests/test_auth_auth_coverage.py` (created in this phase) parametrize over `app.routes` and assert every admin/auth-protected route returns 401/403 without proper auth.

---

### Pattern D: `standard_responses` decorator helper

**Source:** `backend/app/api/utils/endpoint_decorators.py` imported + used at `backend/app/api/endpoints/admin.py:184, 231, 254`.

```python
from app.api.utils.endpoint_decorators import standard_responses

@router.get(
    "/path",
    response_model=SomeSchema,
    responses=standard_responses(
        success_description="Human description",
        forbidden=True,              # Admin routes
        not_found=True,              # Routes with path params
    ),
)
```

Apply to every new admin + auth route (preserves Phase 1 OpenAPI snapshot shape).

---

### Pattern E: `ResponsePatterns.raise_*` for error responses (auth sub-routers)

**Source:** `backend/app/api/utils/response_patterns.py` imported + used at `auth.py:104, 107, 144, 194`.

```python
from app.api.utils.response_patterns import ResponsePatterns

ResponsePatterns.raise_unauthorized("Message", headers={"WWW-Authenticate": "Bearer"})
ResponsePatterns.raise_bad_request("Message")
ResponsePatterns.raise_not_found("User")
ResponsePatterns.raise_conflict("Message", "ERROR_CODE")
ResponsePatterns.raise_internal_server_error("Message")
```

Apply in all new auth sub-router files (matches current auth.py conventions).

---

### Pattern F: Relative paths in route decorators (D-15)

**Source convention:** Every new route decorator uses a path relative to the sub-module's prefix. The full prefix is applied by `main.py`'s `register_endpoint(..., prefix=...)` call.

Correct:
```python
# In admin/db_ops.py — registered at prefix "/admin/db-ops"
@router.post("/migrations/run")           # final URL: /api/admin/db-ops/migrations/run
```

Wrong:
```python
@router.post("/admin/db-ops/migrations/run")    # DO NOT — double prefix
```

---

### Pattern G: Imports from dependencies/auth (PyJWT-swapped)

**Source (after PR 2):** `backend/app/api/dependencies/auth.py:7, 17` (post-swap state).

Every auth sub-router file uses these imports:
```python
import jwt                          # PyJWT 2.12.1
from jwt import InvalidTokenError   # replaces `from jose import JWTError`

from app.api.dependencies.auth import (
    ALGORITHM,                       # = settings.JWT_ALGORITHM (HS256) per D-07
    create_access_token,
    get_access_token_expires_delta_for_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
```

Every `jwt.decode(...)` call must pass `algorithms=[ALGORITHM]`:
```python
payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
```

Every `except JWTError` becomes `except InvalidTokenError`.

**Regression guard:** `backend/tests/test_jwt_algorithm_regression.py` (created PR 2) fails CI on any bare `jwt.decode(` without `algorithms=[` within 3 lines.

---

### Pattern H: Script shape — pathlib + repo-root resolution

**Source:** `backend/scripts/check_migrations.py:1-35` (for `generate_ext_api_contract.py`).

```python
#!/usr/bin/env python3
"""<Purpose>."""

from __future__ import annotations

import ...
from pathlib import Path

# <repo>/backend/scripts/<this_script>.py -> parents[2] = <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "chrome-extension" / "API_CONTRACT.md"
...

if __name__ == "__main__":
    ...
```

---

### Pattern I: Regression-grep test shape (JWT + future library migrations)

**Source:** `backend/tests/test_session_query_regression.py:1-60` (EXACT shape for `test_jwt_algorithm_regression.py`).

Structure:
1. Module docstring explaining what the guard protects against + scope (`backend/app/` only).
2. `APP_DIR = Path(__file__).resolve().parent.parent / "app"` line.
3. Compiled regex pattern(s).
4. One test function: iterate `APP_DIR.rglob("*.py")`, match each line, collect offenders, assert empty.
5. Assertion message includes actionable remediation + offender list.

---

### Pattern J: Drift-guard test shape (contract doc + OpenAPI snapshot)

**Source:** `backend/tests/test_openapi_snapshot.py:1-59` (EXACT shape for `test_ext_api_contract_up_to_date.py`).

Structure:
1. Module docstring with regeneration command.
2. Function-scope `from app.main import app` (ordering constraint — env vars must be set first).
3. Generate expected content.
4. Read committed file.
5. Assert equality; on failure, print regeneration command in the assertion message.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `chrome-extension/API_CONTRACT.md` | doc (generated) | output-only | First of its kind in the repo; no prior autogenerated Markdown contract exists. Structure defined by the generator script (D-35). |

---

## Metadata

**Analog search scope:**
- `backend/app/api/endpoints/` (all sub-routers)
- `backend/app/api/dependencies/auth.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/scripts/*.py`
- `backend/tests/test_*.py`, `backend/tests/conftest.py`
- `backend/tests/fixtures/openapi_snapshot.json`
- `backend/requirements.txt`
- `frontend/src/services/Api.ts`
- `terraform/scheduler.tf`

**Files scanned:** 30+ read directly (admin.py, auth.py, main.py, dependencies/auth.py, config.py, conftest.py, crawler_schedules.py, test_openapi_snapshot.py, test_session_query_regression.py, test_logger_migration_regression.py, scripts/check_migrations.py, auth/test_characterization_login.py, Api.ts, requirements.txt, scheduler.tf excerpt from RESEARCH.md, plus adjacent listings).

**Pattern extraction date:** 2026-04-22

---

## Planner handoff notes

1. **Every new admin/auth sub-router file** uses Patterns A (logger), B (db.scalars), C (per-route auth Depends), D (standard_responses), F (relative paths), G (post-PyJWT imports) as a unit. Plans for each new file should cite this PATTERNS.md for the imports + router declaration block rather than re-specifying.
2. **PyJWT swap (PR 2)** happens BEFORE auth split (PR 4). The auth sub-router files are written with `import jwt` + `from jwt import InvalidTokenError` from day one — they never touch jose.
3. **Admin-dual-auth routes** (`/run`, `/rescrape-archives`) use the `Optional[DBUser] + X-Admin-Cron-Key` pattern verbatim from `admin.py:831-851`. The 401/403 coverage test accepts `(401, 403)` for these two routes.
4. **Terraform scope is empty** for Phase 5 (RESEARCH.md Finding 5 corrects CONTEXT.md D-11). Document in admin-split PR SUMMARY.md; do not plan a Terraform task.
5. **ADMIN-04 is preventive language** (RESEARCH.md Finding 6). No dedicated plan — document in admin-split PR SUMMARY.md that the split naturally scopes service imports to each sub-module.
6. **Open question for the planner at D-18/D-20:** Where do `OAUTH_2FA_PURPOSE` / `GOOGLE_PROVIDER` live post-split? Three options listed in section 9 above; planner decides.
7. **Test file fixture reuse:** `create_and_login_user`, `login_user`, `create_and_login_admin_user` are module-level helpers (not pytest fixtures) at `conftest.py:356, 368, 688`. Import directly from `tests.conftest` — no `@pytest.fixture` decorator needed.
