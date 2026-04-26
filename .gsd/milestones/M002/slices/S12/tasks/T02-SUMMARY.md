---
id: T02
parent: S12
milestone: M002
key_files:
  - frontend/src/pages/About.tsx
  - frontend/src/pages/ContactUs.tsx
  - frontend/src/pages/Pricing.tsx
  - frontend/src/pages/Checkout.tsx
  - frontend/src/pages/Support.tsx
  - frontend/src/pages/BugReport.tsx
  - frontend/src/pages/authentication/Login.tsx
  - frontend/src/pages/authentication/Register.tsx
  - frontend/src/pages/authentication/ForgotPassword.tsx
  - frontend/src/pages/authentication/ForgotPasswordConfirm.tsx
  - frontend/src/pages/authentication/VerifyEmail.tsx
  - frontend/src/pages/authentication/VerifyEmailConfirm.tsx
  - frontend/src/pages/authentication/ExtensionAuth.tsx
  - frontend/src/components/authentication/GoogleAuthFlow.tsx
key_decisions:
  - Legacy Input `label`/`helperText` props rendered as JSX siblings (label above, helper below) per the plan's Input swap rule; ui/Input has no `label` prop and the form-control wrapper pattern keeps a11y intact via htmlFor+id pairing.
  - Legacy Input `leftIcon`/`rightIcon` props converted to absolute-positioned `<span>` (decorative, pointer-events-none) or `<button>` (interactive, e.g. show/hide password) siblings inside a relative wrapper; Inputs receive `pl-10`/`pr-10` className padding-only overrides to make room. Dropped the bespoke `variant='glass'` styling per the M002 retire-bespoke-palette intent.
  - ButtonStretch → `<Button className='w-full'>` with the layout-shape className override only; the legacy hard-coded `type='button'` was preserved on VerifyEmail's Send Verification Email button to avoid accidental form submission.
  - BugReport's submit button switched from inline `<LoadingSpinner size='sm'/>...Submitting...</>` composition to ui/Button's built-in `loading` prop — saves a JSX branch and aligns with the new design-system spinner placement.
  - GoogleAuthFlow's three legacy `<Dialog isOpen onClose title maxWidth>` shells migrated to the S09 parent-owned-state pattern: `<Dialog open={...} onOpenChange={(o) => { if (!o) closeDialog(); }}><DialogContent className='sm:max-w-md'>` — preserves the closeDialog() side-effects (clears password/otp/username + calls reset()) on Escape/overlay-click/X-button, not just on programmatic close.
  - Register's confirm-password `error` prop replaced by `aria-invalid` on the Input (which the inputVariants `aria-[invalid=true]:border-destructive` token already styles) plus a sibling `<div className='text-destructive'>` for the message — leverages design-token semantics rather than imperative error styling.
  - Card `interactive` prop (legacy added hover scale + cursor-pointer + glow) replaced with className overrides `cursor-pointer transition-transform hover:scale-105` on About + Support feature/option cards; ui/Card has no interactive prop and these cards have no onClick handlers — pure visual hint preserved without a behavior-prop dependency.
duration: 
verification_result: passed
completed_at: 2026-04-26T01:13:17.944Z
blocker_discovered: false
---

# T02: Migrated 14 Tier A static pages + auth pages + GoogleAuthFlow off legacy common/ + buttons/ onto ui/* primitives — zero legacy imports remain in scope

**Migrated 14 Tier A static pages + auth pages + GoogleAuthFlow off legacy common/ + buttons/ onto ui/* primitives — zero legacy imports remain in scope**

## What Happened

Swept 14 files off the legacy `components/common/*` + `components/buttons/*` palette onto the S08 design system primitives created in T01.

**Tier A (trivial public statics):**
- `About.tsx` — `common/Button` → `ui/Button` (default + outline variants); `common/Card` → `ui/Card` with `variant='glass'` preserved. Dropped the legacy `interactive` prop on the four feature/value cards (no onClick handlers existed) and folded its hover scale + cursor-pointer into a className override per MEM116. Removed redundant `mr-3` margins from button icons since `ui/Button` already applies `gap-2`.
- `ContactUs.tsx` — was already partially migrated (Card import only) at the start of this task; verified the swap and left the file as-is; no further changes needed.
- `Pricing.tsx` — `common/Card` → `ui/Card`. The two highlighted tier cards used `contentClassName='h-full flex flex-col'` for equal-height layouts; folded those classes into `className` directly on the new Card (which is just a div with the card styling applied) since `ui/Card` does not expose `contentClassName`.
- `Checkout.tsx` — `common/Card` → `ui/Card` (pure import-rename swap, no further callsite changes).
- `Support.tsx` — `common/Card` + `buttons/ActionButton` → `ui/Card` + `ui/Button`. Removed `interactive` prop on the support-option cards (folded hover scale + cursor-pointer into className). ActionButton callsites kept their bespoke `bg-linear-to-r from-primary-500 to-primary-600 ...` className overrides since the formal variant set doesn't currently encode that gradient — the className override is layout-shape-adjacent (matches the legacy visual without inventing a new variant per MEM111).
- `BugReport.tsx` — `common/{Alerts, Button, Card, Input, LoadingSpinner}` → `ui/{alert, button, card, input}`. The four `<Input label=...>` callsites were converted to label-above-Input JSX siblings per the plan's Input swap rule (legacy Input had `label`/`helperText` props ui/Input doesn't expose). The two `helperText='...'` siblings render as `<div className='mt-2 text-sm text-neutral-400'>` after the Input. The Submit button switched from inline `<LoadingSpinner size='sm'/>...Submitting...</>` composition to ui/Button's built-in `loading={isSubmitting}` prop (which renders Loader2 + children) — drops the unused Spinner import.

**Tier B (auth pages):**
- `Login.tsx` — `buttons/Button` → `ui/Button`; `common/Input` → `ui/Input`. Three inputs (username, password, OTP) had `label`+`leftIcon`+`rightIcon`+`variant='glass'`; converted each to a label-above-Input + relative-positioned-icons wrapper so the show/hide-password button stays interactive (legacy implementation rendered it inside the `rightIcon` slot but it was always click-capable). Dropped the bespoke `glass` variant per the M002 retire-bespoke-styling intent. Used `pl-10`/`pr-10` className overrides to make room for the absolutely-positioned icons. The submit `<Button loading={isLoading} disabled={... || isPasskeyLoading} className='w-full' size='lg'>` already lined up with ui/Button's API.
- `Register.tsx` — same pattern as Login with four inputs (username, email, password, confirm). The legacy `error="Passwords don't match"` prop on the confirm-password Input doesn't exist on `ui/Input` so it was rendered as: (a) `aria-invalid` flag on the Input (which Tailwind's `aria-[invalid=true]:border-destructive` token in inputVariants picks up automatically) plus (b) a sibling `<div className='mt-2 text-sm text-destructive'>` for the message text.
- `ForgotPassword.tsx` — `buttons/StretchButton` → `<Button className='w-full'>`; `common/Alerts` → `ui/alert`; `common/Input` → `ui/Input` with email field's label rendered as JSX sibling. ButtonStretch was a hard-coded indigo full-width button — switching to `<Button className='w-full'>` adopts the design-system primary tokens.
- `ForgotPasswordConfirm.tsx` — same swap rules as ForgotPassword; two password inputs each get a label-above-Input wrapper and the submit becomes `<Button className='w-full'>`.
- `VerifyEmail.tsx` — `buttons/StretchButton` → `<Button className='w-full' type='button'>`; `common/Alerts` → `ui/alert`; `common/LoadingSpinner` → `ui/Spinner` (default export rename only — no other prop changes). Note: legacy ButtonStretch hard-coded `type='button'`, so I added it explicitly on the new Button to preserve behavior (ui/Button defaults to native `<button>` which submits forms when inside one).
- `VerifyEmailConfirm.tsx` — pure `common/Alerts` → `ui/alert` import-path rename, no callsite changes (uses ConfirmationAlert + ErrorAlert with the named-wrapper API T01 preserved).
- `ExtensionAuth.tsx` — `common/LoadingSpinner` → `ui/Spinner` (default export rename). Two callsites (`<LoadingSpinner size='lg' text='...'/>`, `<LoadingSpinner size='md' text='...'/>`) preserve their size+text props since ui/Spinner adopts the same shape per T01.

**Inner component:**
- `components/authentication/GoogleAuthFlow.tsx` — `buttons/Button` → `ui/Button`; `common/Input` → `ui/Input`; `common/Dialog` → `ui/Dialog` parent-owned-state pattern (per S09/T02 ViewBuildlist precedent). Replaced the three `<Dialog isOpen={open*} onClose={closeDialog} title='...' maxWidth='md'>` shells with `<Dialog open={...} onOpenChange={(o) => { if (!o) closeDialog(); }}><DialogContent className='sm:max-w-md'><DialogHeader><DialogTitle>...</DialogTitle></DialogHeader>...</DialogContent></Dialog>`. Each dialog's body Inputs (link-password, link-otp, signup-username, 2fa-otp) converted to label+icon JSX siblings with unique IDs (e.g. `google-link-password`, `google-2fa-otp`) so labels associate correctly even though three dialogs all use `name='otp'`/`name='password'`. The existing `closeDialog()` callback (which clears local state + calls `reset()`) is preserved and now wired up via `onOpenChange(false)` so Escape/overlay-click/X-button all clean up local state correctly.

Notes per MEM107/MEM115/MEM116: layout chrome (PageHeader, Card composition shape, AuthCard, AuthForm, AuthRedirectLink) was deliberately left untouched — only interactive primitives + the Card/Alert/Spinner/Input wrappers were swapped. No useEffect orderings, cancellation flags, redirect logic, or submit handlers changed; this was a pure styling migration. data-testid hooks were preserved (none of the touched files declared any explicitly).

## Verification

Ran the task plan's exact verification command sequence:

1. `npm run type-check` (`tsc -b --noEmit`) — exit 0, no errors. Confirms all 14 swapped files type-check against the rest of the frontend, including the new ui/Card/Alert/Spinner/Input/Button/Dialog imports and the JSX siblings that replaced the legacy `label`/`helperText`/`error` props.

2. `npm test -- --run Login Register ForgotPassword VerifyEmail BugReport About ContactUs Pricing Checkout Support GoogleAuthFlow ExtensionAuth` — 14 test files / 44 tests all passed. The vitest filter matched every relevant per-page test (Login, Register, ForgotPassword, ForgotPasswordConfirm, VerifyEmail, VerifyEmailConfirm, BugReport, About, ContactUs, Pricing, Checkout, Support, ExtensionAuth) plus the unrelated BugReportReview admin test (filename match). All green. Tests query inputs by placeholder text and roles, so the import-path swap + JSX-sibling label restructuring did not break selectors.

3. `! grep -ln 'components/common\|components/buttons' src/pages/About.tsx src/pages/ContactUs.tsx src/pages/Pricing.tsx src/pages/Checkout.tsx src/pages/Support.tsx src/pages/BugReport.tsx src/pages/authentication/*.tsx src/components/authentication/GoogleAuthFlow.tsx` — exit 0 (grep found nothing across all 14 targeted files + the 7 sibling files in `pages/authentication/*.tsx` covered by the glob, including AuthCard's adjacent context). Boundary clean.

Slice-level verification (S12 Verification gate) cannot fully run yet — the e2e suite requires the full migration (T03–T05) plus refreshed baselines (T06). Type-check and per-page vitests are partial passes consistent with intermediate-task expectations.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm run type-check` | 0 | ✅ pass | 3000ms |
| 2 | `npm test -- --run Login Register ForgotPassword VerifyEmail BugReport About ContactUs Pricing Checkout Support GoogleAuthFlow ExtensionAuth` | 0 | ✅ pass | 2040ms |
| 3 | `! grep -ln 'components/common\|components/buttons' src/pages/About.tsx src/pages/ContactUs.tsx src/pages/Pricing.tsx src/pages/Checkout.tsx src/pages/Support.tsx src/pages/BugReport.tsx src/pages/authentication/*.tsx src/components/authentication/GoogleAuthFlow.tsx` | 0 | ✅ pass | 50ms |

## Deviations

No deviations from the task plan. Two minor adaptations were applied in the spirit of the plan's swap rules: (1) the legacy Input `error` prop on Register's confirm-password field was rendered via `aria-invalid` + a sibling `<div className='text-destructive'>` rather than passing `error` through to ui/Input (ui/Input doesn't expose `error`); (2) BugReport's submit button uses ui/Button's built-in `loading` prop instead of an inline `<Spinner/>` JSX block since the plan's swap rules describe Spinner as the LoadingSpinner replacement but ui/Button's built-in loader is the more idiomatic shadcn pattern — no behavior change, drops one unused import. Both fall within the plan's stated style-only-migration scope.

## Known Issues

None. Type-check, per-page vitest filter, and grep guard all pass on the touched files.

## Files Created/Modified

- `frontend/src/pages/About.tsx`
- `frontend/src/pages/ContactUs.tsx`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/pages/Support.tsx`
- `frontend/src/pages/BugReport.tsx`
- `frontend/src/pages/authentication/Login.tsx`
- `frontend/src/pages/authentication/Register.tsx`
- `frontend/src/pages/authentication/ForgotPassword.tsx`
- `frontend/src/pages/authentication/ForgotPasswordConfirm.tsx`
- `frontend/src/pages/authentication/VerifyEmail.tsx`
- `frontend/src/pages/authentication/VerifyEmailConfirm.tsx`
- `frontend/src/pages/authentication/ExtensionAuth.tsx`
- `frontend/src/components/authentication/GoogleAuthFlow.tsx`
