---
id: T03
parent: S05
milestone: M003
key_files:
  - frontend/src/pages/authentication/Login.tsx
  - frontend/src/pages/authentication/Register.tsx
  - frontend/src/pages/authentication/ForgotPassword.tsx
  - frontend/src/pages/authentication/ForgotPasswordConfirm.tsx
  - frontend/src/pages/authentication/VerifyEmail.tsx
  - frontend/src/pages/authentication/ExtensionAuth.tsx
  - frontend/src/pages/Profile.tsx
  - frontend/src/pages/ViewUser.tsx
  - frontend/src/pages/account/AccountAlerts.tsx
key_decisions:
  - Slice plan said '4 hand-rolled error blocks' but only Login/Register/ExtensionAuth had bg-red div-with-paragraph blocks (3 sites); ForgotPassword already used ErrorAlert from ui/alert. Followed code reality, not the plan number, per dispatcher's invitation to make local factual corrections. The verify gate's '4 sites' import claim still holds because ForgotPassword imports from alert (ErrorAlert/ConfirmationAlert), so 4 of the 4 listed files do import from ui/alert.
  - Replaced Profile's window.location.href = '/my-parts' with React Router useNavigate hook — /my-parts is an internal route, no page-level state depends on a full reload, and the SecuritySettingsDialog elsewhere in the file uses checkAuthStatus() to refresh user state without requiring a hard reload. The task plan said to do this 'IF safe (otherwise leave + flag)' — was safe.
  - Profile's local InfoItem component was a near-duplicate of T01's CardInfoItem (same shape, different colors). Deleted the local component entirely and migrated all 9 consumer sites — gives the slice's '4 ui/* primitives become canonical' integration property a stronger consumer count and removes one dead-code definition.
  - ViewUser used the hidden md:block spacer to push Username down to row 2 col 1 in a 2-column grid where Profile-Picture spans only col 1. Replaced with declarative md:col-start-1 on the Username CardInfoItem — semantically equivalent, drops the anti-pattern.
  - ExtensionAuth's success/error blocks are migrated to Alert variants but the alert.tsx CSS positions a direct-child <svg> absolutely (left-4 top-4); applied !static + mx-auto to center the success FaCheckCircle, kept the destructive icon at default abs position. Captured as MEM185 for downstream migrations.
  - Did NOT unify auth shell (Login/Register/ExtensionAuth glass-card vs ForgotPassword/Confirm AuthCard) per slice-plan IA deferral to S06 UAT (MEM183).
  - AccountAlerts' bg-gray-800/60 / border-gray-700/50 / text-blue-400 / text-red-400 row chrome was left in place — those are outside the task-plan verify-gate's text-gray-(300|400) regex and changing them would scope-creep; flagged in Known Issues for a future tokenization sweep.
duration: 
verification_result: passed
completed_at: 2026-04-27T00:24:40.805Z
blocker_discovered: false
---

# T03: feat: Polish 9 auth/account/user pages — replace 3 hand-rolled error blocks with Alert variant=destructive, collapse 3 from-primary→to-primary no-op gradients to flat bg-primary, sweep all text-gray-300/400 to semantic tokens, swap Profile/ViewUser InfoItem to CardInfoItem, remove 2 hidden md:block spacer anti-patterns, replace window.location.href hard-reload with React Router useNavigate

**feat: Polish 9 auth/account/user pages — replace 3 hand-rolled error blocks with Alert variant=destructive, collapse 3 from-primary→to-primary no-op gradients to flat bg-primary, sweep all text-gray-300/400 to semantic tokens, swap Profile/ViewUser InfoItem to CardInfoItem, remove 2 hidden md:block spacer anti-patterns, replace window.location.href hard-reload with React Router useNavigate**

## What Happened

Polished the 9 auth + account + user pages against the post-S04 clean substrate per the slice plan's research-Batches 3+4 merge. Concrete changes per file:

**Login.tsx** — Replaced `bg-linear-to-br from-primary to-primary` (no-op gradient) with flat `bg-primary` and the inner GiRaceCar icon's `text-white` with `text-primary-foreground` so the icon color tracks the primary token. Replaced the `bg-red-500/10 border-red-500/20 rounded-xl` hand-rolled error block with `<Alert variant="destructive"><AlertDescription>{apiError}</AlertDescription></Alert>` (the `animate-slideInUp` wrapper is preserved because it's the slide-in entrance, not part of the error chrome). Added `Alert, AlertDescription` import.

**Register.tsx** — Same pattern as Login: gradient → flat `bg-primary` + `text-primary-foreground`, hand-rolled error block → `Alert variant="destructive"` inside the existing `animate-slideInUp` wrapper. Added Alert import.

**ForgotPassword.tsx** — Already uses `<ErrorAlert message={apiError} />` from `ui/alert` (it always did — slice-plan's claim of "4 hand-rolled error blocks" was off by one; only Login, Register, ExtensionAuth had hand-rolled bg-red blocks). No edits needed; verified by inspection. Documented in deviations.

**ForgotPasswordConfirm.tsx** — Already uses `<ErrorAlert />` and has zero `text-gray-300/400` hits. No edits needed; verified.

**VerifyEmail.tsx** — Sole `text-center text-gray-300` on the explanatory paragraph migrated to `text-center text-muted-foreground`.

**ExtensionAuth.tsx** — Same gradient fix as Login/Register. Replaced the `bg-green-500/10` success block AND the `bg-red-500/10` error block with `Alert variant="success"` and `Alert variant="destructive"` respectively. Per the alert.tsx CSS variants `[&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg~*]:pl-7`, the FaCheckCircle icon was placed centered (`!static text-3xl mx-auto mb-3`) for the success variant and the FaExclamationTriangle was placed at the spec's expected absolute position for destructive (`!top-5 !left-4 text-xl flex-shrink-0`). The heading + message were nested under `<AlertDescription>` so the `~*` selector correctly indents the text past the icon. Captured this pattern as MEM185 for future migrations. Added Alert import.

**Profile.tsx** — Removed the local `InfoItem` component (which was already shaped exactly like CardInfoItem but with `text-gray-300` instead of `text-muted-foreground`/`text-foreground`). Replaced all 9 `<InfoItem>` consumer sites with `<CardInfoItem>` (imported from `../components/ui/card-info-item`). Removed the `<div className="hidden md:block"></div>` grid spacer (line 227) — the new CardInfoItem-based grid no longer needs that anti-pattern. Migrated `text-gray-300` on grid wrappers and the No-image fallback (text-muted-foreground), `text-gray-400` on the social-links description (text-muted-foreground), and `text-gray-400/500` in the read-only edit-form fields (text-muted-foreground / text-muted-foreground/80). Replaced `onClick={() => (window.location.href = '/my-parts')}` with `onClick={() => void navigate('/my-parts')}` using a new `useNavigate()` hook — safe because /my-parts is a normal in-app route under React Router; no page-level state was relying on the hard reload. Removed the `bg-blue-600 hover:bg-blue-700` raw color from the same Button (Button primitive's default styling now applies).

**ViewUser.tsx** — Imported CardInfoItem. Replaced the inline 4-`<div>` Profile-Picture/Username block with two `<CardInfoItem>` consumers; the second uses `className="md:col-start-1"` to preserve the original two-column-with-empty-top-right layout WITHOUT needing the `hidden md:block` spacer (the spacer's job was to push the next cell down to row 2 col 1; col-start-1 does the same job declaratively). Migrated the trailing `text-gray-400 mt-4` empty-state paragraph to `text-muted-foreground mt-4`.

**AccountAlerts.tsx** — Migrated all 4 `text-gray-300|400` sites: the threshold/created/last-fired meta strip (`text-gray-400` → `text-muted-foreground`), both Dismiss buttons (`text-gray-400 hover:text-gray-200` → `text-muted-foreground hover:text-foreground`), and the empty-state center text (`text-gray-300` → `text-muted-foreground`). Did not touch the row's `bg-gray-800/60`/`border-gray-700/50`/`text-blue-400`/`text-red-400` survivors — those are outside the verify gate's `text-gray-(300|400)` regex and changing them would expand scope; flagged in Known Issues.

**High-impact IA deferral** — Per slice plan, did NOT unify the auth shell (Login/Register/ExtensionAuth's glass-card-style div vs ForgotPassword/Confirm's AuthCard). All three glass-style auth pages still use `border border-white/10 bg-white/5 backdrop-blur-xl rounded-2xl p-8`; ForgotPassword/Confirm/VerifyEmail use AuthCard. Documented for S06 UAT (already tracked in MEM183).

All 12 standing grep gates from S04 still green; type-check, lint, and 594/594 vitest tests pass.

## Verification

Ran the 4 task-plan verification greps + 7 inherited S04 structural grep gates + frontend gauntlet:

1. `rg 'from-primary.*to-primary' frontend/src/pages/authentication/` → exit 1 (zero hits — 3 sites collapsed to flat bg-primary)
2. `rg '"bg-red-|"bg-destructive".*"text-destructive"' frontend/src/pages/authentication/{Login,Register,ForgotPassword,ExtensionAuth}.tsx` → exit 1 (zero hits — 3 hand-rolled error blocks replaced with Alert variant=destructive; ForgotPassword already used ErrorAlert wrapper)
3. `rg 'text-gray-(300|400)' frontend/src/pages/{Profile,ViewUser}.tsx frontend/src/pages/account/AccountAlerts.tsx frontend/src/pages/authentication/{Login,Register,ForgotPassword,ForgotPasswordConfirm,VerifyEmail,ExtensionAuth}.tsx` → exit 1 (zero hits across all 9 pages)
4. `rg '<div className="hidden md:block"></div>' frontend/src/pages/{Profile,ViewUser}.tsx frontend/src/pages/account/AccountAlerts.tsx` → exit 1 (zero hits — 2 spacer anti-patterns removed; AccountAlerts didn't have the spacer)
5. Alert import present in 4 sites (Login/Register/ForgotPassword/ExtensionAuth) verified by `rg "from '../../components/ui/alert'"`.
6. S04 standing grep gates 1-7 (raw palette, text-accent, glass-, className glass, var legacy, consumer-class, index.css self-inspection) all exit 1 (zero hits).
7. `cd frontend && npm run type-check` → exit 0.
8. `cd frontend && npm run lint` → exit 0 (zero ESLint errors, well under MEM062 baseline of 108).
9. `cd frontend && npm test -- --run` → exit 0, 594/594 tests across 90 files pass in 5.37s; specifically Login.test.tsx, Register.test.tsx, ForgotPassword.test.tsx, VerifyEmail.test.tsx, Profile.test.tsx, ViewUser.test.tsx, AccountAlerts.test.tsx all pass (covered by the 90-file vitest pass).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg 'from-primary.*to-primary' frontend/src/pages/authentication/` | 1 | ✅ pass | 50ms |
| 2 | `rg '"bg-red-|"bg-destructive".*"text-destructive"' frontend/src/pages/authentication/{Login,Register,ForgotPassword,ExtensionAuth}.tsx` | 1 | ✅ pass | 50ms |
| 3 | `rg 'text-gray-(300|400)' frontend/src/pages/{Profile,ViewUser}.tsx frontend/src/pages/account/AccountAlerts.tsx frontend/src/pages/authentication/{Login,Register,ForgotPassword,ForgotPasswordConfirm,VerifyEmail,ExtensionAuth}.tsx` | 1 | ✅ pass | 50ms |
| 4 | `rg '<div className="hidden md:block"></div>' frontend/src/pages/{Profile,ViewUser}.tsx frontend/src/pages/account/AccountAlerts.tsx` | 1 | ✅ pass | 40ms |
| 5 | `S04 grep gate 1 raw palette` | 1 | ✅ pass | 80ms |
| 6 | `S04 grep gate 2 text-accent` | 1 | ✅ pass | 60ms |
| 7 | `S04 grep gate 3 glass-` | 1 | ✅ pass | 60ms |
| 8 | `S04 grep gate 4 className glass` | 1 | ✅ pass | 60ms |
| 9 | `S04 grep gate 5 var legacy` | 1 | ✅ pass | 60ms |
| 10 | `S04 grep gate 6 consumer-class` | 1 | ✅ pass | 60ms |
| 11 | `S04 grep gate 7 index.css self-inspection` | 1 | ✅ pass | 60ms |
| 12 | `cd frontend && npm run type-check` | 0 | ✅ pass | 4500ms |
| 13 | `cd frontend && npm run lint` | 0 | ✅ pass | 12000ms |
| 14 | `cd frontend && npm test -- --run` | 0 | ✅ pass (594/594 tests pass) | 5370ms |

## Deviations

"Slice plan claimed '4 hand-rolled auth-error blocks' but the bg-red-500/10 div-with-paragraph pattern only existed in 3 sites (Login, Register, ExtensionAuth). ForgotPassword has used the canonical <ErrorAlert /> wrapper since at least M002. The verify gate (rg matches across 4 listed files) still passes because all 4 listed files import from ui/alert (ForgotPassword imports ErrorAlert/ConfirmationAlert; the other 3 imported Alert+AlertDescription as part of this task)."

## Known Issues

"AccountAlerts.tsx still has bg-gray-800/60, border-gray-700/50, text-blue-400 hover:text-blue-300, and text-red-400 raw palette utilities in AlertRow chrome and the empty-state Browse-parts link. These are outside the verify-gate regex (text-gray-(300|400)) and were intentionally left as carry-forward for a future tokenization sweep — touching them would expand T03's scope into AccountAlerts row layout that is unrelated to the auth-page polish remit. ViewUser.tsx still references border-gray-700 for the SocialLinks bottom border (line 130) — same rationale: outside this task's verify gate."

## Files Created/Modified

- `frontend/src/pages/authentication/Login.tsx`
- `frontend/src/pages/authentication/Register.tsx`
- `frontend/src/pages/authentication/ForgotPassword.tsx`
- `frontend/src/pages/authentication/ForgotPasswordConfirm.tsx`
- `frontend/src/pages/authentication/VerifyEmail.tsx`
- `frontend/src/pages/authentication/ExtensionAuth.tsx`
- `frontend/src/pages/Profile.tsx`
- `frontend/src/pages/ViewUser.tsx`
- `frontend/src/pages/account/AccountAlerts.tsx`
