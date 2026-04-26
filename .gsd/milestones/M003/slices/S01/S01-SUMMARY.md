---
id: S01
parent: M003
milestone: M003
provides:
  - ["Zero raw palette utility hits in frontend/src/ for primary|neutral|emerald|indigo|amber|rose stems and text-accent-* legacy utilities — verified by 6 R048 grep gates", "Six new semantic tokens (--success, --success-foreground, --warning, --warning-foreground, --info, --info-foreground) declared in tokens.css :root + @theme bridge", "components/ui/alert.tsx success variant migrated to semantic tokens — variant API unchanged for consumers", "Refreshed/verified Playwright baselines at 3 viewports (mobile 375, tablet 768, desktop 1280) for 6 specs (admin, build-list, components, parts-catalog, price-alerts, price-history)", "Reusable Python regex scripts at frontend/scripts/m003_s01_t02_*.py / t03_*.py / t04_*.py — bulk-swap pattern for downstream slices to reuse", "Pattern-matched key memories MEM156-MEM163 covering migration patterns, gotchas, and conventions"]
requires:
  - slice: M002/S08
    provides: frontend/src/styles/tokens.css semantic-token vocabulary that S01 extends with --success/--warning/--info
  - slice: M002/S08-S12
    provides: frontend/src/components/ui/* primitives that S01 leaves untouched (only alert.tsx success variant migrated)
  - slice: M002/S13
    provides: frontend/playwright.config.ts 3-viewport project setup used for baseline verification
affects:
  - ["frontend/src/styles/tokens.css", "frontend/src/components/ui/alert.tsx", "frontend/src/index.css (1 comment line rewritten to use placeholder strings for grep-gate compatibility)", "frontend/src/pages/**/*.tsx (35+ files)", "frontend/src/components/**/*.tsx (40+ files)", "frontend/src/App.tsx", "frontend/scripts/m003_s01_t02_*.py / t03_*.py / t04_*.py (new bulk-swap scripts)", "frontend/e2e/**/*-snapshots/*.png (24 PNGs verified pixel-equivalent, no rewrites)"]
key_files:
  - ["frontend/src/styles/tokens.css", "frontend/src/components/ui/alert.tsx", "frontend/src/index.css", "frontend/src/App.tsx", "frontend/src/pages/Home.tsx", "frontend/src/pages/Pricing.tsx", "frontend/src/pages/admin/CrawlerAdmin.tsx", "frontend/src/pages/admin/SystemAdmin.tsx", "frontend/src/pages/buildLists/ViewBuildLog.tsx", "frontend/src/pages/builder/ViewPart.tsx", "frontend/src/components/layout/globalHeader/Header.tsx", "frontend/src/components/layout/globalFooter/Footer.tsx", "frontend/scripts/m003_s01_t03_swap_primary.py", "frontend/scripts/m003_s01_t04_swap_status.py"]
key_decisions:
  - ["Two-pass deterministic Python regex script for bulk palette migration over per-file Edit calls — pass 1 captures `\\b(text|bg|border|ring|from|to|via|shadow)-<color>-\\d+(/\\d+)?\\b` and rewrites with alpha preserved; pass 2 collapses `text-X hover:text-X` no-ops to `text-X hover:text-X/90`. Idempotent, scalable, easy to bisect.", "Added 6 new semantic tokens (--success/-foreground, --warning/-foreground, --info/-foreground) in tokens.css :root + @theme bridge. Pattern-matched on existing --destructive token surface. Kept --info distinct from --primary even though both resolve to 217 91% 60% — semantic clarity over channel deduplication.", "Migrated alert.tsx success variant in the same atomic precursor commit (T01) because it's the only ui/* primitive with raw-palette utilities. Consolidating it kept subsequent T02+ swaps purely consumer-side.", "Mapped shadow-primary-N → shadow-primary directly rather than inlining as style={{boxShadow}} — Tailwind v4 derives colored-shadow utilities from --color-primary automatically. The plan's note about no-auto-derive was overcautious.", "Rewrote one explanatory comment in src/index.css to use placeholder strings (`bg-primaryNNN`, `text-accentNNN`) so the .css-file-scanning grep gates ignore comment text. The @theme block itself stays untouched until S04.", "Did NOT use --update-snapshots=all in T05 — Playwright 1.59+ defaults --update-snapshots to `changed` mode. Zero-rewrite outcome was the desired R048 result, not a bug. Pixel-equivalent migration through the surviving @theme legacy bridge.", "Left decorative purple utilities (from-purple-500, to-purple-500, bg-purple-500/10) and superuser role badge (bg-purple-600 text-purple-100) untouched per plan — they resolve via Tailwind v4's default palette and are explicitly S05 polish territory."]
patterns_established:
  - ["Two-pass Python regex bulk migration: pass 1 swaps utilities with alpha preserved, pass 2 repairs collapsed hover no-ops. Use as baseline for S02 var(--*) consumer purge, S04 keyframe deletions, etc.", "All 7 utility prefixes (text|bg|border|ring|from|to|via plus shadow for colored shadows) must be in any palette bulk-swap regex from the start. T02-T04's 4-prefix regex missed gradient sites that the close-gauntlet T06 had to fix in place.", "Comments in .css files that literally contain palette utility names (e.g. `bg-primary-500, text-accent-emerald`) must be rewritten with placeholder strings (`bg-primaryNNN`, `text-accentNNN`) so .css-scanning grep gates don't false-positive. The @theme block content itself survives until S04.", "Per-slice Playwright baseline refresh via `npx playwright test --update-snapshots` (no =all suffix) — only rewrites baselines that actually differ. Zero-rewrite is the desired outcome for pixel-equivalent migrations through a surviving legacy bridge."]
observability_surfaces:
  - ["Six R048 grep gates as standing inspection surface — `rg -c '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' frontend/src/` and `rg -c 'text-accent-(emerald|amber|rose|purple)' frontend/src/` must return 0 going forward. Deviation = regression.", "Playwright `toHaveScreenshot()` baselines at 3 viewports for 6 specs — any unintended visual regression surfaces as a snapshot diff exceeding maxDiffPixelRatio: 0.002.", "vite build is the compile-time signal — until S04 deletes the @theme block, the legacy utilities still resolve, so build-time failure is not the canonical signal for this slice; the grep gates are."]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-26T21:34:39.781Z
blocker_discovered: false
---

# S01: Global token sweep — palette utility migration

**Migrated every raw legacy palette utility (primary/neutral/emerald/amber/rose/indigo/accent) across 68 consumer files to semantic tokens, added --success/--warning/--info tokens, and verified pixel-equivalent rendering at 3 viewports.**

## What Happened

## What S01 delivered

S01 was the first structural slice of M003's design-system migration completion: replace every raw legacy palette utility (`bg-primary-[0-9]`, `text-neutral-[0-9]`, `text-emerald-[0-9]`, `text-indigo-[0-9]`, `text-amber-[0-9]`, `text-rose-[0-9]`, `text-accent-{emerald,amber,rose,purple}`, plus their `bg-/border-/ring-/from-/to-/via-/shadow-` companions) across all `frontend/src/` consumer files with semantic tokens backed by `frontend/src/styles/tokens.css`. The legacy `@theme` palette block in `index.css` was deliberately preserved (it gets hard-deleted in S04) — that bridge let the migration land pixel-equivalent through every viewport.

### Task-by-task

- **T01 (precursor commit):** Added 6 new semantic tokens — `--success`, `--success-foreground`, `--warning`, `--warning-foreground`, `--info`, `--info-foreground` — to `tokens.css` :root + @theme bridge using HSL channels matching the existing dark palette (success: `142 71% 45%`, warning: `38 92% 50%`, info: `217 91% 60%`). Pattern-matched the existing `--destructive` token surface exactly. Migrated `components/ui/alert.tsx` `success` variant onto `bg-success/10 text-success border-success/50` — the only `ui/*` primitive with raw-palette utilities. Variant API unchanged; consumers like `ConfirmationAlert` keep working.

- **T02 (neutrals):** Bulk swap of 267 occurrences across 42 files using a deterministic Python regex script with explicit shade → semantic mapping (`text-neutral-{100,200,300}` → `text-foreground`; `text-neutral-{400,500,600}` → `text-muted-foreground`; `bg-neutral-700` → `bg-muted`; `bg-neutral-{800,900}` → `bg-card` with one manual override in `ErrorBoundary.tsx` for full-screen page surface; `bg-neutral-950` → `bg-background`; `border-neutral-{500,600,700}` → `border-border`). Alpha modifiers preserved through capture-and-reemit. The script's plan-listed 33 files turned out to be 42 in practice — the grep gate (zero hits) was the authoritative contract.

- **T03 (primary):** Bulk swap of 157 + 11 hover repairs across 27 files using a two-pass script (bulk swap pass + hover-fix pass collapsing `text-primary hover:text-primary` no-ops to `text-primary hover:text-primary/90`). All `text-primary-{200,300,400}` → `text-primary`; `bg-primary-{500,600}` → `bg-primary`; `bg-primary-700` → `bg-primary/80`; gradient and shadow prefixes resolved via `--color-primary` automatically. Rewrote one explanatory comment in `src/index.css` so it no longer literally contains `bg-primary-500` (the gate regex matches `.css` files).

- **T04 (status colors):** Bulk swap of 279 + 25 hover repairs across 36 files. `*-emerald-` → `*-success`, `*-amber-` → `*-warning`, `*-rose-` → `*-destructive`, `*-indigo-` → `*-info`. The single `text-accent-emerald` occurrence migrated to `text-success`; the other `text-accent-*` legacies had zero `.tsx`/`.ts` occurrences. Decorative purple gradients and the superuser role badge in `UserManagement.tsx` were left untouched per plan — they resolve via Tailwind v4's default palette and are explicitly out of S01 scope.

- **T05 (visual baselines):** Ran `npx playwright test --update-snapshots` against all 6 S01-touched specs (admin, build-list, components, parts-catalog, price-alerts, price-history) at all 3 viewports (mobile 375×667, tablet 768×1024, desktop 1280×800). Surprise finding: zero PNG rewrites because Playwright 1.59+ defaults `--update-snapshots` to `changed` mode and the migration was pixel-equivalent through the surviving `@theme` bridge. Verified via second run without `--update-snapshots`: 35 passed / 10 skipped / 0 failed in 15.7s.

- **T06 (close gauntlet):** Ran the 6 grep gates + build + type-check + lint + vitest + Playwright. First pass surfaced 6 surviving raw-palette gradient sites in 4 files (App.tsx, Header.tsx ×2, Footer.tsx ×2, Pricing.tsx) — the T02–T04 bulk-swap scripts had used only `text|bg|border|ring` prefixes and missed `from|to|via`. Fixed in place using the same shade → token mapping table; re-ran the full gauntlet which then passed clean.

### Patterns established

- **Two-pass deterministic Python regex script** for palette migrations (MEM158): bulk-swap pass + hover-repair pass. Idempotent, easy to bisect, scales to hundreds of replacements in seconds.
- **All 7 utility prefixes in one regex** (MEM159, MEM157): `text|bg|border|ring|from|to|via` plus `shadow` for colored shadows. Future palette sweeps in S02–S04 must include all of them from the start to avoid the gradient-prefix gotcha that bit T02–T04.
- **Comment-as-grep-target convention** (MEM163): rewrite descriptive comments in `.css` files that literally contain palette utility names to use placeholder strings (`bg-primaryNNN`, `text-accentNNN`) so they remain readable but don't trip the gate.
- **Playwright `--update-snapshots` semantics** (MEM156, MEM160): defaults to `changed` mode in 1.59+; zero-rewrite outcome after a pixel-equivalent migration is the desired R048 result, not a bug.
- **Worktree env handoff** (MEM161): `backend/.env` must be copied from main repo into the worktree before running uvicorn; docker-compose containers (Postgres, MinIO) are shared.

### Out of scope (deferred to downstream slices)

- `glass-card` / `glass-button` / `.glass*` references — S02 territory.
- `var(--primary-*)` / `var(--neutral-*)` / `var(--accent-*)` direct CSS calls (e.g. 3 hits in `CookieConsentBanner.tsx`) — S02 territory.
- Hard delete of `@theme` palette + legacy `:root` block + `.glass*` + decorative/animation utilities in `index.css` — S04 territory.
- Decorative purple gradients (`from-purple-500`, `to-purple-500`, `bg-purple-500/10`) and the `bg-purple-600 text-purple-100` superuser badge — Tailwind v4 default palette; flagged for S05 polish.

### What S02 should know

The semantic-token vocabulary is now the canonical surface for every consumer file in `frontend/src/`. When S02 reskins Home/Login/Register/Header/AccountAlerts/AdminDashboard to remove `glass-*`, the surrounding text/bg utilities already resolve through `tokens.css` — replacement card surfaces should be `bg-card border-border` plus appropriate shadow/backdrop-blur tokens. The `var(--primary-*)` direct CSS calls in `CookieConsentBanner.tsx` are the canonical example of the `:root` consumer purge S02 owns. Use the same two-pass Python regex pattern from S01 for any bulk swap, and include all 7 prefixes from the start.

## Verification

## Slice-level verification — all gates green

### Grep gates (R048) — all 6 returned 0 hits in the worktree at slice close

| # | Command | Hits |
|---|---------|------|
| 1 | `rg -c 'bg-(primary\|neutral\|emerald\|indigo\|amber\|rose)-[0-9]' src/` | 0 |
| 2 | `rg -c 'text-(primary\|neutral\|emerald\|indigo\|amber\|rose)-[0-9]' src/` | 0 |
| 3 | `rg -c 'border-(primary\|neutral\|emerald\|indigo\|amber\|rose)-[0-9]' src/` | 0 |
| 4 | `rg -c 'ring-(primary\|neutral\|emerald\|indigo\|amber\|rose)-[0-9]' src/` | 0 |
| 5 | `rg -c '(from\|to\|via)-(primary\|neutral\|emerald\|indigo\|amber\|rose)-[0-9]' src/` | 0 |
| 6 | `rg -c 'text-accent-(emerald\|amber\|rose\|purple)' src/` | 0 |

### Build / lint / type-check / vitest — all green at slice close

| Command | Exit | Result |
|---------|------|--------|
| `npm run type-check` (tsc -b --noEmit) | 0 | clean |
| `npm run lint` (eslint .) | 0 | clean (well under MEM062 baseline of 108) |
| `npm test -- --run` (vitest) | 0 | 90 files / 594 tests / 0 failures in 5.33s |
| `npm run build` (vite + prerender) | 0 | 4.35s build + 11.1s prerender of 7 routes |

### Playwright e2e — verified in T05 + T06

| Command | Result |
|---------|--------|
| `npx playwright test --update-snapshots` (T05) | 35 passed / 10 skipped / 0 failed in 16.4s — zero PNG rewrites (pixel-equivalent through `@theme` legacy bridge) |
| `npx playwright test` (T06 close pass, no --update-snapshots) | 35 passed / 10 skipped / 0 failed in 16s — baselines held across 3 viewports × 6 specs |

### Negative tests confirmed S01 stayed in scope

- `rg 'glass-card\|glass-button' src/` returns hits in 9 consumer files + index.css — S01 did NOT over-step into S02 territory ✓
- `rg 'var\(--primary-' src/` returns hits in tokens.css + index.css (legacy `:root` block survives until S04) and in CookieConsentBanner.tsx (S02 territory) ✓

### Operational readiness

- **Health signal:** Grep gates are the canonical inspection surface — running the 6 commands listed above against `frontend/src/` should always return 0 hits going forward. Deviation = regression.
- **Failure signal:** A regressed page would surface as a Playwright snapshot diff exceeding `maxDiffPixelRatio: 0.002`. Build-time the legacy utilities still resolve (via the `@theme` block, which survives until S04) so failure mode is purely visual, not compile-time.
- **Recovery procedure:** If a future PR reintroduces a raw palette utility, the grep gate fails locally; fix is mechanical — apply the shade → token mapping table from this slice (preserved in `frontend/scripts/m003_s01_t02_*.py`, `m003_s01_t03_*.py`, `m003_s01_t04_*.py`).
- **Monitoring gaps:** No CI gate yet enforces the grep gates — S06's optional vitest grep-guard extension would close this.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"T02 Expected Output enumerated 33 files; actual fix set was 42 — the grep gate (zero hits) was the authoritative contract. T03 Expected Output similarly speculative — 27 files actually contained primary-N utilities, including 18 not on the plan list and excluding several that were on it. T06 was framed as pure verification but caught 6 surviving raw-palette gradient sites that T02-T04 missed (gradient prefixes weren't in those scripts' regex). Fixed in place per the plan's explicit `If any gate fails: fix in place, re-run the full gauntlet from step 1` instruction. T05 staged zero PNG files because Playwright 1.59+ defaults --update-snapshots to `changed` mode and the migration was pixel-equivalent."

## Known Limitations

"S01 only touched consumer files plus tokens.css plus components/ui/alert.tsx. The legacy @theme palette block in index.css is intentionally preserved — it survives until S04. As a result: (1) raw palette utilities still RESOLVE at build-time (the @theme bridge is still live) so the grep gate is the only structural enforcement for now; (2) `var(--primary-*)` / `var(--neutral-*)` / `var(--accent-*)` direct CSS calls in consumer code are still functional and out of S01 scope (S02 territory). Decorative purple utilities are also untouched — they resolve via Tailwind v4 default palette and are S05 polish judgment-calls."

## Follow-ups

["S02 must include all 7 utility prefixes in any bulk-swap regex from the start (MEM157, MEM159) — gradient prefixes (from|to|via) bit T02-T04. ", "CookieConsentBanner.tsx contains 3 direct var(--primary-*) calls in inline className strings — S02 territory.", "S06 should consider extending the vitest grep-guard to enforce the 6 R048 gates as a CI-level invariant so regression is caught at PR time, not at the next milestone gauntlet.", "S05 polish should evaluate the superuser bg-purple-600 role badge in UserManagement.tsx and the decorative purple gradients on Home — left untouched in S01 per plan."]

## Files Created/Modified

None.
