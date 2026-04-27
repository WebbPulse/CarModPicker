# S01: Global token sweep — palette utility migration — UAT

**Milestone:** M003
**Written:** 2026-04-26T21:34:39.781Z

# S01 UAT — Palette utility migration

## Preconditions

- Backend dev stack running: `cd backend && docker-compose up -d` (Postgres + MinIO) and `uvicorn app.main:app --port 8000`. The worktree's `backend/.env` must be present (copied from main repo if missing — worktrees don't share untracked files).
- Frontend dev server running: `cd frontend && npm run dev` (or rely on Playwright's `webServer` auto-start).
- Sample data populated: `python ../scripts/populate_sample_data.py` from `backend/`.

## Test cases

### TC1: Grep gates return zero hits across `frontend/src/`

**Goal:** Prove the consumer-side palette migration is structurally complete for the migration-targeted color stems.

**Steps:**
1. From `frontend/`, run each of these six commands:
   ```
   rg -c 'bg-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/
   rg -c 'text-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/
   rg -c 'border-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/
   rg -c 'ring-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/
   rg -c '(from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/
   rg -c 'text-accent-(emerald|amber|rose|purple)' src/
   ```

**Expected outcome:** Every command returns 0 hits (no output) and exit code 1 (ripgrep's "no matches" exit). Confirmed at slice close.

### TC2: Build / type-check / lint / vitest all green

**Goal:** Prove the migration didn't break compilation, types, lint baseline (MEM062 = 108), or unit tests.

**Steps:**
1. `cd frontend && npm run type-check` — expect exit 0, no output.
2. `npm run lint` — expect exit 0, well under MEM062 baseline of 108.
3. `npm test -- --run` — expect 90 files / 594 tests / 0 failures.
4. `npm run build` — expect vite build to succeed plus prerender of 7 routes.

**Expected outcome:** All four commands exit 0. Confirmed at slice close: vitest finished in 5.33s, build in 4.35s + 11.1s prerender.

### TC3: Playwright visual baselines hold at 3 viewports

**Goal:** Prove the token swap was pixel-equivalent (via the surviving `@theme` legacy bridge in `index.css`) — no unintended visual regression.

**Steps:**
1. Ensure backend + frontend dev servers are reachable (preconditions).
2. From `frontend/`, run `npx playwright test` (no `--update-snapshots`).
3. Inspect the report.

**Expected outcome:** 35 passed / 10 skipped / 0 failed across 6 specs (admin, build-list, components, parts-catalog, price-alerts, price-history) × 3 viewports (mobile 375, tablet 768, desktop 1280). Zero diffs above `maxDiffPixelRatio: 0.002`. Confirmed in T05 + T06.

### TC4: Alert success variant renders correctly

**Goal:** Prove the only `ui/*` primitive that was migrated in T01 (`alert.tsx` success variant) still works visually.

**Steps:**
1. Navigate to the kitchen-sink page (`/components` or whichever the components.spec.ts visits).
2. Locate the `<Alert variant="success">` example.
3. Inspect the rendered HTML in DevTools.

**Expected outcome:** The Alert renders with green semantic styling (resolved through `--success` token). Class names should include `bg-success/10 text-success border-success/50` (not `bg-emerald-500/10 text-emerald-300`). Existing consumers (`ConfirmationAlert`, `SuccessAlert`) render identically to pre-migration.

### TC5: Status colors render on `/admin/extraction-health`

**Goal:** Heavy emerald/amber/rose status colors on the extraction-health page must still color-code correctly through the new semantic vocabulary.

**Steps:**
1. Log in as admin.
2. Navigate to `/admin/extraction-health`.
3. Inspect failure-rate badges, success indicators, warning callouts.

**Expected outcome:** Failure-rate badges still color-coded (success-green for healthy, warning-amber for degraded, destructive-red for failed). Visual parity with pre-migration baseline modulo expected token-swap noise (<1px shift). Confirmed via Playwright spec.

## Edge cases

### EC1: Hover differentiation preserved on collapsed shade pairs

**Setup:** T03/T04 collapsed `text-primary-300 hover:text-primary-200` and `text-emerald-400 hover:text-emerald-300` style patterns to single semantic tokens, then a follow-up pass restored hover differentiation as `text-primary hover:text-primary/90` / `text-success hover:text-success/90`.

**Test:** Hover over any link or button on `/admin/crawler` (4 fixed sites), `/build-logs/<id>` (6 sites), `/build-lists/<id>` (3 sites), `/admin/system` (3 sites).

**Expected:** Visible hover state (10% opacity drop). No `hover:text-X` no-ops left in the codebase.

### EC2: Decorative purple gradients still render

**Setup:** T04 explicitly left purple decorative utilities (`bg-purple-500/10`, `from-purple-500`, `to-purple-500`) and the `bg-purple-600 text-purple-100` superuser role badge in `UserManagement.tsx` untouched. They resolve via Tailwind v4's default palette, not the legacy `@theme` block.

**Test:** Visit pages that use these (Home decorative section, `/admin/users`).

**Expected:** Purple decorations render normally; superuser badge shows purple. These are S05 polish judgment-calls, not S01 regressions.

### EC3: Worktree env handoff

**Setup:** T05 discovered worktrees don't share untracked `backend/.env` files.

**Test:** From a fresh worktree, attempt to start `uvicorn app.main:app --port 8000` without copying `backend/.env`.

**Expected:** uvicorn fails with missing-env errors. Resolution: `cp /path/to/main/backend/.env backend/.env` before starting. Documented as MEM161.

## Out-of-scope confirmations (negative tests)

These should still have hits — they are S02/S04 territory, not S01:

- `rg 'glass-card|glass-button' src/` — expect hits in 9 consumer files + index.css (S02 reskin target).
- `rg 'var\(--primary-' src/` — expect hits in tokens.css + index.css (legacy `:root` block, S04 hard-delete target) and CookieConsentBanner.tsx (S02 territory).
- Decorative purple utilities still present (see EC2).

## Sign-off

S01 is structurally complete when all 5 test cases (TC1–TC5) pass and all 3 edge cases (EC1–EC3) behave as documented. At slice close: confirmed.
