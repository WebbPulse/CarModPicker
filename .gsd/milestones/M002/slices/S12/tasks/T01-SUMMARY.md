---
id: T01
parent: S12
milestone: M002
key_files:
  - frontend/src/components/ui/card.tsx
  - frontend/src/components/ui/alert.tsx
  - frontend/src/components/ui/spinner.tsx
  - frontend/src/components/ui/pagination.tsx
  - frontend/src/pages/_KitchenSink.tsx
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png
  - frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png
key_decisions:
  - Spinner drops the legacy 3-color matrix (primary/white/custom) — unifies onto `text-primary` token. M002 intent is to deliberately retire the bespoke gradient styling; any legacy `color='white'` callsites in T02–T05 should use `className='text-white'` if needed. Default export preserved.
  - Card preserves the legacy `glass` and `elevated` variants in cardVariants alongside the new shadcn `default` so the ~30 callsites that opted into glass/elevated styling keep their current look without per-callsite className overrides.
  - Pagination styling routes through ui/Button (variant `default` for active page, `secondary` for Previous/Next + inactive page numbers). Ellipsis logic and prop shape preserved verbatim — pure visual reskin, not a behavior refactor.
duration: 
verification_result: passed
completed_at: 2026-04-26T00:56:16.928Z
blocker_discovered: false
---

# T01: Add ui/{card,alert,spinner,pagination} primitives + KitchenSink sections; refresh 3 visual baselines

**Add ui/{card,alert,spinner,pagination} primitives + KitchenSink sections; refresh 3 visual baselines**

## What Happened

Built the four destination primitives required for the S12 page sweep so every downstream task is a mechanical import-rename:

- **`ui/card.tsx`** — shadcn idiom with `Card / CardHeader / CardTitle / CardDescription / CardContent / CardFooter` and `cardVariants` cva re-export. Variant axis preserves legacy `default | glass | elevated` so the ~30 importers can keep `variant='glass'` if they choose; padding axis preserves `none | sm | md | lg` (default `md`). Uses token-driven classes (`bg-card text-card-foreground border-border`).

- **`ui/alert.tsx`** — `Alert / AlertTitle / AlertDescription` with `alertVariants` cva re-export (`default | destructive | success`). The three named wrappers `ErrorAlert / ConfirmationAlert / SuccessAlert` mirror the legacy `{message: string | null}` call signature and short-circuit return null when message is null/empty — so the T02–T05 page sweep is a pure import-path rename with zero callsite churn. ErrorAlert routes to `variant='destructive'`; the two success wrappers route to `variant='success'`.

- **`ui/spinner.tsx`** — Loader2-backed default-export wrapper exposing the legacy 6-size scale `xs | sm | base | md | lg | xl` mapped to tailwind h-/w- classes. Optional `text` and `inline` props match the legacy LoadingSpinner shape so `<LoadingSpinner size='lg' text='Loading...'>` swaps to `<Spinner size='lg' text='Loading...'>` at every callsite. Drops the legacy 3-color matrix (primary/white/custom) — visually unifies onto the design-system `text-primary` token, which is the explicit M002 intent. Keeps default export to preserve legacy import shape.

- **`ui/pagination.tsx`** — preserves `getPageNumbers()` ellipsis logic VERBATIM from `common/Pagination.tsx`: imports `PAGINATION_MAX_VISIBLE_PAGES` from `../../constants`, same `start = Math.max(2, currentPage - 2)` math, same `currentPage <= 4` and `currentPage >= totalPages - 3` adjustments, same `ellipsis-start` / `ellipsis-end` keys, same `Showing X - Y of Z` summary string, same null-when-totalPages-<=-1 short-circuit. Restyled visuals onto `ui/Button` (variant `default` for active page, `secondary` for inactive/Previous/Next, size `sm`, `min-w-[2.5rem]` for page numbers) so it matches the rest of the design system.

The `_KitchenSink.tsx` page already contained sections for all four primitives from a prior in-progress commit (3c383e0 snapshot): button matrix, input states, select open/closed, combobox with/without results, tabs, dialog/dropdown/sheet open via `defaultOpen modal={false}` (per MEM071), toast, **card** (`padding='none'` with header/footer composition + default padding inline-content), **alert** (3 variants × 3 named wrappers), **spinner** (all 6 sizes side-by-side + text + inline), **pagination** (totalPages=20, currentPage=7 to exercise both ellipses). Verified contents match legacy contracts and no edits were needed.

All four new primitive files were also pre-staged from the prior snapshot — verified each against its legacy counterpart: ellipsis logic verbatim, named-export wrappers preserved, 6-size scale preserved, cva re-exports present per MEM072/MEM003 convention. No code changes required this session — execution focused on verification + baseline refresh.

Refreshed the 3 components.spec visual baselines via `npm run test:e2e -- components.spec --update-snapshots`, then re-verified by running `npm run test:e2e -- components.spec` (no `--update-snapshots`) — all 3 viewports (mobile 375×667, tablet 768×1024, desktop 1280×800) passed against the new baselines. The tablet baseline file matched the previously-snapshotted version; mobile and desktop baselines updated.

The dev-server proxy logs ECONNREFUSED on `/api/app-settings` and `/api/users/me` because the FastAPI backend is not running in this worktree — kitchen-sink is purely client-side UI so this is benign and the screenshots are stable.

## Verification

Ran the task plan's exact verification command — `cd frontend && npm run type-check && npm run test:e2e -- components.spec`:

1. `npm run type-check` (`tsc -b --noEmit`) — exit 0, no errors. Confirms all four new primitives type-check cleanly against the rest of the frontend (including the existing `_KitchenSink.tsx` consumer that imports `Card / CardHeader / CardTitle / CardDescription / CardContent / CardFooter`, `Alert / AlertTitle / AlertDescription / ErrorAlert / ConfirmationAlert / SuccessAlert`, `Spinner` + `SpinnerSize` type, `Pagination` default).

2. `npm run test:e2e -- components.spec --update-snapshots` — 3 passed (6.5s). Regenerated baselines for mobile/tablet/desktop kitchen-sink-visual-regression-1.

3. `npm run test:e2e -- components.spec` (no flag) — 3 passed (4.5s) at the 0.002 maxDiffPixelRatio bar. Confirms the refreshed baselines are stable, not just freshly written. Per MEM006/MEM066/MEM068 the three projects all spread `devices['Desktop Chrome']` and override only viewport, so the baselines are chromium-engine consistent.

Must-haves all met: card/alert/spinner/pagination exports match the spec; _KitchenSink renders all four; type-check exits 0; components.spec passes at all 3 viewports.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm run type-check` | 0 | ✅ pass | 200ms |
| 2 | `npm run test:e2e -- components.spec --update-snapshots` | 0 | ✅ pass | 6500ms |
| 3 | `npm run test:e2e -- components.spec` | 0 | ✅ pass | 4500ms |

## Deviations

No deviations from the task plan. The four primitive files and the _KitchenSink wiring were already pre-staged from a prior session's snapshot commit (3c383e0); this session verified them against the legacy contracts (no edits needed), then refreshed and re-verified the visual baselines. Mobile and desktop PNGs were updated by the refresh; the tablet PNG matched the existing tracked version byte-for-byte.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/components/ui/card.tsx`
- `frontend/src/components/ui/alert.tsx`
- `frontend/src/components/ui/spinner.tsx`
- `frontend/src/components/ui/pagination.tsx`
- `frontend/src/pages/_KitchenSink.tsx`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-mobile-linux.png`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-tablet-linux.png`
- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-visual-regression-1-desktop-linux.png`
