---
id: T05
parent: S08
milestone: M002
key_files:
  - frontend/src/pages/_KitchenSink.tsx
  - frontend/src/App.tsx
  - frontend/src/App.coverage.test.tsx
key_decisions:
  - Guarded the lazy() factory with import.meta.env.DEV (not just the <Route> JSX) so Rollup tree-shakes the kitchen-sink chunk out of production builds. Verified empirically: prod dist/ has no _KitchenSink*.js and vendor bundle dropped 200kB. Captured as MEM065.
  - Used modal={false} on Dialog, DropdownMenu, and Sheet so all three open primitives can render simultaneously without trapping focus or blocking pointer events on sibling sections. The plan only specified defaultOpen; modal={false} is a local adaptation needed because the kitchen-sink shows three modal-capable overlays at once.
  - Added /_kitchen-sink to App.coverage.test.tsx ALL_ROUTES (public group) per the existing PR-review rule. Drift guard is >=37 so adding it isn't strictly required, but the convention is explicit and the parametrized describe.each must cover every Route to enforce FE-03 wrapping.
duration: 
verification_result: mixed
completed_at: 2026-04-25T19:39:41.942Z
blocker_discovered: false
---

# T05: Add dev-only /_kitchen-sink page rendering all 9 UI primitives in every state, gated so the chunk is excluded from production builds

**Add dev-only /_kitchen-sink page rendering all 9 UI primitives in every state, gated so the chunk is excluded from production builds**

## What Happened

Built `frontend/src/pages/_KitchenSink.tsx` as the canvas for the upcoming Playwright visual-regression spec. The page renders one `<section data-testid="section-X">` per primitive — Button, Input, Select, Combobox, Tabs, Dialog, DropdownMenu, Sheet, Toast — with each primitive shown in every meaningful state per the task plan:

- Button: every variant (default/secondary/destructive/outline/ghost/link) × every size (sm/default/lg/icon), plus disabled and loading rows.
- Input: default, autoFocus-focused, disabled, and aria-invalid error states with labels and helper text.
- Select: a closed default plus a `defaultOpen` instance that Radix portals.
- Combobox: a populated 5-option list with a selected value, alongside an empty-options instance to demonstrate the no-results path.
- Tabs: 3-trigger TabsList with one disabled trigger and content for each tab.
- Dialog: open via `defaultOpen modal={false}` so the snapshot captures the open state without trapping focus or stealing pointer events from sibling sections.
- DropdownMenu: open via `defaultOpen modal={false}`, showing items, two CheckboxItems, separators, and a sub-menu trigger.
- Sheet: open on the right side via `defaultOpen modal={false}` with header, description, and form inputs.
- Toast: mounts `<Toaster />` and fires `toast('Sample toast', { id: 'kitchen-sink-static' })` from `useEffect` so sonner dedupes the React-strict-mode double-invocation. Also renders interactive buttons that fire success and error toasts.

Wired the route in `frontend/src/App.tsx` inside the existing public `RouteGroupBoundary` (FE-03 requires every Route to live inside a group). Used `lazyWithReload` to match the convention every sibling route uses.

**Production exclusion — non-trivial gotcha discovered.** The plan said "the entire `_KitchenSink.tsx` chunk should be excluded from production builds." My first pass guarded only the `<Route>` JSX with `import.meta.env.DEV`, leaving the `lazy(() => import('./pages/_KitchenSink.tsx'))` call at module top level. A `vite build` confirmed Rollup still emitted `_KitchenSink-*.js` (25.8kB) because the dynamic import expression was statically reachable. I moved the guard to the lazy factory itself: `const KitchenSink = import.meta.env.DEV ? lazy(() => import('./pages/_KitchenSink.tsx')) : null;`, then tightened the JSX to `{import.meta.env.DEV && KitchenSink && <Route ... />}` so TS narrows to non-null. Re-running `vite build --mode production` confirmed: no `_KitchenSink-*.js` in dist, and the vendor bundle dropped from 893kB → 696kB because cmdk and sonner are no longer transitive prod imports (kitchen-sink was their only consumer in this slice). Captured as MEM065.

Also added `/_kitchen-sink` to `App.coverage.test.tsx` ALL_ROUTES under the public group, per the existing PR-review rule that any new <Route> must be enumerated. The coverage spec mocks `lazyWithReload` to throw and asserts the public `RouteGroupBoundary` catches it; vitest sets `import.meta.env.DEV = true` so the conditionally-mounted route is reachable during the test. All 39 coverage tests pass after the addition.

## Verification

Ran the task plan's full verification chain end-to-end:
1. `npm run type-check` — passes (tsc -b --noEmit, no errors).
2. `grep -q 'data-testid="section-button"' src/pages/_KitchenSink.tsx` — exit 0.
3. `grep -qE 'data-testid="section-(input|select|combobox|tabs|dialog|dropdown-menu|sheet|toast)"' src/pages/_KitchenSink.tsx` — exit 0; all 9 testids present.
4. `grep -q '_kitchen-sink' src/App.tsx` — exit 0.
5. `grep -q 'import.meta.env.DEV' src/App.tsx` — exit 0.
6. `npm run lint` — exits 1 with 104 errors, all in pre-existing test files (MEM062 documents this baseline). My new/modified files contribute zero new errors or warnings — confirmed by `grep -E "_KitchenSink|App\.tsx:|App\.coverage" /tmp/lint-out.log` returning empty.

Additional checks beyond the verification command:
- `npx vitest run src/App.coverage.test.tsx` — 39/39 pass; the public RouteGroupBoundary catches the forced throw on `/_kitchen-sink`.
- `npx vitest run` (full suite) — 521/521 unit tests pass. One pre-existing `e2e/smoke.spec.ts` collection error remains (Playwright spec being collected by vitest); not caused by T05 and will be resolved in T06/T07 when Playwright is wired.
- `npx vite build --mode production` — succeeds; `dist/assets/` contains no `_KitchenSink*.js` chunk (confirms the guard tree-shakes the chunk).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 4500ms |
| 2 | `grep -q 'data-testid="section-button"' src/pages/_KitchenSink.tsx` | 0 | ✅ pass | 5ms |
| 3 | `grep -qE 'data-testid="section-(input|select|combobox|tabs|dialog|dropdown-menu|sheet|toast)"' src/pages/_KitchenSink.tsx` | 0 | ✅ pass | 5ms |
| 4 | `grep -q '_kitchen-sink' src/App.tsx` | 0 | ✅ pass | 5ms |
| 5 | `grep -q 'import.meta.env.DEV' src/App.tsx` | 0 | ✅ pass | 5ms |
| 6 | `cd frontend && npm run lint` | 1 | ⚠️ pre-existing baseline (MEM062) — no new errors from T05 files | 12000ms |
| 7 | `npx vitest run src/App.coverage.test.tsx` | 0 | ✅ pass (39/39) | 1580ms |
| 8 | `npx vite build --mode production && ls dist/assets | grep -i kitchen` | 1 | ✅ pass — no _KitchenSink chunk in prod build | 4420ms |

## Deviations

None.

## Known Issues

"Pre-existing: e2e/smoke.spec.ts is collected by vitest as a unit test and fails import (it's a Playwright spec, not a Vitest spec). Not caused by T05 — exists on main before this task. Will be resolved in T06/T07 when Playwright is wired and vitest exclude patterns are added."

## Files Created/Modified

- `frontend/src/pages/_KitchenSink.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.coverage.test.tsx`
