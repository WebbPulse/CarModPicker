# S02: Glass-card & legacy `:root` var purge — pass 1 reskin — UAT

**Milestone:** M003
**Written:** 2026-04-26T21:59:35.936Z

# S02 — UAT: Glass-card & legacy `:root` var purge — pass 1 reskin

**Slice goal:** No `glass-card`/`glass-button`/bare-`glass` consumers, no `var(--primary|neutral|accent|gradient)-*` consumers, in `frontend/src/`. The 9 reskinned pages render with replacement chrome at three viewports without obvious regressions.

## Preconditions

- Working tree at the worktree root: `/home/tyler-webb/Documents/Github/CarModPicker/.gsd/worktrees/M003`
- `frontend/` dependencies installed (`npm ci` in `frontend/`).
- Local backend NOT required for these UAT cases — all 9 touched pages render shell chrome that does not require a logged-in user.
- Playwright browsers installed (`npx playwright install` if needed).

## Test Cases

### TC1 — Grep-gate cleanliness (mechanical proof)

**Steps:**
1. From the worktree root, run `rg 'glass-(card|button)?' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/`.
2. Run `rg 'className=.*\bglass\b' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/`.
3. Run `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/`.

**Expected:** All three commands exit 1 (zero matches). Any non-zero hit count means a consumer was missed.

**Edge case:** `<Card variant="glass">` at `frontend/src/pages/Home.tsx:385` MUST be present and MUST NOT match command 2 (the regex requires `className=` prefix; the variant prop is the deliberate carve-out).

### TC2 — Type-check + lint + vitest

**Steps:**
1. `cd frontend && npm run type-check` → expect exit 0.
2. `cd frontend && npm run lint` → expect exit 0 (≤ 108 errors net, MEM062 baseline; T04 measured zero).
3. `cd frontend && npm test -- --run` → expect exit 0 with all suites green (594 tests / 90 files at T04 close).

**Expected:** All three commands exit 0. Any new lint error must originate in a file outside the 9 S02-touched files (T01–T03's diffs are className-only).

### TC3 — Build proves no `.glass*` consumer survives compilation

**Steps:**
1. `cd frontend && npm run build`.

**Expected:** Exit 0. All 7 prerendered routes succeed. The `.glass*` block in `frontend/src/index.css` is still defined (S04 territory), so this build only proves consumers don't reference deleted classes; absence-of-failure for the legacy block is intentional.

### TC4 — Playwright e2e at 3 viewports with zero baseline drift

**Steps:**
1. `cd frontend && npx playwright test` (NO `--update-snapshots` flag).
2. After completion, run `git status --short` from the worktree root.

**Expected:** Playwright exits 0 (35 passed / 10 skipped at T04 close), and `git status --short` is empty — confirming zero PNG baseline drift. The 9 S02-touched pages have no Playwright coverage, so any drift would indicate an unintended ripple into a covered page.

**Edge case:** If a baseline drifts, the failure is a real regression — investigate and fix the root cause. Do NOT pass `--update-snapshots`.

### TC5 — Visual spot-check of the 9 reskinned pages (manual; skipped under auto-mode)

For each viewport (360 px, 768 px, 1280 px), open each route below in a browser pointed at `npm run dev` (port 4000) and verify the chrome renders cleanly:

| # | Route / Component | What to verify |
|---|---|---|
| 1 | `/` (Home) | Hero section's `<Card variant="glass">` mid-page renders the standard glass surface; entrance animations still play. |
| 2 | `/login` | Auth panel's outer container shows the inline tokenized glass surface (subtle white border, translucent fill, backdrop blur); form inputs render normally. |
| 3 | `/register` | Same as `/login` for the registration panel. |
| 4 | `/extension-auth` | Extension-auth panel renders with the same tokenized glass surface. |
| 5 | `/privacy-policy` | Body container shows the tokenized glass surface; legal text remains readable on the translucent background. |
| 6 | `/terms-of-service` | Same as privacy-policy. |
| 7 | NotFound (visit any unmatched path, e.g. `/zzzz-not-real`) | 404 panel renders with tokenized glass surface inside the centered shell. |
| 8 | Header chrome (any logged-out page) | Profile/login/logout buttons + mobile-menu toggle render with the new bordered translucent surface; hover states feel consistent (slight white-tint shift). |
| 9 | Footer chrome (any page) | Three social-icon buttons render the new tokenized surface; hover state feels consistent. |
| 10 | CookieConsentBanner (clear localStorage and reload to trigger) | Top border is solid `border-primary`; "Privacy Policy" link uses `text-primary` with `/80` lighter hover; "Accept All" button uses `bg-primary` with `/90` darker hover. No layout shift from the legacy `var(--primary-*)` arbitrary-value strings. |

**Expected:** Every chrome surface looks coherent with the existing M002 `<Card variant="glass">` consumers (About, Pricing, Support, ContactUs, Checkout). No visible color shifts on hover (alpha-modifier feedback is subtle but perceptible). Mobile menu container at Header.tsx:156 has a single border, not double.

**Acceptance criterion:** Each row gets a one-line verdict per viewport (`pass` / `fixed` / `acceptable`). Under autonomous mode this case is skipped — the 3 grep gates + build are the canonical proof; manual spot-check is a recommended-but-optional backstop and a known coverage gap recorded for S05.

## Notes

- The legacy `.glass*` block in `frontend/src/index.css` survives S02 — it is deliberately preserved until S04 deletes it together with the legacy `:root` palette and `@theme` mirror. Any unexpected build failure mentioning a missing legacy class indicates a typo in T01/T02, not a missing legacy class.
- Lint baseline (MEM062) is 108 errors. T04 measured zero in the slice — net-new errors in S02-touched files would be a regression.
