# S09: Build-list view redesign — UAT

**Milestone:** M002
**Written:** 2026-04-25T23:26:59.007Z

# S09 UAT: Build-list view redesign

**Slice:** S09 — /build-lists/:id reskinned onto S08 design system
**Build under test:** Local dev server (frontend/ on port 4000) + backend on port 8000 with a populated DB containing at least one build list owned by the logged-in user.

## Preconditions

1. Backend running: `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
2. Frontend running: `cd frontend && npm run dev` → http://localhost:4000.
3. DB populated with sample data: `cd backend && python ../scripts/populate_sample_data.py`.
4. Logged in as the user who owns at least one build list (so canManage evaluates true and the Edit/Delete affordances render).
5. Browser dev tools open with DevTools → Console + Network panes visible.

## Automated Coverage (already green)

The following are covered by `frontend/e2e/build-list.spec.ts` and `frontend/src/components/ui/confirm-dialog.test.tsx` + `frontend/src/pages/builder/ViewBuildlist.test.tsx` — 17 unit tests + 8 e2e tests pass. No human action required for these.

- ConfirmDialog: closed-state portal, default labels, onConfirm wiring, onOpenChange(false) on cancel, loading disables both buttons + sets aria-busy + swaps to loadingLabel, no-auto-close-on-confirm during loading, cancel-while-loading is a no-op, error region presence/absence, warning slot presence/absence, destructive vs default variant produces expected button class, custom children rendering.
- ViewBuildlist render: header/info card render path, parts row render path, empty parts message path.
- E2E visual regression at mobile (375×812), tablet (768×1024), desktop (1280×800): full-page screenshots match committed baselines within 0.2% pixel threshold.
- E2E Escape closes the Edit dialog (desktop only): click [data-testid="build-list-edit-trigger"], dialog visible, focus trapped inside dialog, press Escape, dialog hidden.
- E2E tab order (desktop only): page.keyboard.press('Tab') reaches the first action button (View Build Log), focused button matches `:focus-visible` AND has non-empty outline OR boxShadow.

## Manual UAT Cases (recommended for S13 milestone validation pass)

### TC1 — Visual continuity on the new design system

**Steps:**
1. Navigate to `/build-lists/{id}` for a build list you own.
2. Visually compare against staging or a known-good screenshot.

**Expected:**
- Page chrome (PageHeader, Card, info-item layout) intact (chrome stays on legacy primitives in S09 — rides S12 ripple).
- Action buttons (Edit Build List, Delete Build List, View Build Log, Copy Build List, Add Part) render on dark-token palette with correct variants: secondary for Edit, destructive for Delete, default for View Build Log + Copy + Add Part.
- Phase view-mode toggle visible as ui/Tabs with focus-visible ring on hover/focus.
- No raw HTML buttons or unstyled inputs visible anywhere on the page surface owned by ViewBuildlist + BuildListParts.

### TC2 — Edit Build List dialog flow

**Steps:**
1. Click `Edit Build List`.
2. Observe the dialog opens and focus moves into it (Radix focus management).
3. Tab through the dialog — focus rings visible on every interactive control.
4. Press Escape.
5. Open it again and click outside the dialog (on the overlay).

**Expected:**
- Dialog renders inside ui/Dialog with the title `Edit ${buildList.name}`.
- Dialog max-width is `sm:max-w-2xl` (~672px).
- Escape closes the dialog and returns focus to the trigger.
- Outside-click also closes the dialog (Radix default).
- No console errors.

### TC3 — Delete Build List ConfirmDialog flow (destructive)

**Steps:**
1. Click `Delete Build List`.
2. Observe the ConfirmDialog with the destructive variant.
3. Click `Cancel`.
4. Open it again, click `Confirm`. (Heads up: this will actually delete the list — only run on a throwaway list.)

**Expected:**
- ConfirmDialog title: "Confirm Deletion".
- Description: "Are you sure you want to delete the build list '${name}'? This action cannot be undone."
- Confirm button is destructive variant (red), shows "Deleting..." with spinner during the in-flight delete.
- Cancel button disabled while loading; outside-click/Escape do NOT dismiss the dialog while loading (handleDeleteOpenChange swallows it).
- After successful delete, the page navigates back to the parent car-generation page (or `/builder` if no car_id).
- If the API errors, the inline error region renders the error string (role="alert").

### TC4 — Phase management (canManageParts gate)

**Steps:**
1. As the owner, expand the phase-management Card.
2. Type a new phase name in the Add phase input. Click `Add phase`.
3. Click `Edit` on a phase row, change the name, click `Save`.
4. Click `Cancel` on a phase edit instead of saving.
5. Click `Delete` on a phase row.

**Expected:**
- New-phase row uses ui/Input + ui/Button. Add button disabled until input has non-whitespace content; remains disabled during the request (loading=true).
- Per-row Edit replaces the row with an inline ui/Input + Cancel/Save (ui/Button secondary + default). Save shows loading state during the request.
- Cancel reverts to the read-only row without saving.
- Delete opens the phase-delete ConfirmDialog (destructive variant). Confirming removes the phase. testid `build-list-phase-delete-confirm` present on the dialog.
- All phase mutations gated on canManageParts — log out and confirm phase controls are absent for non-owners.

### TC5 — Add Build List Part dialog

**Steps:**
1. Click `Add Part`.
2. Inspect the dialog max width (should be wide — sm:max-w-[64rem] ≈ 1024px).
3. Cancel out and reopen.

**Expected:**
- Dialog renders inside ui/Dialog with the wide max-width (matches the legacy 4xl-equivalent).
- Form fields (Category select, Manufacturer select, etc.) inside the dialog still use legacy styling — they ride S12 along with common/Input.
- testid `build-list-add-part-dialog` present on the DialogContent.

### TC6 — Edit Build List Part dialog (BuildListParts.EditBuildListPartForm)

**Steps:**
1. With at least one part on the build list, click `Edit` on a part row.
2. Observe the dialog opens.
3. Modify quantity, click `Save`.
4. Open it again, click `Cancel`.

**Expected:**
- Dialog title: "Edit Part".
- Cancel + Save buttons are ui/Button (secondary, default).
- Save button shows loading spinner during the in-flight request.
- Outside-click and Escape do NOT dismiss the dialog while loading (handleOpenChange refuses to close).
- testid `build-list-part-edit-dialog` and `build-list-part-edit-submit` present.

### TC7 — Phase view-mode toggle

**Steps:**
1. Click the `Phase` tab in the view-mode toggle (ui/Tabs).
2. Click the `Category` tab.

**Expected:**
- Tab swaps the BuildListPartList rendering mode without re-fetching.
- Focus-visible ring on the active tab.
- testid `build-list-view-mode-tabs` present on the TabsList.

### TC8 — Optimistic purchased toggle (no dialog)

**Steps:**
1. Click the purchased toggle on a part row.
2. Observe immediate UI update.

**Expected:**
- No dialog opens (the optimistic toggle preserves the legacy non-dialog flow).
- On API error, the toggle reverts to its previous state.

### TC9 — Keyboard navigation (R020 hardening)

**Steps:**
1. Reload the page.
2. Press Tab repeatedly until focus reaches the View Build Log button.
3. Continue tabbing through Edit, Delete, Add Part, Phase tabs, Add Phase input.
4. At each step, observe the focus ring.

**Expected:**
- Every interactive control shows a visible focus-visible ring (Tailwind focus-visible:ring-* utilities from ui/Button + ui/Input + ui/Tabs).
- No focus jumps over an interactive control.
- Tab order is left-to-right, top-to-bottom across the page.

### TC10 — Non-owner gate (canManage = false)

**Steps:**
1. Log in as a different user (not the build list's owner).
2. Navigate to the same `/build-lists/{id}`.

**Expected:**
- View Build Log button still renders (read-only path).
- Edit Build List, Delete Build List, Add Part, phase management Card all hidden.
- ViewBuildLog log button + voting controls + body remain functional.

## Edge Cases

- **No car assigned:** Build list with `car_id = null` renders the no-car-assigned warning + Assign Car Now button (yellow ui/Button). Confirmed via mocked e2e fixture.
- **Empty parts:** "No parts yet" empty state renders without errors; Add Part button still functional.
- **Slow network:** Throttle to Slow 3G; Edit dialog still opens responsively (Radix portal renders immediately); ConfirmDialog Delete shows the spinner for the duration of the request without auto-closing.
- **Multiple rapid double-clicks:** Add phase input + double-click Add — only one phase added (existing `disabled={!newPhaseName.trim() || isAddingPhase}` guard preserved).

## Sign-off Criteria

- [ ] All 10 manual TC cases pass.
- [ ] No console errors during any flow.
- [ ] No visual regressions vs the committed baseline PNGs.
- [ ] Focus rings visible on every interactive control under keyboard Tab.
- [ ] Escape closes every dialog except mid-flight destructive ones.

## Known Follow-ups (not blockers)

- EditBuildListForm internals (car make/model/generation Card grids) and PageHeader/SectionHeader/Card layout chrome still on legacy primitives — ride S12 ripple along with components/common/Card and components/common/Input.
- Lint baseline drifted from MEM062's 104 to 108 (+4 errors all in pre-existing test files); recommend MEM062 update or hunt-down in a future maintenance task.
- A real-network manual smoke pass is recommended during S13 milestone validation; the autonomous-mode closure substituted Playwright e2e assertions for the human pass.
