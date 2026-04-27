---
id: T02
parent: S04
milestone: M003
key_files:
  - frontend/src/pages/NotFound.tsx
  - frontend/src/pages/Checkout.tsx
  - frontend/src/components/layout/globalHeader/Header.tsx
  - frontend/src/components/routes/RouteGroupBoundary.tsx
  - frontend/src/components/shell/ChromeExtensionPromo.tsx
  - frontend/src/components/shell/SubscriptionPromo.tsx
key_decisions:
  - Used variant='default' for all btn-primary sites and variant='secondary' for the single btn-secondary site (RouteGroupBoundary Go Home), per MEM116/MEM132 — formal cva variants over bespoke className overrides
  - For the 5 sites originally rendering as <Link> or <a>, used <Button asChild>{anchor}</Button> to preserve routing/anchor semantics rather than swapping the underlying element
  - Verified Button's base cva already includes disabled:opacity-50 disabled:pointer-events-none, so the Checkout disabled CTA dropped its explicit opacity-50 cursor-not-allowed override and relies solely on the `disabled` prop
  - Preserved `rounded-xl` className overrides on Header Register CTAs and Checkout disabled CTA (Button defaults to rounded-md) — shape override per MEM116; collapsed `rounded-lg` cases to Button default since visual delta is acceptable
  - Dropped redundant `px-4 py-2 text-sm font-medium inline-flex items-center gap-2` overrides everywhere they matched Button's size=default + base styles per MEM116
duration: 
verification_result: passed
completed_at: 2026-04-26T22:58:31.239Z
blocker_discovered: false
---

# T02: Migrate 8 btn-primary/btn-secondary consumer sites to ui/Button primitive (variant=default/secondary, asChild for Link/anchor)

**Migrate 8 btn-primary/btn-secondary consumer sites to ui/Button primitive (variant=default/secondary, asChild for Link/anchor)**

## What Happened

Replaced the 8 surviving legacy `btn-*` consumer sites with the ui/Button primitive at frontend/src/components/ui/button.tsx so the S04 deletion of `.btn-primary` / `.btn-secondary` / `.btn-outline` from index.css will leave zero unresolved references. Per MEM116/MEM132, used formal cva variants over bespoke className overrides — `variant="default"` for btn-primary (its `bg-primary text-primary-foreground hover:bg-primary/90` is the M002-token equivalent of the legacy gradient/box-shadow chrome) and `variant="secondary"` for btn-secondary. For Link/anchor consumers used `<Button asChild>` to preserve routing semantics.

Consumer-by-consumer:
- NotFound.tsx:19 — `<a href="/" className="btn-primary inline-flex items-center">` → `<Button asChild><a href="/">Go Home</a></Button>` (Button base already has `inline-flex items-center justify-center`).
- Checkout.tsx:130 — disabled subscribe CTA. Verified Button's base styles include `disabled:pointer-events-none disabled:opacity-50` so `disabled` prop alone reproduces the legacy `opacity-50 cursor-not-allowed` behavior; dropped the override classes. Kept `rounded-xl` since Button defaults to `rounded-md` (shape override per MEM116). Dropped `px-5 py-3` and `text-sm font-semibold` — Button's default size already gives `h-10 px-4 py-2` and `text-sm font-medium` which is the closer M002 visual standard.
- Header.tsx:93 (desktop Register CTA) — `<Link className="btn-primary px-4 py-2 rounded-xl text-sm font-medium">` → `<Button asChild className="rounded-xl"><Link to="/register">…</Link></Button>` (px-4 py-2 redundant with size=default; text-sm font-medium is base; rounded-xl preserved as shape override).
- Header.tsx:188 (mobile Register CTA) — same swap with `className="w-full rounded-xl"` to preserve the mobile full-width layout. The legacy `block ... text-center` is implicit in `<Button>`'s `inline-flex justify-center` once stretched to `w-full`.
- RouteGroupBoundary.tsx:69 — Retry button → `<Button>` (default variant).
- RouteGroupBoundary.tsx:76 — Go Home button → `<Button variant="secondary">`.
- ChromeExtensionPromo.tsx:114 — install CTA → `<Button>`. The legacy `px-4 py-2 rounded-lg text-sm font-medium inline-flex items-center gap-2` collapses entirely into Button defaults; dropped wholesale (rounded-lg → rounded-md is acceptable per MEM116 base-shape parity).
- SubscriptionPromo.tsx:75 — upgrade CTA `<Link>` → `<Button asChild><Link>…</Link></Button>` with same defaulting rationale.

All 6 modified files added a `Button` import from the appropriate relative path. No legacy class strings remain in consumer dirs after this task; the next task can hard-delete the `.btn-*` rules from index.css without breaking any consumer.

## Verification

Ran the slice-plan canonical verification chain: (1) `rg 'btn-primary|btn-secondary|btn-outline' src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero matches — gate passes); (2) `npm run type-check` → exit 0 (tsc -b --noEmit clean); (3) `npm run lint` → exit 0 (eslint clean); (4) `npm test -- --run` → 594/594 passed across 90 test files in 6.14s, including the 3 RouteGroupBoundary fallback tests which directly exercise the Retry/Go-Home button swap path.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg 'btn-primary|btn-secondary|btn-outline' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | pass | 80ms |
| 2 | `npm run type-check` | 0 | pass | 9000ms |
| 3 | `npm run lint` | 0 | pass | 5000ms |
| 4 | `npm test -- --run` | 0 | pass | 6140ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/NotFound.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/routes/RouteGroupBoundary.tsx`
- `frontend/src/components/shell/ChromeExtensionPromo.tsx`
- `frontend/src/components/shell/SubscriptionPromo.tsx`
