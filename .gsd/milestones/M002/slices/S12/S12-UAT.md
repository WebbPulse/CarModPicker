# S12: Repo-wide ripple reskin — retire components/common/ + components/buttons/ — UAT

**Milestone:** M002
**Written:** 2026-04-26T04:04:44.077Z

# S12 UAT — Repo-wide ripple reskin

## Acceptance preconditions

- Backend not required to be running — kitchen-sink + most static page tests are client-side only. For Tier C/D dynamic pages (Profile, Search, parts catalog, admin), the dev server proxies `/api` to the backend at port 8000.
- Frontend dev: `cd frontend && npm run dev` (port 4000).
- Vitest test runner: `cd frontend && npm test -- --run`.
- Playwright e2e runner: `cd frontend && npm run test:e2e` (auto-starts dev server).

## Autonomous-mode evidence

The Playwright e2e suite at three viewports (mobile 375×667, tablet 768×1024, desktop 1280×800) serves as primary visual evidence for the priority pages migrated through S08–S11 + S12 (kitchen-sink, build-list view, parts catalog, price-history, price-alerts, admin shell + ExtractionHealth, smoke). All 35 tests pass / 10 skipped against post-migration baselines.

For the ~30 surfaces not exercised by Playwright (Tier A statics like About/ContactUs/Pricing/Checkout/Support/BugReport, Tier B auth pages, Tier C1/C2 inner forms), import correctness is enforced by:
- type-check (catches broken imports at compile time)
- vitest no-legacy-primitives.test.ts (catches new legacy imports at unit-test time)
- ESLint no-restricted-imports rule (catches at PR/lint time)
- per-page vitest suites where they exist (Login, Register, Profile, Home, AccountAlerts, etc. — 597 unit tests total)

## Test cases

### TC1: Kitchen-sink renders every primitive in every state at all 3 viewports

**Preconditions:** Dev server running.

**Steps:**
1. Navigate to `http://localhost:4000/_kitchen-sink` at viewport 1280×800 (desktop).
2. Visually confirm: Button matrix (default/destructive/secondary/outline/ghost/link × xs/sm/md/lg/icon × default/disabled/loading); Input states; Select open + closed; Combobox with + without results; Tabs; Dialog/DropdownMenu/Sheet open via `defaultOpen modal={false}`; Toast; Card (padding=none with header/footer composition + default-padding inline content); Alert (3 variants × 3 named wrappers); Spinner (all 6 sizes side-by-side + text + inline); Pagination (totalPages=20, currentPage=7 to exercise both ellipses).
3. Resize viewport to 768×1024 (tablet). Verify layout reflows without overflow / clipping.
4. Resize viewport to 375×667 (mobile). Verify same.

**Expected outcome:** All primitives render with the new design tokens. No console errors. Layout responsive. **Automated equivalent:** `npm run test:e2e -- components.spec` (3 passed).

### TC2: Grep guard fails the build on a future legacy import

**Preconditions:** None.

**Steps:**
1. Temporarily add `import Card from '../../components/common/Card';` to any file in `frontend/src/`.
2. Run `cd frontend && npm test -- --run no-legacy-primitives`.
3. Revert the change.

**Expected outcome:** Step 2 fails with the grep-guard's diagnostic naming the offending file and import. Step 3 returns the suite to green. **Verifies R017's enforcement gate.**

### TC3: ESLint no-restricted-imports rule fires

**Preconditions:** None.

**Steps:**
1. Temporarily add `import { Button } from '../../components/buttons/Button';` to any source file.
2. Run `cd frontend && npm run lint`.
3. Revert the change.

**Expected outcome:** Step 2 reports a `no-restricted-imports` error pointing at the offending line. Step 3 returns lint to the MEM062 baseline (108 errors, 0 new). **Redundant safety net for R017 — fires at PR-time before vitest runs.**

### TC4: Profile page (densest C1 surface) — full interaction smoke

**Preconditions:** Dev server + backend; user logged in.

**Steps:**
1. Navigate to `/profile`.
2. Verify all 8 InfoItem fields render (username, email, etc.) with the new InfoItem inline composition (matches ViewUser pattern).
3. Click "Manage Security" → SecuritySettingsDialog opens via parent-owned-state pattern. Tab through every field; focus indicators visible; Escape closes; verify `closeDialog()` side-effect (form state reset).
4. Click "Change Password" tab → ChangePasswordDialog opens. Submit with mismatched passwords → aria-invalid + destructive sibling div renders. Cancel → state cleared.
5. Click "Manage My Parts" → navigates to /parts/user.
6. Edit profile fields → click "Save Changes". Button shows ui/Button's built-in loading prop (Loader2 + label) during submit.

**Expected outcome:** Every interaction works identically to pre-migration; only the visual polish changed (formal variants, design-token colors). No regressions in useEffect ordering, cancellation flags, or async behavior.

### TC5: ViewPart (978 LOC, heaviest C2 page) — list + dialogs

**Preconditions:** Dev server + backend; at least one part in catalog.

**Steps:**
1. Navigate to `/parts/<id>`.
2. Verify ParentNavigationLink-replacement: "Created by <username>" link renders inline with `text-indigo-400 hover:text-indigo-300 underline` (per the inlined Link spec).
3. Open AddToBuildListDialog (S10/T03 partial → S12/T04 finished). Pick a build list. Confirm it appears in the part's associated build lists tally.
4. Click Delete → ui/ConfirmDialog opens with destructive variant. Verify the description shows the part name + the build-list count tally. Cancel → dialog closes; state preserved.
5. Confirm delete → loading state shows "Deleting..." (loadingLabel preserved); error path renders `error={...}` slot.

**Expected outcome:** All dialog flows work; ConfirmDialog adapter pattern preserves the legacy DeleteConfirmationDialog UX (warning text, loading label, error display).

### TC6: Admin extraction-health (Tier D) on new design system

**Preconditions:** Dev server + backend with admin user.

**Steps:**
1. Navigate to `/admin/extraction-health`.
2. Verify 111/111 compliance summary, per-tier coverage gradient (T0/T1/T2 with field-presence heatmap), per-adapter failure rates over 7d window — all on ui/Card containers, no legacy imports.
3. Tab through the page → focus indicators visible; keyboard nav works.

**Expected outcome:** Page renders with new design system; data structure unchanged from S04. **Automated equivalent:** `npm run test:e2e -- admin.spec` (green at 3 viewports).

### TC7: Authentication flow on new design system

**Preconditions:** Dev server + backend.

**Steps:**
1. Navigate to `/login`. Verify Username/Password Inputs with relative-positioned icons (FaUser, FaLock); show/hide-password button stays clickable inside the rightIcon wrapper.
2. Submit invalid credentials → ErrorAlert renders inline with destructive token.
3. Click "Sign in with Google" → GoogleAuthFlow's account-link/2FA/signup dialogs all open via parent-owned-state pattern. Escape closes each, fires `closeDialog()` to clear local state (password/otp/username + reset()).
4. Repeat for `/register` (verify confirm-password aria-invalid + destructive sibling on mismatch).

**Expected outcome:** All auth flows work end-to-end; dialogs preserve closeDialog() side-effects on every dismiss path.

### TC8: Build-list / parts-catalog priority pages (S09/S10 + S12 sweep finished)

**Preconditions:** Dev server + backend; at least one build list with parts.

**Steps:**
1. Navigate to `/build-lists/<id>`. Verify Sparkline + PriceDeltaLine on each part row (S06 components preserved through S12 sweep). Tab through; focus indicators visible.
2. Navigate to `/parts`. Verify part cards show sparkline + delta where observations exist; PartsFilterSidebar renders correctly with the inner div padding wrapper (PartsFilterSidebar Card swap).
3. Pagination at bottom of catalog: verify ellipsis logic, "Showing X – Y of Z" summary, Previous/Next disabled states match the verbatim pre-migration behavior.

**Expected outcome:** S08 primitives + S06 chart components compose correctly on the priority pages. **Automated equivalents:** `npm run test:e2e -- build-list.spec` and `parts-catalog.spec` (green at 3 viewports).

## Surfaces deferred to S13 / future manual UAT

These pages are migrated and verified by type-check + lint + grep-guard for import correctness, but not screenshot-asserted by Playwright:

- Tier A statics: About, ContactUs, Pricing, Checkout, Support, BugReport
- Tier B auth: Register, ForgotPassword, ForgotPasswordConfirm, VerifyEmail, VerifyEmailConfirm, ExtensionAuth
- Tier C1 inner: SecuritySettings, PasskeySettings, ConnectedAccountsSettings, ChangePasswordDialog, TwoFactorAuthDialog, SecuritySettingsDialog (covered by Profile.test.tsx interactions)
- Tier C2 inner: ImageGallery, ImageGalleryManage, all CreateXForm/EditXForm components (covered by per-page vitest suites where they exist)
- Tier D admin sub-pages: ReportReview, BugReportReview, UserManagement, PartsCuration, SystemAdmin, SystemStatistics, CrawlerAdmin (only AdminDashboard + ExtractionHealth screenshot-asserted)

S13 milestone validation should pick up a manual smoke pass over these — type-check + lint + grep prove imports are correct; visual polish verification benefits from human eyeball.

## Pass/fail criteria

- **Pass:** All 8 test cases above pass on a manual run; the full automated gauntlet (type-check + 597 vitests + 35 e2e + lint baseline + grep) returns to green.
- **Fail:** Any unexpected console error, broken interaction, focus regression, or new lint/type/test failure introduced by the migration. The fail mode is "swap regressed behavior" — fix is to compare the offending file's pre-migration commit against the new state.

## Operational readiness signals

- **Health signal:** ui/* primitives are pure-client React components with no runtime dependencies; failure manifests as a render-time crash inside RouteGroupBoundary (Sentry-tagged with route_group from the pre-existing tagging in App.tsx). No new runtime signals needed.
- **Failure signal:** Pixel-diff PNGs at `frontend/test-results/*` on Playwright regression; vitest stack traces surface broken imports; type-check surfaces broken imports at compile-time; the new grep guard fires at CI time before merge.
- **Recovery procedure:** Revert the offending file via `git revert <sha>`; `git mv` history is intact thanks to the MEM127 relocation pattern, so blame and history follow individual files.
- **Monitoring gaps:** None introduced by S12. R020 accessibility regressions (focus indicators, keyboard nav, escape-on-dialog) are not auto-monitored — manual UAT in S13 is the catch-all.
