---
estimated_steps: 4
estimated_files: 14
skills_used: []
---

# T02: Sweep Tier A (trivial public statics) + Tier B (auth pages) onto ui/* primitives

Smallest, lowest-risk surface — ~14 files using only Card/Alerts/LoadingSpinner/Input + the buttons/* family. Knocking them out first establishes the swap pattern (formal variants over bespoke className per MEM116; no layout-chrome rewrites per MEM107/MEM115) before the heavier sweeps in T03–T05.

Swap rules (apply uniformly across this task and T03–T05): import Card from '../../components/common/Card' → import { Card } from '../../components/ui/card'; import { ErrorAlert, ConfirmationAlert, SuccessAlert } from '../../components/common/Alerts' → from '../../components/ui/alert' (T01 named wrappers); import LoadingSpinner from '../../components/common/LoadingSpinner' → import Spinner from '../../components/ui/spinner' (rename calls; preserve size/text/inline props); import Input from '../../components/common/Input' → import { Input } from '../../components/ui/input' (note: legacy Input has label/error/helperText/leftIcon/rightIcon props that ui/Input does NOT expose — for those callsites, render the label/icon as JSX siblings of <Input> rather than props); ButtonStretch → <Button className='w-full'>; Button from buttons/Button → ui/Button (default variant); LinkButton → <Button asChild><Link to='...'>...</Link></Button> (shadcn convention).

Apply MEM116 — formal variants (destructive/secondary/link/ghost) over bespoke color className overrides; className overrides only for layout shape (h-auto, p-0, w-full, justify-start). Preserve every existing data-testid hook. Preserve existing useEffect orderings, cancellation flags, and submit handlers — this is a styling migration, not a behavior refactor.

Must-haves: every file in the file list no longer imports from components/common/ or components/buttons/; npm run type-check exits 0; existing vitests for these pages still pass; no console errors when rendering each page in dev.

## Inputs

- ``frontend/src/components/ui/card.tsx` — created in T01; destination for Card swap.`
- ``frontend/src/components/ui/alert.tsx` — created in T01; destination for Alerts swap (named wrappers preserve legacy call signature).`
- ``frontend/src/components/ui/spinner.tsx` — created in T01; destination for LoadingSpinner swap.`
- ``frontend/src/components/ui/input.tsx` — destination for legacy Input swap.`
- ``frontend/src/components/ui/button.tsx` — destination for ActionButton/SecondaryButton/StretchButton/Button/LinkButton swaps.`
- ``frontend/src/pages/About.tsx` — Tier A trivial.`
- ``frontend/src/pages/ContactUs.tsx` — Tier A trivial.`
- ``frontend/src/pages/Pricing.tsx` — Tier A trivial.`
- ``frontend/src/pages/Checkout.tsx` — Tier A trivial.`
- ``frontend/src/pages/Support.tsx` — Tier A trivial.`
- ``frontend/src/pages/BugReport.tsx` — uses Alerts + Button + Card + Input + LoadingSpinner.`
- ``frontend/src/pages/authentication/Login.tsx` — uses ButtonStretch + buttons/Button + Input + Alerts + LoadingSpinner.`
- ``frontend/src/pages/authentication/Register.tsx` — same pattern as Login.`
- ``frontend/src/pages/authentication/ForgotPassword.tsx` — Input + ButtonStretch + Alerts + LoadingSpinner.`
- ``frontend/src/pages/authentication/ForgotPasswordConfirm.tsx` — same.`
- ``frontend/src/pages/authentication/VerifyEmail.tsx` — Alerts + LoadingSpinner.`
- ``frontend/src/pages/authentication/VerifyEmailConfirm.tsx` — Alerts only.`
- ``frontend/src/pages/authentication/ExtensionAuth.tsx` — Alerts + LoadingSpinner + Input.`
- ``frontend/src/components/authentication/GoogleAuthFlow.tsx` — buttons/Button + Dialog + Input.`
- ``frontend/src/components/common/Card.tsx` — legacy import to remove.`
- ``frontend/src/components/common/Alerts.tsx` — legacy import to remove.`
- ``frontend/src/components/common/LoadingSpinner.tsx` — legacy import to remove.`
- ``frontend/src/components/common/Input.tsx` — legacy import to remove.`
- ``frontend/src/components/common/Dialog.tsx` — legacy import to remove (GoogleAuthFlow only).`
- ``frontend/src/components/buttons/Button.tsx` — legacy import to remove.`
- ``frontend/src/components/buttons/StretchButton.tsx` — legacy import to remove.`

## Expected Output

- ``frontend/src/pages/About.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/ContactUs.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/Pricing.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/Checkout.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/Support.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/BugReport.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/authentication/Login.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/authentication/Register.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/authentication/ForgotPassword.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/authentication/ForgotPasswordConfirm.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/authentication/VerifyEmail.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/authentication/VerifyEmailConfirm.tsx` — modified, no legacy imports.`
- ``frontend/src/pages/authentication/ExtensionAuth.tsx` — modified, no legacy imports.`
- ``frontend/src/components/authentication/GoogleAuthFlow.tsx` — modified, no legacy imports.`

## Verification

cd frontend && npm run type-check && npm test -- --run Login Register ForgotPassword VerifyEmail BugReport About ContactUs Pricing Checkout Support GoogleAuthFlow ExtensionAuth && ! grep -ln 'components/common\|components/buttons' src/pages/About.tsx src/pages/ContactUs.tsx src/pages/Pricing.tsx src/pages/Checkout.tsx src/pages/Support.tsx src/pages/BugReport.tsx src/pages/authentication/*.tsx src/components/authentication/GoogleAuthFlow.tsx
