# Phase 6: Frontend Cleanup & Final CI Gates — Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 30+ (new + modified, across frontend/backend/terraform/ci)
**Analogs found:** 28/30 (2 files have no direct analog — noted at bottom)

This PATTERNS.md is organized by **wave** to match D-21 sequencing. Each wave section lists the files that wave touches and the concrete analog + excerpts the planner should copy from.

---

## File Classification (Wave-Ordered)

| Wave | File (new/modified) | Role | Data Flow | Closest Analog | Match |
|------|---------------------|------|-----------|----------------|-------|
| 0 | `backend/tests/test_bandit_high_gate.py` (new) | test/subprocess-invoking | batch/static-guard | `backend/tests/test_check_migrations.py` + `backend/tests/test_cassette_secret_audit.py` | role-match (subprocess + grep-guard hybrid) |
| 0 | `frontend/src/test/no-legacy-gradient.test.ts` (new) | test/grep-guard | static-guard | `backend/tests/test_pydantic_v1_regression.py` (backend grep) + `frontend/src/test/setup.ts` (vitest scaffold) | role-match (vitest adaptation of backend grep pattern) |
| 0 | `frontend/src/test/no-process-env.test.ts` (new) | test/grep-guard | static-guard | same as `no-legacy-gradient.test.ts` | role-match |
| 0 | `frontend/src/test/extension-content-type.test.ts` (new) | test/grep-guard | static-guard | same as `no-legacy-gradient.test.ts` | role-match |
| 0 | `frontend/src/components/common/RouteGroupBoundary.tsx` (new) | component/error-boundary | request-response | `frontend/src/components/common/ErrorBoundary.tsx` | role-match (class-component → Sentry.ErrorBoundary) |
| 0 | `frontend/src/components/common/RouteGroupBoundary.test.tsx` (new) | test/component | render-time | `frontend/src/components/common/ErrorBoundary.test.tsx` | exact |
| 0 | `frontend/src/App.coverage.test.tsx` (new) | test/parametrized-integration | render-time | `backend/tests/test_admin_auth_coverage.py` + `backend/tests/test_auth_auth_coverage.py` | role-match (parametrized coverage, pytest→vitest) |
| 0 | `.github/workflows/frontend-ci.yml` (modified) | config/ci | — | existing file (edit in place) | exact |
| 0 | `frontend/package.json` (modified) | config/manifest | — | existing file (edit in place) | exact |
| 0 | `frontend/eslint.config.js` (modified) | config/lint | — | existing file (edit in place) | exact |
| 0 | `frontend/06-LINT-BASELINE.txt` (new, committed artifact) | docs/baseline | — | n/a (generated tool output) | no-analog |
| 1 | `terraform/s3.tf` (modified — appends lifecycle resource) | infra/IaC | declarative | existing `aws_s3_bucket "crawl_data"` in same file | exact (co-located declaration) |
| 1 | Frontend `process.env` audit touches (read-only) | source-audit | — | `frontend/src/lib/sentry.ts:12` (docstring; legit) | n/a (no new file) |
| 1 | Tailwind gradient rename: `App.tsx`, `Card.tsx`, `Header.tsx`, `Footer.tsx`, `ChromeExtensionPromo.tsx`, `DeleteConfirmationDialog.tsx`, `SubscriptionPromo.tsx`, `Button.tsx`, `DangerousActionDialog.tsx`, `Home.tsx`, `Support.tsx` | source/style | — | in-place `bg-gradient-to-*` → `bg-linear-to-*` | exact (mechanical codemod) |
| 2 | `frontend/src/api/client.ts` (new — Axios instance + interceptors) | api-client/infrastructure | request-response | `frontend/src/services/Api.ts` lines 65-194 (base URL, axios.create, interceptors, token helpers) | exact (extract existing code) |
| 2 | `frontend/src/api/users.ts` (new) | api-client/domain module | CRUD | `frontend/src/services/Api.ts` lines 196-233 (`usersApi`) + backend `app/api/endpoints/users.py` | exact (split existing export) |
| 2 | `frontend/src/api/parts.ts` (new) | api-client/domain module | CRUD | `frontend/src/services/Api.ts` lines 351-459 (`partsApi`) + backend `app/api/endpoints/parts.py` | exact |
| 2 | `frontend/src/api/{auth,build_lists,build_list_parts,build_list_phases,build_logs,categories,car_generations,part_manufacturers,retailers,votes,reports,images,search,admin,crawled_pages,bug_reports,app_settings}.ts` (new) | api-client/domain modules | CRUD | `frontend/src/services/Api.ts` per-domain `export const` sections (line-ranges in "Pattern Assignments" below) + matching `backend/app/api/endpoints/*.py` | exact |
| 2 | `frontend/src/utils/lazyWithReload.ts` (modified) | utility/type-fix | — | in-place (remove `any`, add `unknown` bound) | exact |
| 3 | `frontend/src/App.tsx` (modified — wrap routes) | app-root/routing | render-time | self (edit in place, insert 4 wrappers at line 192) | exact |
| 4 | `backend/requirements.txt` (modified — PR-A) | config/deps | — | in-place (bump fastapi 0.128→0.136.1, pydantic 2.11→2.13.3) | exact |
| 4 | Chrome extension audit (no code change, guard covers it) | audit | — | `chrome-extension/src/background.ts:81-96` (apiRequest helper already compliant) | n/a |
| 5 | `backend/requirements.txt` (modified — PR-B) | config/deps | — | in-place (bump sqlalchemy/alembic/uvicorn; DELETE jose line 33) | exact |
| 5 | `backend/tests/test_pyjwt_migration.py` (DELETED) | test | — | n/a (file deletion) | n/a |
| 5 | `backend/tests/dependencies/test_auth_utils.py` (modified) | test | — | `backend/app/api/dependencies/auth.py:7` (`import jwt` from PyJWT — the canonical target) | exact |
| 6 | `pages/parts/*`, `components/parts/*` (modified — polish pass) | page/component | — | existing `frontend/src/components/common/Card.tsx` shadow/rounded variants | style-reference |

---

## Pattern Assignments

### Wave 0 — Foundation (Infra before impl)

#### `backend/tests/test_bandit_high_gate.py` (new, test, subprocess + grep-guard hybrid)

**Primary analog:** `backend/tests/test_check_migrations.py` (subprocess-adjacent pattern: imports a script by path, invokes a binary, asserts exit code).
**Secondary analog:** `backend/tests/test_cassette_secret_audit.py` (meta-guard pattern — lines 78-100 show the "inject fixture, prove detection works" shape that QUAL-04 needs).

**Imports + subprocess invocation pattern** (modeled on both):

```python
# Source: test_check_migrations.py lines 1-26 (imports/structure) + test_cassette_secret_audit.py lines 60-75 (body shape)
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
```

**Fixture + assertion pattern** (exactly what RESEARCH.md §Example 4 composes):

```python
@pytest.fixture
def high_severity_fixture(tmp_path: Path) -> Path:
    """Synthetic file with a bandit B602 HIGH-severity finding."""
    src = tmp_path / "fixture.py"
    src.write_text(
        "import subprocess\n"
        "import os\n"
        "user_input = os.environ.get('CMD', '')\n"
        "subprocess.call(user_input, shell=True)  # B602 HIGH\n"
    )
    return src


def test_bandit_fails_on_high_severity(high_severity_fixture: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", str(high_severity_fixture), "-ll"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Severity: High" in result.stdout
```

**xdist-safety note:** `tmp_path` is per-worker in pytest-xdist; no shared-state collisions. Matches `test_check_migrations.py`'s approach at lines 28-31.

---

#### `frontend/src/test/no-legacy-gradient.test.ts` (new, vitest grep-guard)

**Primary analog:** `backend/tests/test_pydantic_v1_regression.py` (the project's canonical grep-guard pattern — file iteration with regex detection + violation collection + aggregated assert).

**File iteration pattern** (port from pytest to vitest — mirror the shape, not the framework):

```python
# Source: backend/tests/test_pydantic_v1_regression.py lines 49-74
def test_no_forbidden_patterns_in_app() -> None:
    offenders: list[tuple[str, int, str]] = []
    for pyfile in BACKEND_APP.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for pat, label in FORBIDDEN_PATTERNS:
                if pat.search(line):
                    offenders.append((str(pyfile.relative_to(BACKEND_APP)), lineno, label))
    assert not offenders, "Forbidden Pydantic v1 patterns found:\n" + "\n".join(...)
```

**Vitest port** (RESEARCH.md §Code Examples Pattern 4, lines 402-421):

```typescript
import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';

describe('FE-05: no bg-gradient-to-* class names in source', () => {
  it('no file contains bg-gradient-to- (Tailwind v3 legacy)', () => {
    const files = globSync('src/**/*.{ts,tsx}', { cwd: `${__dirname}/../..` });
    const violations: Array<{ file: string; line: number; match: string }> = [];
    for (const file of files) {
      const src = readFileSync(file, 'utf8').split('\n');
      src.forEach((line, i) => {
        if (/bg-gradient-to-/.test(line)) {
          violations.push({ file, line: i + 1, match: line.trim() });
        }
      });
    }
    expect(violations).toEqual([]);
  });
});
```

**Allowlist pattern** (if the test itself needs to mention the forbidden string for documentation): lift the `DICT_ALLOWLIST: set[str]` approach from `test_pydantic_v1_regression.py:46`.

---

#### `frontend/src/test/no-process-env.test.ts` (new, vitest grep-guard)

**Same analog and shape as `no-legacy-gradient.test.ts`.** Single regex swap: `/\bprocess\.env\b/`. Allowlist must include `src/lib/sentry.ts` (docstring-only mention, verified at line 12 — "process.env.CI cross-CI standard"). Use the `DICT_ALLOWLIST` pattern from `test_pydantic_v1_regression.py:46` — a `Set<string>` of relative paths with rationale comments.

---

#### `frontend/src/test/extension-content-type.test.ts` (new, vitest grep-guard)

**Same analog and shape as `no-legacy-gradient.test.ts`.** Regex from RESEARCH.md §Example Pattern 4 (lines 386-398):

```typescript
const postRegex = /fetch\([^)]+\{[^}]*method:\s*["']POST["'][^}]*\}/gs;
// For each match: assert Content-Type: application/json OR FormData body
```

**Empirical compliance baseline:** `chrome-extension/src/background.ts:81-96` already sets `"Content-Type": "application/json"` in the shared `apiRequest` helper. Grep will pass on current source; guard is preventive.

---

#### `frontend/src/components/common/RouteGroupBoundary.tsx` (new)

**Primary analog:** `frontend/src/components/common/ErrorBoundary.tsx` — existing class-component pattern, already wires Sentry.captureException, has a styled fallback UI.

**Delta vs analog:** The existing ErrorBoundary uses a handrolled `Component` class; the new RouteGroupBoundary uses `@sentry/react`'s `Sentry.ErrorBoundary` to get `eventId` in the fallback for free (D-08).

**Existing ErrorBoundary fallback UI shape** (copy the Tailwind class conventions, not the structure):

```typescript
// Source: frontend/src/components/common/ErrorBoundary.tsx lines 45-63
<div className="min-h-screen flex items-center justify-center bg-neutral-900">
  <div className="text-center p-8">
    <h1 className="text-4xl font-bold text-red-400 mb-4">
      Something went wrong
    </h1>
    <p className="text-neutral-300 mb-4">
      {this.state.error?.message || 'An unexpected error occurred'}
    </p>
    <button
      type="button"
      onClick={() => window.location.reload()}
      className="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
    >
      Reload Page
    </button>
  </div>
</div>
```

**Sentry import pattern** (already in analog, line 1):

```typescript
import * as Sentry from '@sentry/react';
```

**New component shape** (composes analog UX + Sentry.ErrorBoundary API; RESEARCH.md §Example 1 lines 605-649 is the verbatim starting point — planner may adjust classNames to match dark-theme conventions from ErrorBoundary.tsx):

```typescript
// Source: RESEARCH.md §Example 1 (verified against @sentry/react v10 FallbackRender signature)
import * as Sentry from '@sentry/react';
import { useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';

type GroupName = 'admin' | 'authentication' | 'builder' | 'public';

export function RouteGroupBoundary({
  groupName,
  children,
}: {
  groupName: GroupName;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <Sentry.ErrorBoundary
      beforeCapture={(scope) => scope.setTag('route_group', groupName)}
      fallback={({ error, eventId, resetError }) => (
        <section
          data-route-group={groupName}
          className="container mx-auto px-4 py-16"
        >
          {/* Use same neutral-900/400 tokens as analog ErrorBoundary.tsx */}
          <h2 className="text-2xl font-semibold text-neutral-100 mb-3">
            Something went wrong in the {groupName} section
          </h2>
          <p className="text-sm text-neutral-400 mb-2">
            {(error as Error)?.message ?? 'Unknown error'}
          </p>
          <p className="text-xs text-neutral-500 mb-6">
            Event ID: <code className="font-mono">{eventId}</code>
          </p>
          <div className="flex gap-3">
            <button type="button" onClick={resetError} className="btn-primary">Retry</button>
            <button type="button" onClick={() => navigate('/')} className="btn-secondary">Go Home</button>
          </div>
        </section>
      )}
    >
      {children}
    </Sentry.ErrorBoundary>
  );
}
```

**Note on the `data-route-group` attribute:** required by `App.coverage.test.tsx` for route-group discoverability (see below).

---

#### `frontend/src/components/common/RouteGroupBoundary.test.tsx` (new)

**Primary analog:** `frontend/src/components/common/ErrorBoundary.test.tsx` — exact shape match. Copy:

1. **Mock hoisting pattern** (lines 21-27):

    ```typescript
    const { mockedCapture } = vi.hoisted(() => ({ mockedCapture: vi.fn() }));
    vi.mock('@sentry/react', () => ({
      captureException: mockedCapture,
      // For Sentry.ErrorBoundary, mock the component class too:
      ErrorBoundary: ({ children, fallback }: { children: ReactNode; fallback: FallbackRenderFn }) => ...
    }));
    ```

   (Or — simpler — do NOT mock `Sentry.ErrorBoundary`; let the real component run and verify fallback renders when a child throws. The root ErrorBoundary test took the mock route; the route-group test does not need to.)

2. **Thrower / Safe component pattern** (lines 32-38):

    ```typescript
    function Thrower(): ReactNode { throw new Error('boom'); }
    function Safe(): ReactNode { return <div>all good</div>; }
    ```

3. **Console.error silence** (lines 55-57 — React logs throw messages):

    ```typescript
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    // ...
    errorSpy.mockRestore();
    ```

**Three tests to include:** (a) renders children when no error (matches analog line 41); (b) renders fallback with event ID when child throws; (c) `Retry` button calls `resetError` and restores children (new behavior not in analog — test the D-08 Retry UX).

---

#### `frontend/src/App.coverage.test.tsx` (new)

**Primary analog:** `backend/tests/test_admin_auth_coverage.py` + `backend/tests/test_auth_auth_coverage.py` — parametrized coverage over an enumerated route list.

**Route enumeration pattern** (backend analog, `test_admin_auth_coverage.py` lines 34-43):

```python
def _admin_routes() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/api/admin"):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                out.append((m, r.path))
    return out

ADMIN_ROUTES = _admin_routes()
```

**Parametrize idiom** (line 50):

```python
@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_requires_auth(method: str, path: str, client: TestClient) -> None:
    ...
```

**Drift guard** (line 72-76) — carry this pattern into the vitest port:

```python
def test_admin_route_count_at_or_above_expected() -> None:
    assert len(ADMIN_ROUTES) >= 23, f"Expected >=23 admin routes, got {len(ADMIN_ROUTES)}"
```

**Vitest port** (D-24 = RTL + MemoryRouter; RESEARCH.md §Example 3 lines 707-735 is the starting point):

```typescript
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import App from '../App';

// Hand-enumerated; PR review gates any additions (mirrors the backend allow-list approach in test_auth_auth_coverage.py lines 22-36)
const ALL_ROUTES = [
  { path: '/', group: 'public' },
  { path: '/about', group: 'public' },
  { path: '/login', group: 'authentication' },
  { path: '/admin', group: 'admin' },
  { path: '/profile', group: 'builder' },
  // ... all routes from App.tsx:192-283
] as const;

// Drift guard — mirrors test_admin_auth_coverage.py:72
it('route enumeration is at-or-above expected count', () => {
  expect(ALL_ROUTES.length).toBeGreaterThanOrEqual(36); // count routes in App.tsx
});

describe.each(ALL_ROUTES)('FE-03 route-group coverage: $path', ({ path, group }) => {
  it(`renders within a RouteGroupBoundary(groupName="${group}")`, () => {
    const { container } = render(
      <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>
    );
    expect(container.querySelector(`[data-route-group="${group}"]`)).toBeTruthy();
  });
});
```

**Existing vitest scaffolding:** `frontend/src/test/setup.ts` + `frontend/src/test/utils/TestProviders.tsx` + `.../TestWrapper.tsx` already exist (confirmed via directory listing). Reuse `TestProviders` if route-group boundary needs context providers (auth, premium) to render.

---

#### `.github/workflows/frontend-ci.yml` (modified — insert madge step)

**Current step order** (lines 28-57):

```yaml
- name: Check code formatting           # line 28
- name: Run linting                      # line 33
- name: Run type checking                # line 38
- name: Audit dependencies for vuln...   # line 43
- name: Run tests                        # line 48
- name: Build application                # line 53
```

**Exact insertion point (D-16):** between "Run tests" (line 48-51) and "Build application" (line 53-56). New step:

```yaml
      - name: Check circular imports
        run: |
          cd frontend
          npx madge --circular --extensions ts,tsx src/
```

**YAML-indent anchor to copy:** 6 spaces before `- name:`, 8 spaces before `run: |`, 10 spaces before `cd frontend`. Match exactly with surrounding steps.

---

#### `frontend/package.json` (modified)

**Analog:** the file itself. Add under `devDependencies` (alphabetical ordering preserved):

```json
"madge": "^8.0.0"
```

Plus regenerate `package-lock.json` via `npm install`.

---

#### `frontend/eslint.config.js` (modified)

**Current rule set (lines 48-61)** — the main app block already extends `recommendedTypeChecked` + has react-x, react-dom plugins. `no-unsafe-*` rules come from `recommendedTypeChecked` defaults (they are `error` by default in that preset as of typescript-eslint 8.x).

**What to change (FE-01 D-01 + D-05):**

1. **Explicit `error` reinforcement (insurance against future preset churn)** in the main app block (after line 57):

    ```javascript
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/no-unsafe-assignment': 'error',
    '@typescript-eslint/no-unsafe-call': 'error',
    '@typescript-eslint/no-unsafe-return': 'error',
    '@typescript-eslint/no-unsafe-member-access': 'error',
    '@typescript-eslint/no-unsafe-argument': 'error',
    ```

2. **DELETE the test-file override block** — current lines 63-80:

    ```javascript
    // DELETE this entire block (D-05 ratchets test files to match source rules):
    {
      files: ['src/test/**/*.ts', 'src/test/**/*.tsx'],
      extends: [...tseslint.configs.recommended],
      // ...
      rules: {
        '@typescript-eslint/no-unsafe-assignment': 'off',   // DELETE
        '@typescript-eslint/no-unsafe-call': 'off',         // DELETE
        '@typescript-eslint/no-unsafe-return': 'off',       // DELETE
        '@typescript-eslint/no-unsafe-member-access': 'off',// DELETE
        // ...
      },
    },
    ```

   After deletion, `src/test/**` falls through to the main `src/**/*.ts, src/**/*.tsx` block (line 29) — exactly what D-05 wants.

**Tests (`*.test.ts`, `*.test.tsx`) live alongside source** (confirmed by `find` output: `src/lib/sentry.test.ts`, `src/utils/carUtils.test.ts`, `src/components/common/ErrorBoundary.test.tsx`). The current test-file override only covers `src/test/**` — mocks + utilities. Dropping it applies strict rules to those mock/util files too.

---

### Wave 1 — Parallel-safe small tasks

#### `terraform/s3.tf` (modified — append lifecycle resource)

**Analog:** the existing `aws_s3_bucket "crawl_data"` declaration at lines 20-22 and its `public_access_block` at lines 24-31.

```hcl
# Source: terraform/s3.tf lines 20-31 (existing crawl_data resources)
resource "aws_s3_bucket" "crawl_data" {
  bucket = "${local.prefix}-crawl-data"
}

resource "aws_s3_bucket_public_access_block" "crawl_data" {
  bucket = aws_s3_bucket.crawl_data.id
  # ...
}
```

**Insertion point:** immediately after line 31 (end of `public_access_block.crawl_data`), before the `# --- Frontend SPA --- ` comment at line 33. New resource (from RESEARCH.md §Example 5 + D-19 + Pitfall 4):

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "crawl_data" {
  bucket = aws_s3_bucket.crawl_data.id

  rule {
    id     = "archive-old-snapshots"
    status = "Enabled"

    # Empty filter block = apply to all objects in bucket.
    # DO NOT use `filter { prefix = "" }` — see Pitfall 4 (generates wrong AWS XML).
    filter {}

    transition {
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }
  }
}
```

**Naming convention:** resource name `"crawl_data"` matches the existing `aws_s3_bucket "crawl_data"` — terraform-native pattern for co-located config. The `bucket` attribute uses `aws_s3_bucket.crawl_data.id` (not the literal name), matching the `public_access_block` pattern at line 25.

---

#### Frontend Tailwind gradient rename (11+ files)

**Affected files** (per CONTEXT.md line 137 + RESEARCH.md Component Responsibilities):

- `frontend/src/App.tsx` (lines 133, 149, 151, 155 — 4 occurrences)
- `frontend/src/components/layout/globalFooter/Footer.tsx`
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/common/Card.tsx`
- `frontend/src/components/common/ChromeExtensionPromo.tsx`
- `frontend/src/components/common/DeleteConfirmationDialog.tsx`
- `frontend/src/components/common/DangerousActionDialog.tsx`
- `frontend/src/components/common/SubscriptionPromo.tsx`
- `frontend/src/components/common/Button.tsx`
- `frontend/src/pages/Home.tsx`, `.../Support.tsx`

**Pattern = in-place string substitution.** RESEARCH.md §Pitfall 2 table (lines 531-541) maps all 8 directional variants. Example from `App.tsx:133`:

```tsx
// BEFORE:
<div className="relative flex flex-col min-h-screen bg-gradient-to-br from-neutral-900 via-neutral-800 to-neutral-900">

// AFTER:
<div className="relative flex flex-col min-h-screen bg-linear-to-br from-neutral-900 via-neutral-800 to-neutral-900">
```

**Only change the class prefix.** `from-*`, `via-*`, `to-*` stops stay identical (those are Tailwind v4-native color stops, not v3 gradient direction).

---

### Wave 2 — Typing rollout + Api.ts split (D-22)

#### `frontend/src/api/client.ts` (new)

**Primary analog:** `frontend/src/services/Api.ts` lines 65-194 — extract verbatim.

**What to carry across:**

- `normalizeApiUrl` (lines 65-71)
- `getApiBaseUrl` (lines 74-110)
- `apiClient = axios.create(...)` (lines 113-137) including `paramsSerializer` — load-bearing for array-valued params like `ids`, `category_ids`
- Token helpers: `getStoredToken`, `setStoredToken`, `removeStoredToken` (lines 143-155)
- Request interceptor: `apiClient.interceptors.request.use(...)` for Bearer token (lines 158-171)
- Response interceptor: `apiClient.interceptors.response.use(...)` for x-new-access-token header handling + 401 passthrough (lines 173-194)

**Default export:** the `apiClient` instance. Domain modules import it via `import { apiClient } from './client'`.

**Import pattern for this file:**

```typescript
// Source: Api.ts line 1
import axios, { type AxiosError, type AxiosResponse } from 'axios';
```

---

#### `frontend/src/api/users.ts` (new — FE-04 co-located types + D-22 domain split)

**Primary analog (frontend):** `frontend/src/services/Api.ts` lines 196-233 (`usersApi` export) — copy verbatim.
**Structural mirror (backend):** `backend/app/api/endpoints/users.py` — confirms endpoint path pattern (`/users/`, `/users/{user_id}`, `/users/me`, `/users/count`, `/users/admin/users`, `/users/me/profile-picture`). The frontend domain module is a 1:1 mirror of the backend domain module.

**Export shape** (copy from `Api.ts:197-233`):

```typescript
// Source: frontend/src/services/Api.ts lines 197-233
export const usersApi = {
  getMe: () => apiClient.get<UserRead>('/users/me'),
  createUser: (data: UserCreate) => apiClient.post<UserRead>('/users/', data),
  getUser: (userId: string) => apiClient.get<UserRead>(`/users/${userId}`),
  updateUser: (userId: string, data: UserUpdate) =>
    apiClient.put<UserRead>(`/users/${userId}`, data),
  deleteUser: (userId: string) =>
    apiClient.delete<UserRead>(`/users/${userId}`),

  // Profile picture endpoints — NOTE: FormData body keeps 'Content-Type': 'multipart/form-data'
  uploadProfilePicture: (file: File): Promise<{ data: UserRead }> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<UserRead>('/users/me/profile-picture', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // ... remaining methods
};
```

**FE-04 narrowing addition (D-03 pattern from RESEARCH.md §Pattern 3):** For any method currently using `as any` or an untyped response, replace with `unknown` + type predicate:

```typescript
// Source: RESEARCH.md §Pattern 3 lines 344-361
function isUserRead(data: unknown): data is UserRead {
  return (
    typeof data === 'object' && data !== null &&
    'id' in data && 'username' in data && 'email' in data
  );
}
// Narrow at the module boundary; pages import already-typed results.
```

**Co-location pattern (D-04):** Response types for users live in `frontend/src/api/users.ts`, imported into pages. Existing pydantic-generated types stay in `frontend/src/types/Api.ts` and are re-imported here.

**Imports for this file:**

```typescript
import { apiClient } from './client';
import type {
  AdminUserUpdate,
  PaginatedResponse,
  UserCreate,
  UserRead,
  UserUpdate,
} from '../types/Api';
```

---

#### `frontend/src/api/{parts,auth,build_lists,...}.ts` (new — the remaining 16 domain modules)

**Same pattern as `users.ts`.** Per-domain source line-ranges in `Api.ts` (from grep output):

| New file | Source lines in `Api.ts` | Backend mirror |
|----------|--------------------------|----------------|
| `api/users.ts` | 197-233 | `endpoints/users.py` |
| `api/car_generations.ts` | 236-273 | `endpoints/car_generations.py` |
| `api/build_lists.ts` | 276-342 + votes 615-631 + reports | `endpoints/build_lists.py` |
| `api/build_list_phases.ts` | 343-350 | `endpoints/build_list_phases.py` |
| `api/parts.ts` | 351-460 + votes 602-613 + reports 633-659 | `endpoints/parts.py` |
| `api/categories.ts` | 461-479 | `endpoints/categories.py` |
| `api/part_manufacturers.ts` | 480-528 | `endpoints/part_manufacturers.py` |
| `api/retailers.ts` | 529-533 | `endpoints/retailers.py` |
| `api/votes.ts` | 534-562 + 602-631 | `endpoints/votes.py` |
| `api/reports.ts` | 563-601 + 633-659 | `endpoints/reports.py` |
| `api/build_list_parts.ts` | 661-746 | `endpoints/build_list_parts.py` |
| `api/auth.ts` | 747-934 | `endpoints/auth/*` (auth module has sub-files: core, webauthn, oauth) |
| `api/search.ts` | 935-940 | `endpoints/search.py` |
| `api/utility.ts` | 941-957 | n/a (health/etc) |
| `api/images.ts` | 958-1037 | `endpoints/images.py` |
| `api/build_logs.ts` | 1038-1065 | `endpoints/build_logs.py` |
| `api/bug_reports.ts` | 1066-1378 | `endpoints/bug_reports.py` |
| `api/app_settings.ts` | 1379-1386 | `endpoints/app_settings.py` |
| `api/admin.ts` | 1387-end | `endpoints/admin/*` |

**Copy rule:** take the `export const fooApi = { ... }` block verbatim; add `import { apiClient } from './client'` and import only the types referenced by that block from `../types/Api`. The existing giant import list at `Api.ts:2-63` is split proportionally across the 17 domain files.

**Backend mirror for endpoint path confirmation** (excerpt from `backend/app/api/endpoints/users.py:57-64` — the frontend `/users/me` maps to this):

```python
@router.get("/me", response_model=UserRead)
async def read_users_me_route(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    return current_user
```

---

#### `frontend/src/utils/lazyWithReload.ts` (modified — FE-01/D-06)

**Analog:** the file itself. Lines 22-23 contain the only `any` in source:

```typescript
// Source: frontend/src/utils/lazyWithReload.ts lines 22-23 (CURRENT)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function lazyWithReload<T extends ComponentType<any>>(
```

**Planner's options (D-06):**

```typescript
// Option A: wide unknown bound
export function lazyWithReload<T extends ComponentType<unknown>>(

// Option B: props-object bound
export function lazyWithReload<T extends ComponentType<Record<string, unknown>>>(
```

D-06 says the planner picks based on which makes React.lazy's type inference thread cleanly through the ~40 `lazy(() => import('./pages/...'))` call-sites in `App.tsx:34-83`. Also remove the `// eslint-disable-next-line` comment on line 22 (becomes stale).

---

### Wave 3 — Route-group wrapper wiring

#### `frontend/src/App.tsx` (modified — insert 4 RouteGroupBoundary wrappers)

**Analog:** the file itself, lines 192-304 (current `<Routes>` tree).

**Insertion pattern** (RESEARCH.md §Example 2 lines 654-698 is the blueprint):

```tsx
// BEFORE — App.tsx:192-201 (current structure)
<Routes>
  {/* Public Routes */}
  <Route path="/" element={<Home />} />
  <Route element={<GuestRoute />}>
    <Route path="/login" element={<Login />} />
    ...
  </Route>

// AFTER — group public/auth/builder/admin under RouteGroupBoundary wrappers:
<Routes>
  <Route element={<RouteGroupBoundary groupName="public"><Outlet /></RouteGroupBoundary>}>
    <Route path="/" element={<Home />} />
    <Route path="/about" element={<About />} />
    ...
  </Route>

  <Route element={<RouteGroupBoundary groupName="authentication"><Outlet /></RouteGroupBoundary>}>
    <Route element={<GuestRoute />}>
      <Route path="/login" element={<Login />} />
      ...
    </Route>
    ...
  </Route>

  <Route element={<RouteGroupBoundary groupName="builder"><Outlet /></RouteGroupBoundary>}>
    <Route element={<ProtectedRoute />}>
      ...
    </Route>
  </Route>

  <Route element={<RouteGroupBoundary groupName="admin"><Outlet /></RouteGroupBoundary>}>
    <Route path="/admin" element={<AdminDashboard />} />
    ...
  </Route>
</Routes>
```

**Additional imports needed in App.tsx:**

```typescript
import { Outlet, ... } from 'react-router-dom'; // Outlet is new
import { RouteGroupBoundary } from './components/common/RouteGroupBoundary';
```

**Do NOT change:** the existing top-level `<ErrorBoundary>` at line 132 (D-09 keeps it) and the `<Suspense>` at line 185 (D-09 keeps it). The 4 RouteGroupBoundaries live INSIDE the Suspense, OUTSIDE the ProtectedRoute/GuestRoute auth guards where appropriate.

---

### Wave 4 — PR-A (FastAPI 0.136 + Pydantic 2.13)

#### `backend/requirements.txt` (modified — PR-A)

**Analog:** the file itself. Lines to update (from current file contents):

```diff
- fastapi==0.128.0
+ fastapi==0.136.1
- pydantic==2.11.3
+ pydantic==2.13.3
- pydantic_core==2.33.1
+ # Let pydantic pin pydantic_core; remove explicit pin (or verify new pinned value after pip install)
```

**pydantic_core note:** Pydantic 2.13.x ships with an updated pydantic_core version. The explicit pin at line 11 (`pydantic_core==2.33.1`) should be removed and allowed to resolve transitively via `pip install`. If CI insists on a pin, capture the new pydantic_core version after running `pip install -r requirements.txt` locally.

**Validation guards this rides (D-13):**
- `backend/tests/test_pydantic_v1_regression.py` — already exists, catches Pydantic 2.13 deprecations via `catch_warnings`.
- `backend/tests/test_openapi_snapshot.py` — already exists, catches FastAPI 0.136 schema drift.
- `backend/tests/test_auth_auth_coverage.py` + `.../test_admin_auth_coverage.py` — auth characterization, already parametrized.

---

### Wave 5 — PR-B (SQLAlchemy/Alembic/Uvicorn + jose removal)

#### `backend/requirements.txt` (modified — PR-B)

**Analog:** the file itself.

```diff
- sqlalchemy==2.0.41
+ sqlalchemy==2.0.49
- alembic==1.16.2
+ alembic==1.18.4
- uvicorn==0.34.0
+ uvicorn==0.45.0
- # python-jose — KEPT through Phase 5 only for test_pyjwt_migration.py parity assertion.
- # Scheduled for removal in Phase 6 dependency cleanup.
- # Note: python-jose depends on ecdsa (CVE-2024-23342), not exploitable in HS256-only usage.
- python-jose[cryptography]==3.5.0
```

**Exact lines to delete:** `backend/requirements.txt` lines 30-33 (comment block + the `python-jose[cryptography]==3.5.0` line).

---

#### `backend/tests/test_pyjwt_migration.py` (DELETED — D-14)

**No analog needed** — file removal. `git rm backend/tests/test_pyjwt_migration.py`.

---

#### `backend/tests/dependencies/test_auth_utils.py` (modified — D-23 migrate to PyJWT)

**Primary analog:** `backend/app/api/dependencies/auth.py:7` — the canonical PyJWT import in production code. Also `backend/app/api/endpoints/auth/core.py:12`, `.../webauthn.py:14`, `.../oauth.py:13` — same `import jwt` pattern everywhere in production.

**Current import** (line 3):

```python
# Source: backend/tests/dependencies/test_auth_utils.py line 3 (CURRENT)
from jose import jwt
```

**Target import (mirroring production auth.py:7):**

```python
# Source: backend/app/api/dependencies/auth.py line 7 (the canonical pattern)
import jwt
```

**API migration notes:** `jose.jwt.decode(token, secret, algorithms=[ALG])` → `jwt.decode(token, secret, algorithms=[ALG])` — signature is identical for HS256. Only changes are:

1. Line 3: `from jose import jwt` → `import jwt`
2. Lines 51, 67 (verified in file): `jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])` — no change, symbol `jwt` resolves to PyJWT instead.

**Exception imports** (if the test ever catches `jose.JWTError`): migrate to `jwt.InvalidTokenError`. Check current file for any exception handling (none found in the 72-line file).

**Verification command (D-14 static grep):**

```bash
! grep -rn "from jose\|import jose" backend/
```

---

### Wave 6 — Opportunistic polish (FE-07)

#### `pages/parts/*` and `components/parts/*` (modified — bounded polish pass)

**Primary style analog:** `frontend/src/components/common/Card.tsx` — the existing shadow/rounded-corner/padding token vocabulary. Polish checklist (D-17) follows this file's variants.

**Other referenced patterns:** `frontend/src/pages/Home.tsx` typography hierarchy (`text-3xl` landing → `text-2xl` section → `text-xl` card).

**No code excerpts needed** — this is aesthetic convergence, not structural pattern-copy. The checklist is drafted by the planner (per D-17) and UAT-approved.

---

## Shared Patterns

### Authentication / Bearer token handling
**Source:** `frontend/src/services/Api.ts` lines 158-171 (request interceptor).
**Apply to:** `frontend/src/api/client.ts` — copy verbatim.

```typescript
apiClient.interceptors.request.use(
  (config) => {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error instanceof Error ? error : new Error(String(error)))
);
```

### Error handling (Axios → Error guarantee)
**Source:** `frontend/src/services/Api.ts` lines 183-193 (response interceptor error path).
**Apply to:** `frontend/src/api/client.ts` response interceptor; all domain modules inherit this.

```typescript
apiClient.interceptors.response.use(
  (response) => { ... },
  (error: unknown) => {
    const axiosError = error as AxiosError;
    if (axiosError.response?.status === 401) { /* ... */ }
    return Promise.reject(error instanceof Error ? error : new Error(String(error)));
  }
);
```

### Grep-guard test shape (used 3× in Wave 0)
**Source:** `backend/tests/test_pydantic_v1_regression.py` lines 31-74 (Python canonical) + RESEARCH.md §Example Pattern 4 (TypeScript port).
**Apply to:** `no-legacy-gradient.test.ts`, `no-process-env.test.ts`, `extension-content-type.test.ts`.

Common structure: (1) define forbidden regex + optional allowlist; (2) glob over target source tree; (3) collect violations into array; (4) single `expect(violations).toEqual([])` assertion.

### Parametrized coverage with drift guard
**Source:** `backend/tests/test_admin_auth_coverage.py` lines 34-76 + `test_auth_auth_coverage.py` lines 39-59.
**Apply to:** `frontend/src/App.coverage.test.tsx`.

Common structure: (1) enumerate from canonical source (backend: `app.routes`; frontend: hand-maintained list); (2) `parametrize`/`describe.each` over enumeration; (3) drift guard with "count at or above N" assertion.

### Subprocess-invoking pytest
**Source:** `backend/tests/test_check_migrations.py` lines 14-25 (sys.path manipulation for script imports) + RESEARCH.md §Example 4 (subprocess.run pattern).
**Apply to:** `backend/tests/test_bandit_high_gate.py`.

xdist-safe: uses `tmp_path` fixture for per-worker isolation; no shared state.

### Sentry error capture wiring
**Source:** `frontend/src/components/common/ErrorBoundary.tsx` lines 1, 24-37 (import + componentDidCatch + captureException).
**Apply to:** `RouteGroupBoundary.tsx` — but via Sentry.ErrorBoundary's built-in `beforeCapture` / `onError` props, not a hand-rolled `componentDidCatch`. The existing ErrorBoundary stays at app root (D-09).

### Test mock hoisting (vitest)
**Source:** `frontend/src/components/common/ErrorBoundary.test.tsx` lines 21-27 (`vi.hoisted` pattern for Sentry mock).
**Apply to:** `RouteGroupBoundary.test.tsx` if the planner mocks `@sentry/react` (optional — can let the real ErrorBoundary run).

### Terraform resource co-location
**Source:** `terraform/s3.tf` lines 4-31 (existing `user_images` + `crawl_data` buckets each paired with `public_access_block` immediately below).
**Apply to:** QUAL-08 lifecycle rule — place immediately after `public_access_block.crawl_data` (line 31), before the `Frontend SPA` comment at line 33.

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `frontend/06-LINT-BASELINE.txt` | generated tool output / committed artifact | Not a code file; output of `npm run lint` captured via `tee`. The only similar artifact in-repo is per-phase planning docs. Planner just needs to run the command and commit the result per D-02. |
| Chrome extension `chrome-extension/src/**/*.ts` (no modifications) | audit target | Nothing new is built; the QUAL-06 grep guard verifies zero-code-change compliance. `background.ts:81-96` confirmed already compliant. |

---

## Metadata

**Analog search scope:**
- `frontend/src/components/common/*.tsx`
- `frontend/src/services/Api.ts` (full file, 1520 lines — scanned via grep for `export const`, then targeted reads)
- `frontend/src/test/**`
- `frontend/eslint.config.js`
- `frontend/src/App.tsx`, `utils/lazyWithReload.ts`
- `backend/tests/test_*.py` (grep-guard + subprocess + parametrized-coverage analogs)
- `backend/tests/dependencies/test_auth_utils.py`
- `backend/app/api/endpoints/users.py` (backend-domain mirror reference)
- `backend/app/api/dependencies/auth.py` (PyJWT import canonical)
- `backend/requirements.txt`
- `terraform/s3.tf`
- `.github/workflows/frontend-ci.yml`
- `chrome-extension/src/background.ts`

**Files scanned:** ~35 source + config files across 4 workspaces (frontend, backend, terraform, chrome-extension, CI).

**Pattern extraction date:** 2026-04-23.

**Key cross-wave observations:**
- The codebase already has a robust grep-guard tradition (`test_pydantic_v1_regression.py`, `test_cassette_secret_audit.py`) — Phase 6 Wave 0 adds 3 more vitest-side variants on top.
- Parametrized coverage tests are an established Phase 5 pattern (`test_admin_auth_coverage.py`, `test_auth_auth_coverage.py`) — FE-03 is the frontend adaptation.
- The current `frontend/src/services/Api.ts` is already domain-sectioned via `export const *Api` blocks (24 of them) — the D-22 split is mechanical extraction, not a refactor, which keeps the blast radius small.
- `ErrorBoundary.tsx` + `ErrorBoundary.test.tsx` are a clean pair that the RouteGroupBoundary pair can pattern-match 1:1.
- Terraform s3.tf structure (bucket + public_access_block co-located) makes the QUAL-08 insertion point unambiguous.
