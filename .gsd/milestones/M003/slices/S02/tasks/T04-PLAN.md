---
estimated_steps: 21
estimated_files: 3
skills_used: []
---

# T04: S02 close gauntlet — run all 3 grep gates + build + type-check + lint + vitest + Playwright

Verify the slice is closed by running the full S02 gauntlet from the slice goal in sequence. All commands must exit 0 / return zero hits. If any gate fails, fix in place and re-run the full gauntlet from the start (do NOT auto-rewrite Playwright baselines).

**Sequence (run from `frontend/` unless otherwise specified):**

1. **Grep gate 1 (glass class consumers):** `rg 'glass-(card|button)?' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — Expected: zero hits.

2. **Grep gate 2 (bare-`glass` in className strings):** `rg 'className=.*\bglass\b' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — Expected: zero hits. (`<Card variant="glass">` consumers do not match because the regex requires `className=` prefix.)

3. **Grep gate 3 (`var(--*)` consumers, scoped past `tokens.css` and `index.css`):** `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — Expected: zero hits.

4. **Type-check:** `cd frontend && npm run type-check` — expect exit 0.
5. **Lint:** `cd frontend && npm run lint` — expect exit 0 (or no net-new errors against MEM062 baseline of 108).
6. **Vitest:** `cd frontend && npm test -- --run` — expect exit 0.
7. **Build:** `cd frontend && npm run build` — expect exit 0 (proves no `.glass*` consumer survives compilation).
8. **Playwright e2e at 3 viewports:** `cd frontend && npx playwright test` — expect exit 0 with NO `--update-snapshots` flag. Zero baseline drift expected because no covered spec visits an S02-touched page; if a baseline drifts, that's a real regression — investigate, do NOT auto-rewrite.

**Manual visual spot-check (optional but recommended for slice summary):**

The 9 S02-touched pages have no Playwright coverage. If running in autonomous mode, record "manual visual spot-check skipped — autonomous-mode" in the summary. If interactive, document a one-line per-page verdict at 360 / 768 / 1280 viewports for `/`, `/login`, `/register`, `/extension-auth`, `/privacy-policy`, `/terms-of-service`, NotFound (any 404 path), Header chrome, Footer chrome, CookieConsentBanner.

**Pitfalls:**
- Do NOT pass `--update-snapshots` to Playwright. Zero-rewrite is the desired R048 outcome.
- The legacy `.glass*` block in `frontend/src/index.css` survives. If `npm run build` fails, the issue is a typo from T01/T02, NOT a missing legacy class.
- The 3 grep gates are all scoped past `tokens.css` and `index.css` (consumer dirs only). Don't widen the scope until S04 deletes them.

**Failure modes:**
- Surviving glass-* hit → missed call site in T01/T02. Fix in place, re-run gauntlet from step 1.
- Surviving `var(--*)` hit → confirm gate is scoped past `tokens.css` and `index.css`. If still failing, fix file in place.
- Playwright baseline diff → real visual regression. Run failing spec headed and inspect; likely T02 over-stripped a className.
- Vitest failure → component test snapshot drifted. Investigate; do not blanket-update.

## Inputs

- ``frontend/src/``
- ``frontend/playwright.config.ts``
- ``frontend/package.json``

## Expected Output

- ``.gsd/milestones/M003/slices/S02/tasks/T04-SUMMARY.md``

## Verification

All 8 commands above complete with exit 0 / zero hits in a single linear sequence on a clean working tree (no `--update-snapshots` flag anywhere). Document the verification command sequence and outputs in the task SUMMARY when calling `gsd_complete_task`.

## Observability Impact

Grep gates 1–3 above become standing inspection surfaces — they should always return zero hits in S02-onward worktrees until S04 deletes the legacy block. Playwright baselines remain at S01's `maxDiffPixelRatio: 0.002`. Build-time legacy `.glass*` resolution survives until S04, so build is not yet the canonical signal — the grep gates are.
