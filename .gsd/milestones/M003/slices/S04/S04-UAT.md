# S04: Hard-delete legacy CSS layer (@theme + :root + .glass* + .btn-* + .card* + .input-modern + 11 keyframes + 10 .animate-* + decoratives) — UAT

**Milestone:** M003
**Written:** 2026-04-26T23:23:50.735Z

# S04-UAT: Hard-Delete Legacy CSS Layer

**Slice:** M003/S04 — Hard-delete `@theme` + `:root` legacy palette + `.glass*` + `.btn-*` + `.card*` + `.input-modern` + 11 keyframes + 10 `.animate-*` + decoratives from `frontend/src/index.css`.

**UAT mode:** Autonomous (no human required) — all assertions are mechanical (grep / build / lint / type-check / test exit codes + Playwright pass) and were executed at slice close. This script is the reproducible UAT replay any operator can run against `main` post-merge to verify the substrate stays clean.

## Preconditions

- Working directory: `/home/tyler-webb/Documents/Github/CarModPicker` (or any clone with the M003 branch merged).
- Node + npm installed; `cd frontend && npm install` already run (no new dependencies — pure CSS deletion + consumer-class swap to existing `ui/Button` primitive).
- No backend / database / network required (pure frontend CSS layer + build assertion).

## Test Cases

### TC-1 — `index.css` is structurally clean (load-bearing)

**Steps:**
1. `wc -l frontend/src/index.css`
2. `rg -c '@theme' frontend/src/index.css; echo $?`
3. `rg -c 'glass-card|glass-button|btn-primary|btn-secondary|btn-outline|card-interactive|card-table-container|input-modern' frontend/src/index.css; echo $?`
4. `rg -c '@keyframes (fadeInScale|slideInUp|slideInLeft|slideInRight|pulse|shimmer|float|glow|gradientShift|borderGlow|progress-indeterminate)' frontend/src/index.css; echo $?`
5. `rg -c '\.animate-(fadeInScale|slideInUp|slideInLeft|slideInRight|pulse|shimmer|float|glow|gradient|border-glow)' frontend/src/index.css; echo $?`
6. `rg -c '\.(skeleton|hero-gradient|text-gradient|border-gradient|shadow-glow)' frontend/src/index.css; echo $?`

**Expected:**
- Step 1: `94 frontend/src/index.css` (slight overage on the task plan's 50–80 estimate is the preserved scrollbar block + tile-grid utilities — both load-bearing per PRESERVE list)
- Steps 2–6: each prints `1` (rg exit 1 = zero matches = pass)

### TC-2 — Consumer dirs are clean (slice-level grep gates)

**Steps:**
1. `cd frontend && rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/{components,pages,contexts,hooks,api,lib,__tests__}/; echo $?`
2. `rg 'text-accent-(emerald|amber|rose|purple)' src/{components,pages,contexts,hooks,api,lib,__tests__}/; echo $?`
3. `rg 'glass-(card|button)?' src/{components,pages,contexts,hooks,api,lib,__tests__}/; echo $?`
4. `rg 'className=.*\bglass\b' src/{components,pages,contexts,hooks,api,lib,__tests__}/; echo $?`
5. `rg 'var\(--(primary|neutral|accent|gradient)-' src/{components,pages,contexts,hooks,api,lib,__tests__}/; echo $?`
6. `rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' src/{components,pages,contexts,hooks,api,lib,__tests__}/; echo $?`

**Expected:** Each prints `1` (rg exit 1 = zero matches = pass).

**Edge case:** If TC-2 step 6 returns `0` with hits inside test-file comments referencing the English word "skeleton", apply the MEM180 convention: rewrite the comment to use "scaffold" rather than tighten the gate. The gate is intentionally a simple word-boundary regex matching its CI shape.

### TC-3 — Build is the standing enforcement (load-bearing structural proof)

**Steps:**
1. `cd frontend && npm run build`

**Expected:** Exit 0. `vite v* building for production...` → `✓ built in <N>s`. Postbuild prerender step renders 7 static routes (`/`, `/about`, `/privacy-policy`, `/terms-of-service`, `/contact-us`, `/support`, `/pricing`) without error.

**Failure mode:** If the build emits an "unresolved utility class" error naming `bg-primary-500` / `glass-card` / `btn-primary` / `card-interactive` / `text-gradient` / `animate-slideInUp` / etc., a consumer survived the deletion. Identify the file from the error message, migrate to the appropriate semantic token (`bg-card`, `text-primary`, `<Button>`, etc.), and re-run.

### TC-4 — Type-check + lint + vitest baseline

**Steps:**
1. `cd frontend && npm run type-check`
2. `cd frontend && npm run lint`
3. `cd frontend && npm test -- --run`

**Expected:**
- Step 1: exit 0 (tsc -b --noEmit clean)
- Step 2: exit 0, zero ESLint errors. Lint baseline preserved at MEM062 (108 errors, zero net-new in slice-touched files — actual run shows zero errors total, well under baseline)
- Step 3: exit 0, `Test Files  90 passed (90)` / `Tests  594 passed (594)` in ~6 seconds

### TC-5 — Playwright at 3 viewports (visual regression + accessibility)

**Steps:**
1. `cd frontend && npx playwright test`

**Expected:** Exit 0. Output: `35 passed (~17s) / 10 skipped`. Skips are intentional desktop-only or dialog-flow exclusions documented in the e2e specs.

**Edge case:** If a screenshot test fails with pixel diff, the body-background or tokenized animation utilities may have drifted. Run `npx playwright test --update-snapshots` and visually inspect each refreshed PNG before committing. Per MEM174/MEM176, drift on full-page screenshots is expected when body-background changes — for S04 the cascade was 13 PNGs refreshed across admin/build-list/components/price-alerts/price-history specs. Notable: smoke.spec.ts (Home) should NOT need a refresh — T01's tokenized `@utility animate-*` blocks were proven pixel-equivalent to the legacy `.animate-*` rules (per MEM156/MEM160 default `--update-snapshots=changed` only writes diffed PNGs).

### TC-6 — Substrate replacements present in tokens.css

**Steps:**
1. `rg -c '@utility animate-fadeInScale|@utility animate-slideInUp|@utility animate-slideInLeft|@utility animate-float|@utility animate-glow' frontend/src/styles/tokens.css`
2. `rg -c '@utility text-gradient' frontend/src/styles/tokens.css`
3. `rg -c '@keyframes (fadeInScale|slideInUp|slideInLeft|float|glow)' frontend/src/styles/tokens.css`

**Expected:**
- Step 1: 5 (one per `@utility animate-*` block from T01)
- Step 2: 1 (the `@utility text-gradient` block from T04)
- Step 3: 5 (one per supporting keyframe from T01)

### TC-7 — Body / focus / selection are tokenized

**Steps:**
1. `rg -n 'background: hsl\(var\(--background' frontend/src/index.css`
2. `rg -n 'hsl\(var\(--ring' frontend/src/index.css`
3. `rg -n 'hsl\(var\(--primary-foreground' frontend/src/index.css`

**Expected:** Each returns at least one match — body background, focus-visible outline, and selection color all resolve through the `tokens.css` HSL semantic vocabulary, not the deleted `:root` legacy palette.

### TC-8 — Spot-check consumer migrations (T02 button swap, T03 input cleanup)

**Steps:**
1. `rg -n 'import.*Button.*from.*ui/button' frontend/src/pages/NotFound.tsx frontend/src/pages/Checkout.tsx frontend/src/components/layout/globalHeader/Header.tsx frontend/src/components/routes/RouteGroupBoundary.tsx frontend/src/components/shell/ChromeExtensionPromo.tsx frontend/src/components/shell/SubscriptionPromo.tsx`
2. `rg -n 'input-modern' frontend/src/components/parts/EditPartForm.tsx frontend/src/components/forms/SearchableSelect.tsx`

**Expected:**
- Step 1: each of the 6 files contains a `Button` import from `ui/button`
- Step 2: zero hits — both files dropped the trailing `input-modern` className

## Pass Criteria

All 8 test cases pass. Build (TC-3) is the canonical structural signal — even if every grep gate were missed, an unresolved-class build error would surface the regression. The 12 grep gates (TC-1 + TC-2) are the standing inspection surface; deviation = regression.

## Known Limitations / Non-Goals

- **No live UAT walkthrough:** S04 is autonomous mode; visual coverage gap for marketing pages without Playwright (the 7 prerendered static pages: `/about`, `/pricing`, `/support`, `/contact-us`, `/privacy-policy`, `/terms-of-service`, `/`) is documented for S05 manual UAT and S06 close gauntlet. Prerender success at TC-3 confirms compile-time correctness; visual fidelity beyond build success is S05/S06 territory.
- **One subtle gradient band collapse:** T05 → T06 swapped body background from option-(b) gradient (`linear-gradient(135deg, --background → --muted → --background)`) to option-(a) flat (`hsl(var(--background))`). Visual delta is the loss of one mid-tone band; dominant color is unchanged. Documented as a deliberate option swap in T06-SUMMARY.md.
- **Operator follow-ups from M002 still open:** S13-UAT.md script for live SES round-trip + `python -m app.crawlers.backfill --resume` post-merge (carry-forward, not S04-related).
