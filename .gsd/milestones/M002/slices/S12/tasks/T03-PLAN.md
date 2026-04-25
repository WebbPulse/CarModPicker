---
estimated_steps: 4
estimated_files: 13
skills_used: []
---

# T03: Sweep Tier C1 (account/profile/user pages + profile inner components + global header) onto ui/* primitives

Profile is the densest single page in this tier (461 lines, 8 legacy primitives). The profile inner components (SecuritySettings, PasskeySettings, ConnectedAccountsSettings, ChangePasswordDialog, TwoFactorAuthDialog, SecuritySettingsDialog) all share the same legacy import set (ActionButton + SecondaryButton + Alerts + Input + LoadingSpinner + Dialog). Migrating Profile and its inner components together keeps the per-task context coherent — a Profile sweep that doesn't also migrate its inner forms would leave the page partly broken at runtime even though it compiles.

Same swap rules as T02. Specific notes: ActionButton → <Button> (default variant) or <Button variant='secondary'> per MEM116; SecondaryButton → <Button variant='secondary'>; legacy Dialog → ui/Dialog using the parent-owned-state pattern S09/T02 established in ViewBuildlist.tsx (open/onOpenChange API, sm:max-w-* sizing, no auto-close on confirm during async); legacy Alerts/LoadingSpinner/Input/Card swaps as in T02. Home.tsx uses LinkButton — replace with <Button asChild><Link to='...'>...</Link></Button>; Home/Profile may use StretchButton — replace with <Button className='w-full'>. Search.tsx is large (522 lines) but uses only Alerts + Card + LoadingSpinner + ActionButton. Header.tsx (layout/globalHeader) only imports LoadingSpinner — trivial.

Do NOT change behavior: useEffect orderings, cancellation flags, redirect logic, async-await patterns stay identical. Run page tests after each file (Profile.test.tsx, AccountAlerts.test.tsx exist; Search/Home/ViewUser may not).

Must-haves: every file in the file list no longer imports from components/common/ or components/buttons/; type-check exit 0; vitest green for Profile, AccountAlerts, ViewUser, UserCard tests if they exist.

## Inputs

- ``frontend/src/components/ui/card.tsx` — destination for Card swap (T01).`
- ``frontend/src/components/ui/alert.tsx` — destination for Alerts swap (T01).`
- ``frontend/src/components/ui/spinner.tsx` — destination for LoadingSpinner swap (T01).`
- ``frontend/src/components/ui/input.tsx` — destination for Input swap.`
- ``frontend/src/components/ui/button.tsx` — destination for button-family swaps.`
- ``frontend/src/components/ui/dialog.tsx` — destination for Dialog swap.`
- ``frontend/src/pages/builder/ViewBuildlist.tsx` — S09 reference for parent-owned Dialog open/onOpenChange pattern.`
- ``frontend/src/pages/Profile.tsx` — densest single page in this tier.`
- ``frontend/src/pages/Home.tsx` — uses LinkButton + Alerts + Card + ImageWithPlaceholder + LoadingSpinner.`
- ``frontend/src/pages/Search.tsx` — uses ActionButton + Alerts + Card + LoadingSpinner.`
- ``frontend/src/pages/ViewUser.tsx` — uses Alerts + Card + CardInfoItem + LoadingSpinner.`
- ``frontend/src/pages/account/AccountAlerts.tsx` — uses Alerts + Card + LoadingSpinner; preserve MEM097/MEM102 cancelled-flag pattern.`
- ``frontend/src/components/users/UserCard.tsx` — Card only.`
- ``frontend/src/components/profile/SecuritySettings.tsx` — ActionButton + SecondaryButton + Alerts + Input + LoadingSpinner.`
- ``frontend/src/components/profile/PasskeySettings.tsx` — same set.`
- ``frontend/src/components/profile/ConnectedAccountsSettings.tsx` — SecondaryButton + Alerts + LoadingSpinner.`
- ``frontend/src/components/profile/ChangePasswordDialog.tsx` — Dialog + Input + ButtonStretch + SecondaryButton + Alerts + LoadingSpinner.`
- ``frontend/src/components/profile/TwoFactorAuthDialog.tsx` — Dialog + Input + ActionButton + SecondaryButton + Alerts.`
- ``frontend/src/components/profile/SecuritySettingsDialog.tsx` — Dialog + Input + ActionButton + SecondaryButton + Alerts + LoadingSpinner.`
- ``frontend/src/components/layout/globalHeader/Header.tsx` — LoadingSpinner only.`
- ``frontend/src/components/buttons/LinkButton.tsx` — legacy import (Home).`
- ``frontend/src/components/buttons/ActionButton.tsx` — legacy import.`
- ``frontend/src/components/buttons/SecondaryButton.tsx` — legacy import.`
- ``frontend/src/components/buttons/StretchButton.tsx` — legacy import.`

## Expected Output

- ``frontend/src/pages/Profile.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/Home.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/Search.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/ViewUser.tsx` — modified, CardInfoItem call replaced with inline JSX (CardInfoItem itself relocates in T05).`
- ``frontend/src/pages/account/AccountAlerts.tsx` — modified, no legacy imports.`
- ``frontend/src/components/users/UserCard.tsx` — modified, no legacy imports.`
- ``frontend/src/components/profile/SecuritySettings.tsx` — modified, no legacy imports.`
- ``frontend/src/components/profile/PasskeySettings.tsx` — modified, no legacy imports.`
- ``frontend/src/components/profile/ConnectedAccountsSettings.tsx` — modified, no legacy imports.`
- ``frontend/src/components/profile/ChangePasswordDialog.tsx` — modified, no legacy imports.`
- ``frontend/src/components/profile/TwoFactorAuthDialog.tsx` — modified, no legacy imports.`
- ``frontend/src/components/profile/SecuritySettingsDialog.tsx` — modified, no legacy imports.`
- ``frontend/src/components/layout/globalHeader/Header.tsx` — modified, no legacy imports.`

## Verification

cd frontend && npm run type-check && npm test -- --run Profile Home Search ViewUser AccountAlerts UserCard SecuritySettings PasskeySettings ConnectedAccountsSettings ChangePasswordDialog TwoFactorAuthDialog SecuritySettingsDialog Header && ! grep -ln 'components/common\|components/buttons' src/pages/Profile.tsx src/pages/Home.tsx src/pages/Search.tsx src/pages/ViewUser.tsx src/pages/account/AccountAlerts.tsx src/components/users/UserCard.tsx src/components/profile/*.tsx src/components/layout/globalHeader/Header.tsx
