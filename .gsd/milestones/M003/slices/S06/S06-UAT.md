# S06: Migration completion gauntlet + UAT — UAT

**Milestone:** M003
**Written:** 2026-04-27T01:52:13.086Z

## UAT — M003/S06 Migration Completion Gauntlet + Operator Handoff

This slice closes the M003 design-system migration in auto-mode. The acceptance suite below is what an operator runs to confirm the close-out evidence is genuine and the operator-judgment items are properly staged. The full priority-page walkthrough lives in `.gsd/milestones/M003/M003-UAT.md` (operator-driven, non-blocking per MEM142).

### Preconditions
- Working tree clean on branch `milestone/M003` at SHA `fb922fc` or later
- Node 20+, npm installed
- `cd frontend && npm install` completed
- Postgres / backend NOT required (this is a frontend-only milestone)

---

### UAT-1: 7 grep gates pass with zero hits in consumer code

**Steps:**
1. From worktree root, run each of the 7 grep gates listed in `.gsd/milestones/M003/slices/S06/gauntlet/gate{1..7}-*.txt`.
2. For each gate, verify exit code = 1 (rg's "no matches" exit).

**Expected:** All 7 gates exit 1, zero matching files printed, matching the persisted evidence files exactly.

**Edge cases:**
- If gate 3 or 4 prints `frontend/src/__tests__/no-legacy-primitives.test.ts` as a match, the T03 self-trip fix has regressed — check that the regex sources are still constructed via `new RegExp('\\bgla' + 'ss-...')` rather than literal `/glass-.../` slash-syntax.
- If any gate prints a file under `frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/`, M003 has regressed — that file must be migrated before close.

---

### UAT-2: 5 toolchain gates pass

**Steps:**
1. `cd frontend && npm run type-check` → expect exit 0, tsc -b --noEmit clean.
2. `cd frontend && npm run lint` → expect exit 0, zero eslint errors.
3. `cd frontend && npm test -- --run` → expect exit 0, **597 tests across 90 files** (the +3 over S05's 594 are the T02 grep-guard extensions).
4. `cd frontend && npm run build` → expect exit 0, vite build + prerender 7 routes complete.
5. `cd frontend && npx playwright test` → expect exit 0, **155 passed / 10 skipped / 0 failed** at 3 viewports.

**Expected:** All 5 commands exit 0, test counts match exactly, no PNG baseline drift afterward (`git status --short -- frontend/e2e/` empty).

**Edge cases:**
- Test count drift (≠597) means tests were added/removed since S06 close — investigate before re-citing.
- Playwright failures often surface as PNG diff — if any baseline drifted, decide whether the drift is an intended regression (refresh) or actual regression (fix).

---

### UAT-3: vitest grep-guard catches re-entry

**Steps:**
1. Create a temporary `frontend/src/pages/__probe_violation__.tsx` containing one of: `<div className="bg-primary-500" />` (raw palette), `<div className="glass-card" />` (glass), or `<textarea />` (hand-rolled primitive).
2. From `frontend/`, run `npm test -- --run __tests__/no-legacy-primitives`.
3. Verify the test fails with file:line:match output identifying `__probe_violation__.tsx`.
4. Delete the probe file. Re-run the test. Verify 4/4 tests pass.

**Expected:** Failure message names the probe file with file:line:match. After deletion, test suite returns to 4/4 green.

**Edge cases:**
- If the probe file does not trip the assertion, the regex pattern or scan helper is broken — review `no-legacy-primitives.test.ts` against the M003-S06 describe block.

---

### UAT-4: DangerActionPanel renders correctly in SystemAdmin

**Steps:**
1. Start dev server: `cd frontend && npm run dev` (port 4000).
2. Log in as admin and navigate to `/admin/system`.
3. Open the "Deletion options" accordion at the bottom of the page.
4. Verify 3 panels render with distinct tone borders:
   - **Cars** — warning-tone (amber/yellow border + bg)
   - **Global parts / manufacturers** — destructive-tone (red border + bg)
   - **Bucket cleanup** — info-tone (blue border + bg)
5. Each panel shows a heading + description + action buttons. Bucket-cleanup shows two buttons (List + Purge), where only Purge opens a confirm dialog.
6. Click each button to confirm the dialog flow / list flow works.

**Expected:** All 3 panels visually consistent with their previous (pre-S06) inline JSX form, button flows unchanged, no console errors.

**Edge cases:**
- If a panel renders without its tone styling, check that `dangerColor` prop is passed correctly.
- If the bucket-cleanup List button accidentally opens a dialog, the API was extended incorrectly — DangerActionPanel does not own dialog composition, consumers do.

---

### UAT-5: M003-UAT.md operator handoff is complete

**Steps:**
1. Open `.gsd/milestones/M003/M003-UAT.md`.
2. Verify the document contains:
   - Top-level summary block citing SHA `d79f15b` and MEM142 framing.
   - Priority-page verdict table (11 priority pages × 3 viewports).
   - 360px operator walkthrough checklist (11 entries).
   - 3 human-judgment IA decision slots (#1 Auth-shell unification, #2 ContactUs 3-card collapse, #3 BuildListsCatalog sidebar drawer).
   - 3 auto-resolved sections (#4 ViewBuildLog prose-plugin deferral, #5 UserManagement scroll-lock, #6 DangerActionPanel extraction).
3. Verify all 14 referenced file paths resolve to real files: `Login.tsx`, `Register.tsx`, `ExtensionAuth.tsx`, `ForgotPassword.tsx`, `ForgotPasswordConfirm.tsx`, `VerifyEmail.tsx`, `AuthCard.tsx`, `ContactUs.tsx`, `BuildListsCatalog.tsx`, `ui/sheet.tsx`, `ViewBuildLog.tsx`, `UserManagement.tsx`, `SystemAdmin.tsx`, `DangerActionPanel.tsx`.

**Expected:** Document is complete, all file refs resolve, decision slots have file:line + observation + trade-offs + verdict checkbox.

**Edge cases:**
- A missing file ref means a refactor renamed/moved a file after T03's path verification — update the reference in `M003-UAT.md`.

---

### UAT-6: Per-gate evidence files exist and match persisted output

**Steps:**
1. `ls .gsd/milestones/M003/slices/S06/gauntlet/` → expect 12 files (gate1 through gate12).
2. Spot-check `gate10-vitest.txt` tail: should end with `Test Files  90 passed (90)` / `Tests  597 passed (597)` / `EXIT=0`.
3. Spot-check `gate12-playwright.txt` tail: should end with `155 passed (48.5s)` / `EXIT=0`.

**Expected:** All 12 files exist, exit codes are 0 (toolchain) or 1 (grep) per the verification table.

---

### UAT-7 (operator-driven, non-blocking per MEM142): 360px manual walkthrough

**Steps:**
1. Open M003-UAT.md "360px Manual Walkthrough" section.
2. Open Chrome DevTools, set viewport to 360×640.
3. For each of the 11 priority pages, navigate and confirm: no horizontal overflow, header navigation usable, primary CTA reachable.
4. Check the box and add operator notes for each page.

**Expected:** 11 checkboxes ticked with operator notes. This step does NOT block S06/M003 close — it is captured as a follow-up per MEM142.

---

### UAT-8 (operator-driven, non-blocking): 3 human-judgment IA decisions

**Steps:**
1. Open M003-UAT.md "IA Deferral Decisions" section.
2. For each of items #1-#3, review the trade-off enumeration and tick the verdict checkbox of choice.
3. If a verdict requires net-new code, file an M004 issue rather than implementing in S06.

**Expected:** 3 verdict checkboxes ticked or 3 M004 issues filed. Does NOT block S06/M003 close.

---

## Done When

- UAT-1 through UAT-6 all pass — these are the auto-verifiable items and represent the canonical S06/M003 close evidence.
- UAT-7 and UAT-8 are operator follow-ups that may be completed asynchronously without blocking M003 close.
