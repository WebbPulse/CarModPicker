---
id: T03
parent: S12
milestone: M002
key_files:
  - frontend/src/pages/Profile.tsx
  - frontend/src/pages/Home.tsx
  - frontend/src/pages/Search.tsx
  - frontend/src/components/profile/SecuritySettings.tsx
  - frontend/src/components/profile/PasskeySettings.tsx
  - frontend/src/components/profile/ConnectedAccountsSettings.tsx
  - frontend/src/components/profile/ChangePasswordDialog.tsx
  - frontend/src/components/profile/TwoFactorAuthDialog.tsx
  - frontend/src/components/profile/SecuritySettingsDialog.tsx
  - frontend/src/components/forms/ImageUpload.tsx
  - frontend/src/components/images/ImageWithPlaceholder.tsx
key_decisions:
  - Used a re-export shim pattern (forms/ImageUpload.tsx, images/ImageWithPlaceholder.tsx → re-export from common/) to let Profile and Home point at future-canonical helper paths without forcing a 16-file importer pre-migration. T05 will collapse these shims when it does the wholesale relocation. Captured as MEM124 so T04/T05 follow the convention.
  - Inlined CardInfoItem in Profile via a private InfoItem component instead of importing from common/CardInfoItem — matches the established pattern in already-migrated ViewUser.tsx. T05's planned move of CardInfoItem → ui/card-info-item is unaffected; Profile just doesn't depend on it anymore.
  - All 3 dialogs (Change Password / 2FA / Security Settings) adopted the S09/T02 parent-owned-state Dialog pattern (open/onOpenChange + DialogContent sm:max-w-* sizing). The legacy handleClose() side-effect callbacks (form-state reset, error-clear) preserved and wired to onOpenChange(false) so Escape/overlay-click/X-button all clean up local state correctly.
  - Spinner-text composition in dialog submit buttons converted to ui/Button's built-in `loading` prop (legacy code used inline `<LoadingSpinner/>...{label}` JSX). Drops one import per file and aligns with shadcn idiom; the disabled state stays explicit via `disabled={isSubmitting}` since `loading` alone implies disabled but tests sometimes assert `disabled` directly.
  - Disable 2FA buttons in SecuritySettings + TwoFactorAuthDialog + SecuritySettingsDialog switched to variant='destructive' per MEM116 — drops the legacy `bg-red-600 hover:bg-red-700` className overrides since the destructive token already encodes that semantic.
  - Search.tsx Load More buttons added explicit `type='button'` to preserve the legacy ActionButton hard-coded `type='button'` (ui/Button defaults to native `<button>` which submits forms; though Search has no enclosing form, defensive explicit-type is consistent with VerifyEmail's swap in T02).
duration: 
verification_result: passed
completed_at: 2026-04-26T02:11:28.856Z
blocker_discovered: false
---

# T03: Migrated Tier C1 (Profile/Home/Search/AccountAlerts/UserCard/ViewUser/Header + 6 profile inner components) onto ui/* primitives; introduced forms/ + images/ re-export shims so future-relocated helper paths resolve cleanly

**Migrated Tier C1 (Profile/Home/Search/AccountAlerts/UserCard/ViewUser/Header + 6 profile inner components) onto ui/* primitives; introduced forms/ + images/ re-export shims so future-relocated helper paths resolve cleanly**

## What Happened

Swept the C1 surface — Profile.tsx (the 461-line densest single page in this tier), Home.tsx, Search.tsx, plus the 6 profile inner components (SecuritySettings, PasskeySettings, ConnectedAccountsSettings, ChangePasswordDialog, TwoFactorAuthDialog, SecuritySettingsDialog) — off the legacy `components/common/*` + `components/buttons/*` palette onto the S08 design system primitives.

**Files already migrated before this task started:** ViewUser.tsx, AccountAlerts.tsx, UserCard.tsx, layout/globalHeader/Header.tsx — verified zero legacy imports remain on each via per-file grep. ViewUser had already inlined CardInfoItem with the `<div><p className="font-medium text-gray-300">{label}</p><div>...</div></div>` pattern; I followed that same pattern for Profile (extracted into a private `InfoItem` component to dedupe the 8 occurrences).

**Profile.tsx (page sweep):** ActionButton → `<Button>` (default variant) for primary actions; the bespoke `bg-indigo-600 hover:bg-indigo-700` className override on Manage Security and `bg-blue-600 hover:bg-blue-700 w-full` on Manage My Parts preserved via className per MEM111 (they encode bespoke colors the formal variant set doesn't have). ButtonStretch → `<Button className='w-full' loading={isUpdating}>` — switched the legacy `{isUpdating ? 'Saving...' : 'Save Changes'}` text-only signal onto ui/Button's built-in `loading` prop. SecondaryButton → `<Button variant='secondary'>`. Card→ui/Card, Input → ui/Input (label-above-input wrappers, social-fields refactored to a static `socialFields` array driving a map). LoadingSpinner → Spinner. CardInfoItem → inlined as a private `InfoItem` component. ImageUpload's import path now points at `../components/forms/ImageUpload` — the future-canonical path resolved by a re-export shim (see "Shims" below).

**Home.tsx (page sweep):** LinkButton → `<Button asChild><Link to='...'>...</Link></Button>` per shadcn convention. Variants mapped: legacy `'primary'` → default; `'secondary'` → variant='secondary'; `'outline'` → variant='outline'; legacy `size='lg'` → size='lg'. Quick Actions sidebar links keep `className='w-full justify-start'` per MEM116 (layout-shape override, not color). Removed redundant `mr-2` margins from icon-children since ui/Button already applies `gap-2` (the [&_svg]:size-4 + flex gap-2 in buttonVariants handle icon spacing). Card/ErrorAlert/Spinner pure import-rename swaps. ImageWithPlaceholder retargeted at `../components/images/ImageWithPlaceholder` — same shim pattern.

**Search.tsx (page sweep):** All 4 ActionButton callsites (Load More Build Lists / Users / Parts; the search submit button is a bespoke styled `<button>` not ActionButton — left as-is since it's not in the legacy ActionButton import set). Each `<ActionButton>` → `<Button type='button'>` (explicit type to preserve the legacy hard-coded `type='button'` semantic). Card / ErrorAlert / Spinner import-rename swaps.

**Profile inner components (the 6 dialog-heavy forms):**
- **SecuritySettings.tsx** — extracted a private `Field` helper component to compose label + relative-positioned absolute icon + Input + helperText (this avoided duplicating the wrapper JSX 6 times across the password / 2fa-setup / 2fa-disable forms). All buttons via formal variants: submit = default, Cancel = variant='secondary', Disable 2FA = variant='destructive' per MEM116 (drops the legacy `bg-red-600 hover:bg-red-700` className override since destructive token already encodes that).
- **PasskeySettings.tsx** — Spinner adopts the new `inline` prop (T01) for the inline "Loading passkeys…" composition; the Add Passkey form's nickname Input gets the relative-positioned FaKey icon wrapper. Create button uses `loading={isRegistering}` to merge the legacy "<Spinner/>...Waiting for your device…" inline composition into one ui/Button prop call.
- **ConnectedAccountsSettings.tsx** — SecondaryButton (Disconnect) → `<Button variant='secondary' size='sm'>` per MEM116 (formal `size='sm'` instead of the bespoke `!py-1 !px-3 text-sm` className override).
- **ChangePasswordDialog / TwoFactorAuthDialog / SecuritySettingsDialog** — legacy Dialog → ui/Dialog parent-owned-state pattern per S09/T02 ViewBuildlist precedent. `<Dialog open={isOpen} onOpenChange={(o) => { if (!o) handleClose(); }}><DialogContent className='sm:max-w-{md|lg|2xl}'><DialogHeader><DialogTitle>…</DialogTitle></DialogHeader>…body…</DialogContent></Dialog>`. The local `handleClose()` callbacks (which reset form state, clear errors) preserved and now wired up via `onOpenChange(false)` so Escape / overlay-click / X-button all clean up state correctly. SecuritySettingsDialog uses `sm:max-w-2xl max-h-[90vh] overflow-y-auto` to accommodate the 5-tab layout (password / 2fa / passkeys / connected / session) on smaller viewports. Each dialog's submit/disable buttons use ui/Button's `loading` prop instead of the inline `<LoadingSpinner/>...{label}` composition the legacy code used.

**Shims (new):** Created two one-line re-export stubs to let Profile and Home point at future-canonical helper paths without forcing a full T04+T5-style 16-file importer sweep right now: `frontend/src/components/forms/ImageUpload.tsx` (`export { default } from '../common/ImageUpload'`) and `frontend/src/components/images/ImageWithPlaceholder.tsx` (same pattern). T05 will collapse these by deleting the originals at `components/common/` and replacing the shim bodies with the real implementations once it migrates the rest of the importer set. Captured as MEM124 so T04/T05 know about the convention.

**Behavior preserved end-to-end:** No useEffect orderings, no cancellation flag patterns (MEM097/MEM102's AccountAlerts self-cancel race was already addressed in the existing-migrated AccountAlerts.tsx), no redirect logic, no async-await patterns, no submit-handler signatures, no data-testid hooks (the few that exist on AccountAlerts and Profile are preserved). Pure styling migration. Auth-flow side-effects (closeDialog clearing local state + calling reset()) preserved via onOpenChange wiring.

## Verification

Ran the task plan's exact verification command sequence from `frontend/`:

1. **`npm run type-check`** (`tsc -b --noEmit`) — exit 0, no errors. Confirms all 9 swapped files type-check against the rest of the frontend, including the new ui/Card/Alert/Spinner/Input/Button/Dialog imports, the JSX-sibling label restructuring, the parent-owned-state Dialog pattern, and the new forms/+images/ re-export shims.

2. **`npm test -- --run Profile Home Search ViewUser AccountAlerts UserCard SecuritySettings PasskeySettings ConnectedAccountsSettings ChangePasswordDialog TwoFactorAuthDialog SecuritySettingsDialog Header`** — 6 test files / 24 tests all passed (Profile.test.tsx 3/3, Home.test.tsx 4/4, AccountAlerts.test.tsx 9/9, plus 3 other vitest files matched by name pattern). Tests query by role / placeholder text / data-testid, so the import-path swap + JSX-sibling label restructuring did not break any selectors. The act() warnings from Home.tsx are pre-existing (unrelated to this task; they came from sequential setState calls in the homepage's data-loading useEffect).

3. **`! grep -ln 'components/common\|components/buttons' src/pages/Profile.tsx src/pages/Home.tsx src/pages/Search.tsx src/pages/ViewUser.tsx src/pages/account/AccountAlerts.tsx src/components/users/UserCard.tsx src/components/profile/*.tsx src/components/layout/globalHeader/Header.tsx`** — exit 0 (grep found nothing across all 13 in-scope files including the 6 profile inner components). Boundary clean.

Slice-level verification (S12 Verification gate) cannot fully run yet — the e2e suite requires the full migration (T04–T05) plus refreshed baselines (T06). Type-check and per-page vitests are partial passes consistent with intermediate-task expectations.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm run type-check` | 0 | ✅ pass | 4000ms |
| 2 | `npm test -- --run Profile Home Search ViewUser AccountAlerts UserCard SecuritySettings PasskeySettings ConnectedAccountsSettings ChangePasswordDialog TwoFactorAuthDialog SecuritySettingsDialog Header` | 0 | ✅ pass | 1270ms |
| 3 | `! grep -ln 'components/common|components/buttons' src/pages/Profile.tsx src/pages/Home.tsx src/pages/Search.tsx src/pages/ViewUser.tsx src/pages/account/AccountAlerts.tsx src/components/users/UserCard.tsx src/components/profile/*.tsx src/components/layout/globalHeader/Header.tsx` | 0 | ✅ pass | 50ms |

## Deviations

No deviations from the task plan's swap rules. Two minor task-list adaptations: (1) ViewUser.tsx, AccountAlerts.tsx, UserCard.tsx, and layout/globalHeader/Header.tsx were already fully migrated by prior work (verified via per-file grep before starting), so this task only needed to verify them rather than migrate them — they're listed in keyFiles as untouched. (2) Two new files — `frontend/src/components/forms/ImageUpload.tsx` and `frontend/src/components/images/ImageWithPlaceholder.tsx` — were created as one-line re-export shims to let Profile and Home point at the future-canonical paths without forcing T04/T05's 16-file importer sweep into T03. The plan note "Same swap rules as T02" doesn't address these helpers because T02's files don't use them; the shim approach falls within the "future-relocated path" pattern T04 explicitly establishes for forms/cars/images relocations. T05 will collapse the shims when it does the wholesale relocation.

## Known Issues

None. Type-check, per-page vitest filter, and grep guard all pass on the touched files. Pre-existing Home.tsx act() warnings are noise from sequential useEffect setState calls in the homepage's data-loading flow — unrelated to this task and harmless (tests pass green).

## Files Created/Modified

- `frontend/src/pages/Profile.tsx`
- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/Search.tsx`
- `frontend/src/components/profile/SecuritySettings.tsx`
- `frontend/src/components/profile/PasskeySettings.tsx`
- `frontend/src/components/profile/ConnectedAccountsSettings.tsx`
- `frontend/src/components/profile/ChangePasswordDialog.tsx`
- `frontend/src/components/profile/TwoFactorAuthDialog.tsx`
- `frontend/src/components/profile/SecuritySettingsDialog.tsx`
- `frontend/src/components/forms/ImageUpload.tsx`
- `frontend/src/components/images/ImageWithPlaceholder.tsx`
