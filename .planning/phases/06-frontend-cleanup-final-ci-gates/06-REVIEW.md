---
phase: 06-frontend-cleanup-final-ci-gates
reviewed: 2026-04-24T04:44:48Z
depth: standard
files_reviewed: 61
files_reviewed_list:
  - backend/.bandit
  - backend/requirements.txt
  - backend/tests/dependencies/test_auth_utils.py
  - backend/tests/fixtures/openapi_snapshot.json
  - backend/tests/test_bandit_high_gate.py
  - frontend/eslint.config.js
  - frontend/src/api/admin.ts
  - frontend/src/api/app_settings.ts
  - frontend/src/api/auth.ts
  - frontend/src/api/bug_reports.ts
  - frontend/src/api/build_list_parts.ts
  - frontend/src/api/build_list_phases.ts
  - frontend/src/api/build_lists.ts
  - frontend/src/api/build_logs.ts
  - frontend/src/api/car_generations.ts
  - frontend/src/api/categories.ts
  - frontend/src/api/client.ts
  - frontend/src/api/images.ts
  - frontend/src/api/part_manufacturers.ts
  - frontend/src/api/parts.ts
  - frontend/src/api/reports.ts
  - frontend/src/api/retailers.ts
  - frontend/src/api/search.ts
  - frontend/src/api/users.ts
  - frontend/src/api/utility.ts
  - frontend/src/api/votes.ts
  - frontend/src/App.coverage.test.tsx
  - frontend/src/App.tsx
  - frontend/src/components/common/Button.tsx
  - frontend/src/components/common/Card.tsx
  - frontend/src/components/common/ChromeExtensionPromo.tsx
  - frontend/src/components/common/DangerousActionDialog.tsx
  - frontend/src/components/common/DeleteConfirmationDialog.tsx
  - frontend/src/components/common/Dialog.tsx
  - frontend/src/components/common/RouteGroupBoundary.test.tsx
  - frontend/src/components/common/RouteGroupBoundary.tsx
  - frontend/src/components/common/SubscriptionPromo.tsx
  - frontend/src/components/layout/globalFooter/Footer.tsx
  - frontend/src/components/layout/globalHeader/Header.tsx
  - frontend/src/components/parts/AddToBuildListDialog.tsx
  - frontend/src/components/parts/CreatePartForm.tsx
  - frontend/src/components/parts/PartList.tsx
  - frontend/src/pages/About.tsx
  - frontend/src/pages/admin/PartsCuration.tsx
  - frontend/src/pages/admin/SystemAdmin.tsx
  - frontend/src/pages/authentication/ExtensionAuth.tsx
  - frontend/src/pages/authentication/Login.tsx
  - frontend/src/pages/authentication/Register.tsx
  - frontend/src/pages/Checkout.tsx
  - frontend/src/pages/Home.tsx
  - frontend/src/pages/NotFound.tsx
  - frontend/src/pages/Pricing.tsx
  - frontend/src/pages/Support.tsx
  - frontend/src/services/Api.ts
  - frontend/src/test/extension-content-type.test.ts
  - frontend/src/test/no-legacy-gradient.test.ts
  - frontend/src/test/no-process-env.test.ts
  - frontend/src/test/utils/test-mocks.ts
  - frontend/src/utils/lazyWithReload.ts
  - .github/workflows/frontend-ci.yml
  - terraform/s3.tf
findings:
  critical: 0
  warning: 5
  info: 10
  total: 15
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-04-24T04:44:48Z
**Depth:** standard
**Files Reviewed:** 61
**Status:** issues_found

## Summary

Phase 6 lands cleanly across all themed objectives. Spot checks confirm:

- **API split (FE-04):** `frontend/src/services/Api.ts` is a true 28-line re-export shim. Each per-domain module under `frontend/src/api/*.ts` exports its own `*Api` block plus co-located response types where appropriate (admin, auth, app_settings, images, search). Cross-domain type sharing (e.g. `BucketEntityTypeCountResponse` from `images` re-exported by `admin`) is wired correctly to preserve shim back-compat.
- **Sentry RouteGroupBoundary (FE-03):** Uses `Sentry.ErrorBoundary` with the `FallbackRender` form (not the alternate object form), exposes `eventId` + Retry (`resetError`) + Go Home (`useNavigate`), tags captured events with `route_group` via `beforeCapture`. The drift-guard test (`App.coverage.test.tsx`) parametrizes 37 routes — exactly matching `grep -cE 'path="' frontend/src/App.tsx` — and asserts the per-group `data-route-group` marker rendered in the fallback (not just body presence).
- **Auth migration (QUAL-05):** Zero `from jose|import jose` references anywhere in backend. `dependencies/auth.py` uses `import jwt` + `from jwt import InvalidTokenError` (PyJWT) consistently; `requirements.txt` pins `PyJWT==2.12.1` with no `python-jose` line. `tests/dependencies/test_auth_utils.py` imports the same `jwt` module (PyJWT) for round-trip decode assertions.
- **Tailwind v4 codemod (FE-05):** Zero `bg-gradient-to-` occurrences in `frontend/src/**`. All 27 source-file gradients use `bg-linear-to-{r,br}`. The `no-legacy-gradient.test.ts` guard cleverly reconstructs the forbidden prefix at runtime so the guard file itself does not violate.
- **Bandit HIGH gate (QUAL-04):** `test_bandit_high_gate.py` writes a B602 fixture (`subprocess.call(user_input, shell=True)`) and asserts both `returncode != 0` AND `"Severity: High" in stdout`. This is the right shape — it would catch both a flag regression (e.g. `-l` instead of `-ll`) AND a config-skip regression (e.g. adding B602 to `skips`).
- **Backend dep upgrades (D-14/D-23):** FastAPI 0.136.1, Pydantic 2.13.3, SQLAlchemy 2.0.49, Alembic 1.18.4, Uvicorn 0.45.0 — all match plan. Starlette pin (0.49.1) is compatible with FastAPI 0.136.x.
- **Terraform Glacier (QUAL-08):** `aws_s3_bucket_lifecycle_configuration.crawl_data` correctly scopes only to `aws_s3_bucket.crawl_data` — `user_images` bucket has no lifecycle resource. Empty `filter {}` block is the correct shape per RESEARCH §Pitfall 4 (do NOT use explicit empty-string prefix).
- **ESLint strict (FE-01):** `no-explicit-any`, `no-unsafe-assignment/call/return/member-access/argument` all flipped to `error` for `src/**/*.ts(x)`. No test-file override block — strict rules apply uniformly per D-05.
- **CI gates (`frontend-ci.yml`):** lint, type-check, test-with-coverage, `madge --circular`, build all run in sequence.

The findings below are quality nits and one regex-fragility warning in a CI guard test. None of the warnings are correctness bugs in shipping code; they reduce defense-in-depth or signal future-maintenance traps.

## Warnings

### WR-01: extension-content-type guard regex misses POSTs with nested object literals

**File:** `frontend/src/test/extension-content-type.test.ts:10`
**Issue:** The pattern `/fetch\([^)]+\{[^}]*method:\s*["']POST["'][^}]*\}/gs` uses `[^}]*` between `method:` and the closing `}`. This negated-class will stop at the FIRST `}` it encounters, including the closing brace of any nested object literal (e.g. `headers: { 'Content-Type': '...' }`). For example, a fetch shaped like:

```ts
fetch(uploadUrl.toString(), {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
})
```

would produce a match that ends at the closing `}` of `headers`, so the `body:` segment after it is never inspected. A POST that contains `headers: { ... }` then `body: rawString` (no Content-Type because the dev forgot it) would still pattern-match the truncated match, find `'application/json'` inside the `headers` substring, and falsely report compliance. Real-world impact: `chrome-extension/src/background.ts` has 3 fetch sites — at least one (`fetch(uploadUrl.toString(), { method: 'POST', headers: {...}, body: ... })` near line 574) has this nested-object shape. The guard may quietly pass even after a regression.
**Fix:** Use a balanced-brace tokenizer rather than a regex (parse fetch args from `acorn` or `@babel/parser`), or as a simpler intermediate fix, broaden the second `[^}]*` to a non-greedy multi-line `[\s\S]*?` and validate by a separate counter:

```ts
// Safer (still imperfect, but accepts nested {} in headers):
const postRegex = /fetch\([^)]+\{[\s\S]*?method:\s*["']POST["'][\s\S]*?\}\s*\)/g;
```

Then for each match, additionally assert that the brace depth balances correctly before checking for Content-Type. Alternatively, walk every `*.ts` AST and inspect each `fetch(...)` CallExpression — eliminates regex fragility entirely.

### WR-02: `authApi.login` non-null assertion silently swallows missing user

**File:** `frontend/src/api/auth.ts:64`
**Issue:** `data: response.data.user!` uses a TypeScript non-null assertion. If `requires_2fa` is false (so we fall through to the user-storage branch) but `response.data.user` is `undefined` (server contract bug or partial response), this returns an `AxiosResponse<UserRead>` whose `.data` is actually `undefined`. Downstream callers (`authLogin(result)` in `Login.tsx:149`) will then operate on `undefined` and either crash with a confusing read-of-undefined or silently no-op. With strict mode (FE-01) flipping `no-non-null-assertion` is generally desirable, but the deeper fix is to enforce the contract:
**Fix:**

```ts
// auth.ts ~line 60
if (response.data.access_token) {
  setStoredToken(response.data.access_token);
}
if (!response.data.user) {
  throw new Error('Login response missing user payload (server contract violation)');
}
return {
  ...response,
  data: response.data.user,
} as AxiosResponse<UserRead>;
```

### WR-03: `authApi.resetPasswordConfirm` payload double-wraps `new_password`

**File:** `frontend/src/api/auth.ts:98-102`
**Issue:** The function signature is `resetPasswordConfirm: (token: string, data: NewPassword) => apiClient.post(..., { token, new_password: data })`. If `NewPassword` is the schema `{ new_password: string }` (the typical FastAPI pattern, given the type name), then the request body becomes `{ token, new_password: { new_password: '...' } }` — which the backend will reject as `422 Unprocessable Entity`. Either the backend silently accepts the wrong shape (worse — no error, but reset never actually happens), or this code path is currently dead. Either way, this is a contract bug that surfaces only on the password-reset confirm flow, which is rare enough to escape testing.
**Fix:** Verify the `NewPassword` schema. If it is `{ new_password: string }`, change to:

```ts
resetPasswordConfirm: (token: string, data: NewPassword) =>
  apiClient.post<Record<string, string>>('/auth/reset-password/confirm', {
    token,
    ...data,
  }),
```

If `NewPassword` is just `string` (a primitive alias), then change the parameter type for clarity:

```ts
resetPasswordConfirm: (token: string, newPassword: string) =>
  apiClient.post<Record<string, string>>('/auth/reset-password/confirm', {
    token,
    new_password: newPassword,
  }),
```

### WR-04: `PartList.tsx` `case 'price':` uses unbraced `const` declarations

**File:** `frontend/src/components/parts/PartList.tsx:593-596`
**Issue:** Inside the `compare` function's switch, the `case 'price':` body declares `const pa = ...; const pb = ...;` without a wrapping block. JavaScript hoists these `const` bindings to the entire switch's lexical scope — so if a future case `'price_with_tax':` were added below, it would see `pa`/`pb` as already-declared and trigger a TDZ ReferenceError if the switch enters that case before the `'price'` case. Currently safe (one case), but `no-case-declarations` is a standard ESLint rule (not in this project's config) and the pattern is a recurring footgun.
**Fix:** Wrap the case body in a block:

```ts
case 'price': {
  const pa = a.best_price_cents ?? 0;
  const pb = b.best_price_cents ?? 0;
  return mult * (pa - pb);
}
```

Consider enabling the `no-case-declarations` rule in `eslint.config.js`.

### WR-05: `adminApi.getCrawledPageCounts*` URLs are not under `/admin/` prefix — verify backend gating

**File:** `frontend/src/api/admin.ts:302-309`
**Issue:** The two methods are documented as "Admin: archived page count per source" but POST/GET to `/crawled-pages/counts-by-source` and `/crawled-pages/counts-by-source-and-status` — neither URL has the `/admin/` prefix that every other method in `adminApi` uses. Either:

  1. The backend `crawled_pages` router applies admin auth to these specific endpoints (correct behavior, mislabelled URL convention) — verify in `backend/app/api/endpoints/crawled_pages.py`.
  2. These endpoints are NOT admin-gated — in which case the docstring is misleading AND non-admin users could potentially enumerate crawl data.

This is a high-impact information-disclosure vector if (2) is true; flagging as Warning rather than Critical because (1) is more likely given how the rest of the file is structured.
**Fix:** Open `backend/app/api/endpoints/crawled_pages.py` and grep for `Depends(get_current_admin_user)` on the `counts-by-source*` route handlers. If absent, add it. Then also rename the URL prefix here to `/admin/crawled-pages/...` to match the rest of `adminApi` for grep-ability.

## Info

### IN-01: `usersApi.uploadProfilePicture` return type narrows `AxiosResponse`

**File:** `frontend/src/api/users.ts:22-30`
**Issue:** Annotated as `Promise<{ data: UserRead }>` but the body returns the full `AxiosResponse<UserRead>` from `apiClient.post`. The narrowed type prevents callers from accessing `.status`, `.headers`, etc.
**Fix:** Drop the annotation (let TS infer `Promise<AxiosResponse<UserRead>>`) or annotate explicitly:

```ts
uploadProfilePicture: (file: File): Promise<AxiosResponse<UserRead>> => { ... }
```

### IN-02: `CreatePartForm` still imports through `services/Api` shim

**File:** `frontend/src/components/parts/CreatePartForm.tsx:5-10`
**Issue:** Imports `apiClient`, `partManufacturersApi`, `carGenerationsApi`, `categoriesApi`, `partsApi` from `../../services/Api`. Per the D-22 comment in `services/Api.ts`, "New code SHOULD import directly from `../api/<domain>`". Existing call sites are intentionally exempt to keep the phase scope bounded, so no fix required for this PR — flagging only so a future cleanup phase can do a sweep. Same applies to `AddToBuildListDialog.tsx:3` and `PartList.tsx:7`.
**Fix:** During a future cleanup pass:

```ts
import apiClient from '../../api/client';
import { partManufacturersApi } from '../../api/part_manufacturers';
import { carGenerationsApi } from '../../api/car_generations';
import { categoriesApi } from '../../api/categories';
import { partsApi } from '../../api/parts';
```

### IN-03: `partsApi.getPartsByCategory` passes a redundant `filter_id`

**File:** `frontend/src/api/parts.ts:67-74`
**Issue:** Method posts to `/parts/category/${categoryId}` AND also sends `filter_id: categoryId` in `params`. Either the backend already gets the category from the path (params is redundant) or it expects both. Worth confirming and dropping the unused side.
**Fix:** Verify backend `parts/category/{categoryId}` handler signature; remove `filter_id` from params if not consumed.

### IN-04: `PartList.tsx` module-level caches grow unbounded

**File:** `frontend/src/components/parts/PartList.tsx:34-37`
**Issue:** `partsCache: Map<string, CachedData>` and `carByIdCache: Record<string, CarGenerationRead>` are module-scope mutables that accumulate forever — entries never get evicted (only individual entries get refreshed when their TTL expires on read). On a long catalog-browsing session this leaks memory monotonically. Out of v1 perf scope, but worth a TODO.
**Fix:** Add a max-size LRU eviction pass on insertion, or expire on TTL even without read:

```ts
const MAX_CACHE_ENTRIES = 50;
function setCachedData(key: string, value: CachedData) {
  if (partsCache.size >= MAX_CACHE_ENTRIES) {
    const oldest = partsCache.keys().next().value;
    if (oldest != null) partsCache.delete(oldest);
  }
  partsCache.set(key, value);
}
```

### IN-05: `buildLogsApi.getBuildLogByBuildList` builds query string manually

**File:** `frontend/src/api/build_logs.ts:12-24`
**Issue:** Builds a `URLSearchParams` and concatenates it onto the URL string instead of passing `{ params }` to axios. Inconsistent with every other axios call in the per-domain modules, and bypasses the load-bearing `paramsSerializer` in `client.ts:63` (which is OK here because URLSearchParams.toString uses the same encoding for primitives — but new contributors won't know that).
**Fix:**

```ts
getBuildLogByBuildList: (
  buildListId: string,
  skip?: number,
  limit?: number
) =>
  apiClient.get<BuildLogReadPaginated>(
    `/build-logs/build-list/${buildListId}`,
    { params: { skip, limit } }
  ),
```

(axios drops `undefined` values automatically.)

### IN-06: `AddToBuildListDialog` adds parts sequentially with no rollback

**File:** `frontend/src/components/parts/AddToBuildListDialog.tsx:113-119`
**Issue:** `for (const buildListId of selectedBuildListIds) { await buildListPartsApi.addPartToBuildList(...) }` — if the user picks 5 lists and the 3rd add fails, lists 1-2 have the part, lists 3-5 do not, and the user sees a single error message with no per-list status. Performance is also linear in list count. v1 perf scope says skip these, but the user-experience side (no rollback / no granular reporting) is a UX bug.
**Fix:** Either gather per-list outcomes (Settled-style) and report which succeeded, or use `Promise.allSettled` and surface failures:

```ts
const results = await Promise.allSettled(
  Array.from(selectedBuildListIds).map((id) =>
    buildListPartsApi.addPartToBuildList(id, part.id, buildListPartData)
  )
);
const failed = results.filter((r) => r.status === 'rejected');
if (failed.length > 0) {
  setError(`Added to ${results.length - failed.length}/${results.length} build lists.`);
  return; // don't close dialog so user can retry the failed ones
}
onPartAdded();
onClose();
```

### IN-07: `admin.ts` imports + re-exports a type from `images.ts` (latent circular-import risk)

**File:** `frontend/src/api/admin.ts:8,12`
**Issue:** `import type { BucketEntityTypeCountResponse } from './images';` then `export type { BucketEntityTypeCountResponse };`. Type-only imports don't actually create a runtime cycle (TS strips them), so madge will not flag this — but if anyone in a future change converts this to a value import, or if `images.ts` ever imports a value from `admin.ts`, you get a cycle that is hard to debug. Add a TODO-marker comment so future maintainers see the constraint.
**Fix:**

```ts
// NOTE: type-only re-export. If you ever add a value import from './images'
// here, audit images.ts for any imports from this module first — a value-level
// cycle would break tree-shaking and trigger madge --circular CI failure.
import type { BucketEntityTypeCountResponse } from './images';
export type { BucketEntityTypeCountResponse };
```

### IN-08: `SystemAdmin.tsx` mount effect missing exhaustive-deps disable comment

**File:** `frontend/src/pages/admin/SystemAdmin.tsx:105-107`
**Issue:** `useEffect(() => { void fetchCurrentRevision(); }, []);` calls `fetchCurrentRevision` (declared in the component body) but the deps array is empty. Other intentionally-once mount effects in this codebase (e.g. `CreatePartForm.tsx:200`, `PartsCuration.tsx:211`) carry an explicit `// eslint-disable-next-line react-hooks/exhaustive-deps` annotation. Add the same here for consistency — silent reliance on lint not firing is fragile.
**Fix:**

```ts
useEffect(() => {
  void fetchCurrentRevision();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally only on mount
}, []);
```

### IN-09: `SystemAdmin.tsx` ad-hoc `console.error` not gated on env

**File:** `frontend/src/pages/admin/SystemAdmin.tsx:134`
**Issue:** `console.error('Failed to fetch current revision:', error);` — leaves console output in production for every admin who hits the page when the request fails. Other error paths in this file route to user-visible UI state. Pick one pattern.
**Fix:** Either remove (the user already sees the loading spinner stop and revision stays `null`), or surface to a state-setter the way other handlers in this file do:

```ts
} catch (error) {
  setCurrentRevision(null);
  // Optionally: add a `revisionError` state and render it. Don't leave bare console logs in admin UI.
}
```

### IN-10: `Header.tsx` absolute background depends on App.tsx-side positioning

**File:** `frontend/src/components/layout/globalHeader/Header.tsx:33-37`
**Issue:** `<header className="w-full">` (no `relative`) wraps a `<div className="absolute inset-0 ...">` background. The absolute element positions relative to the nearest `position: relative` ancestor — in this case App.tsx's `<div className="sticky top-0 z-50">Header + BetaBanner</div>` (sticky implies relative). Renders correctly today but is fragile: refactor App.tsx's sticky wrapper and the header background silently moves to the next positioned ancestor (potentially `<body>`).
**Fix:**

```tsx
<header className="relative w-full">  {/* anchor the absolute background here */}
```

---

_Reviewed: 2026-04-24T04:44:48Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
