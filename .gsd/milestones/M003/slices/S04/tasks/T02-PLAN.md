---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T02: Migrate 8 `btn-primary`/`btn-secondary` consumer sites to `<Button>` primitive

Migrate the 8 surviving `btn-*` consumer sites to the existing `<Button>` primitive at `frontend/src/components/ui/button.tsx`. Sites confirmed by `rg -n 'btn-primary|btn-secondary|btn-outline' frontend/src/{components,pages}/`: NotFound.tsx:19 (`btn-primary`), Checkout.tsx:130 (`btn-primary`, currently overridden with `px-5 py-3 rounded-xl text-sm font-semibold opacity-50 cursor-not-allowed inline-flex items-center gap-2` — verify Button's `disabled` state matches before swap, otherwise pass `disabled` prop and drop the override classes), Header.tsx:93 (desktop login CTA, `btn-primary px-4 py-2 rounded-xl text-sm font-medium`), Header.tsx:188 (mobile login CTA, same shape), RouteGroupBoundary.tsx:69 (error fallback `btn-primary`), RouteGroupBoundary.tsx:76 (error fallback `btn-secondary`), ChromeExtensionPromo.tsx:114 (`btn-primary` install CTA), SubscriptionPromo.tsx:75 (`btn-primary` upgrade CTA). For each site: replace with `<Button variant="default">` (for `btn-primary`) or `<Button variant="secondary">` / `variant="outline"` (for `btn-secondary` / `btn-outline`). Add `import { Button } from '@/components/ui/button'` if not present. Keep onClick / asChild / size / className overrides intact. The Button primitive's variants already encode the M002 design-system equivalents — drop legacy `px-*`/`py-*`/`rounded-xl`/`text-sm font-medium` overrides only when they match the variant default (size=default = py-2 px-4 text-sm; check `frontend/src/components/ui/button.tsx` cva config before deciding). Single atomic commit — narrative explains the consumer-migration step (per R053).

## Inputs

- `frontend/src/pages/NotFound.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/routes/RouteGroupBoundary.tsx`
- `frontend/src/components/shell/ChromeExtensionPromo.tsx`
- `frontend/src/components/shell/SubscriptionPromo.tsx`
- `frontend/src/components/ui/button.tsx`

## Expected Output

- `frontend/src/pages/NotFound.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/routes/RouteGroupBoundary.tsx`
- `frontend/src/components/shell/ChromeExtensionPromo.tsx`
- `frontend/src/components/shell/SubscriptionPromo.tsx`

## Verification

cd frontend && rg 'btn-primary|btn-secondary|btn-outline' src/{components,pages,contexts,hooks,api,lib,__tests__}/; test $? -eq 1 && npm run type-check && npm run lint && npm test -- --run
