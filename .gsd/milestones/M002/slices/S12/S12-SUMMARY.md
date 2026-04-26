---
id: S12
parent: M002
milestone: M002
provides:
  - ["frontend/src/components/ui/{card,alert,spinner,pagination,card-info-item}.tsx — net-new ui/* primitives composed across every page", "frontend/src/components/{routes,shell,forms,images,filters,tables}/ — relocated structural infra and non-primitive helpers from the retired components/common/", "frontend/src/__tests__/no-legacy-primitives.test.ts — vitest grep-guard enforcing the components/common + components/buttons boundary", "frontend/eslint.config.js no-restricted-imports rule on components/common/* + components/buttons/* (PR-time enforcement)", "frontend/vitest.config.ts include/exclude scoping (MEM129 fix, src/-only, excludes e2e/)", "Refreshed Playwright visual baselines for components.spec at all 3 viewports (mobile/tablet/desktop)", "Empty deletion of frontend/src/components/common/ + frontend/src/components/buttons/ directories"]
requires:
  - slice: S08
    provides: ui/{button,dialog,dropdown-menu,combobox,toast,tabs,input,select,sheet}.tsx primitives + tokens.css + playwright.config.ts mobile/tablet/desktop projects + components.spec kitchen-sink baseline
  - slice: S09
    provides: ConfirmDialog primitive + parent-owned-state Dialog pattern (open/onOpenChange + sm:max-w-* sizing + side-effect wiring)
  - slice: S06
    provides: components/charts/Sparkline.tsx + components/parts/PriceDeltaLine.tsx — preserved through the parts/builder ripple
affects:
  - ["frontend/src/pages/** — every page now on ui/* design system", "frontend/src/components/** — ui/* primitives + relocated infra (routes/, shell/, forms/, cars/, images/, filters/, tables/, buildLists/AddItemTile)", "frontend/eslint.config.js + vitest.config.ts — boundary enforcement + test scoping"]
key_files:
  - ["frontend/src/components/ui/card.tsx", "frontend/src/components/ui/alert.tsx", "frontend/src/components/ui/spinner.tsx", "frontend/src/components/ui/pagination.tsx", "frontend/src/components/ui/card-info-item.tsx", "frontend/src/__tests__/no-legacy-primitives.test.ts", "frontend/eslint.config.js", "frontend/vitest.config.ts", "frontend/src/App.tsx", "frontend/src/main.tsx", "frontend/src/pages/_KitchenSink.tsx"]
key_decisions:
  - ["MEM124 re-export shim pattern: T03/T04 importers point at future-canonical relocated paths; one-line stubs at the new locations re-export from the legacy home until T05 does the wholesale git mv. Lets each task verify type-check/grep guards in isolation without forcing a single big-bang relocation.", "MEM127 relocation sequence: rm shim → git mv original → fix sibling imports inside moved file. Sibling refs (./Card, ./Alerts, ./SearchableSelect) need rewriting after move. Preserves git history instead of recording delete+create churn.", "MEM116-extended swap rule: Use formal ui/Button variants (default/destructive/secondary/outline/ghost/link) over bespoke color className overrides. className overrides allowed only for layout shape (h-auto, p-0, w-full, justify-start). Disable 2FA `bg-red-600` → variant='destructive'; ButtonStretch → `<Button className='w-full'>`; LinkButton → `<Button asChild><Link>`.", "Parent-owned-state Dialog pattern (carried from S09): legacy `<Dialog isOpen onClose title maxWidth>` → `<Dialog open={...} onOpenChange={(o) => { if (!o) closeDialog(); }}><DialogContent className='sm:max-w-{md|lg|2xl}'>...`. Wires legacy closeDialog side-effects (clearing local state, calling reset()) to onOpenChange(false) so Escape/overlay-click/X-button all clean up state.", "ui/Spinner unifies legacy 6-size × 3-color matrix onto `text-primary` token (drops primary/white/custom color axis). Intentional design-system simplification per M002 retire-bespoke-styling intent. Default export preserved so legacy LoadingSpinner imports rename in place.", "MEM129 vitest config: Default include glob picks up Playwright e2e/*.spec.ts files and crashes them. Fix: `test.include: ['src/**/*.{test,spec}.{ts,tsx}']` + `test.exclude: ['e2e/**']` in vitest.config.ts.", "Two-layer boundary enforcement: vitest no-legacy-primitives.test.ts (walks src/ asserting no `from '...common/'` or '...buttons/' import) + ESLint no-restricted-imports rule on `**/components/common/*` + `**/components/buttons/*`. Lint catches at PR-time before vitest runs.", "ConfirmDialog adapter pattern for DeleteConfirmationDialog: destructure-friendly wrapper with `description={<>...{name}...</>}`, `confirmLabel='Confirm Delete'`, `loadingLabel='Deleting...'`, `variant='destructive'`, `error={raw ? `Failed to delete ${type}: ${raw}` : null}`. Preserves legacy UX (warning text, loading label, error display) without per-callsite re-wiring."]
patterns_established:
  - ["MEM124 re-export shim pattern for staged multi-task relocations (verify in isolation without big-bang move)", "MEM127 git-history-preserving relocation sequence (rm shim → git mv → fix sibling refs)", "MEM116 formal-variant-first design-system convention (className overrides only for layout shape)", "S09-derived parent-owned-state Dialog pattern with side-effect wiring on onOpenChange(false)", "MEM129 vitest scoping convention (include src/ test+spec, exclude e2e/)", "Two-layer boundary enforcement (vitest grep-guard + ESLint no-restricted-imports)", "ConfirmDialog adapter pattern (description/confirmLabel/loadingLabel/variant/error props for destructure-friendly DeleteConfirmationDialog migration)", "Inlined Link replacement for ParentNavigationLink (text-indigo-400 hover:text-indigo-300 underline at each callsite)"]
observability_surfaces:
  - none
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-26T04:04:44.077Z
blocker_discovered: false
---

# S12: Repo-wide ripple reskin — retire components/common/ + components/buttons/

**Migrated every page and inner component off legacy components/common/ + components/buttons/ onto the S08 ui/* design system, relocated structural infra to routes/+shell/, deleted both legacy directories, and locked R017 with a vitest grep-guard + ESLint no-restricted-imports rule.**

## What Happened

S12 closed M002's frontend design-language reset by sweeping the entire app (~85 files) onto the S08 ui/* primitive set and retiring the bespoke components/common/ + components/buttons/ directories outright.

**T01** built the four destination primitives (Card / Alert / Spinner / Pagination) so every downstream sweep could be a mechanical import-rename. Card preserved the legacy `glass`/`elevated` variants in cardVariants alongside the new shadcn `default`. Alert exported three named wrappers (ErrorAlert / ConfirmationAlert / SuccessAlert) mirroring the legacy `{message: string | null}` call signature so the page sweep was zero-callsite-churn. Spinner unified the legacy 6-size × 3-color matrix onto `text-primary` (intentional design-system simplification). Pagination preserved `getPageNumbers()` ellipsis logic VERBATIM, restyled onto ui/Button under the hood. Refreshed 3 kitchen-sink visual baselines.

**T02** swept Tier A (6 trivial public statics: About/ContactUs/Pricing/Checkout/Support/BugReport) + Tier B (7 auth pages + GoogleAuthFlow). Established the swap rules applied uniformly across the slice: import-rename for Card/Alert/Spinner; legacy Input `label`/`leftIcon`/`rightIcon` props rendered as JSX siblings; ButtonStretch → `<Button className='w-full'>`; legacy `error` prop → aria-invalid + sibling div; bespoke colors retired in favor of formal variants per MEM116.

**T03** swept Tier C1 (Profile/Home/Search + 6 profile inner components incl. 3 password/2fa dialogs + Header). Profile (461 LOC) was the densest single page. All 3 dialogs adopted the S09 parent-owned-state Dialog pattern (open/onOpenChange + sm:max-w-* sizing) so legacy handleClose() side-effects fire on Escape/overlay-click/X-button. **Introduced the MEM124 re-export shim pattern** — created one-line stubs at `forms/ImageUpload`, `images/ImageWithPlaceholder` so future-canonical paths resolve in T03 without forcing T04/T05's wholesale relocation.

**T04** swept Tier C2 (the heaviest tier — 9 builder/parts/buildLists pages including ViewPart at 978 LOC + 21 inner components in parts/buildListParts/buildLists/cars). Same swap rules; importers updated to point at future-relocated helper paths (forms/, cars/, filters/, tables/, ui/card-info-item, buildLists/AddItemTile). DeleteConfirmationDialog → ui/ConfirmDialog with destructive variant and parent-owned-state. ParentNavigationLink inlined at 4 callsites so T05 could delete the helper. Type-check exited 1 with exactly 3 expected `Cannot find module ./AddItemTile` errors — resolved by T05's file move.

**T05** closed three coordinated chunks atomically: (a) admin tier sweep (9 admin pages incl. 2,665-line CrawlerAdmin + ReportDialog inner component); (b) structural-infra relocation (`git mv` RouteGroupBoundary[+test] → components/routes/, ErrorBoundary[+test] + 4 banner components → components/shell/, App.tsx + main.tsx imports rewired); (c) helper relocation + legacy delete via the **MEM127 sequence** (rm shim → git mv original → fix sibling imports inside moved file). Final delete: components/common/ and components/buttons/ no longer exist on disk. 596 unit/integration tests pass, type-check exits 0.

**T06** locked R017 enforcement and ran the full verification gauntlet. Authored `frontend/src/__tests__/no-legacy-primitives.test.ts` (vitest) — walks src/ recursively, asserts no file matches `from\s+['"](?:\.\.\/)+(?:common|buttons)/`. Paired with ESLint no-restricted-imports rule on `**/components/common/*` + `**/components/buttons/*` for PR-time catches. Discovered + fixed pre-existing vitest test-infra defect (default include glob picks up Playwright e2e specs and crashes them) by adding `test.include: ['src/**/*.{test,spec}.{ts,tsx}']` + `test.exclude: ['e2e/**']` to vitest.config.ts (MEM129). Refreshed 3 kitchen-sink baselines (the only PNGs that drifted post-T03/T04/T05). Final gauntlet: type-check exit 0, 597 unit/integration tests pass, 35 e2e tests pass at all 3 viewports, lint baseline preserved (108 errors == MEM062), grep returns only the self-referential match in the guard test.

**Patterns established for downstream slices and future migrations:**
- MEM124: Re-export shim pattern for staged multi-task relocations.
- MEM127: rm shim → git mv original → fix sibling refs preserves git history.
- MEM116-extended: Formal variant first, className overrides only for layout shape (h-auto, p-0, w-full, justify-start).
- Parent-owned-state Dialog pattern (open/onOpenChange + side-effect wiring) carried forward from S09.
- Two-layer boundary enforcement: vitest grep-guard + ESLint no-restricted-imports.

**What S13 inherits:** Every page in the app is on the new design system; the grep guard locks the boundary at CI time; the e2e suite proves end-to-end correctness at three viewports for the priority pages (kitchen-sink, build-list, parts-catalog, price-history, price-alerts, admin, smoke). S13 only needs the live full-stack milestone-validation pass (real product → spec extraction → ingest → aggregation → UI → alert email + load-test re-run + S05 budget re-check).

## Verification

All slice-level gates pass:

1. **Type-check**: `cd frontend && npm run type-check` → exit 0 (verified post-completion). Confirms every file in the migrated tree resolves cleanly against ui/* primitives, the relocated infra paths (routes/, shell/, forms/, cars/, images/, filters/, tables/), and the new card-info-item primitive.

2. **Unit + integration tests**: `cd frontend && npm test -- --run` → 90 files / 597 tests pass (T06 final gauntlet). Includes the new no-legacy-primitives.test.ts which scans src/ for any `from '...common/'` or `'...buttons/'` import and asserts zero hits.

3. **E2E suite**: `cd frontend && npm run test:e2e` → 35 passed / 10 skipped at mobile (375×667), tablet (768×1024), desktop (1280×800). All 7 spec files (components, build-list, parts-catalog, price-history, price-alerts, admin, smoke) green with refreshed baselines.

4. **Lint baseline preserved**: `cd frontend && npm run lint` → 108 errors / 52 warnings = MEM062 baseline. 0 new errors in S12-touched non-test files. 0 no-restricted-imports violations means the guard fired on nothing.

5. **Grep guard**: `grep -rln 'components/common\|components/buttons' frontend/src/` → only the self-referential match in `no-legacy-primitives.test.ts` (allowlisted in the test docstring/regex literal). No real importers remain.

6. **Legacy directory deletion**: `test ! -d frontend/src/components/buttons` and `test ! -d frontend/src/components/common` → both true. Both directories removed in T05; non-primitive helpers relocated to forms/ + cars/ + images/ + filters/ + tables/ + routes/ + shell/.

7. **CI guard installed**: `frontend/src/__tests__/no-legacy-primitives.test.ts` walks src/ recursively (excluding test dirs), asserts no file matches the legacy-import regex. Paired with `eslint.config.js` no-restricted-imports rule on `**/components/common/*` + `**/components/buttons/*`. Both fail-fast a future PR that re-introduces the legacy palette.

R017 satisfied (every page on the new component library, enforcement check committed). R020 preserved (S09/S10/S11 priority-page accessibility patterns — keyboard nav, focus indicators, escape-on-dialog — applied uniformly across the new sweeps via the parent-owned-state Dialog pattern and ui/* primitives' built-in focus management).

## Requirements Advanced

None.

## Requirements Validated

- R017 — Every page in frontend/src/pages/ migrated to ui/* design system; components/common/ + components/buttons/ directories deleted; no-legacy-primitives.test.ts vitest test enforces boundary; ESLint no-restricted-imports rule provides redundant PR-time check; full grep returns only the self-referential match in the guard test itself; type-check + 597 unit tests + 35 e2e tests + lint baseline all green.
- R020 — Parent-owned-state Dialog pattern (open/onOpenChange + closeDialog wiring) preserved across all dialog migrations (Profile dialogs, GoogleAuthFlow, ConfirmDialog adapters). Escape/overlay-click/X-button all dismiss correctly with side-effect cleanup. ui/* primitives inherit shadcn-style focus management (visible focus indicators, tab order). E2E suite at 3 viewports exercises keyboard nav on the priority pages (build-list, parts-catalog, admin).

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

None.

## Known Limitations

"None blocking. Two surfaced and tracked: (1) Pre-existing lint baseline of 108 errors / 52 warnings (MEM062) is preserved — S12 introduced 0 new errors but did not pay down existing debt. (2) The vitest scoping fix (MEM129) was discovered and applied during T06; future agents can reference vitest.config.ts as the canonical example of how to scope vitest away from Playwright e2e specs."

## Follow-ups

"S13 milestone validation should manually smoke ~30 surfaces deferred from autonomous-mode UAT (Tier A statics, Tier B/C/D inner forms not screenshot-asserted by Playwright). Type-check + lint + grep prove import correctness; visual polish benefits from human eyeball. Optionally: pre-existing lint baseline (108 errors at MEM062) is unchanged but represents technical debt that could be worked down in a future cleanup slice; no blocker for M002 close."

## Files Created/Modified

- `frontend/src/components/ui/card.tsx` — shadcn-idiom Card with cardVariants cva (default/glass/elevated × padding axis); preserves legacy variant axis
- `frontend/src/components/ui/alert.tsx` — Alert with variants (default/destructive/success) + named wrappers ErrorAlert/ConfirmationAlert/SuccessAlert mirroring legacy {message: string|null} signature
- `frontend/src/components/ui/spinner.tsx` — Loader2-backed Spinner with 6-size scale + optional text/inline; default export preserved for legacy import shape
- `frontend/src/components/ui/pagination.tsx` — Pagination with verbatim getPageNumbers ellipsis logic; restyled onto ui/Button under the hood
- `frontend/src/components/ui/card-info-item.tsx` — Folded-into-ui card-info-item primitive (was components/common/CardInfoItem)
- `frontend/src/__tests__/no-legacy-primitives.test.ts` — vitest grep-guard walking src/ asserting no `from '...common/' or '...buttons/'` import (R017 enforcement)
- `frontend/eslint.config.js` — no-restricted-imports rule on **/components/common/* + **/components/buttons/* (R017 enforcement, PR-time)
- `frontend/vitest.config.ts` — scoped test.include to src/ + test.exclude e2e/ (MEM129 fix for Playwright/vitest cross-runner crash)
- `frontend/src/App.tsx + main.tsx` — rewired imports to components/routes/ and components/shell/ for relocated boundary + banner infra
- `frontend/src/components/routes/{RouteGroupBoundary,EmailVerifiedRoute,ProtectedRoute,GuestRoute}.tsx + .test.tsx` — relocated route guards from components/common/
- `frontend/src/components/shell/{ErrorBoundary,CookieConsentBanner,ChromeExtensionPromo,SubscriptionPromo,BetaBanner}.tsx + .test.tsx` — relocated app-shell infra from components/common/
- `frontend/src/components/{forms,cars,images,filters,tables,buildLists}/` — relocated 9 non-primitive helpers (SearchableSelect, ImageUpload, CarModelMultiSelect, ImageWithPlaceholder, VehicleFilterSection/Chips, ResponsiveTableWrapper, AddItemTile)
- `frontend/src/pages/* + components/profile/* + components/parts/* + components/buildLists/* + components/buildListParts/* + components/cars/* + components/admin/* + components/authentication/GoogleAuthFlow.tsx + components/users/UserCard.tsx + components/layout/globalHeader/Header.tsx` — ~85 files swept off legacy common/ + buttons/ onto ui/* primitives; data-testid/useEffect/cancellation/redirect/submit-handler all preserved
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-{mobile,tablet,desktop}-linux.png` — refreshed Playwright visual baselines after T01 + T06 design-system tweaks
- `DELETED: frontend/src/components/common/ + frontend/src/components/buttons/` — legacy directories removed in T05; non-primitive helpers relocated, primitive replacements at ui/*
