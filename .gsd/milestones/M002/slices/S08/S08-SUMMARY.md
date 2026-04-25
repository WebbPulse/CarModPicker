---
id: S08
parent: M002
milestone: M002
provides:
  - ["frontend/src/styles/tokens.css", "frontend/src/components/ui/{button,input,select,tabs,combobox,dialog,dropdown-menu,sheet,toast}.tsx", "frontend/src/pages/_KitchenSink.tsx", "frontend/src/lib/utils.ts (cn helper)", "frontend/playwright.config.ts (mobile/tablet/desktop projects + 0.2% threshold)", "frontend/e2e/components.spec.ts + 3 baseline PNGs under e2e/components.spec.ts-snapshots/"]
requires:
  []
affects:
  - ["S09 (build-list redesign)", "S10 (parts catalog redesign)", "S11 (admin shell + extraction-health UI)", "S12 (repo-wide ripple reskin)", "S13 (final integration)"]
key_files:
  - ["frontend/src/styles/tokens.css", "frontend/src/index.css", "frontend/src/lib/utils.ts", "frontend/src/components/ui/button.tsx", "frontend/src/components/ui/input.tsx", "frontend/src/components/ui/select.tsx", "frontend/src/components/ui/tabs.tsx", "frontend/src/components/ui/combobox.tsx", "frontend/src/components/ui/dialog.tsx", "frontend/src/components/ui/dropdown-menu.tsx", "frontend/src/components/ui/sheet.tsx", "frontend/src/components/ui/toast.tsx", "frontend/src/pages/_KitchenSink.tsx", "frontend/src/App.tsx", "frontend/src/App.coverage.test.tsx", "frontend/playwright.config.ts", "frontend/e2e/components.spec.ts", "frontend/e2e/components.spec.ts-snapshots/", "frontend/package.json"]
key_decisions:
  - ["HSL channel format for color tokens (`222 47% 6%`) wrapped via hsl() in @theme — matches shadcn convention, lets consumers compose alpha later. Legacy --primary-*/--neutral-*/--accent-* blocks left intact for additive coexistence until S12.", "Animation utilities inlined as @keyframes + @utility declarations in tokens.css instead of installing tailwindcss-animate — matches slice plan preference, avoids one more dependency, composes per-axis the way shadcn primitives expect.", "All Playwright projects use `devices['Desktop Chrome']` with explicit viewport overrides (NOT iPhone SE / iPad presets) — those device descriptors default to webkit, mixing engines would produce cross-engine pixel diffs no maxDiffPixelRatio can absorb.", "Production exclusion of /_kitchen-sink requires guarding the `lazy()` factory itself, not just the <Route> JSX — the dynamic-import expression is statically reachable from module top level otherwise.", "Multi-overlay kitchen-sink uses `modal={false}` on Dialog + DropdownMenu + Sheet so all three open primitives coexist without trapping focus or blocking pointer events.", "Each primitive re-exports its cva() instance (buttonVariants, inputVariants, sheetVariants) from the same file — accept the react-refresh/only-export-components warning, this is canonical shadcn convention required for downstream variant composition during S09–S12.", "Used conditional spread `{...(value !== undefined ? { value } : {})}` to satisfy `exactOptionalPropertyTypes: true` on Radix wrappers (DropdownMenuCheckboxItem.checked, Sonner Toaster className) — recurs in every Radix wrapper.", "Combobox uses the local Button as its trigger via PopoverPrimitive.Trigger asChild — keeps trigger styling consistent with the rest of the form surface and inherits all six variants.", "cmdk imported via named exports (CommandInput, CommandList, etc.) NOT the Command.X namespace — verified against node_modules/cmdk/dist/index.d.ts."]
patterns_established:
  - ["shadcn-style primitives in components/ui/: each primitive in its own file, consumes tokens via Tailwind utilities backed by HSL channels, uses cn() helper, exports its cva() instance from the same file for downstream variant composition.", "Tailwind v4 + shadcn animations without tailwindcss-animate: @keyframes enter/exit driven by --tw-enter-*/--tw-exit-* custom properties + @utility declarations for animate-in/animate-out + per-axis utilities (fade-in-0, zoom-in-95, slide-in-from-{dir}-2, duration-200).", "Dev-only routes in Vite: guard the `lazy()` factory itself with `import.meta.env.DEV ? lazy(...) : null` then narrow with `{import.meta.env.DEV && Page && <Route .../>}` so Rollup tree-shakes the chunk out of production bundles.", "Playwright multi-viewport projects: spread `devices['Desktop Chrome']` for all projects + override only viewport — keeps the engine consistent so visual diffs are size-driven, not engine-driven.", "Exact-optional-prop type workaround for Radix wrappers: `{...(value !== undefined ? { value } : {})}` whenever forwarding a maybe-undefined prop to a third-party component."]
observability_surfaces:
  - ["Playwright HTML reporter at frontend/playwright-report/ on failed runs", "Pixel-diff PNGs alongside snapshots on regression (test-results/<test>-<viewport>-{actual,diff}.png)", "`pageerror` listener in components.spec.ts re-throws runtime React errors as hard test failures (not silent pixel drift)", "/_kitchen-sink in dev for live primitive state inspection"]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-25T19:48:23.659Z
blocker_discovered: false
---

# S08: Design system spike + tokens + shadcn primitives + kitchen sink

**Landed the M002 design-system substrate: dark-palette CSS-variable tokens, 9 Radix-based shadcn primitives, dev-only kitchen-sink page, and Playwright multi-viewport visual-regression spec — `npm run test:e2e` exits 0 with 6/6 passing, three baseline PNGs committed.**

## What Happened

S08 delivered the foundation that S09–S12 will reskin against. Six tasks landed in order across one focused work session:

**T01 — Runtime deps + scaffold.** Installed the 7 Radix packages (`@radix-ui/react-{dialog,dropdown-menu,tabs,select,toast,slot,popover}`), the className composition trio (`class-variance-authority` 0.7.1 + `clsx` 2.1.1 + `tailwind-merge` 3.5.0), `lucide-react` (icons), `sonner` (Toast), and `cmdk` (Combobox). Added the standard shadcn `cn()` util at `frontend/src/lib/utils.ts` and scaffolded `frontend/src/components/ui/` and `frontend/src/styles/` with `.gitkeep` placeholders. lucide-react resolved to ^1.11.0 (the 0.x line was retired by npm) — captured as memory so future work doesn't second-guess it.

**T02 — Dark-palette token layer.** Created `frontend/src/styles/tokens.css` declaring the full shadcn-standard token vocabulary on `:root` using HSL-channel values (e.g. `222 47% 6%`) so consumers can compose alpha via `hsl(var(--background) / <alpha>)`. Color tokens cover background/foreground, card, popover, primary/secondary/accent, muted, destructive (each with `-foreground` pair), plus border/input/ring; spacing exposes `--radius` (0.5rem) and the `--radius-sm/md/lg/xl` scale; shadows `--shadow-sm/md/lg/xl`; z-index layers `--z-dropdown/modal/toast`. The `@theme` block bridges every token into Tailwind v4 utilities so `bg-background`, `text-foreground`, `border-border`, etc. resolve. Imported once from `index.css`. Production build confirmed `--background` / `.bg-background` present in `dist/assets/*.css`. Legacy `--primary-*/--neutral-*/--accent-*` blocks left intact — new tokens are strictly additive until S12 retires `components/common/`.

**T03 — Form primitives (Wave 1).** Built `button.tsx` (cva: 6 variants × 4 sizes, `asChild` via Radix Slot, loading state with lucide `Loader2`), `input.tsx` (token-driven default/focus/disabled/error states; error triggers off `aria-[invalid=true]`), `select.tsx` (full Radix Select wrapper with portal + chevron icons), `tabs.tsx` (Radix Tabs with active/focus/disabled states), and `combobox.tsx` (composed primitive: cmdk + Radix Popover + the local Button trigger; toggle-clear behavior on re-select). Verified the cmdk import shape against `node_modules/cmdk/dist/index.d.ts` — all subcomponents are named exports.

**T04 — Overlay primitives (Wave 2).** Built `dialog.tsx` (full Radix wrapper + close button), `dropdown-menu.tsx` (full Radix wrapper with `inset` prop + sub-menu support), `sheet.tsx` (wraps Radix Dialog with a `cva()`-driven `side` variant: top/right/bottom/left; default `right`), and `toast.tsx` (wraps sonner with `theme="dark"` + `toastOptions.classNames` keyed to popover/foreground/destructive tokens). Did NOT install `tailwindcss-animate` per slice plan preference — instead appended `@keyframes enter` / `@keyframes exit` (driven by `--tw-enter-*` / `--tw-exit-*` custom properties) plus `@utility animate-in` / `animate-out` declarations and per-axis utilities (`fade-in-0`, `zoom-in-95`, `slide-in-from-{top,bottom,left,right}-2`, `duration-200`, etc.) inline in `tokens.css`. This retroactively fixed `select.tsx` from T03, which already used `animate-in`/`animate-out` class names. With `exactOptionalPropertyTypes: true` set in tsconfig, applied the `{...(value !== undefined ? { value } : {})}` conditional-spread workaround for `DropdownMenuCheckboxItem.checked` and Sonner Toaster `className` — captured as memory since this will recur in every Radix wrapper.

**T05 — Kitchen-sink page + dev-only routing.** `frontend/src/pages/_KitchenSink.tsx` renders one `<section data-testid="section-X">` per primitive with every meaningful state visible at once: Button (every variant × size + disabled + loading rows), Input (default/focus/disabled/error), Select (closed + `defaultOpen`), Combobox (5-option + empty), Tabs (3-trigger with one disabled), Dialog/DropdownMenu/Sheet (all `defaultOpen modal={false}` so they coexist on the page without trapping focus), Toast (mounts `<Toaster />` + fires `toast('Sample toast', { id: 'kitchen-sink-static' })` from `useEffect` so sonner dedupes the React strict-mode double-invocation). Wired into `App.tsx` inside the public `RouteGroupBoundary` using `lazyWithReload`. **Production exclusion gotcha:** guarding only the `<Route>` JSX with `import.meta.env.DEV` did NOT exclude the chunk because the `lazy(() => import(...))` call at module top level remained statically reachable — Rollup still emitted `_KitchenSink-*.js` (25.8kB). Moved the guard to the lazy factory itself: `const KitchenSink = import.meta.env.DEV ? lazy(...) : null` then narrowed with `{import.meta.env.DEV && KitchenSink && <Route .../>}`. Re-verified: no `_KitchenSink-*.js` in production dist, vendor bundle dropped from 893kB → 696kB because cmdk and sonner are no longer transitive prod imports.

**T06 — Playwright multi-viewport spec.** Replaced the single `chromium` project in `playwright.config.ts` with three viewport projects: `mobile` (375×667), `tablet` (768×1024), `desktop` (1280×800), each spreading `devices['Desktop Chrome']` and overriding only `viewport`. **Did NOT use `devices['iPhone SE']` / `devices['iPad']`** because those descriptors set `defaultBrowserType: 'webkit'` — mixing webkit baselines with chromium desktop would have produced cross-engine pixel diffs no `maxDiffPixelRatio` could absorb. Set `expect.toHaveScreenshot.maxDiffPixelRatio = 0.002` (R013's 0.2% bar) and `animations: 'disabled'`, plus per-test `timeout: 30_000` for cold-start absorption. `e2e/components.spec.ts` navigates to `/_kitchen-sink`, awaits `networkidle` + `document.fonts.ready`, sleeps 300ms for mount-time effects, listens for `pageerror` so runtime React errors surface as hard failures, then asserts `toHaveScreenshot({ fullPage: true })`. Three baseline PNGs landed in `e2e/components.spec.ts-snapshots/` keyed by project name. Final fresh-evidence run: `npm run test:e2e` exits 0 with **6 passed (4.1s)** — 3 components.spec runs + 3 smoke.spec runs across the three projects.

**Pre-existing baseline acknowledged.** `npm run lint` exits 1 with 104 errors, all in test files (Profile.test.tsx, Search.test.tsx, admin/*, ViewBuildLog.test.tsx, api/*.test.ts) and `coverage/*.js`. Confirmed via stash-diff that the new `ui/` primitives contribute zero new errors — only informational warnings (`react-x/no-forward-ref` for React 19 + intentional `react-refresh/only-export-components` from cva re-exports, which is the canonical shadcn convention). Tracked separately for follow-up cleanup; does not block S08.

**Verification gate path bug.** The auto-verify gate that fired before this run executed greps from the repo root (e.g. `grep -q "name: 'mobile'" playwright.config.ts`) instead of from `frontend/`. The artifacts are present and correct — every grep marker passes when run with the proper `cd frontend &&` prefix that every task verify command in the slice plan uses. Fresh `npm run test:e2e` from `frontend/` exits 0. Reported here so the orchestrator can recognize the false-negative and not regress on a path-handling assumption.

This slice is the substrate for S09 (build-list), S10 (parts catalog), S11 (admin shell), and S12 (ripple reskin). Nothing user-facing yet — kitchen-sink is dev-only and excluded from prod bundles.

## Verification

All slice-level "Must-Haves" verified:

1. **Tokens.** `frontend/src/styles/tokens.css` defines color/spacing/type/radii/shadow tokens; `@theme` bridge resolves Tailwind utilities (`bg-background`, `border-border`, `ring-ring`, `rounded-{sm,md,lg,xl}`, `shadow-{sm,md,lg,xl}`); imported from `index.css`. Verified at T02 via `npm run build` (exit 0) + `grep '\.bg-background\|--background' dist/assets/*.css` (match).

2. **9 primitives present.** `ls frontend/src/components/ui/{button,input,select,tabs,combobox,dialog,dropdown-menu,sheet,toast}.tsx` — all 9 files exist. Each renders the documented states (default/hover/focus/disabled/loading/error where applicable). `npm run type-check` exit 0 across all primitives.

3. **Kitchen-sink page mounts in dev.** `/_kitchen-sink` renders all 9 primitives with `data-testid="section-X"` markers. Verified with `grep -qE 'data-testid="section-(button|input|select|combobox|tabs|dialog|dropdown-menu|sheet|toast)"' src/pages/_KitchenSink.tsx`. Route gated by `import.meta.env.DEV`; production build confirms no `_KitchenSink-*.js` chunk in `dist/`.

4. **Playwright config has three projects + 0.2% threshold.** `grep -q "name: 'mobile'" playwright.config.ts && grep -q "name: 'tablet'" playwright.config.ts && grep -q "name: 'desktop'" playwright.config.ts && grep -q 'maxDiffPixelRatio' playwright.config.ts` — all match.

5. **components.spec.ts targets kitchen-sink with toHaveScreenshot.** `grep -q '_kitchen-sink' e2e/components.spec.ts && grep -q 'toHaveScreenshot' e2e/components.spec.ts` — both match. Three baseline PNGs committed under `e2e/components.spec.ts-snapshots/` (kitchen-sink-visual-regression-1-{mobile,tablet,desktop}-linux.png).

6. **smoke.spec.ts continues to pass** — included in the 6/6 passing run.

7. **`npm run test:e2e` exits 0.** Fresh evidence in this session: `cd frontend && npm run test:e2e` → **6 passed (4.1s)** (3 components.spec + 3 smoke.spec runs across mobile/tablet/desktop projects).

| # | Command | Exit | Verdict |
|---|---|---|---|
| 1 | `cd frontend && grep -q "name: 'mobile'" playwright.config.ts && grep -q "name: 'tablet'" playwright.config.ts && grep -q "name: 'desktop'" playwright.config.ts && grep -q 'maxDiffPixelRatio' playwright.config.ts && grep -q '_kitchen-sink' e2e/components.spec.ts && grep -q 'toHaveScreenshot' e2e/components.spec.ts` | 0 | pass |
| 2 | `cd frontend && npm run test:e2e` | 0 | pass (6 passed, 4.1s) |

Pre-existing `npm run lint` baseline (104 errors in test/coverage files; documented as MEM062) acknowledged but not in scope of S08.

## Requirements Advanced

None.

## Requirements Validated

- R011 — tokens.css with HSL channels for background/foreground/card/popover/primary/secondary/accent/muted/destructive/border/input/ring + radius/shadow/z-index scales; @theme bridge into Tailwind v4; imported from index.css; production build confirms tokens reach dist/assets/*.css
- R012 — 9 primitives committed under frontend/src/components/ui/ on Radix + cmdk + sonner; all states (default/hover/focus/disabled/loading/error) covered; npm run type-check exit 0
- R013 — playwright.config.ts has mobile/tablet/desktop projects + maxDiffPixelRatio 0.002; e2e/components.spec.ts targets /_kitchen-sink with toHaveScreenshot fullPage; 3 baseline PNGs committed; npm run test:e2e exits 0 with 6/6 passing

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"T06: substituted `Desktop Chrome` for the slice plan's suggested `iPhone SE` / `iPad` device presets on the mobile and tablet projects to avoid mixing webkit and chromium engines in one snapshot suite — viewport dimensions match the plan exactly. T05: applied `modal={false}` on Dialog/DropdownMenu/Sheet (in addition to the plan's `defaultOpen`) so all three modal-capable overlays coexist in the kitchen-sink without trapping focus or blocking pointer events on sibling sections. T05: moved the dev-only guard from the `<Route>` JSX (per the plan) to the `lazy()` factory itself — the JSX-only guard did not tree-shake the chunk out of production builds."

## Known Limitations

"Pre-existing `npm run lint` baseline of 104 errors in test files (Profile.test.tsx, Search.test.tsx, admin/*, ViewBuildLog.test.tsx, api/*.test.ts) and coverage/*.js — confirmed by stash-diff that no new errors come from S08 work. Tracked as MEM062 for follow-up cleanup; does not block this slice. New ui/ primitives produce only informational warnings (`react-x/no-forward-ref` for React 19 + intentional `react-refresh/only-export-components` from cva re-exports — the canonical shadcn convention). Vite proxy `ECONNREFUSED 127.0.0.1:8000` errors during e2e run are expected (no backend running) and do not affect snapshot capture."

## Follow-ups

"Future cleanup: address the 104 pre-existing lint errors in test/coverage files (MEM062) — separate from S08 scope. When S09–S12 reskin pages onto these primitives, re-run components.spec.ts after each page lands to catch any token regression introduced by page-level customizations. If `e2e/smoke.spec.ts` proxy errors become noisy in CI, mock /api/app-settings + /api/users/me via page.route() in a fixture. Light-mode tokens are deferred per R011 — revisit if it falls out of token architecture naturally during S09–S12."

## Files Created/Modified

- `frontend/src/styles/tokens.css` — New — dark-palette HSL tokens + @theme bridge + inline @keyframes/@utility animation utilities
- `frontend/src/index.css` — Added @import './styles/tokens.css' after the existing tailwindcss import
- `frontend/src/lib/utils.ts` — New — standard shadcn cn() helper (twMerge(clsx(inputs)))
- `frontend/src/components/ui/button.tsx` — New — cva-based Button with 6 variants × 4 sizes + asChild + loading
- `frontend/src/components/ui/input.tsx` — New — token-driven input with default/focus/disabled/error states
- `frontend/src/components/ui/select.tsx` — New — full Radix Select wrapper
- `frontend/src/components/ui/tabs.tsx` — New — Radix Tabs wrapper
- `frontend/src/components/ui/combobox.tsx` — New — cmdk + Popover + local Button trigger composite
- `frontend/src/components/ui/dialog.tsx` — New — full Radix Dialog wrapper with close button
- `frontend/src/components/ui/dropdown-menu.tsx` — New — full Radix DropdownMenu wrapper with sub-menu support
- `frontend/src/components/ui/sheet.tsx` — New — Radix Dialog wrapped with cva side variant
- `frontend/src/components/ui/toast.tsx` — New — sonner Toaster wrapper themed to tokens
- `frontend/src/pages/_KitchenSink.tsx` — New — dev-only canvas rendering all 9 primitives in every state
- `frontend/src/App.tsx` — Wired /_kitchen-sink under public RouteGroupBoundary, guard moved to lazy() factory itself for prod tree-shaking
- `frontend/src/App.coverage.test.tsx` — Added /_kitchen-sink to ALL_ROUTES (public group) per existing PR-review rule
- `frontend/playwright.config.ts` — Replaced single chromium project with mobile/tablet/desktop, added maxDiffPixelRatio 0.002 + animations:disabled + per-test 30s timeout
- `frontend/e2e/components.spec.ts` — New — kitchen-sink visual-regression test with networkidle + fonts.ready + pageerror listener
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png` — Baseline PNG
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png` — Baseline PNG
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png` — Baseline PNG
- `frontend/package.json` — Added Radix, cmdk, sonner, lucide-react, cva, clsx, tailwind-merge runtime deps
- `frontend/package-lock.json` — Lockfile updated for new deps
