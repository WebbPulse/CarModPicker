---
estimated_steps: 1
estimated_files: 9
skills_used: []
---

# T03: Polish auth + account + user pages: Login, Register, ForgotPassword, ForgotPasswordConfirm, VerifyEmail, ExtensionAuth, Profile, ViewUser, AccountAlerts

Polish-pass batch covering 9 auth + account + user pages (research Batches 3+4 merged — both consume the same Alert and (now-retokenized) CardInfoItem primitives, share the text-gray-300/400 survivor pattern, file-disjoint touches). Replace 4 hand-rolled error blocks across Login, Register, ForgotPassword, ExtensionAuth with Alert variant=destructive (the existing frontend/src/components/ui/alert.tsx is the canonical primitive — no new component needed). Remove 3 from-primary to-primary no-op gradients in Login.tsx, Register.tsx, ExtensionAuth.tsx (degrade to flat color — delete gradient classes and use bg-primary or omit). Migrate text-gray-300/400 → text-foreground/text-muted-foreground across all 9 pages (Profile alone has 8 such hits). Replace any inline copy of the InfoItem pattern in Profile/ViewUser/AccountAlerts with CardInfoItem from T01's retokenized primitive. Remove the <div className="hidden md:block"></div> spacer anti-pattern (3 sites per research). Remove Profile's window.location.href hard-reload in favor of React Router navigation IF safe (otherwise leave + flag in summary). Do NOT unify auth shell (Login/Register/ExtensionAuth glass-card vs ForgotPassword/Confirm AuthCard) — high-impact IA decision deferred to S06 UAT. Document the deferral in slice summary. Quality gate (Q3 Threat Surface): Auth pages handle credentials, password reset tokens, email verification flows. Polish edits in this task are visual-only — they touch className/JSX structure but NOT form submit handlers, fetch calls, or token-handling logic. Risk: accidentally breaking a submit handler by editing surrounding markup; mitigated by per-page render test runs (cd frontend && npm test -- --run pages/authentication) included in verify gate. Quality gate (Q4): Touches R060 — auth/account pages currently 0-baseline; this task changes them visually but they get baselines via T06's polish-coverage.spec.ts. Quality gate (Q5): Auth submit handlers must continue to work; existing vitest specs (Login.test.tsx, Register.test.tsx, etc.) must remain green.

## Inputs

- ``frontend/src/components/ui/textarea.tsx``
- ``frontend/src/components/ui/card-info-item.tsx``
- ``frontend/src/components/ui/alert.tsx``
- ``frontend/src/pages/authentication/Login.tsx``
- ``frontend/src/pages/authentication/Register.tsx``
- ``frontend/src/pages/authentication/ForgotPassword.tsx``
- ``frontend/src/pages/authentication/ForgotPasswordConfirm.tsx``
- ``frontend/src/pages/authentication/VerifyEmail.tsx``
- ``frontend/src/pages/authentication/ExtensionAuth.tsx``
- ``frontend/src/pages/Profile.tsx``
- ``frontend/src/pages/ViewUser.tsx``
- ``frontend/src/pages/account/AccountAlerts.tsx``

## Expected Output

- ``frontend/src/pages/authentication/Login.tsx``
- ``frontend/src/pages/authentication/Register.tsx``
- ``frontend/src/pages/authentication/ForgotPassword.tsx``
- ``frontend/src/pages/authentication/ForgotPasswordConfirm.tsx``
- ``frontend/src/pages/authentication/VerifyEmail.tsx``
- ``frontend/src/pages/authentication/ExtensionAuth.tsx``
- ``frontend/src/pages/Profile.tsx``
- ``frontend/src/pages/ViewUser.tsx``
- ``frontend/src/pages/account/AccountAlerts.tsx``

## Verification

1. rg 'from-primary.*to-primary' frontend/src/pages/authentication/ returns 0. 2. rg '"bg-red-|"bg-destructive".*"text-destructive"' frontend/src/pages/authentication/{Login,Register,ForgotPassword,ExtensionAuth}.tsx returns 0 (hand-rolled error blocks replaced with Alert variant=destructive); the import was added in 4 sites (verify by inspection of the import line). 3. rg 'text-gray-(300|400)' frontend/src/pages/{Profile,ViewUser}.tsx frontend/src/pages/account/AccountAlerts.tsx frontend/src/pages/authentication/{Login,Register,ForgotPassword,ForgotPasswordConfirm,VerifyEmail,ExtensionAuth}.tsx returns 0. 4. rg '<div className="hidden md:block"></div>' frontend/src/pages/{Profile,ViewUser}.tsx frontend/src/pages/account/AccountAlerts.tsx returns 0. 5. The 12 S04 grep gates remain green. 6. cd frontend && npm run type-check && npm run lint && npm test -- --run all exit 0; specifically Login.test.tsx, Register.test.tsx, ForgotPassword.test.tsx, VerifyEmail.test.tsx, Profile.test.tsx, ViewUser.test.tsx, AccountAlerts.test.tsx all pass.
