---
estimated_steps: 23
estimated_files: 1
skills_used: []
---

# T06: Run S01 close gauntlet: grep gates + build + type-check + lint + vitest + playwright

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

## Inputs

- `frontend/src/styles/tokens.css`
- `frontend/src/components/ui/alert.tsx`
- `frontend/playwright.config.ts`

## Expected Output

- `.gsd/milestones/M003/slices/S01/tasks/T06-SUMMARY.md`

## Verification

cd frontend && test $(rg -c '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/ 2>/dev/null | wc -l) -eq 0 && test $(rg -c 'text-accent-(emerald|amber|rose|purple)' src/ 2>/dev/null | wc -l) -eq 0 && npm run build && npm run type-check && npm test -- --run && npx playwright test
