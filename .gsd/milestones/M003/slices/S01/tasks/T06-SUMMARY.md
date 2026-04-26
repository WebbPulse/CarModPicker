---
id: T06
parent: S01
milestone: M003
key_files:
  - frontend/src/App.tsx
  - frontend/src/pages/Pricing.tsx
  - frontend/src/components/layout/globalHeader/Header.tsx
  - frontend/src/components/layout/globalFooter/Footer.tsx
key_decisions:
  - Mapped gradient palette utilities using the same shade→token table as T02's solid-bg swap: `from-/to-/via-neutral-900` → `from-/to-/via-card`, `via-neutral-800` → `via-muted` for the page/header/footer surface gradients. Token lightness order (card=9% L, muted=14% L) preserves the original neutral-900→800→900 dark-sheen direction.
  - Collapsed `from-neutral-500 to-neutral-600` (Pricing free-tier iconColor) to `from-muted-foreground to-muted-foreground` because both legacy shades collapse to the same semantic token in T02's table. Gradient becomes flat for this decorative icon — acceptable since the legacy gradient was already very subtle.
  - For `from-white to-neutral-300` (Header/Footer logo brand text), preserved literal `white` (Tailwind static color, not legacy palette) and only swapped `to-neutral-300` → `to-foreground`. Resulting near-flat gradient is acceptable; matches T02's text-neutral-300 mapping.
  - Did NOT extend grep gates to include `purple-[0-9]` per the task plan's explicit note — those decorative survivors are S04 hard-delete territory.
  - Captured MEM157 documenting that future palette bulk-swap scripts must include all 7 prefix types (`text|bg|border|ring|from|to|via`) in the regex, not just the 4 prefixes T02/T03/T04 used.
duration: 
verification_result: passed
completed_at: 2026-04-26T21:29:57.810Z
blocker_discovered: false
---

# T06: test(palette): close S01 with grep gates + build + type-check + lint + vitest + playwright all green; fix 6 surviving from-/to-/via- gradient palette utilities missed by T02-T04 bulk swaps

**test(palette): close S01 with grep gates + build + type-check + lint + vitest + playwright all green; fix 6 surviving from-/to-/via- gradient palette utilities missed by T02-T04 bulk swaps**

## What Happened

Ran the S01 close gauntlet. First pass through the 6 grep gates surfaced a regression that the T02-T04 bulk-swap scripts had missed: gradient prefixes (`from-`, `to-`, `via-`) were not part of the migration regex, so 6 raw-palette gradient sites survived in 4 files (App.tsx, Header.tsx ×2, Footer.tsx ×2, Pricing.tsx).

Fixed in place using the same shade→token mapping table from T02 (MEM153):
- `from-neutral-900 via-neutral-800 to-neutral-900` (App.tsx page surface, Header overlay, Footer overlay) → `from-card via-muted to-card`. Token lightness ratios (card=9%, muted=14%) preserve the original neutral-900→800→900 dark-sheen gradient direction.
- `from-neutral-500 to-neutral-600` (Pricing.tsx free-tier iconColor decorative) → `from-muted-foreground to-muted-foreground`. Both legacy shades map to muted-foreground in T02's table; gradient collapses to flat color, acceptable for a decorative icon backdrop.
- `from-white to-neutral-300` (Header + Footer logo brand text) → `from-white to-foreground`. `white` is a Tailwind static color (not legacy palette), preserved as-is. `neutral-300` → `foreground` per T02.

After the fix, all 6 grep gates returned 0 hits. Negative tests passed: `glass-card|glass-button` hits remain (9 consumer files + index.css — S02 territory), `var(--primary-*)` hits remain in tokens.css/index.css (legacy `:root` block survives until S04). CookieConsentBanner.tsx does carry 3 raw `var(--primary-*)` direct CSS calls, but the slice plan explicitly notes those are S02 territory — S01's migration target is utility classes on the documented color stems, which is now clean.

Full gauntlet: vite build green (4.32s build + 11.1s prerender of 7 routes), tsc --noEmit clean, eslint clean (exit 0, well under MEM062's 108 baseline), vitest 90 files / 594 tests / all passing, Playwright 35 passed / 10 skipped / 0 failures across mobile + tablet + desktop viewports — the post-fix baselines from T05 held without further refresh, confirming the gradient-prefix swap was pixel-equivalent through the surviving `@theme` legacy bridge.

No runtime/observability impact — pure CSS class vocabulary swap. Existing structured logs, metrics, and error paths unchanged. Captured the gradient-prefix gotcha as MEM157 so future palette sweeps include all 7 prefix types in the bulk-swap regex.

Backend dev stack (uvicorn on :8000 against docker-compose Postgres/MinIO from M003 worktree) was restarted as part of the gauntlet — the worktree's `backend/.env` from T05's setup was already in place, so just `nohup uvicorn app.main:app --host 0.0.0.0 --port 8000` got the API back to healthy in ~5s.

## Verification

Ran the full S01 close gauntlet end-to-end after fixing the 6 surviving gradient-prefix sites:

1. Six grep gates per R048 — all return 0 hits across `frontend/src/`:
   - `rg -c 'bg-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` → 0
   - `rg -c 'text-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` → 0
   - `rg -c 'border-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` → 0
   - `rg -c 'ring-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` → 0
   - `rg -c '(from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` → 0 (was 6 before fix)
   - `rg -c 'text-accent-(emerald|amber|rose|purple)' src/` → 0
2. `npm run build` — vite build 4.32s + prerender 7 routes 11.1s, exit 0.
3. `npm run type-check` — `tsc -b --noEmit`, no output, exit 0.
4. `npm run lint` — `eslint .`, no output, exit 0 (well under MEM062 baseline of 108).
5. `npm test -- --run` — vitest 90 files / 594 tests, all passing in 5.50s.
6. `npx playwright test` (no `--update-snapshots`) — 35 passed / 10 skipped / 0 failures across mobile + tablet + desktop viewports. T05's baselines held without further refresh, confirming the T06 gradient-prefix swap was pixel-equivalent through the surviving `@theme` legacy bridge.

Negative tests (per task plan):
- `rg 'glass-card|glass-button' src/` returns hits in 9 consumer files + index.css — confirms S01 did NOT over-step into S02 territory.
- `rg 'var\(--primary-' src/` returns hits in tokens.css + index.css (legacy block survives until S04) and CookieConsentBanner.tsx (S02 territory, not in S01's grep-gate scope).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -c 'bg-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` | 1 | pass | 80ms |
| 2 | `rg -c 'text-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` | 1 | pass | 60ms |
| 3 | `rg -c 'border-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` | 1 | pass | 60ms |
| 4 | `rg -c 'ring-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` | 1 | pass | 60ms |
| 5 | `rg -c '(from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` | 1 | pass | 60ms |
| 6 | `rg -c 'text-accent-(emerald|amber|rose|purple)' src/` | 1 | pass | 60ms |
| 7 | `npm run build (vite + prerender 7 routes)` | 0 | pass | 15400ms |
| 8 | `npm run type-check (tsc -b --noEmit)` | 0 | pass | 11000ms |
| 9 | `npm run lint (eslint .)` | 0 | pass | 9000ms |
| 10 | `npm test -- --run (vitest 90 files / 594 tests)` | 0 | pass | 5500ms |
| 11 | `npx playwright test (35 passed / 10 skipped / 0 failed)` | 0 | pass | 16000ms |

## Deviations

The task plan framed T06 as pure verification ("final verification that S01 is structurally complete"). In practice, the gauntlet caught 6 surviving raw-palette utilities that the T02-T04 bulk-swap scripts had missed — gradient prefixes (`from-`, `to-`, `via-`) weren't part of those scripts' regex. Per the plan's explicit instruction ("If any gate fails: fix in place, re-run the full gauntlet from step 1. Do not partial-commit a failing gate"), fixed the 6 sites in place via direct edits and re-ran the full gauntlet, which then passed clean. This is intended fix-in-place behavior, not a plan deviation.

## Known Issues

CookieConsentBanner.tsx contains 3 direct `var(--primary-*)` calls in inline className strings — these are NOT raw palette utilities (they're inline CSS custom-property references) so they're not caught by the S01 grep gates. The slice plan explicitly notes these are S02 territory. They will be addressed when S02 retires the legacy `:root` block in `index.css`.

## Files Created/Modified

- `frontend/src/App.tsx`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/layout/globalFooter/Footer.tsx`
