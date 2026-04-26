---
estimated_steps: 3
estimated_files: 8
skills_used: []
---

# T01: Build missing ui/* primitives — Card, Alert (with named-export wrappers), Spinner, Pagination

Every subsequent page sweep is mechanical only if the destination primitives already exist. Card has the largest blast radius (~30 importers); Alert second (~30 importers, three named-export variants — ErrorAlert / ConfirmationAlert / SuccessAlert — required so the page sweep is import-rename-only); Pagination has non-trivial ellipsis logic that must be preserved verbatim; Spinner standardizes the legacy 6-size × 3-color × inline matrix onto a Loader2-backed wrapper so the page sweep can drop legacy LoadingSpinner imports without per-call inlining.

Do: Implement Card with shadcn idiom (Card / CardHeader / CardTitle / CardDescription / CardContent / CardFooter); export cardVariants cva() so consumers can compose; map the legacy variant='glass'/'elevated' to className overrides if any callsite still wants them, but default to the simple shadcn Card. Implement Alert with variant: 'default' | 'destructive' | 'success' AND export the three named wrappers (ErrorAlert({message}) → <Alert variant='destructive'>{message}</Alert>, ConfirmationAlert and SuccessAlert → variant='success') so the page sweep is a pure import-path rename. Implement Spinner as a thin Loader2-backed wrapper exposing size: 'xs'|'sm'|'base'|'md'|'lg'|'xl' (mapped to tailwind h-/w- classes preserving the 6-size scale) + optional text + optional inline; default export to keep legacy import shape. Implement Pagination preserving the ellipsis logic from common/Pagination.tsx VERBATIM — accept currentPage/totalPages/onPageChange/itemsPerPage/totalItems, render the 'Showing X – Y of Z' summary, Previous/Next disabled states, ellipsis-start / ellipsis-end keys; restyle button visuals onto ui/Button under the hood for consistency. Add a section per new primitive to _KitchenSink.tsx so components.spec.ts covers them in regression. Re-baseline components.spec.ts via `npm run test:e2e -- components.spec --update-snapshots` and commit the 3 refreshed PNGs.

Must-haves: card.tsx exports {Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, cardVariants}; alert.tsx exports {Alert, AlertTitle, AlertDescription, alertVariants, ErrorAlert, ConfirmationAlert, SuccessAlert}; spinner.tsx exports default Spinner with the 6-size scale; pagination.tsx exports default Pagination with the same prop shape as common/Pagination.tsx; _KitchenSink renders all four; type-check exits 0; components.spec passes at all 3 viewports.

## Inputs

- ``frontend/src/components/common/Card.tsx` — legacy Card to mirror API surface (variants and padding props); new ui/card uses shadcn idiom but should accept a `className` so callers can override.`
- ``frontend/src/components/common/Alerts.tsx` — three named exports (ErrorAlert / ConfirmationAlert / SuccessAlert) that the new alert.tsx must re-export with the same call signature (props: { message: string | null }).`
- ``frontend/src/components/common/LoadingSpinner.tsx` — 6-size × 3-color × inline/text matrix that the new spinner wrapper must support so the page sweep is mechanical.`
- ``frontend/src/components/common/Pagination.tsx` — ellipsis logic and prop shape (currentPage / totalPages / onPageChange / itemsPerPage / totalItems) to preserve verbatim.`
- ``frontend/src/components/ui/button.tsx` — buttonVariants source for Pagination's Previous/Next/page buttons.`
- ``frontend/src/components/ui/dialog.tsx` — pattern reference for shadcn-style primitives.`
- ``frontend/src/lib/utils.ts` — cn() helper used by every new primitive.`
- ``frontend/src/pages/_KitchenSink.tsx` — existing kitchen-sink to extend with one section per new primitive.`
- ``frontend/playwright.config.ts` — three-viewport projects + 0.2% threshold.`

## Expected Output

- ``frontend/src/components/ui/card.tsx` — new file exporting Card + subcomponents + cardVariants.`
- ``frontend/src/components/ui/alert.tsx` — new file exporting Alert + AlertTitle + AlertDescription + alertVariants + ErrorAlert + ConfirmationAlert + SuccessAlert (named wrappers preserving legacy call signature).`
- ``frontend/src/components/ui/spinner.tsx` — new file exporting Spinner (default) wrapping Loader2 with the 6-size scale.`
- ``frontend/src/components/ui/pagination.tsx` — new file exporting Pagination (default) with ellipsis logic preserved verbatim.`
- ``frontend/src/pages/_KitchenSink.tsx` — extended with one section per new primitive.`
- ``frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png` — refreshed baseline.`
- ``frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png` — refreshed baseline.`
- ``frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png` — refreshed baseline.`

## Verification

cd frontend && npm run type-check && npm run test:e2e -- components.spec
