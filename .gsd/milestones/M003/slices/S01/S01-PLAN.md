# S01: Global token sweep — palette utility migration

**Goal:** Replace every raw legacy palette utility (`bg-primary-[0-9]`, `text-primary-[0-9]`, `bg-neutral-[0-9]`, `text-neutral-[0-9]`, `bg-emerald-[0-9]`, `text-emerald-[0-9]`, `bg-indigo-[0-9]`, `text-indigo-[0-9]`, `text-accent-emerald|amber|rose|purple`, plus `bg-/border-/ring-/from-/to-/via-/shadow-` companions on the same color stems) across all 68 consumer files in `frontend/src/` with semantic tokens (`text-foreground`, `text-muted-foreground`, `bg-card`, `bg-muted`, `text-primary`, `text-success`, `text-warning`, `text-info`, `text-destructive`, `border-border`, etc.) backed by `frontend/src/styles/tokens.css`. Land any required gap-fill semantic tokens (`--success`, `--warning`, `--info` and their foregrounds) and the `ui/alert.tsx` `success` variant fix as standalone atomic precursor commits per R053. The legacy `@theme` palette block in `index.css` survives until S04 — this slice only touches consumer files plus `tokens.css` plus `components/ui/alert.tsx`.
**Demo:** Every raw palette utility (`bg-primary-500`, `text-neutral-300`, `text-emerald-400`, `text-indigo-300`, `text-accent-*`, `bg-emerald-400`, etc.) replaced with semantic tokens across all consumer files in `frontend/src/`. Refreshed Playwright baselines at 360/768/1280 for every page touched. Build, lint, type-check, vitest, e2e all green.

## Must-Haves

- After this: zero raw palette utility hits in `frontend/src/` for the migration-targeted color stems verified by the R048 grep gates, refreshed Playwright baselines at mobile (375)/tablet (768)/desktop (1280) for every page touched, and `vite build` + `tsc --noEmit` + `eslint` (108-error baseline preserved per MEM062) + `vitest --run` + full Playwright suite all green.

## Proof Level

- This slice proves: - This slice proves: contract (semantic-token vocabulary covers every consumer surface; no raw palette utility survives in app code; existing UX is preserved at the pixel level modulo expected token-swap diffs)
- Real runtime required: yes (vite build + Playwright e2e run against dev server)
- Human/UAT required: no (mechanical swap; baseline diffs reviewed against expected token-swap deltas before commit; no IA changes)

## Integration Closure

- Upstream surfaces consumed: `frontend/src/styles/tokens.css` semantic-token vocabulary (M002/S08 substrate), `frontend/src/components/ui/*` primitives (M002/S08–S12), `frontend/playwright.config.ts` 3-viewport project setup (M002/S13).
- New wiring introduced in this slice: 4 new semantic tokens (`--success`, `--success-foreground`, `--warning`, `--warning-foreground`, `--info`, `--info-foreground`) added to `tokens.css` `:root` + `@theme` bridge so utilities `bg-success` / `text-success` / `border-success/N` / `text-warning` / `bg-info/10` etc. resolve. `components/ui/alert.tsx` `success` variant rewired onto `bg-success/10 text-success border-success/50`.
- What remains before the milestone is truly usable end-to-end: glass-* + legacy `:root` consumer purge (S02), responsive audit + ViewPart IA (S03), hard delete of `@theme` palette and decorative utilities (S04), polish pass (S05), close gauntlet (S06). After S01 the consumer-side swap is structurally complete for the migration-targeted color stems; downstream slices depend on this clean substrate but do not block it.

## Verification

- Runtime signals: none added by this slice — pure CSS class swaps. Existing structured logging, metrics, and error paths unchanged.
- Inspection surfaces: post-slice grep gates (R048) act as the standing inspection surface — `rg 'text-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' frontend/src/` returning 0 hits is the canonical health check. Playwright baseline diffs surface any unintended visual regression.
- Failure visibility: a regressed page surfaces as a Playwright snapshot diff exceeding `maxDiffPixelRatio: 0.002`; build-time the legacy utilities still resolve (the `@theme` block survives until S04) so the failure mode is purely visual, not compile-time.
- Redaction constraints: none.

## Tasks

- [x] **T01: Add `--success`/`--warning`/`--info` semantic tokens and fix `ui/alert.tsx` success variant** `est:20m`
  Atomic precursor commit. Adds the missing status semantic tokens to `frontend/src/styles/tokens.css` so subsequent swap tasks can map emerald → success, amber → warning, indigo → info, rose → destructive. Pattern-matches the existing token surface: HSL-channel values in `:root`, mirrored in the `@theme` bridge as `--color-<token>: hsl(var(--<token>))`. Also fixes `frontend/src/components/ui/alert.tsx` `success` variant (currently the only `ui/*` raw-palette violator) to consume the new `text-success`/`bg-success/10`/`border-success/50` vocabulary so the variant becomes the canonical success surface for all consumers.

Rationale (per R053, MEM149): the migration cannot complete without these tokens — emerald (success), amber (warning), indigo (info), rose (destructive — token already exists) all need a semantic landing pad. This commit is small, justified, and ships before any consumer swap depends on it. Bias remains consumption: only 3 new color tokens added (with `-foreground` companions), no primitives added, no keyframes added.

Values to use (HSL channels matching the dark palette):
- `--success: 142 71% 45%;` (emerald-500-ish)
- `--success-foreground: 144 70% 96%;`
- `--warning: 38 92% 50%;` (amber-500-ish)
- `--warning-foreground: 48 96% 89%;`
- `--info: 217 91% 60%;` (indigo-500-ish; matches existing primary HSL since indigo-500 ≈ primary-500 in this palette — keep distinct token name for semantic clarity)
- `--info-foreground: 213 100% 97%;`

## Failure Modes

Not applicable — this task adds CSS custom properties and edits one component file. No external dependencies, no async paths.

## Negative Tests

- `vite build` must succeed with the new tokens declared but no consumer using them yet (proves the token additions don't break compilation).
- After alert.tsx swap: existing `<Alert variant="success">` consumers (e.g. `frontend/src/components/__tests__/` if any) still render — class names changed, but the variant API is unchanged.
  - Files: `frontend/src/styles/tokens.css`, `frontend/src/components/ui/alert.tsx`
  - Verify: cd frontend && npm run build && grep -q 'success-foreground' src/styles/tokens.css && grep -q 'bg-success/10 text-success border-success/50' src/components/ui/alert.tsx && ! rg 'emerald-500' src/components/ui/alert.tsx

- [x] **T02: Global swap: neutral palette utilities → semantic tokens (text/bg/border/ring on all surfaces)** `est:2h`
  Bulk semantic swap of every raw `*-neutral-[0-9]+(/[0-9]+)?` utility across all 68 consumer files in `frontend/src/`. The neutrals are the highest-volume cohort (~250+ occurrences across `text-neutral-{100,200,300,400,500,600,900}`, `bg-neutral-{700,800,900,950}`, `border-neutral-{500,600,700}`).

Mapping table (apply file-by-file with per-file judgment for the 300/200 cases):
- `text-neutral-400` → `text-muted-foreground` (default — secondary body text)
- `text-neutral-500` → `text-muted-foreground` (placeholder/tier-3 label)
- `text-neutral-600` → `text-muted-foreground` (very subtle label)
- `text-neutral-300` → `text-foreground` (default; flip to `text-muted-foreground` only when surrounding code shows a tier-2 label — e.g. `text-neutral-400 hover:text-neutral-300` should become `text-muted-foreground hover:text-foreground`)
- `text-neutral-200` → `text-foreground`
- `text-neutral-100` → `text-foreground`
- `text-neutral-900` → `text-background` (rare — usually inverted-on-light contexts; check each occurrence)
- `bg-neutral-950` → `bg-background`
- `bg-neutral-900` → `bg-background` (page surface) or `bg-card` (raised surface) — use surrounding context
- `bg-neutral-800` → `bg-card`
- `bg-neutral-700` → `bg-muted` or `bg-card` — usually muted (slightly raised inside a card)
- `border-neutral-700` → `border-border`
- `border-neutral-600` → `border-border`
- `border-neutral-500` → `border-border`
- Alpha modifiers: `text-neutral-400/80` → `text-muted-foreground/80` (alpha modifier composes through semantic tokens because `--color-muted-foreground: hsl(var(--muted-foreground))`)

Work by-file in alphabetical order across `frontend/src/`. After each file is migrated, re-run the file's vitest spec (if one exists) to catch any test asserting on raw class names. After all neutrals migrated, run `rg '(text|bg|border|ring)-neutral-[0-9]' frontend/src/` and confirm 0 hits.

Do NOT touch `frontend/src/index.css` (legacy block survives until S04). Do NOT touch `frontend/src/styles/tokens.css` again. Do NOT touch decorative purples or default Tailwind v4 colors (orange, sky, etc.).
  - Files: `frontend/src/components/**/*.tsx`, `frontend/src/pages/**/*.tsx`, `frontend/src/App.tsx`
  - Verify: cd frontend && rg -c '(text|bg|border|ring)-neutral-[0-9]' src/ ; test $(rg -c '(text|bg|border|ring)-neutral-[0-9]' src/ 2>/dev/null | wc -l) -eq 0 && npm run type-check && npm test -- --run

- [x] **T03: Global swap: primary palette utilities → semantic tokens** `est:1h30m`
  Bulk semantic swap of every raw `*-primary-[0-9]+(/[0-9]+)?` utility across all consumer files. ~120+ occurrences across `text-primary-{200,300,400}`, `bg-primary-{500,600,700}`, `border-primary-{400,500}`, `ring-primary-500`, `from-primary-500`, `to-primary-600`, `shadow-primary-500/N`.

Mapping table (Tailwind v4's `/N` alpha modifier composes with semantic tokens because `--color-primary` resolves to `hsl(var(--primary))`):
- `text-primary-400` / `text-primary-300` / `text-primary-200` → `text-primary` (let the dark palette tone handle differentiation; if a hover state needed `primary-300`-then-`primary-200`, collapse to `text-primary hover:text-primary/90`)
- `bg-primary-500` → `bg-primary`
- `bg-primary-600` → `bg-primary` (hover/active states use opacity: `hover:bg-primary/90`)
- `bg-primary-700` → `bg-primary/80` (deepest active state)
- `bg-primary-500/10` → `bg-primary/10`, `bg-primary-500/20` → `bg-primary/20`, `bg-primary-500/25` → `bg-primary/25` (alpha modifier preserves)
- `border-primary-500` → `border-primary`, `border-primary-400` → `border-primary`
- `ring-primary-500` → `ring-primary` (also `ring-primary-500/20`, `/30`, `/50` preserve alpha)
- `from-primary-500` / `to-primary-600` / `via-primary-500` → `from-primary` / `to-primary` / `via-primary` (gradient utilities compose with `--color-primary`)
- `shadow-primary-500/10` and `shadow-primary-500/25` — Tailwind v4 does NOT auto-derive `shadow-primary` from `--color-primary` (shadow utility is bespoke). Two options: (a) inline the shadow as a custom utility class via `style={{ boxShadow: '0 0 20px hsl(var(--primary) / 0.25)' }}` or (b) keep as raw decorative `shadow-` and flag for S04. **Recommended: convert to inline `style` boxShadow** so the migration is complete; if there are >5 occurrences and they all live on Home/decorative pages, it is acceptable to leave them and add a comment `// FIXME(S04): shadow-primary token` so the S04 hard-delete catches it.

After swap: `rg -c '(text|bg|border|ring|from|to|via)-primary-[0-9]' frontend/src/` returns 0. Re-run vitest after sweep.
  - Files: `frontend/src/components/**/*.tsx`, `frontend/src/pages/**/*.tsx`, `frontend/src/App.tsx`
  - Verify: cd frontend && test $(rg -c '(text|bg|border|ring|from|to|via)-primary-[0-9]' src/ 2>/dev/null | wc -l) -eq 0 && npm run type-check && npm test -- --run

- [x] **T04: Global swap: status palette utilities → success/warning/destructive/info semantic tokens** `est:1h30m`
  Bulk semantic swap of every raw `*-emerald-`, `*-amber-`, `*-rose-`, `*-indigo-` utility plus the legacy `text-accent-emerald|amber|rose|purple` utilities across all consumer files. Depends on T01 tokens (`--success`, `--warning`, `--info`).

Mapping table:
- All `text-emerald-{200,300,400,500}` → `text-success`
- All `bg-emerald-{400,500,600,700,900}` → `bg-success`; `bg-emerald-500/10` → `bg-success/10`; `bg-emerald-900/40` → `bg-success/40`
- All `border-emerald-{500,700}` → `border-success`; alpha modifiers preserved (`border-emerald-700/60` → `border-success/60`)
- All `ring-emerald-` → `ring-success`
- All `from-emerald-` / `to-emerald-` / `via-emerald-` → `from-success` / `to-success` / `via-success`

- All `text-amber-{200,300,400}` → `text-warning`
- All `bg-amber-` → `bg-warning` (alpha preserved)
- All `border-amber-` → `border-warning`
- All `ring-amber-` → `ring-warning`
- All `from-amber-` / `to-amber-` / `shadow-amber-` → `from-warning` / `to-warning` / `shadow-warning` (or inline boxShadow style if shadow doesn't resolve — same caveat as T03)

- All `text-rose-` → `text-destructive`
- All `bg-rose-` → `bg-destructive` (with alpha)
- All `border-rose-` → `border-destructive`

- All `text-indigo-{300,400,500}` → `text-info`
- All `bg-indigo-{500,600,700}` → `bg-info` (use `/N` alpha for hover states)
- All `border-indigo-{500}` → `border-info` (alpha preserved: `border-indigo-500/50` → `border-info/50`)
- All `ring-indigo-` → `ring-info`

- `text-accent-emerald` (1 occurrence — `frontend/src/components/parts/PartList.tsx` per research) → `text-success`. The other `text-accent-*` utilities (`amber`, `rose`, `purple`) have 0 occurrences — confirm with `rg 'text-accent-' frontend/src/`.

- **Purple decorative gradients are NOT in scope** — `purple-500/10`, `from-purple-500`, `to-purple-500` resolve via Tailwind v4's default palette (NOT via the legacy `@theme` block, which only defines `accent-purple`, not `purple-*`). Leave them; they will surface in S04 only if `@theme` deletion breaks them (it won't — Tailwind v4 default palette is independent).
- **Purple role badge** in `frontend/src/pages/admin/UserManagement.tsx` (`bg-purple-600 text-purple-100` for superuser badge) — leave as-is in S01 (Tailwind v4 default palette resolves it). Flag for owner judgment in S05 polish; not S01 scope per research recommendation.

After swap: `rg -c '(text|bg|border|ring|from|to|via|shadow)-(emerald|amber|rose|indigo)-[0-9]' frontend/src/` returns 0. `rg 'text-accent-(emerald|amber|rose|purple)' frontend/src/` returns 0. Re-run vitest.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| T01 tokens (`--success`, `--warning`, `--info`) | If a token is missing, Tailwind utility `bg-success` resolves to no CSS — page renders without color. Mitigation: verify T01 commit landed via `grep -q 'success-foreground' frontend/src/styles/tokens.css` before starting. | N/A | N/A |
| `vite build` | If swap introduces invalid Tailwind class (typo), build fails fast. | N/A | N/A |

## Negative Tests

- After swap, navigate to `/admin/extraction-health` (heavy emerald/amber/rose status colors) and confirm visual parity with the pre-swap baseline — failure-rate badges should still be color-coded.
- Confirm `<Alert variant="success">` consumers still render correctly (T01 already swapped the variant; confirm no regression here).
- Run `frontend/e2e/components.spec.ts` (kitchen sink) at desktop only as a smoke check that no primitive surface broke — full 3-viewport baseline refresh is T05.
  - Files: `frontend/src/components/**/*.tsx`, `frontend/src/pages/**/*.tsx`
  - Verify: cd frontend && test $(rg -c '(text|bg|border|ring|from|to|via)-(emerald|amber|rose|indigo)-[0-9]' src/ 2>/dev/null | wc -l) -eq 0 && test $(rg -c 'text-accent-(emerald|amber|rose|purple)' src/ 2>/dev/null | wc -l) -eq 0 && npm run type-check && npm test -- --run

- [x] **T05: Refresh Playwright visual-regression baselines at 3 viewports for every page touched by S01** `est:45m`
  Per-slice baseline refresh (R060, MEM148). Every page touched by T02–T04 needs `toHaveScreenshot()` baselines refreshed at the 3 configured viewports (mobile 375×667, tablet 768×1024, desktop 1280×800 — these are what `playwright.config.ts` actually defines; the M003 vocabulary calls mobile '360' but the implemented value is 375 and we keep it that way for S01 — see research).

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Backend dev server (`uvicorn`) | If backend down, frontend e2e specs fail at network calls. Mitigation: start `cd backend && docker-compose up -d && uvicorn app.main:app --port 8000` before running Playwright. | 120s playwright `webServer` timeout | N/A |
| Frontend dev server (`npm run dev`) | playwright.config.ts auto-starts via `webServer` config; reuses existing if running. | 120s timeout | N/A |

## Load Profile

- **Shared resources**: dev backend (sample data), dev frontend (Vite HMR), Playwright workers (`fullyParallel: true`).
- **Per-operation cost**: ~24 PNGs at 3 viewports across ~8 specs. Full sweep ~3–5 min on a warm machine.
- **10x breakpoint**: N/A — single dev-machine run.

## Negative Tests

- After refresh, run the full Playwright suite WITHOUT `--update-snapshots` and confirm 0 diffs. Any non-zero diff means the refresh missed a viewport or spec.
- Inspect each refreshed PNG diff (or the `playwright-report/` HTML) before commit. Expected diffs are limited to color-channel changes (token-swap noise — usually <1px shift). Anything else (layout shift, font change, structural rearrangement) is a real regression and must be investigated, not blindly accepted.

## Steps

1. Ensure backend + frontend dev servers are reachable. If not running, start them: `cd backend && docker-compose up -d` then `uvicorn app.main:app --port 8000` in one terminal; `cd frontend && npm run dev` in another (or rely on Playwright's webServer config).
2. Run `cd frontend && npx playwright test --update-snapshots` to refresh ALL baselines. Specs touched by S01: `admin.spec.ts`, `build-list.spec.ts`, `components.spec.ts`, `parts-catalog.spec.ts`, `price-alerts.spec.ts`, `price-history.spec.ts` — all six are at risk because S01 touches admin pages, build-list pages, kitchen-sink (alert.tsx success variant), parts pages, and price pages.
3. After update, re-run `npx playwright test` (without `--update-snapshots`) and confirm 0 diffs.
4. Spot-check 3–5 refreshed PNGs visually (e.g. `frontend/e2e/parts-catalog.spec.ts-snapshots/*-mobile-linux.png`) — confirm diffs are limited to expected token-swap color changes (text-neutral-400 → text-muted-foreground, etc.). No layout / font / structural diffs.
5. Stage all refreshed `.png` files for commit alongside the migration commits.
  - Files: `frontend/e2e/admin.spec.ts-snapshots/`, `frontend/e2e/build-list.spec.ts-snapshots/`, `frontend/e2e/components.spec.ts-snapshots/`, `frontend/e2e/parts-catalog.spec.ts-snapshots/`, `frontend/e2e/price-alerts.spec.ts-snapshots/`, `frontend/e2e/price-history.spec.ts-snapshots/`
  - Verify: cd frontend && npx playwright test 2>&1 | tee /tmp/playwright-s01-verify.log | grep -E '(passed|failed)' && grep -q 'failed' /tmp/playwright-s01-verify.log && exit 1 || echo 'all snapshots green'

- [x] **T06: Run S01 close gauntlet: grep gates + build + type-check + lint + vitest + playwright** `est:30m`
  Final verification that S01 is structurally complete. Every gate below must pass; if any fail, fix before claiming the slice complete. This task is the slice's objective stopping condition.

## Steps

1. **Grep gates (R048):** All five must return 0 hits.
   - `cd frontend && rg -c 'bg-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/`  — must be 0 (lines with matches; `wc -l` on output should be 0).
   - `rg -c 'text-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` — must be 0.
   - `rg -c 'border-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` — must be 0.
   - `rg -c 'ring-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` — must be 0.
   - `rg -c '(from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` — must be 0.
   - `rg -c 'text-accent-(emerald|amber|rose|purple)' src/` — must be 0.
   - **Note: `purple-[0-9]` decorative survivors are intentionally out of S01 scope** (Tailwind v4 default palette resolves them; they get re-checked in S04 hard-delete). Do NOT extend the grep to include `purple` in S01.
2. **`vite build`** — `cd frontend && npm run build` exits 0. The legacy `@theme` palette block survives in `index.css` until S04, so build is expected to pass even if a stray legacy utility lingered (it shouldn't, after the grep gates pass).
3. **`tsc --noEmit`** — `cd frontend && npm run type-check` exits 0.
4. **`eslint`** — `cd frontend && npm run lint` — total error count must equal MEM062 baseline (108) within ±0 in S01-touched files. Run `npm run lint 2>&1 | tail -20` and compare to baseline; if S01 introduced new errors, fix before proceeding.
5. **`vitest --run`** — `cd frontend && npm test -- --run` — all 594+ specs green.
6. **Playwright full suite** — `cd frontend && npx playwright test` (no `--update-snapshots`) — all 3 viewports × all specs green. T05 already refreshed baselines; this is the second-pass verification that the refresh actually settled.

If any gate fails: fix in place, re-run the full gauntlet from step 1. Do not partial-commit a failing gate.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Backend dev stack for Playwright | Same as T05. Restart docker-compose / uvicorn if needed. | 120s | N/A |

## Negative Tests

- Run `rg 'glass-card|glass-button' frontend/src/` and CONFIRM hits remain — S01 does NOT touch glass-* (that's S02). If glass-* hits are 0, something is wrong (either S01 over-stepped or the grep is malformed).
- Run `rg 'var\(--primary-' frontend/src/` and confirm hits remain in `index.css` (legacy `:root` block survives until S04). Should NOT have any in `frontend/src/components/` or `frontend/src/pages/` — but that's S02 territory; in S01 we only verify the consumer surface for the migration-targeted color stems is clean.
  - Files: `frontend/`
  - Verify: cd frontend && test $(rg -c '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/ 2>/dev/null | wc -l) -eq 0 && test $(rg -c 'text-accent-(emerald|amber|rose|purple)' src/ 2>/dev/null | wc -l) -eq 0 && npm run build && npm run type-check && npm test -- --run && npx playwright test

## Files Likely Touched

- frontend/src/styles/tokens.css
- frontend/src/components/ui/alert.tsx
- frontend/src/components/**/*.tsx
- frontend/src/pages/**/*.tsx
- frontend/src/App.tsx
- frontend/e2e/admin.spec.ts-snapshots/
- frontend/e2e/build-list.spec.ts-snapshots/
- frontend/e2e/components.spec.ts-snapshots/
- frontend/e2e/parts-catalog.spec.ts-snapshots/
- frontend/e2e/price-alerts.spec.ts-snapshots/
- frontend/e2e/price-history.spec.ts-snapshots/
- frontend/
