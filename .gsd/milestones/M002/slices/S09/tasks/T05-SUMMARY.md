---
id: T05
parent: S09
milestone: M002
key_files:
  - frontend/e2e/build-list.spec.ts
  - frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png
key_decisions:
  - Deflaked the mobile e2e baseline by pre-dismissing the chrome-extension promo in spec setup (addInitScript writes today's YYYY-MM-DD into chrome_extension_promo_last_dismissed) — promo's 2s detect-then-show timer was racing the snapshot capture and producing nondeterministic baselines. Treated this as in-scope T05 work because the spec is a S09 deliverable and the flake was discovered by the verification gate.
  - Substituted Playwright e2e assertions for the planned 1-minute manual UAT smoke (autonomous mode, no human available). Desktop edit-dialog Escape test + tab-focus test cover the same R020 surface; recommended a follow-up human pass during S13 milestone validation.
  - Did NOT update MEM062 from 104→108 in this task — drift is from unrelated slice work and should be re-baselined separately to keep S09's audit trail clean. Slice intent (zero net-new errors in S09 touched files) is satisfied.
duration: 
verification_result: passed
completed_at: 2026-04-25T23:22:49.752Z
blocker_discovered: false
---

# T05: test: Slice S09 verification sweep — type-check, vitest, e2e, lint baseline, and import-closure all green; deflaked mobile e2e baseline by pre-dismissing chrome-extension promo

**test: Slice S09 verification sweep — type-check, vitest, e2e, lint baseline, and import-closure all green; deflaked mobile e2e baseline by pre-dismissing chrome-extension promo**

## What Happened

Ran the slice-level verification gauntlet for S09 (build-list view redesign).

**Type-check (Step 1):** `npm run type-check` exit 0.

**Vitest for touched units (Step 2):** `npm run test -- ViewBuildlist BuildListParts confirm-dialog` exit 0 — 17/17 tests pass across `confirm-dialog.test.tsx` (14) and `ViewBuildlist.test.tsx` (3). No `BuildListParts.test.tsx` exists in the repo (legitimate — T03's coverage is via `ViewBuildlist.test.tsx` integration), so vitest's auto-discovery just picks up the two files. Same shape as the slice plan's expected vitest coverage.

**E2E (Step 3):** First run of `npm run test:e2e -- build-list components` failed on the mobile project's `build-list detail visual regression` snapshot — 21,295 px diff (ratio 0.03) exceeded the 0.2% pixel threshold. Root cause was timing flake in T04's mobile baseline: `ChromeExtensionPromo` (frontend/src/components/common/ChromeExtensionPromo.tsx:38) waits 2s after cookie consent before showing, and that 2s timer race-condited with T04's `--update-snapshots` capture — the mobile baseline ended up containing the promo, but the actual run didn't (or vice-versa across runs).

Fixed by extending the spec's `addInitScript` to pre-dismiss the promo for today (frontend/e2e/build-list.spec.ts:191) using the same `chrome_extension_promo_last_dismissed` localStorage key and `YYYY-MM-DD` format that `dailyDismiss.ts` reads. Then regenerated the mobile baseline with `npx playwright test build-list --update-snapshots` (only mobile rewrote; tablet+desktop already matched). Re-ran `npm run test:e2e -- build-list components`: **8 passed, 4 skipped, 0 failed** — 3 visual at mobile/tablet/desktop + 1 desktop edit-dialog Escape + 1 desktop tab-focus + 3 components.spec; the 4 skips are correct (keyboard tests scoped to desktop only, tablet+mobile skip).

The Vite proxy `ECONNREFUSED 127.0.0.1:8000` lines in stderr are noise — Vite logs them on its own startup health poll before backend is up, but the spec uses `page.route('/\\/api\\/(?!.*\\.ts)/', …)` (MEM082) so all real test traffic is mocked.

**Lint (Step 4):** `npm run lint` reports 108 errors / 44 warnings. That is +4 vs the MEM062 baseline of 104, but per-file breakdown confirms all 108 errors live in pre-existing `*.test.ts(x)` files (reports/votes/bug_reports api tests dominate at 38/36/19; Profile, ViewBuildLog, UserManagement, AccountAlerts each contribute 1–4). Zero errors in `confirm-dialog.tsx`, `ViewBuildlist.tsx`, `BuildListParts.tsx`, `EditBuildListPartForm.tsx`, or `e2e/build-list.spec.ts`. Slice closure intent satisfied; the +4 drift is from work in unrelated slices and should be folded into a future MEM062 update (suggest 108 as the new baseline).

**Manual smoke (Step 5):** Substituted the equivalent Playwright assertions for the 1-minute manual UAT (autonomous-mode constraint, no human available). The e2e suite already covers: page renders on the new dark token palette across mobile/tablet/desktop (visual regression), Edit dialog opens via testid trigger and Escape closes it (`edit dialog opens, focuses, and Escape closes`), focus rings visible after Tab (`tab order surfaces visible focus on first interactive control` asserts `:focus-visible` + non-empty outline/boxShadow). Recommend a follow-up human pass on real local DB data when S13 milestone validation runs.

**Import-closure check (Step 6):** `grep -rn "from '../../components/common/Dialog'\|from '../../components/common/DeleteConfirmationDialog'\|from '../../components/buttons/ActionButton'" src/pages/builder/ViewBuildlist.tsx src/components/buildListParts/` returns 0 hits. ViewBuildlist + BuildListParts subtree is fully off the deprecated common/buttons primitives.

**No new pre-commit lint errors (Step 7):** Confirmed by per-file error count — none in T01/T02/T03's modified files.

**Slice S09 verdict: GOAL MET.** All five must-haves from S09-PLAN.md hold; the integration closure (5 dialogs on ui/dialog or ui/confirm-dialog, ui/tabs view-mode toggle, ui/input phase row, multi-viewport e2e + 3 baselines, no NEW lint errors in slice files) is intact.

## Verification

Ran the slice gauntlet end-to-end. Type-check exit 0. Vitest 17/17 pass (confirm-dialog 14 + ViewBuildlist 3). E2E `npm run test:e2e -- build-list components` 8 passed / 4 skipped / 0 failed after deflaking the mobile baseline by pre-dismissing the chrome-extension promo. Lint 108 errors / 44 warnings — zero errors in the five S09 touched files; +4 vs MEM062 baseline are all in unrelated pre-existing test files (reports/votes/bug_reports api tests). Import-closure grep across ViewBuildlist + buildListParts/ for the legacy common/Dialog, common/DeleteConfirmationDialog, buttons/ActionButton sources returns 0 hits. Manual smoke substituted by the desktop edit-dialog Escape and tab-focus e2e assertions (autonomous mode, no human available).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 5500ms |
| 2 | `cd frontend && npm run test -- ViewBuildlist BuildListParts confirm-dialog` | 0 | ✅ pass (17/17) | 1090ms |
| 3 | `cd frontend && npm run test:e2e -- build-list components (after baseline regen)` | 0 | ✅ pass (8 passed / 4 skipped) | 5100ms |
| 4 | `cd frontend && npm run lint (per-file inspection)` | 1 | ✅ pass (108 errors all in pre-existing test files; 0 in S09 touched files) | 18000ms |
| 5 | `grep -rn legacy-imports src/pages/builder/ViewBuildlist.tsx src/components/buildListParts/` | 1 | ✅ pass (0 hits) | 50ms |

## Deviations

Plan said "no source files modified" but T05 ended up modifying frontend/e2e/build-list.spec.ts (8-line addInitScript extension to pre-dismiss the chrome-extension promo) and regenerating frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png. The change fixes a flake the verification gate surfaced — promo's 2s timer racing the snapshot — and lives entirely within S09's test infrastructure (the spec is a T04 deliverable). Treated as in-scope verification-driven fix rather than scope creep; the alternative (re-baseline mobile every CI run when timing wobbles) would have left the slice in a knowingly-flaky state.

## Known Issues

Lint baseline drifted from 104 (MEM062) to 108 errors total — all 4 net-new errors live in pre-existing test files outside S09's scope (reports/votes/bug_reports api test suites accumulate the bulk). Recommend updating MEM062 to 108 (or hunting down the +4) in a future maintenance task.

## Files Created/Modified

- `frontend/e2e/build-list.spec.ts`
- `frontend/e2e/build-list.spec.ts-snapshots/build-list-detail-visual-regression-1-mobile-linux.png`
