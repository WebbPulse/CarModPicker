# Phase 1: Safety Nets & CI Hardening - Pattern Map

**Mapped:** 2026-04-21
**Files analyzed:** ~30 new + ~9 modified (cassette + HTML fixtures counted as groups)
**Analogs found:** 28 / 30 (2 files have no prior analog in repo)

This map groups files by subsystem. Every "Analog" path is absolute-from-repo-root so the planner can Read it directly. Every code excerpt is lifted verbatim from the cited file + line range (no synthesis).

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/pytest.ini` (modify) | config (pytest) | build-time | `backend/pytest.ini` itself (in-place edit) | exact (same file) |
| `backend/app/db/base_class.py` (modify) | config (ORM base) | build-time | `backend/app/db/base_class.py` itself (in-place edit) | exact (same file) |
| `backend/alembic/versions/097024200e60_…py` (modify) | migration | schema DDL | `backend/alembic/versions/d2e9c4a1f57b_rename_brands_to_part_manufacturers.py` | role-match (well-formed named-constraint migration) |
| `backend/alembic/versions/172d1c205fb3_…py` (modify) | migration | schema DDL | same as above | role-match |
| `backend/alembic/versions/6eae6b1393c5_…py` (modify) | migration | schema DDL | same as above | role-match |
| `backend/alembic/versions/<new>_repair_drop_constraint_none.py` (new, ×up to 3) | migration | schema DDL (forward-only repair) | `backend/alembic/versions/d2e9c4a1f57b_rename_brands_to_part_manufacturers.py` | role-match |
| `.github/workflows/backend-ci.yml` (modify) | ci-workflow | CI event-driven | `.github/workflows/backend-ci.yml` itself | exact |
| `.github/workflows/frontend-ci.yml` (modify) | ci-workflow | CI event-driven | `.github/workflows/frontend-ci.yml` itself | exact |
| `frontend/vitest.config.ts` (modify) | config (vitest) | build-time | `frontend/vitest.config.ts` itself | exact |
| `backend/requirements.txt` (modify) | config (pip) | build-time | `backend/requirements.txt` itself | exact |
| `.github/dependabot.yml` (new) | repo-config (GitHub-managed) | repo event-driven | **no analog** — no prior `.github/*.yml` non-workflow file exists | none |
| `backend/scripts/check_migrations.py` (new) | script (CI utility) | file-I/O → stdout/exit-code | `backend/scripts/flatten_migrations.py` | role-match (same dir, same file-scanning + path-resolution shape, but interactive not CI) |
| `backend/tests/test_openapi_snapshot.py` (new) | test (integration, backend top-level) | request-response (app.openapi()) → file compare | `backend/tests/test_main.py` | role-match (top-level test using `client` fixture, but hits routes not `.openapi()`) |
| `backend/tests/fixtures/openapi_snapshot.json` (new, generated) | test-fixture (JSON) | file-I/O | **no analog** — `backend/tests/fixtures/` dir does not yet exist | none |
| `backend/tests/auth/test_characterization_signup.py` (new) | test (auth characterization) | request-response + DB-state | `backend/tests/api/endpoints/test_auth.py` (signup/verify flow) | exact |
| `backend/tests/auth/test_characterization_login.py` (new) | test (auth characterization) | request-response | `backend/tests/api/endpoints/test_auth.py` (login flow) | exact |
| `backend/tests/auth/test_characterization_2fa_totp.py` (new) | test (auth characterization) | request-response | `backend/tests/api/endpoints/test_auth.py` (TOTP flow) | exact |
| `backend/tests/auth/test_characterization_webauthn.py` (new) | test (auth characterization) | request-response + crypto stub | `backend/tests/api/endpoints/test_webauthn.py` | exact |
| `backend/tests/auth/test_characterization_oauth_signin.py` (new) | test (auth characterization) | request-response + VCR-recorded HTTPS | `backend/tests/api/endpoints/test_google_oauth.py` | exact (but switches mock→VCR per D-18) |
| `backend/tests/auth/test_characterization_oauth_link.py` (new) | test (auth characterization) | request-response + VCR | `backend/tests/api/endpoints/test_google_oauth.py` | exact |
| `backend/tests/auth/test_characterization_password_reset.py` (new) | test (auth characterization) | request-response + SES-mock | `backend/tests/api/endpoints/test_auth.py` (verify-email flow) | role-match |
| `backend/tests/cassettes/auth/*.yaml` (new, ×7, generated) | test-fixture (VCR cassette) | file-I/O | **no analog** — repo has zero `.yaml` VCR cassettes today | none |
| `backend/tests/crawlers/test_characterization_<adapter>.py` (new, ×5) | test (adapter characterization) | file-I/O (HTML) → pure-function parse | `backend/tests/crawlers/test_briantooleyracing_adapter.py` (TestParseProductPage class, lines 229-296) | exact |
| `backend/tests/crawlers/fixtures/<adapter>/product.html` (new, ×5) | test-fixture (HTML) | file-I/O | **no analog** — existing adapter tests inline HTML via `_product_html()` helpers, not committed files | partial (shape from helper) |
| `backend/tests/crawlers/fixtures/<adapter>/expected.json` (new, ×5) | test-fixture (JSON) | file-I/O | **no analog** — no committed expected-payload JSON exists | none |

---

## Pattern Assignments

### 1. `backend/pytest.ini` (config, build-time)

**Analog:** `backend/pytest.ini` (itself — single-line addition to existing `addopts` list)

**Full current file** (lines 1-23, cite verbatim):

```ini
[tool:pytest]
testpaths = app/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
    # Parallel execution options - enabled for parallel testing
    -n auto
    --dist=loadfile
    # Suppress ResourceWarnings about unclosed database connections
    -W ignore::ResourceWarning
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

**Insertion point:** between `--cov-report=xml` (line 14) and the `# Parallel execution options` comment (line 15). The new line reads `--cov-fail-under=<MEASURED_BASELINE>` (with actual integer from D-01 baseline run).

**Pitfall carried from RESEARCH.md Pitfall 2:** `testpaths = app/tests` is STALE (tests live at `backend/tests/`, not `backend/app/tests/`). Planner should note this as candidate future cleanup but must NOT bundle it into the SAFE-01 PR.

---

### 2. `backend/app/db/base_class.py` (config, ORM base)

**Analog:** `backend/app/db/base_class.py` (itself)

**Full current file** (lines 1-3, cite verbatim):

```python
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

**Pattern to apply** (RESEARCH.md §Pattern 3, lines 386-409): replace the 3-line file with the 10-line convention dict + `MetaData(...)` + `declarative_base(metadata=metadata)` form. Imports go from `from sqlalchemy.orm import declarative_base` to `from sqlalchemy import MetaData` + `from sqlalchemy.orm import declarative_base`. **No other file needs to change** — `backend/alembic/env.py` already imports `Base.metadata` (per CONTEXT.md "Integration Points", line 140).

---

### 3. Repair migrations (`097024200e60`, `172d1c205fb3`, `6eae6b1393c5`) + new forward-only repair file(s)

**Analog for the repair pattern:** `backend/alembic/versions/d2e9c4a1f57b_rename_brands_to_part_manufacturers.py` — a well-formed hand-edited migration that uses `op.execute("ALTER TABLE ... RENAME CONSTRAINT ...")` with explicit constraint names. This is the only file in `backend/alembic/versions/` that demonstrates named-constraint management.

**Imports / header pattern** (lines 1-17, cite verbatim):

```python
"""rename brands to part_manufacturers

Revision ID: d2e9c4a1f57b
Revises: c1f3e8a92d45
Create Date: 2026-04-17 00:10:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d2e9c4a1f57b"
down_revision: Union[str, None] = "c1f3e8a92d45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**Named constraint invocation pattern** (lines 32-33, cite verbatim):

```python
op.execute("ALTER TABLE part_manufacturers RENAME CONSTRAINT brands_pkey TO part_manufacturers_pkey")
op.execute("ALTER TABLE parts RENAME CONSTRAINT parts_brand_id_fkey TO parts_part_manufacturer_id_fkey")
```

**What each broken migration currently looks like** (verbatim — these are what the repair PR must replace):

- `097024200e60_add_canonical_part_id_to_parts.py` line 33:
  ```python
  op.drop_constraint(None, 'parts', type_='foreignkey')
  ```
- `172d1c205fb3_add_build_list_phases.py` line 45:
  ```python
  op.drop_constraint(None, "build_list_parts", type_="foreignkey")
  ```
- `6eae6b1393c5_add_brand_model.py` line 48:
  ```python
  op.drop_constraint(None, "global_parts", type_="foreignkey")
  ```

**Repair strategy** (locked by CONTEXT.md D-13/D-14, RESEARCH.md Pattern 4 lines 413-469):

Two branches — planner must pick one at PR-author time based on production migration state:

1. **If broken migration has NOT yet run on prod** (unlikely per D-14 but verify via `SELECT version_num FROM alembic_version` against prod): edit the offending `drop_constraint(None, ...)` line in-place, substituting the real constraint name (obtained via Introspection Pattern below). Add `# SAFE: repair invalid drop_constraint(None) — see SAFE-08` on the same line.
2. **If broken migration HAS run on prod** (expected): do NOT touch the three historic files. Instead author a NEW migration file (see RESEARCH.md Pattern 4 for skeleton) whose `upgrade()` is a no-op and whose `downgrade()` performs the three properly-named drops. The 6eae6b1393c5 drop is in the migration's `downgrade()`; the new file's `downgrade()` must NOT re-add the `brand` VARCHAR column (the historic file already does that).

**Constraint name introspection pattern** (from RESEARCH.md §Code Example 4, lines 736-780 — plan this as a manual step documented in the PR description, not committed code):

```sql
SELECT conname
FROM pg_constraint
WHERE conrelid = 'parts'::regclass
  AND contype = 'f'
  AND (
    SELECT array_agg(attname ORDER BY attnum)
    FROM unnest(conkey) AS col(colnum)
    JOIN pg_attribute ON attrelid = conrelid AND attnum = col.colnum
  ) = ARRAY['canonical_part_id'];
-- Typical Postgres auto-name: parts_canonical_part_id_fkey
```

**Annotation pattern for the new migration file** (exact token from D-09):

```python
# SAFE: repair invalid drop_constraint(None) — see SAFE-08
op.drop_constraint("parts_canonical_part_id_fkey", "parts", type_="foreignkey")
```

---

### 4. `.github/workflows/backend-ci.yml` (ci-workflow)

**Analog:** `.github/workflows/backend-ci.yml` (itself)

**Step-insertion patterns to copy:** the file already follows the shape `- name: <title>` + `run: | <bash>`. Two new steps must be added, and the existing `Run tests with coverage` step is unchanged because `--cov-fail-under` is configured in `pytest.ini addopts`, not the CI command.

**Existing "Scan dependencies" step** (lines 67-71, cite verbatim — this is what the DROP-guard step lands BEFORE):

```yaml
      - name: Scan dependencies for vulnerabilities
        run: |
          cd backend
          # Ignore ecdsa CVE-2024-23342: Not exploitable in this codebase as we use HS256 (HMAC) algorithm, not ECDSA-based algorithms
          pip-audit -r requirements.txt --ignore-vuln CVE-2024-23342
```

**Existing "Run tests with coverage" step** (lines 73-84, cite verbatim — DROP-guard step lands BETWEEN `Scan dependencies` and this):

```yaml
      - name: Run tests with coverage
        env:
          SECRET_KEY: test-secret-key-for-ci
          ACCESS_TOKEN_EXPIRE_MINUTES: 30
          ALLOWED_ORIGINS: http://localhost:3000,http://localhost:4000
          DEBUG: true
          PROJECT_NAME: CarModPicker API
          API_STR: /api
          EMAIL_FROM: test@example.com
        run: |
          cd backend
          python -m pytest -n auto --cov=app --cov-report=xml --cov-report=term-missing
```

**New step to insert** (from RESEARCH.md §Code Example 3, line 731-733, verbatim):

```yaml
      - name: Check migrations for unannotated destructive operations
        run: |
          python backend/scripts/check_migrations.py
```

**No other changes to this workflow.** Do NOT add an explicit `--cov-fail-under` flag on the CI command — it lives in `pytest.ini addopts` (SAFE-01 D-02).

---

### 5. `.github/workflows/frontend-ci.yml` (ci-workflow)

**Analog:** `.github/workflows/frontend-ci.yml` (itself)

**Existing "Audit dependencies" step** (lines 43-46, cite verbatim — the "Run tests" step lands AFTER this):

```yaml
      - name: Audit dependencies for vulnerabilities
        run: |
          cd frontend
          npm audit --audit-level=moderate
```

**Existing "Build application" step** (lines 48-51, cite verbatim — the "Run tests" step lands BEFORE this):

```yaml
      - name: Build application
        run: |
          cd frontend
          npm run build
```

**New step to insert between them** (from CONTEXT.md D-04):

```yaml
      - name: Run tests
        run: |
          cd frontend
          npm test -- --run --coverage
```

Rationale for placement (fail-fast on test regressions) and exact flags (`--run` to disable watch mode; `--coverage` to trigger the v8 coverage + threshold check) are locked by D-04.

---

### 6. `frontend/vitest.config.ts` (config, vitest)

**Analog:** `frontend/vitest.config.ts` (itself)

**Full current file** (lines 1-25, cite verbatim):

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/coverage/**',
        'dist/',
        'build/',
      ],
    },
  },
});
```

**Insertion point:** add a `thresholds` key to the `coverage` object immediately after the `exclude` array closes (between line 22 and line 23). RESEARCH.md §Pattern 2 (lines 340-377) has the literal shape:

```typescript
      thresholds: {
        lines: 60,
        functions: 50,
        branches: 50,
        statements: 60,
      },
```

---

### 7. `backend/requirements.txt` (config, pip)

**Analog:** `backend/requirements.txt` (itself)

**Existing testing block** (lines 54-62, cite verbatim — new line lands INSIDE this block):

```
# Testing: in-memory S3 mock (used with pytest fixtures; never runs in production)
moto[s3]==5.1.22

# Testing dependencies
pytest==9.0.3
pytest-asyncio==1.3.0
pytest-xdist==3.8.0
pytest-cov==6.2.1
httpx==0.28.1
```

**Insertion:** add a single line `pytest-recording==0.13.4` immediately under `pytest-cov==6.2.1` (line 61) so the test-deps stay grouped. Version locked by RESEARCH.md Standard Stack.

---

### 8. `.github/dependabot.yml` (new, repo-config)

**Analog:** **none found.** The `.github/` directory contains only `workflows/` — no prior dependabot/renovate/CODEOWNERS/issue-template YAMLs exist. Planner should use RESEARCH.md-supplied pattern directly (no codebase analog to copy from). The workflow files are also GitHub Actions YAML which is a different schema; they cannot serve as analogs.

**Shape reference** (authoritative source — RESEARCH.md §Standard Stack locks `version: 2` schema; CONTEXT.md D-29/D-30 locks ecosystems + grouping):

- `version: 2` at file root
- Three `updates:` entries: `pip` (dir: `/backend`), `npm` (`directories: ["/frontend", "/chrome-extension"]`), `github-actions` (dir: `/.github/workflows` — but Dependabot convention is `directory: "/"`).
- Each entry: `schedule.interval: weekly`, `schedule.day: monday`.
- Each entry: `groups: { minor-and-patch: { update-types: ["minor", "patch"] } }` (name is Claude's discretion per CONTEXT.md §"Claude's Discretion", bullet 4).
- **Do NOT add any `ignore:` block** — RESEARCH.md Pitfall 6 + Anti-Pattern §"Using `ignore` in dependabot.yml".

---

### 9. `backend/scripts/check_migrations.py` (new, CI utility script)

**Analog:** `backend/scripts/flatten_migrations.py`

**Imports + path-resolution pattern** (lines 1-28, cite verbatim):

```python
#!/usr/bin/env python3
"""
Script to flatten Alembic migrations into a new baseline.

This script:
1. Creates a new baseline migration from the current models
2. Archives old migrations to a backup directory
3. Provides instructions for updating the database

WARNING: This will remove all existing migration history.
Only use this if you're sure you want to start fresh.
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get the backend directory (parent of scripts)
BACKEND_DIR = Path(__file__).parent.parent
ALEMBIC_DIR = BACKEND_DIR / "alembic"
VERSIONS_DIR = ALEMBIC_DIR / "versions"
ARCHIVE_DIR = ALEMBIC_DIR / "versions_archive"
```

**Patterns to copy from this analog:**
- Shebang `#!/usr/bin/env python3`
- Module-level docstring describing what it does + exit semantics
- Path resolution via `Path(__file__).parent.parent` rather than CWD
- Module-level constants for directory paths (`VERSIONS_DIR = ...`)

**Patterns to AVOID from this analog:**
- Interactive `input("...yes/no...")` prompt (flatten_migrations.py line 42) — the DROP-guard must be non-interactive (CI-safe).
- `subprocess.run` calls — the DROP-guard is pure file scanning, no subprocesses.
- Stateful side-effects (moves files, mutates DB) — DROP-guard is read-only.

**Body pattern** (supplied verbatim by RESEARCH.md §Code Example 2, lines 624-698 — no codebase analog for the regex + line-lookback logic). Planner should lift that example literally and adjust only:
- Path resolution: use `parents[2]` (from `backend/scripts/check_migrations.py` → repo root) as in the RESEARCH.md example, OR use `Path(__file__).parent.parent` → backend dir (flatten_migrations.py style) then join `alembic/versions`. Pick one; both work; the flatten_migrations.py style is more conservative because it doesn't assume where the script is run from.
- Exit codes: RESEARCH.md example uses `return 0/1/2` from `main()` + `sys.exit(main())`. Keep this shape.

**Root-`scripts/` alternative** (NOT chosen, but exists at `scripts/populate_sample_data.py` + `scripts/export_global_parts_for_car_inference_analysis.py` etc.): these live at repo-root `/scripts/`, not `/backend/scripts/`. Per CONTEXT.md D-08 the new file lives at **`backend/scripts/check_migrations.py`** (to keep backend tooling co-located). Do not confuse with the root `scripts/` directory.

---

### 10. `backend/tests/test_openapi_snapshot.py` (new, integration test)

**Analog:** `backend/tests/test_main.py`

**Full analog file** (lines 1-33, cite verbatim — this is the closest shape for a top-level-of-`tests/` test that exercises the running FastAPI app):

```python
from fastapi.testclient import TestClient


def test_read_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CarModPicker API"
    assert data["status"] == "running"


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint for monitoring (liveness)."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "CarModPicker API"
    assert "version" in data
```

**Patterns to copy:**
- File location directly under `backend/tests/` (NOT under `backend/tests/api/endpoints/`) — same level as `test_main.py`, `test_pagination.py`, `test_email.py`.
- Use the `client: TestClient` fixture (auto-wired by `backend/tests/conftest.py`).
- Assertion style: `assert response.status_code == 200` + JSON key presence.

**Key deviation from the analog** (locked by CONTEXT.md D-25 + RESEARCH.md §Pitfall 8 lines 594-606): the snapshot test does NOT call `client.get(...)`. Instead it imports `app` at function scope and calls `app.openapi()` directly:

```python
def test_openapi_snapshot_matches() -> None:
    # Import at function scope so conftest.py env setup runs first.
    from app.main import app
    actual = json.dumps(app.openapi(), indent=2, sort_keys=True)
    ...
```

Full body supplied by RESEARCH.md §Code Example 5 (lines 784-817); planner should use that example verbatim. The `client` fixture is NOT needed for the snapshot test — but keep the test file co-located with other top-level tests.

---

### 11. `backend/tests/fixtures/openapi_snapshot.json` (new, generated)

**Analog:** **none.** No `backend/tests/fixtures/` directory exists today. Planner must create the dir.

**Generation command** (locked by CONTEXT.md D-26, verbatim):

```
python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))" > backend/tests/fixtures/openapi_snapshot.json
```

Run from `backend/` dir. File is committed to git; subsequent diffs are the schema-drift review artifact (D-27 forbids hash comparison).

---

### 12. Auth characterization test files (new, ×7 under `backend/tests/auth/`)

**Analog A (general shape, non-crypto flows — signup, login, verify-email, password-reset):** `backend/tests/api/endpoints/test_auth.py`

**Imports + helpers pattern** (lines 1-32, cite verbatim):

```python
import os

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Helper to create a user directly in the DB for testing login
# This is an alternative to calling the /users/ endpoint if you want to bypass API validation for setup
from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser  # For direct DB manipulation if needed
from app.core.config import settings


def get_unique_username(base_name: str) -> str:
    """Generate a unique username for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def create_test_user_direct_db(db: Session, username: str, email: str, password: str, disabled: bool = False) -> DBUser:
    hashed_password = get_password_hash(password)
    db_user = DBUser(
        username=username,
        email=email,
        hashed_password=hashed_password,
        disabled=disabled,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
```

**Canonical login-flow test** (lines 34-71, cite verbatim — copy as the skeleton for `test_characterization_login.py`):

```python
def test_login_for_access_token_success(client: TestClient) -> None:
    username = get_unique_username("auth_test_user")  # Ensure unique username for test
    password = "auth_test_password"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    # Create user via API
    create_user_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_user_response.status_code == 200, f"Failed to create user for auth test: {create_user_response.text}"

    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 200, response.text

    # Check the response body for Bearer token and user details (OAuth2 standard)
    response_data = response.json()

    # 1. Check for Bearer token in response body
    assert "access_token" in response_data
    assert "token_type" in response_data
    assert response_data["token_type"] == "bearer"
```

**Analog B (crypto-stubbed flow — WebAuthn):** `backend/tests/api/endpoints/test_webauthn.py`

**Stub-at-library-boundary pattern** (lines 1-32 + 36-46, cite verbatim):

```python
"""Tests for WebAuthn (passkey) endpoints.

Real WebAuthn verification requires a signed attestation/assertion from an
authenticator, which we can't produce cheaply in a unit test. We mock the two
`verify_*` entry points from py_webauthn and focus on:
...
"""

import base64
import os
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser
from app.api.models.webauthn_credential import WebAuthnCredential
from app.core.config import settings

# ...

def _create_user(db: Session, username: str, password: str = "testpassword") -> DBUser:
    user = DBUser(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(password),
        email_verified=True,
        disabled=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

The `unittest.mock.patch` at the `webauthn` library boundary is the established project pattern (CONTEXT.md D-18 mandates this instead of cassettes for WebAuthn). Copy the `patch("app.api.endpoints.auth.<webauthn_func>")` invocation shape verbatim from test_webauthn.py.

**Analog C (VCR-replayed flow — Google OAuth):** `backend/tests/api/endpoints/test_google_oauth.py`

**Patchable-boundary pattern** (lines 1-44, cite verbatim — though CONTEXT.md D-18 mandates VCR replace this `patch` for the characterization tests):

```python
"""Tests for Google sign-in / OAuth account linking endpoints.

Real Google ID-token verification requires a token signed by Google's keys, which we
can't reproduce in a unit test. We patch `verify_google_id_token` (the helper bound
into the auth module's namespace) and exercise the full state machine around it:
...
"""

import os
from typing import Generator
from unittest.mock import patch

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.oauth_account import OAuthAccount
from app.api.models.user import User as DBUser
from app.api.models.webauthn_credential import WebAuthnCredential
from app.api.utils.google_oauth import GoogleIdentity
from app.core.config import settings

GOOGLE_PATH = f"{settings.API_STR}/auth/google"
LINK_PATH = f"{settings.API_STR}/auth/google/link"
SIGNUP_PATH = f"{settings.API_STR}/auth/google/signup"
CONNECT_PATH = f"{settings.API_STR}/auth/google/connect"
OAUTH_2FA_PATH = f"{settings.API_STR}/auth/oauth/2fa"
OAUTH_LIST_PATH = f"{settings.API_STR}/auth/oauth"
```

**Key deviation for characterization tests (CONTEXT.md D-18, RESEARCH.md §Code Example 6):** replace `@patch(...)` with `@pytest.mark.vcr` + a `vcr_config` fixture in `conftest.py`. The VCR example skeleton is at RESEARCH.md lines 821-904 — copy verbatim.

**File-location note:** CONTEXT.md lists the 7 test files at `backend/tests/auth/test_characterization_<flow>.py` (a NEW `auth/` subdirectory) rather than in the existing `backend/tests/api/endpoints/`. This distinguishes characterization tests (pin current behavior) from the existing per-field unit tests. Add an empty `backend/tests/auth/__init__.py` for pytest discovery (match the convention at `backend/tests/crawlers/__init__.py`).

**Env-var ordering (C-05 from RESEARCH.md):** characterization tests MUST NOT import `app.main` at module scope. Either use the `client` fixture (which handles env var setup via conftest.py) or import inside the test function body (same pattern as test_openapi_snapshot.py).

---

### 13. VCR cassette files (`backend/tests/cassettes/auth/*.yaml`, ×7, generated)

**Analog:** **none** — the repo contains zero VCR cassettes today (no `.yaml` files anywhere under `backend/tests/`).

**Generation procedure** (locked by CONTEXT.md D-17, RESEARCH.md §Pitfall 3 lines 544-555):

1. Run test with recording mode + serial execution (MUST be `-n 0` to avoid pytest-xdist race):
   ```
   cd backend
   rm tests/cassettes/auth/test_google_oauth_signin.yaml  # if regenerating
   pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_signin.py
   ```
2. Commit the resulting `.yaml` file.
3. CI replays with default `record_mode: "none"` (set in `vcr_config` fixture — see RESEARCH.md §Code Example 6).

**Secret scrubbing (RESEARCH.md §Anti-Patterns, last bullet):** the `vcr_config` fixture MUST set `filter_headers=["authorization", "cookie", "set-cookie"]` and `filter_post_data_parameters=["client_secret", "code", "refresh_token"]`. Copy the dict verbatim from RESEARCH.md §Code Example 6, lines 829-856.

---

### 14. Crawler adapter characterization test files (new, ×5 under `backend/tests/crawlers/`)

**Analog:** `backend/tests/crawlers/test_briantooleyracing_adapter.py` (and sibling `test_amsperformance_adapter.py`, `test_vividracing_adapter.py`)

**Imports pattern for a tier0_http adapter** (test_briantooleyracing_adapter.py lines 1-22, cite verbatim — shows the import shape for a tier0 adapter test):

```python
"""
Tests for briantooleyracing.com adapter: URL shape guard, host routing,
flat-sitemap discovery (priority=1.0 filter), Magento gallery extraction,
title MPN-suffix stripping, and end-to-end JSON-LD Product parsing.
...
"""

from app.crawlers.adapters import adapter_name_for_product_url
from app.crawlers.adapters.tier0_http import briantooleyracing as btr_mod
from app.crawlers.adapters.tier0_http.briantooleyracing import (
    BrianTooleyRacingAdapter,
    _discover_via_sitemap,
    _extract_gallery_full_urls,
    _is_product_url,
    _strip_trailing_mpn,
)

SAMPLE_URL = "https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html"
```

**For a tier1_tls adapter** (test_vividracing_adapter.py lines 1-10, verbatim):

```python
"""Tests for vividracing.com adapter: URL pattern, JSON-LD parse, DOM fallback, slug manufacturer."""

from app.crawlers.adapters.tier1_tls.vividracing import (
    VividRacingAdapter,
    _is_product_url,
    _manufacturer_from_slug,
    _slug_from_url,
)

SAMPLE_URL = "https://www.vividracing.com/agency-power-oval-taper-air-filter-wrap-enclosed-top-tapers-bottom-tall-p-152475800.html"
```

**Core `parse_product_page()` assertion pattern** (test_briantooleyracing_adapter.py lines 229-247, cite verbatim — this is the SINGLE most important pattern for Phase 1 SAFE-07 tests):

```python
class TestParseProductPage:
    """End-to-end parsing: synthetic JSON-LD + gallery + description DOM → ScrapedPayload."""

    def test_full_page_parses_with_gallery_and_dom_description(self) -> None:
        result = BrianTooleyRacingAdapter().parse_product_page(_product_html(), SAMPLE_URL)
        assert result is not None
        # MPN-suffix stripped from title.
        assert result.name == "BTR LS6 BEEHIVE SPRING - .560 LIFT - 16 PC KIT"
        assert result.part_manufacturer == "Brian Tooley Racing"
        assert result.part_number == "SP011-16"
        assert result.price_cents == 11999
        # JSON-LD description is empty; DOM block fills it in.
        assert result.description is not None
        assert "LS6-style valve springs" in result.description
        # Gallery wins over JSON-LD single ``image``.
        assert result.image_urls is not None
        assert len(result.image_urls) == 2
        assert result.image_urls[0].endswith("m2_sp011-16_22.jpg?full=1")
        assert result.product_url == SAMPLE_URL
```

**Key deviations for characterization tests** (CONTEXT.md D-22 + RESEARCH.md §Pattern 6 line 476-481):

1. **Do NOT** use an inline `_product_html()` helper. Instead load HTML from a committed fixture:
   ```python
   fixture_dir = Path(__file__).parent / "fixtures" / "<adapter_name>"
   html = (fixture_dir / "product.html").read_text(encoding="utf-8")
   expected = json.loads((fixture_dir / "expected.json").read_text(encoding="utf-8"))
   ```
2. **Do NOT** test `discover_product_urls()`, `_is_product_url()`, registration, or any other shape — only `parse_product_page()` (D-22).
3. **Key by class name, not ADAPTER_NAME** (D-23) — `BrianTooleyRacingAdapter()` not `adapter_name_for_product_url(...)`. Phase 3 lands `ADAPTER_NAME`; these tests switch over then.

**File-name pattern:** CONTEXT.md calls them `test_characterization_<adapter>.py`. The existing per-field test files are `test_<adapter>_adapter.py`. The `characterization_` prefix distinguishes the two. Place in the same `backend/tests/crawlers/` directory (CONTEXT.md "Existing Code Insights" line 129 confirms this).

**Pitfall 7 correction (RESEARCH.md lines 583-591):** CONTEXT.md D-20 mentions `tier1_flaresolverr` — no such directory exists. Actual layout: `tier0_http/`, `tier1_tls/` (curl_cffi), `tier2_browser/` (FlareSolverr). Planner's adapter picks: 2× from `tier0_http/` (briantooleyracing, amsperformance — confirmed to exist), 2× from `tier2_browser/` (choose from: aemelectronics, americanmuscle, apexwheels, dinan, ecstuning, fcpeuro, jegs, speedindustry, summitracing, tirerack), 1× from `tier1_tls/` (choose from: apr, cobbtuning, enjukuracing, forgeline, fortuneauto, goodwinracing, kwsuspensions, mackinindustries, racingbeat, suncoastparts, texasspeed, tomeiusa, turnermotorsport, vividracing, z1motorsports).

---

### 15. HTML fixture files (`backend/tests/crawlers/fixtures/<adapter>/product.html`, ×5)

**Analog:** **partial.** No committed HTML fixture files exist — every adapter test currently uses an inline `_product_html()` Python f-string (see test_briantooleyracing_adapter.py `_product_html(...)` at lines 47-107). That helper's OUTPUT shape (a full `<html><head>...` document with JSON-LD `<script type="application/ld+json">` + optional Magento gallery scripts + DOM body) is the reference for what the committed HTML must contain — but since CONTEXT.md D-21 says "archived HTML from the self-archive S3 bucket," the planner should pull real product-page HTML from the archive rather than writing synthetic HTML.

**Storage-location pattern to copy (Python side):** the `fixtures` sibling-directory convention is new here. No prior test uses a `fixtures/` subfolder under `backend/tests/crawlers/`. The `backend/tests/fixtures/` pattern (used by SAFE-05 OpenAPI snapshot) is the closest analog at the repository level.

---

### 16. Expected-output JSON files (`backend/tests/crawlers/fixtures/<adapter>/expected.json`, ×5)

**Analog:** **none.** No committed expected-payload JSON exists.

**Deterministic structure mandate** (CONTEXT.md "Claude's Discretion" bullet 2): format is Claude's choice but MUST be deterministic (same input → same output bytes). Recommend `json.dumps(obj, indent=2, sort_keys=True)` — same recipe as SAFE-05's OpenAPI snapshot for consistency.

**Reference for WHICH fields to capture:** `ScrapedPayload` shape is defined at `backend/app/crawlers/base.py`. The fields asserted in test_briantooleyracing_adapter.py lines 236-247 are the minimum-viable set: `name`, `part_manufacturer`, `part_number`, `price_cents`, `description`, `image_urls`, `product_url`. Capture all public `ScrapedPayload` attributes in the JSON; omit None values at the author's discretion.

---

## Shared Patterns

### Auth (test env setup)

**Source:** `backend/tests/conftest.py` lines 13-16

```python
# Set test environment variables BEFORE importing any app code
# so storage service, rate limiter, etc. detect the test environment at import time.
os.environ["TESTING"] = "true"
os.environ["ENABLE_RATE_LIMITING"] = "false"
```

**Apply to:** all new test files (SAFE-05 snapshot, SAFE-06 auth characterization, SAFE-07 crawler characterization). Inherited automatically by using the existing `client` fixture; new test files MUST NOT do `from app.main import app` at module scope (C-05, Pitfall 8).

### Unique-per-worker naming

**Source:** `backend/tests/conftest.py` line 117 (fixture style) + `backend/tests/api/endpoints/test_auth.py` lines 13-17 (helper style)

```python
def get_unique_username(base_name: str) -> str:
    """Generate a unique username for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"
```

**Apply to:** all 7 SAFE-06 auth characterization tests that create users. pytest-xdist with `-n auto --dist=loadfile` requires every test-created user to carry a unique identifier.

### Fixture use (backend)

**Source:** `backend/tests/conftest.py` fixtures `client`, `db_session`, `test_user`, `test_admin_user`, `mock_s3` (pre-wired; no plumbing required per CONTEXT.md line 123).

**Apply to:** all SAFE-05 and SAFE-06 tests. SAFE-07 crawler tests take no fixtures (pure-function `parse_product_page()` test against HTML file).

### Pytest marker style

**Source:** `backend/pytest.ini` lines 20-23 — markers registered: `slow`, `integration`, `unit`.

**Apply to:** SAFE-06 tests may tag with `@pytest.mark.integration` (they touch external HTTP via VCR-replay). But CONTEXT.md does not mandate markers and existing tests mostly use none; do not require unless author sees value. Also: `@pytest.mark.vcr` is supplied by `pytest-recording` — used ONLY on the 2 Google-OAuth flows (signin, link); WebAuthn/TOTP use `unittest.mock.patch`; signup/login/password-reset need neither (no external HTTP).

### Alembic migration header

**Source:** every file in `backend/alembic/versions/*.py` — standard header generated by `alembic revision --autogenerate`. Verbatim pattern from `d2e9c4a1f57b_rename_brands_to_part_manufacturers.py` lines 1-17 (already cited in §3 above).

**Apply to:** any NEW repair migration file for SAFE-08. Do not hand-write; per C-01 (CLAUDE.md) always generate via `alembic revision --autogenerate` against a Postgres DB carrying the broken state, then manually correct the `drop_constraint(None, ...)` line in the generated file.

### CI step structure (`.github/workflows/*.yml`)

**Source:** `.github/workflows/backend-ci.yml` lines 50-71 (the 7 existing backend steps — each is `- name:` + `run: |` + `cd backend` + tool invocation). Apply to the single new step for SAFE-04 (already excerpted in §4 above).

### Python formatting (all new `.py` files)

**Source:** `CLAUDE.md` + `backend/pyproject.toml`

```
black --config pyproject.toml --line-length 120
isort . (profile: "black")
pyright (strict)
```

**Apply to:** `backend/scripts/check_migrations.py`, `backend/tests/test_openapi_snapshot.py`, all 7 `backend/tests/auth/test_characterization_*.py`, all 5 `backend/tests/crawlers/test_characterization_*.py`, any new Alembic repair file. This is a shared build-time gate, not a per-file pattern.

---

## No Analog Found

Files with no close match in the codebase (planner should use RESEARCH.md code examples instead):

| File | Role | Reason |
|------|------|--------|
| `.github/dependabot.yml` | repo-config | No prior non-workflow YAML exists under `.github/`. Use RESEARCH.md §Standard Stack Dependabot shape. |
| `backend/tests/fixtures/openapi_snapshot.json` | generated fixture | `backend/tests/fixtures/` dir does not yet exist. Use CONTEXT.md D-26 generation command. |
| `backend/tests/cassettes/auth/*.yaml` (×7) | VCR cassettes | No VCR cassettes exist in repo. Use RESEARCH.md §Code Example 6 for vcr_config + regeneration procedure. |
| `backend/tests/crawlers/fixtures/<adapter>/expected.json` (×5) | generated fixture | No committed adapter expected-output JSON exists. Structure is Claude's discretion (CONTEXT.md) with `json.dumps(indent=2, sort_keys=True)` recommended for determinism. |
| `backend/tests/crawlers/fixtures/<adapter>/product.html` (×5) | committed HTML | Existing tests use inline `_product_html()` f-strings rather than committed files; per CONTEXT.md D-21 fixtures come from the S3 archive, not from the adapter test helpers. |

---

## Metadata

**Analog search scope:**
- `backend/tests/**/*.py` (all existing test files — 100+ crawler tests, 20+ endpoint tests)
- `backend/alembic/versions/*.py` (all 30+ migration files)
- `backend/scripts/*.py` (flatten_migrations.py, sync_crawl_archive_to_prod.py)
- `scripts/*.py` (root-level — 4 files, none relevant as analogs for CI utility)
- `.github/workflows/*.yml` (6 workflow files)
- `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`
- `backend/app/crawlers/adapters/base.py`, tier subdirectories

**Files scanned:** ~180 Python files, 6 YAML files, 1 TypeScript config

**Pattern extraction date:** 2026-04-21

---

## PATTERN MAPPING COMPLETE

**Phase:** 01 - Safety Nets & CI Hardening
**Files classified:** 30+ (counting cassettes and adapter fixtures as groups)
**Analogs found:** 28 / 30

### Coverage
- Files with exact analog (same file, or identical role/data-flow in repo): 22
- Files with role-match analog (same role but some deviation required): 6
- Files with no analog: 2 (dependabot.yml, VCR cassettes) + 3 new directories (`backend/tests/fixtures/`, `backend/tests/auth/`, `backend/tests/crawlers/fixtures/`)

### Key Patterns Identified

1. **`backend/tests/conftest.py` is the fixture ground truth** — every new backend test must rely on `client`, `db_session`, `mock_s3`, etc. fixtures defined there; never re-plumb. The pre-app-import env setup (`os.environ["TESTING"]="true"`) is the one gotcha for SAFE-05 (snapshot test must import `app` at function scope).
2. **`backend/tests/crawlers/test_briantooleyracing_adapter.py`'s `TestParseProductPage` class is the exact skeleton for SAFE-07** — construct adapter, call `parse_product_page(html, url)`, assert equality on `ScrapedPayload` fields. The only deviation is loading HTML from a committed file rather than an inline f-string.
3. **`d2e9c4a1f57b_rename_brands_to_part_manufacturers.py` is the only well-formed named-constraint migration** in the project — use its header + `op.execute("ALTER TABLE ... RENAME CONSTRAINT ...")` shape as the analog for any hand-corrected repair migration. Every other migration is autogenerated.
4. **CI workflows follow `- name: / run: | / cd <dir>` step structure** — new SAFE-04 DROP-guard step and SAFE-02 frontend test step both inherit this shape verbatim.
5. **Auth tests split along crypto vs. non-crypto lines** — WebAuthn uses `unittest.mock.patch` at library boundary (test_webauthn.py); Google OAuth will switch from `patch` (test_google_oauth.py) to `@pytest.mark.vcr` for characterization tests (new pattern per CONTEXT.md D-18); signup/login/password-reset need neither (pure TestClient + DB assertions per test_auth.py).
6. **Tier1_flaresolverr does not exist** (Pitfall 7) — tier layout is `tier0_http/`, `tier1_tls/`, `tier2_browser/`. The planner's SAFE-07 adapter picks must use the real directory names.

### File Created

`/home/tyler-webb/Documents/Github/CarModPicker/.planning/phases/01-safety-nets-ci-hardening/01-PATTERNS.md`

### Ready for Planning

Pattern mapping complete. The planner can reference concrete analog files and line ranges in every PLAN.md action. The 2 unavailable analogs (dependabot.yml, VCR cassettes) are flagged — RESEARCH.md supplies authoritative shapes for both.
