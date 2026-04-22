---
phase: 05-structural-router-splits
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/api/endpoints/admin/__init__.py
  - backend/app/api/endpoints/admin/_helpers.py
  - backend/app/api/endpoints/admin/stats.py
  - backend/app/api/endpoints/admin/jobs.py
  - backend/app/api/endpoints/admin/crawlers.py
  - backend/app/api/endpoints/admin/db_ops.py
  - backend/app/api/endpoints/admin/parts.py
  - backend/app/api/endpoints/admin.py
  - backend/app/main.py
  - backend/app/api/utils/admin_endpoint_patterns.py
  - backend/tests/test_admin_auth_coverage.py
  - backend/tests/fixtures/openapi_snapshot.json
  - frontend/src/services/Api.ts
autonomous: true
requirements:
  - ADMIN-01
  - ADMIN-02
  - ADMIN-03
  - ADMIN-04
user_setup: []

must_haves:
  truths:
    - "POST /api/admin/stats/table-counts returns 401 without auth and 403 with a regular user token"
    - "GET /api/admin/db-ops/migrations/current returns 401 without auth (path moved from /admin/migrations/current per D-09)"
    - "POST /api/admin/crawlers/run accepts either an admin JWT OR an X-Admin-Cron-Key header (path preserved for EventBridge per D-12, Finding 5)"
    - "POST /api/admin/crawlers/rescrape-archives is reachable at new path (moved from /admin/crawled-pages/rescrape-archives per D-09)"
    - "backend/app/api/endpoints/admin.py no longer exists; all 23 routes served from admin/ sub-package"
    - "Frontend admin UI calls (Api.ts) point at the new admin URL tree with zero 404s in type-check"
    - "OpenAPI snapshot regenerated and committed; diff matches the 7 admin URL moves per D-09"
  artifacts:
    - path: "backend/app/api/endpoints/admin/__init__.py"
      provides: "Admin package init (empty or single-line docstring per D-08)"
    - path: "backend/app/api/endpoints/admin/_helpers.py"
      provides: "_stamp_heartbeat, _heartbeat_loop, _get_superadmin_emails, _notify_job_completion (D-21)"
      contains: "logger = logging.getLogger"
    - path: "backend/app/api/endpoints/admin/stats.py"
      provides: "2 routes: /table-counts (GET), /crawl-bucket (GET)"
    - path: "backend/app/api/endpoints/admin/jobs.py"
      provides: "4 routes: / (GET), /{job_id} (GET), /{job_id}/crawler-progress (GET), /{job_id}/cancel (POST)"
    - path: "backend/app/api/endpoints/admin/crawlers.py"
      provides: "4 routes + _verify_cron_key + 4 ECS launcher helpers inline (D-22, D-24)"
    - path: "backend/app/api/endpoints/admin/db_ops.py"
      provides: "7 routes: migrations/run, migrations/current, init/car-generations, init/part-categories, cars/delete-all, parts/delete-all, part-manufacturers/delete-all"
    - path: "backend/app/api/endpoints/admin/parts.py"
      provides: "6 routes: lookup-by-url, {part_id}/link-group, promote-canonical, unlink, link, rescan"
    - path: "backend/tests/test_admin_auth_coverage.py"
      provides: "Parametrized 401/403 coverage over every /api/admin route (D-27—D-30)"
  key_links:
    - from: "backend/app/main.py"
      to: "backend/app/api/endpoints/admin/{stats,jobs,crawlers,db_ops,parts}"
      via: "endpoint_registry.register_endpoint(sub.router, prefix='/admin/<name>', tags=['admin'])"
      pattern: "register_endpoint\\(admin_(stats|jobs|crawlers|db_ops|parts)\\.router"
    - from: "backend/tests/test_admin_auth_coverage.py"
      to: "app.routes (filtered by /api/admin prefix)"
      via: "fastapi.routing.APIRoute enumeration + @pytest.mark.parametrize"
      pattern: "APIRoute.*/api/admin"
---

<objective>
Decompose backend/app/api/endpoints/admin.py (2,068 lines, 23 routes) into a 7-file admin/ sub-package per D-09, delete the old file, update main.py to register 5 sub-routers, migrate frontend admin URL paths, create the parametrized 401/403 coverage test, and regenerate the OpenAPI snapshot.

Purpose: Pay down the oversized admin.py structural-debt item (CONCERNS.md) in the lower-stakes refactor (Chrome extension does not call /admin/*, per D-14 and Finding 3) as the dry run for the split pattern before the auth split.

Output: 5 admin sub-router files + _helpers.py + __init__.py + parametrized 401/403 test + updated main.py registrations + migrated frontend paths + regenerated OpenAPI snapshot. ADMIN-01/02/03/04 closed.
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

# Source file being decomposed (MUST READ during extraction)
@backend/app/api/endpoints/admin.py

# Reference for the split shape (already a clean sub-router)
@backend/app/api/endpoints/crawler_schedules.py

# Dependencies consumed by the new sub-package
@backend/app/api/dependencies/auth.py
@backend/app/api/utils/endpoint_decorators.py
@backend/app/api/utils/response_patterns.py

# Main registration point
@backend/app/main.py

# Fixtures reused by the coverage test
@backend/tests/conftest.py

<interfaces>
<!-- Extracted contracts the executor needs. No codebase re-exploration required. -->

From backend/app/api/dependencies/auth.py (post-PR-2 state — PyJWT already swapped if admin split lands in Wave 1):
```python
# At Wave 1 time (before PyJWT swap) these still use jose; admin split does NOT touch the import.
# Exports used by admin sub-modules:
def get_current_admin_user(...) -> DBUser: ...
def get_current_superuser(...) -> DBUser: ...
def get_optional_current_admin_user(...) -> Optional[DBUser]: ...   # used by dual-auth /run and /rescrape-archives
```

From backend/app/api/utils/endpoint_registry.py:
```python
class EndpointRegistry:
    def register_endpoint(self, router: APIRouter, *, prefix: str, tags: list[str], description: str) -> None: ...
```

From backend/app/api/utils/endpoint_decorators.py:
```python
def standard_responses(*, success_description: str, forbidden: bool = False, not_found: bool = False, ...) -> dict: ...
```

From backend/app/api/utils/response_patterns.py:
```python
class ResponsePatterns:
    @staticmethod
    def raise_unauthorized(message: str, headers: Optional[dict] = None) -> None: ...
    @staticmethod
    def raise_bad_request(message: str) -> None: ...
    @staticmethod
    def raise_not_found(resource: str) -> None: ...
    @staticmethod
    def raise_forbidden(message: str) -> None: ...
```

From backend/tests/conftest.py (module-level helpers — import directly, NOT pytest fixtures):
```python
def login_user(client: TestClient, username: str, password: str = "testpassword") -> str: ...  # conftest.py:356
#   → username is REQUIRED positional, password default is "testpassword" (NOT "Testpassword123!").
def create_and_login_user(client: TestClient, username: str, password_override: str = "testpassword") -> Dict[str, Any]: ...  # conftest.py:368
#   → username is REQUIRED positional; use password_override kwarg to override the default "testpassword".
def create_and_login_admin_user(client: TestClient, username: str) -> User: ...  # conftest.py:688
#   → username is REQUIRED positional; no password override parameter; helper calls login_user internally.
```

From backend/app/api/endpoints/admin.py — admin routes inventory (per RESEARCH.md Finding 2, VERIFIED via grep):
| Line | Method | Current path                                  | Target prefix/path                    | Sub-module     |
|------|--------|-----------------------------------------------|---------------------------------------|----------------|
| 181  | GET    | /stats/table-counts                           | /admin/stats GET /table-counts        | stats          |
| 228  | GET    | /stats/crawl-bucket                           | /admin/stats GET /crawl-bucket        | stats          |
| 251  | POST   | /migrations/run                               | /admin/db-ops POST /migrations/run    | db_ops         |
| 351  | GET    | /migrations/current                           | /admin/db-ops GET /migrations/current | db_ops         |
| 416  | POST   | /init/car-generations                         | /admin/db-ops POST /init/car-generations | db_ops      |
| 450  | POST   | /init/part-categories                         | /admin/db-ops POST /init/part-categories | db_ops      |
| 491  | POST   | /cars/delete-all                              | /admin/db-ops POST /cars/delete-all   | db_ops         |
| 641  | GET    | /crawlers                                     | /admin/crawlers GET /                 | crawlers       |
| 823  | POST   | /crawlers/run                                 | /admin/crawlers POST /run             | crawlers       |
| 1205 | POST   | /crawled-pages/rescrape-archives              | /admin/crawlers POST /rescrape-archives | crawlers     |
| 1341 | GET    | /service-accounts/crawler                     | /admin/crawlers GET /service-account  | crawlers       |
| 1379 | GET    | /jobs                                         | /admin/jobs GET /                     | jobs           |
| 1432 | GET    | /jobs/{job_id}                                | /admin/jobs GET /{job_id}             | jobs           |
| 1465 | GET    | /jobs/{job_id}/crawler-progress               | /admin/jobs GET /{job_id}/crawler-progress | jobs      |
| 1533 | POST   | /jobs/{job_id}/cancel                         | /admin/jobs POST /{job_id}/cancel     | jobs           |
| 1598 | POST   | /parts/delete-all                             | /admin/db-ops POST /parts/delete-all  | db_ops         |
| 1745 | GET    | /parts/lookup-by-url                          | /admin/parts GET /lookup-by-url       | parts          |
| 1788 | GET    | /parts/{part_id}/link-group                   | /admin/parts GET /{part_id}/link-group| parts          |
| 1825 | POST   | /parts/promote-canonical                      | /admin/parts POST /promote-canonical  | parts          |
| 1847 | POST   | /parts/unlink                                 | /admin/parts POST /unlink             | parts          |
| 1869 | POST   | /parts/link                                   | /admin/parts POST /link               | parts          |
| 1914 | POST   | /parts/rescan                                 | /admin/parts POST /rescan             | parts          |
| 2029 | POST   | /part-manufacturers/delete-all                | /admin/db-ops POST /part-manufacturers/delete-all | db_ops |

Dual-auth routes (use Optional[DBUser] admin + X-Admin-Cron-Key per admin.py:823-851):
  - POST /api/admin/crawlers/run
  - POST /api/admin/crawlers/rescrape-archives

Helpers from admin.py that move to admin/_helpers.py (D-21, lines 88-136):
  _stamp_heartbeat, _heartbeat_loop, _get_superadmin_emails, _notify_job_completion

Helpers that stay in admin/db_ops.py (D-23, lines 150-179 + 411-414):
  _get_alembic_directory, _init_result

Helpers that stay in admin/crawlers.py (D-22, D-24, lines 139-147 + 665-1204):
  _verify_cron_key
  _launch_ecs_crawler_task, _run_crawlers_in_process,
  _launch_ecs_rescrape_task, _run_rescrape_in_process

Helpers that stay in admin/parts.py (D-25, lines 1719-1743):
  _first_listing_for, _link_group_member
```

From backend/app/main.py — current registrations that get replaced (VERIFIED: line 279-285):
```python
# Current (admin — ONE registration):
endpoint_registry.register_endpoint(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    description="Admin-only system management operations",
)
# Replace with 5 sub-router registrations per Pattern 2 in PATTERNS.md Section 19.
```

From frontend/src/services/Api.ts — URL literals that MUST update (VERIFIED per RESEARCH.md Risk 3):
```
Line 1388: '/admin/migrations/run'               → '/admin/db-ops/migrations/run'
Line 1390: '/admin/migrations/current'           → '/admin/db-ops/migrations/current'
Line 1392: '/admin/init/car-generations'         → '/admin/db-ops/init/car-generations'
Line 1394: '/admin/init/part-categories'         → '/admin/db-ops/init/part-categories'
Line 1403: '/admin/service-accounts/crawler'     → '/admin/crawlers/service-account'
Line 1410: '/admin/crawled-pages/rescrape-archives' → '/admin/crawlers/rescrape-archives'
Line 1426: '/admin/parts/delete-all'             → '/admin/db-ops/parts/delete-all'
Line 1434: '/admin/cars/delete-all'              → '/admin/db-ops/cars/delete-all'
Line 1439: '/admin/part-manufacturers/delete-all'→ '/admin/db-ops/part-manufacturers/delete-all'
Lines 1444/1448 (/admin/stats/*) — unchanged
Lines 1401/1405 (/admin/crawlers, /admin/crawlers/run) — unchanged
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create admin/ sub-package skeleton + extract helper modules + coverage test scaffold</name>
  <files>
    backend/app/api/endpoints/admin/__init__.py,
    backend/app/api/endpoints/admin/_helpers.py,
    backend/app/api/endpoints/admin/stats.py,
    backend/app/api/endpoints/admin/jobs.py,
    backend/app/api/endpoints/admin/crawlers.py,
    backend/app/api/endpoints/admin/db_ops.py,
    backend/app/api/endpoints/admin/parts.py,
    backend/tests/test_admin_auth_coverage.py
  </files>
  <read_first>
    - backend/app/api/endpoints/admin.py (the file being decomposed — ALL 2,068 lines)
    - backend/app/api/endpoints/crawler_schedules.py (reference sub-router — imports + router declaration pattern)
    - backend/tests/conftest.py (fixtures + module-level helpers: create_and_login_user at line 368, login_user at 356, create_and_login_admin_user at 688)
    - backend/tests/test_session_query_regression.py (shape reference for parametrized test drift guard)
    - .planning/phases/05-structural-router-splits/05-PATTERNS.md (Sections 1-5, 12 — imports, route decorators, helper extraction, 401/403 test template)
  </read_first>
  <behavior>
    - Creating empty sub-router files with correct imports, logger, router, and zero routes — pytest imports them without error.
    - admin/_helpers.py has exactly these functions (verbatim from admin.py:88-136): _stamp_heartbeat, _heartbeat_loop, _get_superadmin_emails, _notify_job_completion.
    - admin/_helpers.py imports ONLY from stdlib + third-party + app.api.services.* + app.api.models.* + app.core.* + app.db.session (leaf module per Risk 4).
    - test_admin_auth_coverage.py exists with parametrized signatures but ADMIN_ROUTES enumeration evaluates to [] pre-Task-2 (no routes registered yet) — the "count >= 23" drift guard is EXPECTED TO FAIL in this task's run, which proves the guard works. After Task 2 it passes.
  </behavior>
  <action>
Create seven new files and one new test file, verbatim to the templates below. NO route content in the sub-router files yet (that's Task 2). NO main.py changes yet (that's Task 3). The test file is scaffolded here with xfail-style count guard so we can run pytest on it after Task 2 without re-editing.

**1. Create `backend/app/api/endpoints/admin/__init__.py`** (one-line docstring per D-08):
```python
"""Admin endpoint sub-package — sub-routers registered individually in main.py (D-08)."""
```

**2. Create `backend/app/api/endpoints/admin/_helpers.py`** — Move verbatim from admin.py:88-136 per D-21. Imports only from stdlib + third-party + app.api.services/models + app.core + app.db.session (leaf module per Risk 4). Start from:
```python
"""Background-job lifecycle helpers shared across admin sub-routers (D-21).

Mirrors auth/_helpers.py for package consistency. Used by crawlers.py (crawler-run
job) and potentially db_ops.py (migrations/run). Leaf module — no sibling
sub-module imports (Risk 4 mitigation).
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
```
Then copy-verbatim the 4 helper function bodies from admin.py:88-136 (_stamp_heartbeat, _heartbeat_loop, _get_superadmin_emails, _notify_job_completion). If the source uses imports not listed above (e.g., datetime), add them to this module.

**3-7. Create five sub-router files**, each initially with ONLY imports + logger + router declaration (NO routes yet — Task 2 adds them). Template for each (adapt imports per sub-module needs):
```python
"""<Sub-module purpose — one-line>."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user, get_current_superuser
from app.api.utils.endpoint_decorators import standard_responses
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()
```

Sub-module docstrings (first line):
- `stats.py`: "Admin statistics endpoints (table counts, crawl bucket listing)."
- `jobs.py`: "Admin background job list/detail/cancel endpoints."
- `crawlers.py`: "Admin crawler run, rescrape-archives, service-account endpoints (EventBridge-invokable per D-22)."
- `db_ops.py`: "Admin database operations: migrations, data init, bulk delete."
- `parts.py`: "Admin canonical-parts management: lookup, link-group, promote, unlink, link, rescan."

**8. Create `backend/tests/test_admin_auth_coverage.py`** — Verbatim template (adapted from 05-PATTERNS.md §12 + Finding 4 recommendation):
```python
"""ADMIN-02 regression: every route under /api/admin requires admin auth.

D-27—D-30: parametrized over (method, path) extracted from app.routes at
collection time. Per-route assertions:
  (a) no auth header -> 401 (or 401|403 for dual-auth cron-key routes)
  (b) regular-user token -> 403

D-30 drift guard: count-at-or-above check catches a disabled parametrized
test or a route removal without test update. Combined with SAFE-05 OpenAPI
snapshot, the drift surface is fully covered.
"""

from __future__ import annotations

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import create_and_login_user, login_user

# D-28 + Risk 7: routes using Optional[DBUser] admin dep + X-Admin-Cron-Key.
# These may return 403 (not 401) when no auth header + no cron key present
# because the dependency doesn't raise; the body check does.
# See admin.py:823-851 pattern.
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
    username = f"cov_user_{method.lower()}_{abs(hash(path)) & 0xFFFF:04x}"
    create_and_login_user(client, username=username)
    token = login_user(client, username)
    resp = client.request(
        method, _fill_path_params(path), headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403, (
        f"{method} {path} with regular user -> {resp.status_code} (expected 403)"
    )


def test_admin_route_count_at_or_above_expected() -> None:
    # D-30 drift guard
    assert len(ADMIN_ROUTES) >= 23, (
        f"Expected >=23 admin routes (post-split), got {len(ADMIN_ROUTES)}"
    )
```
  </action>
  <verify>
    <automated>cd backend && python -c "from app.api.endpoints.admin import stats, jobs, crawlers, db_ops, parts, _helpers; print('import ok'); print('stats routes', len(stats.router.routes)); print('helpers funcs', sorted(n for n in dir(_helpers) if n.startswith('_') and not n.startswith('__')))"</automated>
    <automated>test -f backend/app/api/endpoints/admin/__init__.py && test -f backend/app/api/endpoints/admin/_helpers.py && test -f backend/app/api/endpoints/admin/stats.py && test -f backend/app/api/endpoints/admin/jobs.py && test -f backend/app/api/endpoints/admin/crawlers.py && test -f backend/app/api/endpoints/admin/db_ops.py && test -f backend/app/api/endpoints/admin/parts.py && test -f backend/tests/test_admin_auth_coverage.py</automated>
    <automated>cd backend && grep -c "^logger = logging.getLogger(__name__)" app/api/endpoints/admin/_helpers.py app/api/endpoints/admin/stats.py app/api/endpoints/admin/jobs.py app/api/endpoints/admin/crawlers.py app/api/endpoints/admin/db_ops.py app/api/endpoints/admin/parts.py | awk -F: '$2!=1 {exit 1}'</automated>
    <automated>cd backend && grep -q "def _stamp_heartbeat" app/api/endpoints/admin/_helpers.py && grep -q "def _heartbeat_loop" app/api/endpoints/admin/_helpers.py && grep -q "def _get_superadmin_emails" app/api/endpoints/admin/_helpers.py && grep -q "def _notify_job_completion" app/api/endpoints/admin/_helpers.py</automated>
  </verify>
  <acceptance_criteria>
    - Command `test -f backend/app/api/endpoints/admin/__init__.py` exits 0
    - Command `test -f backend/app/api/endpoints/admin/_helpers.py` exits 0
    - Command `test -f backend/app/api/endpoints/admin/stats.py` exits 0
    - Command `test -f backend/app/api/endpoints/admin/jobs.py` exits 0
    - Command `test -f backend/app/api/endpoints/admin/crawlers.py` exits 0
    - Command `test -f backend/app/api/endpoints/admin/db_ops.py` exits 0
    - Command `test -f backend/app/api/endpoints/admin/parts.py` exits 0
    - Command `test -f backend/tests/test_admin_auth_coverage.py` exits 0
    - `cd backend && python -c "from app.api.endpoints.admin import stats, jobs, crawlers, db_ops, parts, _helpers"` exits 0
    - `grep -c "^logger = logging.getLogger(__name__)" backend/app/api/endpoints/admin/*.py` reports `1` for EACH of: _helpers.py, stats.py, jobs.py, crawlers.py, db_ops.py, parts.py
    - `grep -q "def _stamp_heartbeat" backend/app/api/endpoints/admin/_helpers.py` exits 0
    - `grep -q "def _heartbeat_loop" backend/app/api/endpoints/admin/_helpers.py` exits 0
    - `grep -q "def _get_superadmin_emails" backend/app/api/endpoints/admin/_helpers.py` exits 0
    - `grep -q "def _notify_job_completion" backend/app/api/endpoints/admin/_helpers.py` exits 0
    - `grep -rn "from app.api.endpoints.admin" backend/app/api/endpoints/admin/_helpers.py` returns exit code 1 (no sibling-module imports in the helper — Risk 4)
  </acceptance_criteria>
  <done>Sub-package directory + 7 files created, _helpers.py contains the 4 job-lifecycle helpers verbatim, sub-router files import cleanly with empty routers, coverage test scaffolded and will fail count guard until Task 2 wires main.py.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extract 23 admin routes into sub-router files + wire main.py + delete admin.py + regenerate OpenAPI snapshot</name>
  <files>
    backend/app/api/endpoints/admin/stats.py,
    backend/app/api/endpoints/admin/jobs.py,
    backend/app/api/endpoints/admin/crawlers.py,
    backend/app/api/endpoints/admin/db_ops.py,
    backend/app/api/endpoints/admin/parts.py,
    backend/app/api/endpoints/admin.py,
    backend/app/main.py,
    backend/app/api/utils/admin_endpoint_patterns.py,
    backend/tests/fixtures/openapi_snapshot.json
  </files>
  <read_first>
    - backend/app/api/endpoints/admin.py (source-of-truth — extract all 23 routes from this)
    - backend/app/main.py (lines 1-40 for imports, 279-285 for admin registration block)
    - backend/app/api/utils/admin_endpoint_patterns.py (check for `from app.api.endpoints.admin import` — audit per D-17)
    - .planning/phases/05-structural-router-splits/05-PATTERNS.md (Sections 1, 2, 4, 5, 19 — route move templates + main.py registration pattern)
    - .planning/phases/05-structural-router-splits/05-RESEARCH.md (Finding 2 table for route→sub-module map)
    - backend/tests/test_openapi_snapshot.py (shows regeneration invocation — `TESTING=true ENABLE_RATE_LIMITING=false`)
  </read_first>
  <behavior>
    - After extraction, `pytest -n auto backend/tests/test_admin_auth_coverage.py` passes all 3 test functions (23 parametrize cases × 2 tests + 1 count guard = 47 cases total).
    - `pytest -n auto backend/tests/test_openapi_snapshot.py` passes AFTER the snapshot is regenerated.
    - `pytest -n auto backend/tests/test_session_query_regression.py` passes (no `db.query(` introduced in the new files — Phase 4 guard).
    - `pytest -n auto backend/tests/test_logger_migration_regression.py` passes (no `Depends(get_logger)` introduced — Phase 3 guard).
    - `pytest -n auto backend/tests/test_pydantic_v1_regression.py` passes (no Pydantic v1 patterns — Phase 3 guard).
    - `python -c "from app.api.endpoints import admin"` FAILS with ModuleNotFoundError (old file deleted per REQ-ADMIN-01).
    - Every admin route in `app.routes` has path prefix `/api/admin/<sub-module>` matching the target map in Finding 2.
  </behavior>
  <action>
**Step A — Extract the 23 routes into the 5 sub-router files.** Use the target map in the `<interfaces>` block (lines 181-2068 of admin.py) and these literal transformations:

For each route in admin.py:
1. Identify target sub-module + target relative path per the Finding 2 table in `<interfaces>`.
2. Copy the full `@router.*` decorator + handler function body VERBATIM into the target sub-module file.
3. REWRITE the decorator path: strip the sub-module prefix so the decorator's path is RELATIVE to the sub-module's mount prefix (D-15).
   - Example: `@router.get("/stats/table-counts", ...)` (in admin.py) → `@router.get("/table-counts", ...)` (in admin/stats.py at prefix `/admin/stats`).
   - Example: `@router.post("/crawled-pages/rescrape-archives", ...)` (in admin.py) → `@router.post("/rescrape-archives", ...)` (in admin/crawlers.py at prefix `/admin/crawlers`). THIS IS D-09 AGGRESSIVE MOVE.
   - Example: `@router.get("/service-accounts/crawler", ...)` (in admin.py) → `@router.get("/service-account", ...)` (in admin/crawlers.py). THIS IS D-09 AGGRESSIVE MOVE.
   - Example: `@router.post("/migrations/run", ...)` (in admin.py) → `@router.post("/migrations/run", ...)` (in admin/db_ops.py at prefix `/admin/db-ops`). Relative path unchanged, only sub-module prefix is new.
4. PRESERVE per-route `current_user: DBUser = Depends(get_current_admin_user)` (or `Depends(get_current_superuser)` where source uses it) verbatim — ADMIN-02 literal.
5. DO NOT add, remove, or re-order decorator arguments (preserves OpenAPI snapshot shape except for paths).

**Sub-module-specific extras:**

`admin/crawlers.py`: Also copy verbatim from admin.py:
- `_verify_cron_key` (lines 139-147) — D-22.
- `_launch_ecs_crawler_task` (lines 665-756) — D-24 inline.
- `_run_crawlers_in_process` (lines 757-820) — D-24 inline.
- `_launch_ecs_rescrape_task` (lines 1081-1141) — D-24 inline.
- `_run_rescrape_in_process` (lines 1142-1204) — D-24 inline.
- The dual-auth pattern for `/run` and `/rescrape-archives` — preserve the `Optional[DBUser] = Depends(get_current_admin_user)` + `x_admin_cron_key: Optional[str] = Header(default=None)` + `_verify_cron_key(x_admin_cron_key)` body check verbatim (Pattern 2 in PATTERNS.md).

`admin/db_ops.py`: Also copy verbatim:
- `_get_alembic_directory` (lines 150-179) — D-23.
- `_init_result` (lines 411-414) — D-23.

`admin/parts.py`: Also copy verbatim:
- `_first_listing_for` (lines 1719-1735) — D-25.
- `_link_group_member` (lines 1736-1743) — D-25.
- Hoist inline service imports from admin.py lines 1728/1799/1809/1836/1858/1896/1932/1996 to module-level imports at top of admin/parts.py (per PATTERNS.md §5 Finding 6, satisfies ADMIN-04 per D-21 document):
```python
from app.api.services.part_linker_service import (
    _point_siblings_at,
    link_group_part_ids,
    reelect_canonical,
    score_metadata_richness,
    unlink_part,
)
```
Then delete the inline imports inside function bodies.

**Pattern reminder:** every sub-module file uses `logger = logging.getLogger(__name__)` per D-26 (already set in Task 1). Use `db.scalars(select(...))` — NOT `db.query(...)` (Phase 4 grep guard; Pattern B). Keep `standard_responses(...)` helpers on every route (Pattern D).

**Step B — Update `backend/app/main.py`:** Replace the single `admin.router` registration (lines 279-285) with 5 sub-router registrations. Also update imports: replace `from .api.endpoints import admin` with per-sub-module imports.

Exact diff at the imports block (top of main.py — find the existing `from .api.endpoints import` line that includes `admin`):
- DELETE `admin` from the existing tuple import.
- ADD this block:
```python
from .api.endpoints.admin import (
    crawlers as admin_crawlers,
    db_ops as admin_db_ops,
    jobs as admin_jobs,
    parts as admin_parts,
    stats as admin_stats,
)
```

Exact replacement at lines 279-285:
```python
endpoint_registry.register_endpoint(
    admin_stats.router,
    prefix="/admin/stats",
    tags=["admin"],
    description="Admin statistics (table counts, crawl bucket listing)",
)
endpoint_registry.register_endpoint(
    admin_jobs.router,
    prefix="/admin/jobs",
    tags=["admin"],
    description="Admin background jobs (list, detail, crawler-progress, cancel)",
)
endpoint_registry.register_endpoint(
    admin_crawlers.router,
    prefix="/admin/crawlers",
    tags=["admin"],
    description="Admin crawler management (run, rescrape-archives, service-account)",
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
    description="Admin canonical parts management (lookup, link, unlink, rescan)",
)
```

**Step C — Audit + update `backend/app/api/utils/admin_endpoint_patterns.py`:** Run `grep -n "from app.api.endpoints.admin" backend/app/api/utils/admin_endpoint_patterns.py`. If any import references the old admin module, update to the new sub-module path (e.g., `from app.api.endpoints.admin.jobs import <name>`). If no matches, leave the file untouched.

**Step D — Delete `backend/app/api/endpoints/admin.py`** per REQ-ADMIN-01 "old file deleted in same PR". Use `git rm backend/app/api/endpoints/admin.py` OR directly delete the file.

**Step E — Update all test imports to new sub-module paths:**
Run `grep -rn "from app.api.endpoints.admin import" backend/tests/`. For each match, rewrite the import to point at the correct sub-module (based on which function/class is being imported). If only the module itself is imported (e.g., `from app.api.endpoints import admin`), replace with whatever sub-module is actually used downstream OR delete if unused.

**Step F — Regenerate OpenAPI snapshot per D-44 + Phase 1 D-26 convention:**
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

(If the project has an existing regeneration script — e.g., `backend/scripts/regenerate_openapi_snapshot.py` — use that instead; read the test file `backend/tests/test_openapi_snapshot.py` to find the canonical regeneration command. Record the command in the plan SUMMARY.md.)

**Step G — Verify no `db.query(` or `Depends(get_logger)` introduced** in the new files (these are caught by Phase 3/4 regression grep tests — we verify directly too):
```bash
cd backend
grep -rn "db\.query\|session\.query\|self\.db\.query" app/api/endpoints/admin/ && exit 1 || true
grep -rn "Depends(get_logger)" app/api/endpoints/admin/ && exit 1 || true
```
  </action>
  <verify>
    <automated>cd backend && pytest -n auto tests/test_admin_auth_coverage.py -x</automated>
    <automated>cd backend && pytest -n auto tests/test_openapi_snapshot.py -x</automated>
    <automated>cd backend && pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x</automated>
    <automated>test ! -f backend/app/api/endpoints/admin.py</automated>
    <automated>cd backend && python -c "from app.main import app; from fastapi.routing import APIRoute; paths = sorted({r.path for r in app.routes if isinstance(r, APIRoute) and r.path.startswith('/api/admin')}); print('\n'.join(paths)); assert len(paths) >= 23, f'got {len(paths)}'"</automated>
    <automated>cd backend && grep -rn "db\.query\|session\.query" app/api/endpoints/admin/ ; test $? -eq 1</automated>
    <automated>cd backend && grep -rn "from app.api.endpoints.admin import" app/ tests/ | grep -v "from app.api.endpoints.admin\.\(stats\|jobs\|crawlers\|db_ops\|parts\|_helpers\)" ; test $? -eq 1</automated>
    <automated>cd backend && python -c "from app.main import app; from fastapi.routing import APIRoute; r = next(x for x in app.routes if isinstance(x, APIRoute) and x.path == '/api/admin/crawlers/run' and 'POST' in x.methods); assert 'admin.crawlers' in r.endpoint.__module__, f'Expected admin.crawlers module, got {r.endpoint.__module__}'; print('OK')"</automated>
    <automated>cd backend && python -c "from app.main import app; from fastapi.routing import APIRoute
for method, path in [('POST','/api/admin/crawlers/rescrape-archives'), ('GET','/api/admin/crawlers/service-account')]:
    r = next(x for x in app.routes if isinstance(x, APIRoute) and x.path == path and method in x.methods)
    assert 'admin.crawlers' in r.endpoint.__module__, f'{method} {path} -> {r.endpoint.__module__}'
print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test ! -f backend/app/api/endpoints/admin.py` exits 0 (old file deleted per REQ-ADMIN-01)
    - `cd backend && pytest -n auto tests/test_admin_auth_coverage.py -x` exits 0 with at least 47 test cases collected (23 × 2 parametrized + 1 drift-guard)
    - `cd backend && pytest -n auto tests/test_openapi_snapshot.py -x` exits 0
    - `cd backend && pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x` exits 0
    - `cd backend && python -c "from app.main import app; from fastapi.routing import APIRoute; assert len([r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith('/api/admin')]) >= 23"` exits 0
    - `grep -rn "db\.query\|session\.query\|self\.db\.query" backend/app/api/endpoints/admin/` returns exit code 1 (no SQLAlchemy 1.x pattern)
    - `grep -rn "Depends(get_logger)" backend/app/api/endpoints/admin/` returns exit code 1 (Phase 3 guard upheld)
    - `grep -rn "from app.api.endpoints.admin import" backend/app/ backend/tests/ | grep -v "endpoints\.admin\.\(stats\|jobs\|crawlers\|db_ops\|parts\|_helpers\)"` returns exit code 1 (D-17 hard-migration)
    - `cd backend && python -c "from app.main import app; from fastapi.routing import APIRoute; paths = [r.path for r in app.routes if isinstance(r, APIRoute) and r.path.startswith('/api/admin')]; assert '/api/admin/db-ops/migrations/run' in paths and '/api/admin/crawlers/rescrape-archives' in paths and '/api/admin/crawlers/service-account' in paths and '/api/admin/crawlers/run' in paths"` exits 0
    - ADMIN-03 module-location assertion: the POST /api/admin/crawlers/run route is actually served by the admin/crawlers.py module (not left stranded in admin.py or misrouted to another sub-module). Verify via:
      ```bash
      cd backend && python -c "
      from app.main import app
      from fastapi.routing import APIRoute
      r = next(x for x in app.routes if isinstance(x, APIRoute) and x.path == '/api/admin/crawlers/run' and 'POST' in x.methods)
      assert 'admin.crawlers' in r.endpoint.__module__, f'Expected admin.crawlers module, got {r.endpoint.__module__}'
      print('OK')
      "
      ```
      exits 0.
    - Module-location extended for the other 3 dual-auth / EventBridge-adjacent routes (defense-in-depth for ADMIN-03 + Threat T-05-01-02): POST /api/admin/crawlers/rescrape-archives and GET /api/admin/crawlers/service-account also live in the admin.crawlers module. Verify via:
      ```bash
      cd backend && python -c "
      from app.main import app
      from fastapi.routing import APIRoute
      for method, path in [('POST','/api/admin/crawlers/rescrape-archives'), ('GET','/api/admin/crawlers/service-account')]:
          r = next(x for x in app.routes if isinstance(x, APIRoute) and x.path == path and method in x.methods)
          assert 'admin.crawlers' in r.endpoint.__module__, f'{method} {path} → expected admin.crawlers, got {r.endpoint.__module__}'
      print('OK')
      "
      ```
      exits 0.
    - OpenAPI snapshot fixture shows intentional diff (7 admin URL moves per D-09) and reviewer confirms in PR description.
  </acceptance_criteria>
  <done>All 23 admin routes served from the sub-package, admin.py deleted, main.py registers 5 sub-routers, OpenAPI snapshot regenerated, parametrized 401/403 tests pass for every route, all Phase 3/4 regression guards green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Migrate frontend admin URL literals per D-13 and verify with type-check + tests</name>
  <files>
    frontend/src/services/Api.ts
  </files>
  <read_first>
    - frontend/src/services/Api.ts (all admin URL literals; target lines 1388/1390/1392/1394/1403/1410/1426/1434/1439/1444/1448 per Finding 2 / Risk 3)
    - .planning/phases/05-structural-router-splits/05-RESEARCH.md (Risk 3 table — verified delta map)
  </read_first>
  <behavior>
    - Every old admin URL literal (`/admin/migrations/*`, `/admin/init/*`, `/admin/service-accounts/crawler`, `/admin/crawled-pages/rescrape-archives`, `/admin/cars/delete-all`, `/admin/parts/delete-all`, `/admin/part-manufacturers/delete-all`) is replaced with the new path.
    - `/admin/stats/*` and `/admin/crawlers` + `/admin/crawlers/run` + `/admin/jobs/*` are UNCHANGED.
    - `frontend/npm run type-check` exits 0.
    - `frontend/npm test` exits 0.
    - Post-migration grep `grep -rn "'/admin/migrations\|'/admin/init\|'/admin/service-accounts\|'/admin/crawled-pages/rescrape-archives\|'/admin/cars/delete-all\|'/admin/parts/delete-all\|'/admin/part-manufacturers/delete-all" frontend/src/` returns empty (exit 1).
  </behavior>
  <action>
Edit `frontend/src/services/Api.ts`. For each of the 9 admin URL literals listed in the Finding 2 / Risk 3 verified map below, do an exact-string replacement:

| Old literal                                      | New literal                                          |
|--------------------------------------------------|------------------------------------------------------|
| `'/admin/migrations/run'`                        | `'/admin/db-ops/migrations/run'`                     |
| `'/admin/migrations/current'`                    | `'/admin/db-ops/migrations/current'`                 |
| `'/admin/init/car-generations'`                  | `'/admin/db-ops/init/car-generations'`               |
| `'/admin/init/part-categories'`                  | `'/admin/db-ops/init/part-categories'`               |
| `'/admin/service-accounts/crawler'`              | `'/admin/crawlers/service-account'`                  |
| `'/admin/crawled-pages/rescrape-archives'`       | `'/admin/crawlers/rescrape-archives'`                |
| `'/admin/parts/delete-all'`                      | `'/admin/db-ops/parts/delete-all'`                   |
| `'/admin/cars/delete-all'`                       | `'/admin/db-ops/cars/delete-all'`                    |
| `'/admin/part-manufacturers/delete-all'`         | `'/admin/db-ops/part-manufacturers/delete-all'`      |

DO NOT touch `/admin/stats/*`, `/admin/crawlers` (GET listing), `/admin/crawlers/run`, or `/admin/jobs/*` — these paths are preserved per D-09 (and D-12 for crawlers/run EventBridge contract).

After the edit, run:
```bash
cd frontend
npm run type-check
npm test
```

Then the final guard grep (MUST return empty):
```bash
grep -rn "'/admin/migrations\|'/admin/init\|'/admin/service-accounts\|'/admin/crawled-pages/rescrape-archives\|'/admin/cars/delete-all\|'/admin/parts/delete-all\|'/admin/part-manufacturers/delete-all" frontend/src/
```

If the grep returns matches, there are unmigrated usages (possibly outside Api.ts — audit the specific file(s) and migrate). If type-check or tests fail, read the error output and correct the path strings.
  </action>
  <verify>
    <automated>cd frontend && npm run type-check</automated>
    <automated>cd frontend && npm test -- --run 2>&1 | tail -40</automated>
    <automated>grep -rn "'/admin/migrations\|'/admin/init\|'/admin/service-accounts\|'/admin/crawled-pages/rescrape-archives\|'/admin/cars/delete-all\|'/admin/parts/delete-all\|'/admin/part-manufacturers/delete-all" frontend/src/ ; test $? -eq 1</automated>
    <automated>grep -q "'/admin/db-ops/migrations/run'" frontend/src/services/Api.ts</automated>
    <automated>grep -q "'/admin/crawlers/rescrape-archives'" frontend/src/services/Api.ts</automated>
    <automated>grep -q "'/admin/crawlers/service-account'" frontend/src/services/Api.ts</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "'/admin/db-ops/migrations/run'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/admin/db-ops/migrations/current'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/admin/db-ops/init/car-generations'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/admin/db-ops/init/part-categories'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/admin/crawlers/service-account'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/admin/crawlers/rescrape-archives'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/admin/db-ops/parts/delete-all'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/admin/db-ops/cars/delete-all'" frontend/src/services/Api.ts` exits 0
    - `grep -q "'/admin/db-ops/part-manufacturers/delete-all'" frontend/src/services/Api.ts` exits 0
    - `grep -rn "'/admin/migrations\|'/admin/init\|'/admin/service-accounts\|'/admin/crawled-pages/rescrape-archives\|'/admin/cars/delete-all\|'/admin/parts/delete-all\|'/admin/part-manufacturers/delete-all" frontend/src/` returns exit code 1 (no old literals anywhere in src/)
    - `cd frontend && npm run type-check` exits 0
    - `cd frontend && npm test -- --run` exits 0
  </acceptance_criteria>
  <done>Frontend calls the new admin URL tree; type-check and tests green; pre/post grep audit confirms zero stragglers. Chrome extension untouched (D-14 — extension never calls /admin/*).</done>
</task>

</tasks>

<deferred>
## Deferred / documented-only in this plan (per CONTEXT.md Deferred Ideas + RESEARCH.md Findings 5 + 6)

- **Terraform EventBridge update (D-11 original claim):** Per RESEARCH.md Finding 5, Terraform is NOT modified. Only `/api/admin/crawlers/run` is EventBridge-bound and its path is preserved. The `/rescrape-archives` path move is admin-UI-only (never EventBridge-invoked). Document in SUMMARY.md.
- **ADMIN-04 separate task (D-21-derived concern):** Per RESEARCH.md Finding 6, no god-service pattern exists. The split itself satisfies ADMIN-04 — service imports naturally distribute to sub-modules (job_service → jobs.py + crawlers.py; part_linker_service → parts.py). Hoist-inline-imports-to-module-top in parts.py is the only concrete action, done inside Task 2. Document in SUMMARY.md.
- **ECS launcher extraction to services/:** D-24 locks "stays inline in admin/crawlers.py". Deferred to future service-layer extraction phase.
- **Admin UI URL routing polish:** Deferred to Phase 6 opportunistic UX arc.
</deferred>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Unauthenticated HTTP → FastAPI | Any `/api/admin/*` route is a potential target if auth dependency is absent |
| Authenticated regular user → admin surface | Privilege-escalation target if role check is absent |
| External EventBridge → `/api/admin/crawlers/run` + `/api/admin/crawlers/rescrape-archives` | Cron-key-authenticated boundary (dual-auth with Optional[JWT]) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-01-01 | Elevation of Privilege | New admin sub-router files (stats/jobs/crawlers/db_ops/parts) | mitigate | Task 2 extraction preserves per-route `current_user: DBUser = Depends(get_current_admin_user)` verbatim (ADMIN-02). Task 1 + Task 2 create `test_admin_auth_coverage.py` that parametrizes over `app.routes` filtered by `/api/admin` and asserts 401 without auth + 403 with regular user for EVERY route (drift guard per D-30). |
| T-05-01-02 | Spoofing | Dual-auth routes `/api/admin/crawlers/run` and `/api/admin/crawlers/rescrape-archives` (EventBridge) | mitigate | Task 2 extracts `_verify_cron_key` verbatim (D-22). DUAL_AUTH_ROUTES allow-list in coverage test accepts `(401, 403)` for these two routes per Open Question 3 / Risk 7. `X-Admin-Cron-Key` lives in AWS Secrets Manager (unchanged). Constant-time compare via `secrets.compare_digest` preserved. |
| T-05-01-03 | Elevation of Privilege | Frontend calls to moved admin URL paths (D-13) | mitigate | Task 3 grep-audit verifies every old literal is removed; type-check + tests catch mis-typed new literals at CI time. Any stray old literal would 404 at runtime (not escalate) — low severity but monitored via Sentry (Phase 2 OBS-01). |
| T-05-01-04 | Tampering | Sub-module imports — circular or wrong-sibling import accidentally loads stale admin.py code | mitigate | Task 2 deletes admin.py; Python import system forces ModuleNotFoundError for any stale `from app.api.endpoints.admin import` without a sub-module suffix. `admin/_helpers.py` is a leaf module (Risk 4) — does not import from sibling sub-modules. Grep-audit in acceptance criteria confirms. |
| T-05-01-05 | Spoofing (role confusion) | Routes using `get_current_superuser` vs `get_current_admin_user` | mitigate | Task 2 preserves the exact dependency each route currently uses (verified by reading admin.py before extracting). Coverage test's 403-with-regular-user assertion covers BOTH `get_current_admin_user` and `get_current_superuser` routes (a regular user fails both checks). |
| T-05-01-06 | Denial of Service | OpenAPI snapshot drift on routes outside the expected 7-move delta | mitigate | Task 2 regenerates snapshot with `TESTING=true ENABLE_RATE_LIMITING=false`. Phase 1 `test_openapi_snapshot.py` verifies equality on subsequent runs. Reviewer validates diff shows ONLY the 7 intentional moves + 16 unchanged paths per D-16. |
</threat_model>

<verification>
**Full plan verification** (run before marking plan complete):

```bash
cd backend
pytest -n auto tests/test_admin_auth_coverage.py tests/test_openapi_snapshot.py tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x

# Phase 1 characterization MUST stay green
pytest -n auto tests/auth/ tests/test_auth_characterization.py 2>/dev/null || pytest -n auto -k "characterization" -x

cd ../frontend
npm run type-check
npm test -- --run

# Old-file deletion + import-migration audit
test ! -f ../backend/app/api/endpoints/admin.py
grep -rn "from app.api.endpoints.admin import" ../backend/app/ ../backend/tests/ | grep -v "endpoints\.admin\.\(stats\|jobs\|crawlers\|db_ops\|parts\|_helpers\)"  # MUST return exit 1

# No Terraform change required (per RESEARCH.md Finding 5)
# EventBridge API destination unchanged: /api/admin/crawlers/run
```
</verification>

<success_criteria>
1. `backend/app/api/endpoints/admin.py` does NOT exist; 23 routes served from `backend/app/api/endpoints/admin/{stats,jobs,crawlers,db_ops,parts}.py`.
2. `pytest -n auto backend/tests/test_admin_auth_coverage.py` exits 0 with at least 47 test cases collected (23 × 2 parametrized + 1 drift-guard, plus the 2 `DUAL_AUTH_ROUTES` accepting 401|403).
3. Phase 1 OpenAPI snapshot test passes after snapshot regeneration; diff matches the 7 intentional admin URL moves per D-09.
4. Phase 3 logger + Phase 4 session.query + Phase 3 Pydantic v1 regression tests all pass.
5. `frontend/npm run type-check` + `frontend/npm test` green; grep for old admin literals in `frontend/src/` returns empty.
6. SUMMARY.md documents: (a) no Terraform change (Finding 5), (b) ADMIN-04 satisfied-by-construction (Finding 6), (c) deploy sequencing for the rescrape-archives path move per Risk 3 / Finding 5.
</success_criteria>

<output>
After completion, create `.planning/phases/05-structural-router-splits/05-01-SUMMARY.md` per the template with:
- Routes extracted per sub-module (counts: 2/4/4/7/6 = 23)
- OpenAPI snapshot delta summary (7 moves)
- Terraform scope-empty documentation (Finding 5)
- ADMIN-04 satisfied-by-construction note (Finding 6)
- Deploy sequencing note for `/admin/crawlers/rescrape-archives` path move (Risk 3 / Finding 5)
- Confirmation the Chrome extension is untouched (D-14)
</output>
