# Phase 8: Frontend Coverage Expansion (SAFE-03) — Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** ~80 new test files across 6 waves + 5 modified infrastructure files
**Analogs found:** 9 / 10 strong analogs located. 1 pattern (`renderHook` + `vi.useFakeTimers`) has no existing in-repo analog — Wave 2/4 will introduce first use.

**Bounded scope note:** Rather than enumerate one row per new test file (~80 rows), clusters are keyed by pattern-kind (API test, hook test, context test, page test, admin page test, component test). Every file in a cluster applies the same skeleton.

---

## File Classification

| New File Cluster | Count | Role | Data Flow | Closest Analog | Match Quality |
|------------------|-------|------|-----------|----------------|---------------|
| `frontend/vitest.config.ts` (modify) | 1 | config | n/a | itself (D-13 additions + D-22 uncomment) | exact (self) |
| `frontend/src/test/setup.ts` (modify) | 1 | test-infra | global mock | itself + `vi.mock('../services/Api')` block | exact (self) |
| `frontend/src/test/utils/test-mocks.ts` (modify) | 1 | test-infra | auth mock | existing `mockUseAuth` typed against `AuthContextType` | exact (self) |
| `frontend/src/test/utils/test-utils.tsx` (modify) | 1 | test-infra | provider fixtures | existing `testScenarios.authenticated/unauthenticated/loading` | exact (self) |
| `frontend/src/test/mocks/admin/*.ts` | 7 | test-infra | fixture | `frontend/src/test/mocks/api.ts` (`mockUser`, `mockPart`, `setupApiMocks`) | role-match |
| `frontend/src/test/utils/async.ts` | 1 | test-infra | timer utilities | **no analog** — first-use of `vi.useFakeTimers` in repo | none (new pattern) |
| `frontend/src/test/guards/README.md` + relocated guards | 4 | docs + test | lint guard | `frontend/src/test/no-process-env.test.ts` (moves as-is) | exact (self) |
| `frontend/src/api/*.test.ts` (API domain tests) | 19 | unit test | request-response | **NO existing API-module test exists**. Closest primitive: `frontend/src/utils/carUtils.test.ts` pure-function skeleton; mocking primitives from `frontend/src/test/setup.ts` | role-match (partial) |
| `frontend/src/api/admin.test.ts` (solo plan) | 1 | unit test | CRUD + admin | same as above | role-match |
| `frontend/src/api/client.test.ts` | 1 | unit test | env + interceptor | `frontend/src/lib/sentry.test.ts` (`vi.stubEnv` + dynamic-import) | exact |
| `frontend/src/hooks/*.test.{ts,tsx}` | 11 | hook test | state/effect | **no existing `renderHook` test**. `@testing-library/react` docs pattern only. | none (first use) |
| `frontend/src/contexts/*.test.tsx` | 2 | provider test | state transitions | `frontend/src/components/common/RouteGroupBoundary.test.tsx` (render + fireEvent + assert) | role-match |
| `frontend/src/pages/authentication/*.test.tsx` | 7 | page test | form + auth | `frontend/src/components/common/RouteGroupBoundary.test.tsx` (MemoryRouter + render + screen) + `App.coverage.test.tsx` (auth mock pattern) | role-match |
| `frontend/src/pages/builder/*.test.tsx` | 4 | page test | fetch + render | same analogs as above | role-match |
| `frontend/src/pages/parts/*.test.tsx` | 3 | page test | fetch + render | same | role-match |
| `frontend/src/pages/buildLists/*.test.tsx` | 2 | page test | fetch + list + form | same | role-match |
| `frontend/src/pages/*.test.tsx` (public top-level) | 14 | page test | render + static | same + `RouteGroupBoundary.test.tsx` | role-match |
| `frontend/src/pages/admin/CrawlerAdmin.test.tsx` | 1 | page test | polling + fetch | same + **no timer analog** — first-use of `vi.useFakeTimers` | partial (needs new pattern) |
| `frontend/src/pages/admin/*.test.tsx` (4 others) | 4 | page test | fetch + render + form | Wave 3 page-test pattern | role-match |
| `frontend/src/components/**/*.test.tsx` (gap-fill) | TBD | component test | render | `frontend/src/components/common/RouteGroupBoundary.test.tsx` (primary analog) | exact |

---

## Pattern Assignments

### 1. `frontend/src/test/setup.ts` (modified — D-18)

**Analog:** itself — augment existing `vi.mock('../services/Api')` block.

**Current content** (`frontend/src/test/setup.ts:1-16`):
```ts
import '@testing-library/jest-dom';
import { vi, beforeAll, afterAll } from 'vitest';

// Mock the API client to prevent network requests during tests
const mockApiClient = {
  get: vi.fn().mockResolvedValue({ data: null }),
  post: vi.fn().mockResolvedValue({ data: null }),
  put: vi.fn().mockResolvedValue({ data: null }),
  delete: vi.fn().mockResolvedValue({ data: null }),
  patch: vi.fn().mockResolvedValue({ data: null }),
};

vi.mock('../services/Api', () => ({
  default: mockApiClient,
}));
```

**D-18 target pattern:** add a sibling `vi.mock('../api/client', ...)` **that points to the same `mockApiClient` object.** Because `services/Api.ts` is `export { apiClient as default } from '../api/client'` (VERIFIED at `frontend/src/services/Api.ts:7`), both mocks resolve to the same module identity and cannot diverge.

```ts
// ADD alongside the existing block, reusing the same mockApiClient
vi.mock('../api/client', () => ({
  default: mockApiClient,
  apiClient: mockApiClient,
  // Note: setStoredToken/getStoredToken/removeStoredToken also live in api/client.
  // Per-test overrides can stub these via vi.mocked() if needed; default is vi.fn().
  setStoredToken: vi.fn(),
  getStoredToken: vi.fn(() => null),
  removeStoredToken: vi.fn(),
}));
```

**Critical:** per research §Pitfall 7 + §Assumptions Log A1, Wave 0's executor MUST open `frontend/src/services/Api.ts` and confirm the `export { apiClient as default } from '../api/client'` shim pattern BEFORE landing this change.

---

### 2. `frontend/src/test/utils/test-mocks.ts` (modified — D-05)

**Analog:** itself — extend existing pattern.

**Current content** (`frontend/src/test/utils/test-mocks.ts:1-15`):
```ts
import { vi } from 'vitest';
import type { AuthContextType } from '../../contexts/AuthContextDefinition';

type MockAuthState = {
  [K in keyof AuthContextType]?: AuthContextType[K] | undefined;
};

export const mockUseAuth = vi.fn<() => MockAuthState>();
```

**D-05 target pattern:** add typed fixtures using the existing `mockUser` shape from `frontend/src/test/mocks/api.ts:12-25`:

```ts
// Imports from test/mocks/api.ts — mockUser already exists there.
import { mockUser } from '../mocks/api';
import type { UserRead } from '../../types/Api';

// Do NOT assign explicit undefined per Pitfall 2 (exactOptionalPropertyTypes).
// Compose from the canonical mockUser rather than hand-roll.
export const mockAdminUser: UserRead = { ...mockUser, is_admin: true };
export const mockSuperuserUser: UserRead = {
  ...mockUser,
  is_admin: true,
  is_superuser: true,
};
```

---

### 3. `frontend/src/test/utils/test-utils.tsx` (modified — D-05)

**Analog:** itself — extend `testScenarios` block.

**Current pattern** (`frontend/src/test/utils/test-utils.tsx:126-148`):
```tsx
export const testScenarios = {
  authenticated: {
    initialAuthState: {
      isAuthenticated: true,
      user: createMockUser(),
      isLoading: false,
    },
  },
  unauthenticated: {
    initialAuthState: {
      isAuthenticated: false,
      user: null,
      isLoading: false,
    },
  },
  loading: {
    initialAuthState: {
      isAuthenticated: false,
      user: null,
      isLoading: true,
    },
  },
};
```

**D-05 additions (copy pattern):**
```tsx
// ADD to testScenarios object above. Reuse mockAdminUser/mockSuperuserUser
// from ./test-mocks.ts so the user shapes stay canonical.
import { mockAdminUser, mockSuperuserUser } from './test-mocks';

adminAuthenticated: {
  initialAuthState: {
    isAuthenticated: true,
    user: mockAdminUser,
    isLoading: false,
  },
},
superuserAuthenticated: {
  initialAuthState: {
    isAuthenticated: true,
    user: mockSuperuserUser,
    isLoading: false,
  },
},
```

---

### 4. `frontend/src/test/mocks/admin/*.ts` (new — D-06)

**Analog:** `frontend/src/test/mocks/api.ts` — 7 new files follow its factory pattern.

**Imports pattern** (`frontend/src/test/mocks/api.ts:1-9`):
```ts
import { vi } from 'vitest';
import type {
  BuildListRead,
  CarGenerationRead,
  // ... typed imports, not `as any`
} from '../../types/Api';
```

**Factory pattern** (per Pitfall 6 — Vitest parallelizes per-file, so mutable singletons leak):

Per research §Pitfall 6 ("admin/*.ts mock fixtures leak between parallel test files"), each file MUST export either a **factory function** (e.g. `makeJobsList()`) OR a **frozen constant**. Do NOT export mutable arrays that a test can `.push()` to.

```ts
// frontend/src/test/mocks/admin/jobs.ts — NEW
import type { BackgroundJob, BackgroundJobList } from '../../../api/admin';

export const makeJob = (overrides: Partial<BackgroundJob> = {}): BackgroundJob => ({
  id: '99999999-9999-7999-8999-999999999999',
  job_type: 'crawler_run',
  status: 'completed',
  triggered_by: 'manual',
  params: null,
  result_summary: null,
  error_message: null,
  started_at: '2026-04-24T00:00:00Z',
  completed_at: '2026-04-24T00:05:00Z',
  last_heartbeat_at: null,
  worker_instance_id: null,
  created_by_user_id: null,
  ...overrides,
});

export const makeJobsList = (opts: { running?: boolean } = {}): BackgroundJobList => ({
  items: [
    opts.running ? makeJob({ status: 'running', completed_at: null }) : makeJob(),
  ],
  total: 1,
  limit: 25,
  offset: 0,
});
```

Same factory pattern for `reports.ts`, `bugs.ts`, `users.ts`, `crawlers.ts`, `stats.ts`, `curation.ts`. Each imports only the types it needs from the corresponding admin API type surface (`frontend/src/api/admin.ts`).

---

### 5. `frontend/src/test/utils/async.ts` (new — D-07)

**Analog:** **NO existing analog in the repo.** `grep -l "useFakeTimers" /home/tyler-webb/.../frontend/src` returns zero hits. This file is the first-use.

**Pattern source:** Vitest docs (Context7 `/vitest-dev/vitest` — `docs/api/vi.md` + `docs/guide/mocking.md`).

**Research §1 verdict:** keep only the `vi.useFakeTimers` helpers; DELETE the EventSource stub (CrawlerAdmin uses NO SSE — verified).

```ts
// frontend/src/test/utils/async.ts — NEW
import { act } from '@testing-library/react';
import { vi } from 'vitest';

/**
 * Enter fake-timer mode. Pair with `stopFakeTimers()` in afterEach.
 * Use `{ toFake: ['setInterval', 'setTimeout'] }` to leave microtasks alone —
 * research §Pitfall 5 + §Assumptions Log A4 flag that full fake-timer mode
 * can interact badly with async `waitFor` calls.
 */
export function startFakeTimers() {
  vi.useFakeTimers({ toFake: ['setInterval', 'setTimeout', 'Date'] });
}

export function stopFakeTimers() {
  vi.useRealTimers();
}

/**
 * Advance timers and flush React state updates. ALWAYS await this wrapper in
 * polling tests — per Pitfall 5 bare `vi.advanceTimersByTime()` leaves React
 * with an unflushed batch and assertions see stale DOM.
 */
export async function advanceTimersAndFlush(ms: number): Promise<void> {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
}
```

---

### 6. `frontend/src/test/guards/` (relocation — D-17)

**Analog:** `frontend/src/test/no-process-env.test.ts` (and its two siblings) move as-is. The test logic does not change.

**Current pattern** (`frontend/src/test/no-process-env.test.ts:1-29`) — copy for reference:
```ts
import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

describe('FE-02: no process.env in frontend browser source (use import.meta.env.VITE_*)', () => {
  it('no non-allowlisted src file contains process.env', () => {
    const srcDir = resolve(__dirname, '..', '..');
    const files = globSync('src/**/*.{ts,tsx}', {
      cwd: srcDir,
      absolute: true,
    });
    const allowlist = new Set([
      resolve(srcDir, 'src/lib/sentry.ts'),
      resolve(__dirname, 'no-process-env.test.ts'), // this guard itself
    ]);
    // ...
  });
});
```

**Relocation note:** `__dirname` in `src/test/no-process-env.test.ts` points to `src/test/`. After move to `src/test/guards/`, `__dirname` changes to `src/test/guards/` — `resolve(__dirname, '..', '..')` still resolves to `frontend/` so the `cwd: srcDir + 'src/**/*.{ts,tsx}'` glob continues to work. The allowlist `resolve(__dirname, 'no-process-env.test.ts')` also stays correct because it's relative to the test file's own directory. **No code change required in any of the 3 guards** — only the README.md is new.

`frontend/src/test/guards/README.md` is a NEW ~15-line doc stub explaining the guards' role (no analog in repo; planner/executor composes prose per CLAUDE.md style).

---

### 7. Wave 1: `frontend/src/api/*.test.ts` — API module tests (D-08)

**Analog:** **No existing API-module test exists.** Closest primitives are:
- `frontend/src/test/setup.ts` — the mocked `apiClient` (imports resolve to `mockApiClient`).
- `frontend/src/utils/carUtils.test.ts` — pure-function assert skeleton for the describe/it shape.
- Pattern 1 in RESEARCH.md §Architecture Patterns — provides the canonical skeleton.

**Canonical skeleton** (apply to every `api/*.test.ts`):

```ts
// frontend/src/api/build_lists.test.ts — EXAMPLE
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { buildListsApi } from './build_lists';
import { mockBuildList } from '../test/mocks/api';

describe('buildListsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getBuildList hits /build-lists/:id with GET', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockBuildList });

    const result = await buildListsApi.getBuildList(mockBuildList.id);

    expect(apiClient.get).toHaveBeenCalledWith(
      `/build-lists/${mockBuildList.id}`
    );
    expect(result.data).toEqual(mockBuildList);
  });

  it('createBuildList POSTs body to /build-lists/', async () => {
    const body = { name: 'Test', car_id: mockBuildList.car_id };
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...mockBuildList, ...body },
    });

    await buildListsApi.createBuildList(body);

    expect(apiClient.post).toHaveBeenCalledWith('/build-lists/', body);
  });
});
```

**FormData variant** (ONLY for `images.test.ts` and `users.test.ts` per research §2):

Per `frontend/src/api/images.ts:36-54` and `frontend/src/api/users.ts:22-30`, `uploadImage` and `uploadProfilePicture` build a `FormData` and set a multipart Content-Type override. Assert both.

```ts
// In images.test.ts:
it('uploadImage posts FormData with multipart content-type', async () => {
  const file = new File(['x'], 'test.jpg', { type: 'image/jpeg' });
  vi.mocked(apiClient.post).mockResolvedValueOnce({
    data: { file_key: 'k', presigned_url: 'u', message: 'ok' },
  });

  await imageApi.uploadImage(file, 'part', 'abc-123');

  expect(apiClient.post).toHaveBeenCalledWith(
    '/images/upload?entity_type=part&entity_id=abc-123',
    expect.any(FormData),
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  // Assert FormData contents (FormData is iterable in jsdom):
  const fd = vi.mocked(apiClient.post).mock.calls[0][1] as FormData;
  expect(fd.get('file')).toBe(file);
});
```

---

### 8. Wave 1: `frontend/src/api/client.test.ts` — dedicated interceptor + env test

**Analog:** `frontend/src/lib/sentry.test.ts` — the `vi.stubEnv` + dynamic-import pattern (MEDIUM-confidence per research §Sources).

**Pattern excerpt** (`frontend/src/lib/sentry.test.ts:46-76`):
```ts
describe('initSentry — env gate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  it('no-ops when MODE is development', async () => {
    vi.stubEnv('MODE', 'development');
    vi.stubEnv('VITE_SENTRY_DSN', 'https://x@y/1');
    const { initSentry } = await import('./sentry');
    initSentry();
    expect(mockedInit).not.toHaveBeenCalled();
  });
});
```

**Apply to `client.ts` tests.** Dedicated file must cover, per research §2 "Dedicated `client.ts` test content":
- `getStoredToken` / `setStoredToken` / `removeStoredToken` round-trip via `localStorage`.
- Request interceptor adds `Authorization: Bearer <token>` when token present; omits otherwise.
- Response interceptor stores `x-new-access-token` response header; on 401 does NOT redirect (commented-out behavior preserved per `api/client.ts:130-133`).
- `paramsSerializer`: array expansion (`ids=1&ids=2`), `URLSearchParams` passthrough, skip `undefined`/`null` (tested via `apiClient.get('/x', { params: ... })`).
- `normalizeApiUrl` / `getApiBaseUrl` — use `vi.stubEnv` + `vi.resetModules()` + dynamic `await import('./client')` to re-read `import.meta.env.DEV` / `VITE_BACKEND` / `VITE_API_URL` / `VITE_STAGING_API_URL` / `VITE_PROD_API_URL` between cases.

**Critical:** `client.test.ts` is the ONE file in Wave 1 that CANNOT rely on the `setup.ts` mock — it's testing the real `apiClient` construction. It must run with `vi.doUnmock('./client')` or live in a `describe` block that dynamically imports AFTER env stubs are set. Follow the sentry.test.ts pattern.

---

### 9. Wave 2: `frontend/src/hooks/*.test.{ts,tsx}` — hook tests (D-09)

**Analog:** **NO existing `renderHook` test in the repo** (grep verified). Wave 2 is first-use of `renderHook` from `@testing-library/react` 16.1.0.

**Pattern source:** `@testing-library/react` docs — `renderHook()` with `wrapper` option. Cross-reference RESEARCH.md Pattern 2 (§Architecture Patterns).

**Canonical skeleton for hooks that DO consume `AuthContext`** (`useAuth.ts`, `useAppSettings.ts`, `useIsPremium.ts`, etc.):

```tsx
// frontend/src/hooks/useAuth.test.tsx — EXAMPLE
import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useAuth } from './useAuth';
import { AllTheProviders } from '../test/utils/TestWrapper';
import { testScenarios } from '../test/utils/test-utils';

describe('useAuth', () => {
  it('returns unauthenticated state when no user', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AllTheProviders
          initialAuthState={testScenarios.unauthenticated.initialAuthState}
        >
          {children}
        </AllTheProviders>
      ),
    });
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });
});
```

**Canonical skeleton for hooks that do NOT need providers** (`useDocumentMeta`, `useCookieConsent`, `useContainerWidth`, `useResponsiveColumns`):

```tsx
// frontend/src/hooks/useDocumentMeta.test.ts — EXAMPLE
import { renderHook } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useDocumentMeta } from './useDocumentMeta';

describe('useDocumentMeta', () => {
  it('sets document.title to "<title> | CarModPicker" by default', () => {
    renderHook(() => useDocumentMeta({ title: 'Home' }));
    expect(document.title).toBe('Home | CarModPicker');
  });

  it('does not duplicate site name when title already contains it', () => {
    renderHook(() => useDocumentMeta({ title: 'About CarModPicker' }));
    expect(document.title).toBe('About CarModPicker');
  });
});
```

**Hook inventory** (`frontend/src/hooks/`):
- `UseApiRequest.tsx` — custom wrapper around `apiClient`; needs `vi.mocked(apiClient.*)` per-test setup.
- `useAppSettings.ts` — context consumer (simple; mirrors `useAuth`).
- `useAuth.ts` — context consumer.
- `useContainerWidth.ts` — `ResizeObserver`; stub per `App.coverage.test.tsx:54-68` pattern.
- `useCookieConsent.ts` — localStorage + custom event; mock `window.dispatchEvent` + `localStorage`.
- `useDocumentMeta.ts` — DOM mutation; assert via `document.title` / `document.querySelector('meta[...]')`.
- `useGoogleSignIn.ts` — checks `VITE_GOOGLE_CLIENT_ID`; use `vi.stubEnv` per `sentry.test.ts` pattern.
- `useIsPremium.ts` — composes `useAuth` + `useAppSettings`; test with testScenarios.
- `usePartsFilters.ts` — URL state; test with `MemoryRouter` initialEntries.
- `useResponsiveColumns.ts` — `window.matchMedia`; stub the matchMedia method.

---

### 10. Wave 2: `frontend/src/contexts/*.test.tsx` — provider tests (D-10)

**Analog:** `frontend/src/components/common/RouteGroupBoundary.test.tsx` — renders children under a provider, triggers a transition via `fireEvent`, asserts DOM change.

**Pattern excerpt** (`frontend/src/components/common/RouteGroupBoundary.test.tsx:42-52`):
```tsx
it('renders children when no error is thrown', () => {
  render(
    <MemoryRouter>
      <RouteGroupBoundary groupName="admin">
        <Safe />
      </RouteGroupBoundary>
    </MemoryRouter>
  );
  expect(screen.getByText('safe content')).toBeInTheDocument();
  expect(document.querySelector('[data-route-group]')).toBeNull();
});
```

**Apply to `AuthContext.test.tsx`:** Use an in-test `<Consumer>` component that reads from `useAuth()`; render `<AuthProvider><Consumer /></AuthProvider>` directly (NOT via `TestProviders` — that wrapper mocks `useAuth`; real context tests want the real provider). Seed a token in `localStorage`, let the provider's `checkAuthStatus` `useEffect` fire, assert the consumer flips from anon to username after `apiClient.get('/users/me')` resolves.

Per RESEARCH.md §Code Examples "Verified pattern: context provider state transition" (§row at line 898):

```tsx
// Pattern skeleton — follow AuthContext.test.tsx & AppSettingsContext.test.tsx
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom'; // needed — AuthProvider calls useNavigate()
import { vi } from 'vitest';
import { AuthProvider } from './AuthContext';
import { useAuth } from '../hooks/useAuth';
import apiClient from '../services/Api';

function Consumer() {
  const { isAuthenticated, user, logout } = useAuth();
  return (
    <div>
      <span data-testid="state">{isAuthenticated ? user?.username : 'anon'}</span>
      <button onClick={logout}>logout</button>
    </div>
  );
}

it('flips state from authenticated to unauthenticated on logout', async () => {
  // seed the /users/me response before provider mount
  vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockUser });
  vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { message: 'ok' } });

  render(
    <MemoryRouter>
      <AuthProvider><Consumer /></AuthProvider>
    </MemoryRouter>
  );

  await waitFor(() =>
    expect(screen.getByTestId('state').textContent).toBe('testuser')
  );

  await act(async () => {
    fireEvent.click(screen.getByText('logout'));
  });

  await waitFor(() =>
    expect(screen.getByTestId('state').textContent).toBe('anon')
  );
});
```

**Important:** `AuthProvider` calls `useNavigate()` at `frontend/src/contexts/AuthContext.tsx:16` — tests MUST wrap in `<MemoryRouter>` or rendering throws.

---

### 11. Waves 3 & 4: Page tests (D-11 + D-02)

**Analogs (composed — no single file does all of this):**
- `frontend/src/test/utils/test-utils.tsx:42-61` — `customRender` helper that wraps in `AllTheProviders` + `testScenarios`.
- `frontend/src/App.coverage.test.tsx:239-267` — `MemoryRouter initialEntries={[path]}` pattern for route-dependent pages.
- `frontend/src/test/mocks/api.ts:136-171` — `setupApiMocks()` default-response helper.

**Canonical skeleton** (apply to every `pages/**/*.test.tsx`):

```tsx
// frontend/src/pages/authentication/Login.test.tsx — EXAMPLE
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, testScenarios } from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import { mockUser } from '../../test/mocks/api';
import Login from './Login';

describe('Login page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the login form (unauthenticated)', () => {
    render(<Login />, testScenarios.unauthenticated);
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('submits credentials and redirects on success', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { access_token: 'tok', token_type: 'bearer', user: mockUser },
    });
    render(<Login />, testScenarios.unauthenticated);
    // ...fill username + password + click submit
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/auth/token',
        expect.anything(),
        expect.objectContaining({
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        })
      )
    );
  });

  it('shows an error when credentials are invalid', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: { status: 401, data: { detail: 'Invalid credentials' } },
    });
    render(<Login />, testScenarios.unauthenticated);
    // ... submit, then assert error text
  });
});
```

**Use `testScenarios.adminAuthenticated`** for admin-page tests (Wave 4), `testScenarios.authenticated` for builder/profile pages (Wave 3 builder group), `testScenarios.unauthenticated` for auth pages (Login/Register).

**Per research §3 "Pages with non-trivial test setup":**
- `Login.tsx` / `Register.tsx`: mock `useGoogleSignIn` hook; mock `@simplewebauthn/browser` for `startAuthentication` / `browserSupportsWebAuthn` (see `frontend/src/pages/authentication/Login.tsx:13-15`).
- `Profile.tsx` / `ViewBuildLog.tsx`: mock `imageApi.uploadImage` resolved value; create File via `new File(['x'], 'test.jpg', { type: 'image/jpeg' })`.
- `BugReport.tsx`: mock the `bug_reports` endpoint; don't inspect FormData internals.
- `Search.tsx`: mock `usePartsFilters` hook to return deterministic state (don't test serialization).

---

### 12. Wave 4: `frontend/src/pages/admin/CrawlerAdmin.test.tsx` (D-07 fake-timer path)

**Analog:** composed — `RouteGroupBoundary.test.tsx` render pattern + RESEARCH.md Pattern 4 + Code Example (§line 862) for fake-timer + admin-auth.

**Pattern excerpt (from research §Code Examples — first in-repo use):**

```tsx
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, act, testScenarios } from '../../test/utils/test-utils';
import { apiClient } from '../../api/client';
import { startFakeTimers, stopFakeTimers, advanceTimersAndFlush } from '../../test/utils/async';
import { makeJobsList } from '../../test/mocks/admin/jobs';
import CrawlerAdmin from './CrawlerAdmin';

describe('CrawlerAdmin — Background Jobs section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    startFakeTimers();
  });
  afterEach(() => {
    stopFakeTimers();
  });

  it('polls jobs every 5 seconds while one is running', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: makeJobsList({ running: true }),
    });
    render(<CrawlerAdmin />, testScenarios.adminAuthenticated);

    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    const initialCalls = vi.mocked(apiClient.get).mock.calls.length;

    await advanceTimersAndFlush(5000);

    expect(vi.mocked(apiClient.get).mock.calls.length).toBeGreaterThan(initialCalls);
  });
});
```

**CrawlerAdmin section structure to cover** (research §1, verified):
1. Crawler Schedules (line 1505) — schedule list + draft editor + Reconcile All + create form.
2. Adapter Tuning (line 1874) — per-adapter delay/limit/skip_known_urls/default_category edit row.
3. Background Jobs (line 2043) — polled job list. **This section needs fake timers.**
4. Manual Run (line 2290) — crawler adapter multi-select grid + Run Crawl + Rescrape Archives buttons.

Also cover the two auth-deny early returns at ~line 1445 (`testScenarios.unauthenticated` / `testScenarios.authenticated` non-admin).

---

### 13. Wave 5: `frontend/src/components/**/*.test.tsx` (D-12 gap-fill)

**Analog (PRIMARY):** `frontend/src/components/common/RouteGroupBoundary.test.tsx` — the established Phase 6 render-and-assert pattern.

**Pattern excerpt** (already shown in §10 above). Copy this skeleton for any presentational or smart component surfacing below-threshold coverage after Wave 4.

---

## Shared Patterns

### Authentication injection (applies to all page + hook + context tests)

**Source:** `frontend/src/test/utils/test-utils.tsx:33-40` (useAuth module mock) + `frontend/src/test/utils/TestProviders.tsx:22-37` (mockUseAuth.mockReturnValue).

**Apply to:** every test that imports a source file that eventually calls `useAuth()`.

```tsx
// Already done automatically by the customRender in test-utils.tsx.
// Per-test override (if a test needs a different auth state inside a single describe):
import { mockUseAuth } from '../../test/utils/test-mocks';
mockUseAuth.mockReturnValue({
  isAuthenticated: true,
  user: mockAdminUser,
  isLoading: false,
  login: vi.fn(),
  logout: vi.fn(),
  checkAuthStatus: vi.fn(),
});
```

---

### API client mocking (applies to ALL Wave 1-5 tests)

**Source:** `frontend/src/test/setup.ts:13-15` (existing) + D-18 addition.

**Apply to:** every test file that imports source code that transitively reaches `api/client` or `services/Api`. Because setup.ts runs for every test, no per-file `vi.mock` call is needed — just use `vi.mocked(apiClient.<verb>)` for per-test overrides:

```ts
import { apiClient } from '../api/client'; // resolves to mockApiClient per setup.ts D-18
vi.mocked(apiClient.get).mockResolvedValueOnce({ data: ... });
```

---

### Hoisted mock references (applies when a test needs a mock to close over a declared variable)

**Source:** `frontend/src/components/common/ErrorBoundary.test.tsx:20-27` + `frontend/src/App.coverage.test.tsx:72-75`.

**Apply to:** any test where a `vi.mock(...)` factory must reference a test-local value. Factories are hoisted to the top of the file BEFORE imports and local variable declarations — you MUST use `vi.hoisted` to co-declare.

```ts
// Copy pattern from ErrorBoundary.test.tsx
const { mockedCapture } = vi.hoisted(() => ({
  mockedCapture: vi.fn(),
}));

vi.mock('@sentry/react', () => ({
  captureException: mockedCapture,
}));

// Now mockedCapture is safely referenced inside the factory (hoisted together)
// AND inside the test body below.
```

---

### Console silencing (applies to any test that intentionally throws)

**Source:** `frontend/src/components/common/RouteGroupBoundary.test.tsx:29-40` + `ErrorBoundary.test.tsx:55-57`.

**Apply to:** tests that exercise error-boundary paths or thrown errors.

```ts
let errorSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  errorSpy.mockRestore();
});
```

---

### Mock isolation per-file (applies to admin fixtures)

**Source:** research §Pitfall 6 — Vitest parallelizes per-file; mutable singletons leak across files.

**Apply to:** every file in `frontend/src/test/mocks/admin/*.ts`.

```ts
// Export factories, NOT mutable singletons:
export const makeFoo = (overrides = {}): Foo => ({ ...defaults, ...overrides });
// NOT: export const fooList: Foo[] = [...];
```

---

### `vi.stubEnv` for env-gated modules

**Source:** `frontend/src/lib/sentry.test.ts:47-75`.

**Apply to:** `api/client.test.ts` (base URL resolution branches) + `hooks/useGoogleSignIn.test.ts` (VITE_GOOGLE_CLIENT_ID gate).

```ts
beforeEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
  vi.unstubAllEnvs();
});

it('resolves staging URL when VITE_BACKEND=staging in DEV', async () => {
  vi.stubEnv('DEV', 'true');
  vi.stubEnv('VITE_BACKEND', 'staging');
  vi.stubEnv('VITE_STAGING_API_URL', 'staging.example.com');
  const { apiClient } = await import('./client');
  expect(apiClient.defaults.baseURL).toBe('https://staging.example.com/api');
});
```

---

## No Analog Found

Files / patterns with NO existing match in the codebase (executor needs to introduce the pattern using library docs or the skeletons above):

| File / Pattern | Cluster | Reason | Source to use |
|----------------|---------|--------|---------------|
| `frontend/src/test/utils/async.ts` | Wave 0 infra | No existing `vi.useFakeTimers` usage in repo | Vitest fake-timer docs (Context7) + §5 above |
| `frontend/src/api/*.test.ts` (19 files) | Wave 1 | No existing API-module test in repo | Skeleton in §7 above |
| `frontend/src/api/client.test.ts` | Wave 1 | No existing Axios-instance + interceptor test | Skeleton in §8 + `sentry.test.ts` pattern |
| `frontend/src/hooks/*.test.{ts,tsx}` (11 files) | Wave 2 | No existing `renderHook` usage in repo | Skeleton in §9 + @testing-library/react docs |
| `frontend/src/pages/admin/CrawlerAdmin.test.tsx` (Background Jobs section) | Wave 4 | No existing `vi.useFakeTimers` usage | Skeleton in §12 + helper from `async.ts` |

---

## Gotchas

### 1. `renderHook` has never been used in this repo.

Per `grep -rn "renderHook" frontend/src`, zero hits at HEAD. Wave 2 is the first integration. `@testing-library/react` 16.1.0 (per `frontend/package.json`) ships `renderHook` natively — no separate install needed. Use the wrapper pattern in §9 for context-consuming hooks and the bare pattern for pure hooks.

### 2. `vi.useFakeTimers` has never been used in this repo.

Per `grep -rn "useFakeTimers" frontend/src`, zero hits at HEAD. Wave 4 CrawlerAdmin is the first use. Follow §5 `async.ts` helper pattern and pair with `await act(...)` per Pitfall 5.

### 3. `AuthProvider` requires `<MemoryRouter>` to render.

`frontend/src/contexts/AuthContext.tsx:16` calls `useNavigate()` unconditionally at render. Context provider tests (Wave 2 `AuthContext.test.tsx`) MUST wrap `<AuthProvider>` in `<MemoryRouter>` or rendering throws synchronously. `AllTheProviders` already handles this (via `TestProviders` which uses `BrowserRouter`), but direct `AuthContext` tests that use the real provider need the explicit Router.

### 4. `setup.ts` D-18 requires verifying `services/Api.ts` shim shape BEFORE landing.

Confirmed: `frontend/src/services/Api.ts:7` reads `export { apiClient as default } from '../api/client'`. This means both `vi.mock('../services/Api', ...)` and `vi.mock('../api/client', ...)` pointing at the same `mockApiClient` object is coherent. Wave 0 must record this finding in its SUMMARY.md per research §Assumptions Log A1.

### 5. FormData tests ONLY in `images.ts` and `users.ts`.

Per research §2 "Non-JSON patterns", `FormData` + `multipart/form-data` Content-Type appears ONLY at:
- `frontend/src/api/images.ts:36,50` (`uploadImage`)
- `frontend/src/api/users.ts:23,27` (`uploadProfilePicture`)

Every other API module uses plain JSON `apiClient.{get,post,put,delete,patch}`. Don't add FormData assertions to unrelated tests.

### 6. Vitest counts UNTESTED files in global threshold denominator.

Per research §6 + §Pitfall 3 — Vitest's default include globs count files never imported by any test. Wave 5's gap-fill MUST run `npm run test:coverage -- --reporter=text` and inspect per-file percentages; any 0%-coverage file either needs a minimal test OR a `vitest.config.ts` `coverage.exclude` entry with D-15 rationale comment.

### 7. Page tests must import page components DIRECTLY, not via App.

Per research §Pitfall 4, importing App and routing to a page via `MemoryRouter` causes `lazyWithReload` to hang in jsdom (dynamic imports don't resolve). Page tests should `import Login from './Login'` and render `<Login />` directly under `customRender`, NOT mount through `<App />`.

### 8. `test-utils.tsx` already mocks `services/Api` AND `useAuth`.

Per `frontend/src/test/utils/test-utils.tsx:32-40`, `customRender` already installs `vi.mock('../../services/Api')` AND `vi.mock('../../hooks/useAuth')`. Tests that use `customRender` (i.e. import `render` from `'../../test/utils/test-utils'`) inherit both mocks automatically. Do NOT re-mock these in the test file — it causes confusion. Use `vi.mocked(apiClient.get).mockResolvedValueOnce(...)` for per-test overrides instead.

### 9. `exactOptionalPropertyTypes` prohibits explicit `undefined`.

Per research §Pitfall 2 + `frontend/tsconfig.json` (strict mode). Writing `initialAuthState: { isAuthenticated: true, isLoading: undefined }` is a TS error. Use the existing `testScenarios.*` fixtures or compose via `{ ...base, key: value }` spread; never assign `undefined` explicitly.

### 10. D-17 guard relocation requires NO code change in the 3 guard files.

Per `frontend/src/test/no-process-env.test.ts:8`, the `__dirname` + `resolve(..., '..', '..')` path math continues to resolve to `frontend/` after moving the file from `src/test/` to `src/test/guards/` (one directory deeper, but both `..` segments absorb the delta). Executor should only verify by running `npm test -- --run src/test/guards/` post-move; no source edits needed.

---

## Metadata

**Analog search scope:**
- `frontend/src/test/` (all infrastructure)
- `frontend/src/*.test.*` (9 existing tests at `setup.ts`, `utils/carUtils.test.ts`, `utils/externalImageUrls.test.ts`, `App.coverage.test.tsx`, `lib/sentry.test.ts`, `components/common/ErrorBoundary.test.tsx`, `components/common/RouteGroupBoundary.test.tsx`, `test/no-process-env.test.ts`, `test/no-legacy-gradient.test.ts`, `test/extension-content-type.test.ts`)
- `frontend/src/api/client.ts` + `auth.ts` + `images.ts` + `users.ts` + `admin.ts` (sample of 5 / 20 domain modules for shape characterization)
- `frontend/src/hooks/` (all 10 hook source files)
- `frontend/src/contexts/` (all 4 context definition + provider files)
- `frontend/src/pages/admin/CrawlerAdmin.tsx` (targeted grep at lines 1270-1310 for polling; section headers at 1505/1874/2043/2290)
- `frontend/vitest.config.ts` (config shape for D-13 exclusions + D-22 threshold block)
- `frontend/src/services/Api.ts` (shim pattern confirmation per Pitfall 7)

**Files scanned:** ~30 source + 9 test + 1 config = 40 file reads.

**Key insight:** ~70% of Phase 8's test-writing work has NO in-repo analog. Waves 1 (API tests), 2 (hooks), and CrawlerAdmin's polling section are introducing new patterns that become the canonical examples for future frontend tests. Waves 3, 4, and 5 have strong analogs in `RouteGroupBoundary.test.tsx` + `test-utils.tsx` customRender.

**Pattern extraction date:** 2026-04-24

## PATTERN MAPPING COMPLETE
