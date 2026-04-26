---
estimated_steps: 32
estimated_files: 2
skills_used: []
---

# T04: Global swap: status palette utilities → success/warning/destructive/info semantic tokens

Bulk semantic swap of every raw `*-emerald-`, `*-amber-`, `*-rose-`, `*-indigo-` utility plus the legacy `text-accent-emerald|amber|rose|purple` utilities across all consumer files. Depends on T01 tokens (`--success`, `--warning`, `--info`).

Mapping table:
- All `text-emerald-{200,300,400,500}` → `text-success`
- All `bg-emerald-{400,500,600,700,900}` → `bg-success`; `bg-emerald-500/10` → `bg-success/10`; `bg-emerald-900/40` → `bg-success/40`
- All `border-emerald-{500,700}` → `border-success`; alpha modifiers preserved (`border-emerald-700/60` → `border-success/60`)
- All `ring-emerald-` → `ring-success`
- All `from-emerald-` / `to-emerald-` / `via-emerald-` → `from-success` / `to-success` / `via-success`

- All `text-amber-{200,300,400}` → `text-warning`
- All `bg-amber-` → `bg-warning` (alpha preserved)
- All `border-amber-` → `border-warning`
- All `ring-amber-` → `ring-warning`
- All `from-amber-` / `to-amber-` / `shadow-amber-` → `from-warning` / `to-warning` / `shadow-warning` (or inline boxShadow style if shadow doesn't resolve — same caveat as T03)

- All `text-rose-` → `text-destructive`
- All `bg-rose-` → `bg-destructive` (with alpha)
- All `border-rose-` → `border-destructive`

- All `text-indigo-{300,400,500}` → `text-info`
- All `bg-indigo-{500,600,700}` → `bg-info` (use `/N` alpha for hover states)
- All `border-indigo-{500}` → `border-info` (alpha preserved: `border-indigo-500/50` → `border-info/50`)
- All `ring-indigo-` → `ring-info`

- `text-accent-emerald` (1 occurrence — `frontend/src/components/parts/PartList.tsx` per research) → `text-success`. The other `text-accent-*` utilities (`amber`, `rose`, `purple`) have 0 occurrences — confirm with `rg 'text-accent-' frontend/src/`.

- **Purple decorative gradients are NOT in scope** — `purple-500/10`, `from-purple-500`, `to-purple-500` resolve via Tailwind v4's default palette (NOT via the legacy `@theme` block, which only defines `accent-purple`, not `purple-*`). Leave them; they will surface in S04 only if `@theme` deletion breaks them (it won't — Tailwind v4 default palette is independent).
- **Purple role badge** in `frontend/src/pages/admin/UserManagement.tsx` (`bg-purple-600 text-purple-100` for superuser badge) — leave as-is in S01 (Tailwind v4 default palette resolves it). Flag for owner judgment in S05 polish; not S01 scope per research recommendation.

After swap: `rg -c '(text|bg|border|ring|from|to|via|shadow)-(emerald|amber|rose|indigo)-[0-9]' frontend/src/` returns 0. `rg 'text-accent-(emerald|amber|rose|purple)' frontend/src/` returns 0. Re-run vitest.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| T01 tokens (`--success`, `--warning`, `--info`) | If a token is missing, Tailwind utility `bg-success` resolves to no CSS — page renders without color. Mitigation: verify T01 commit landed via `grep -q 'success-foreground' frontend/src/styles/tokens.css` before starting. | N/A | N/A |
| `vite build` | If swap introduces invalid Tailwind class (typo), build fails fast. | N/A | N/A |

## Negative Tests

- After swap, navigate to `/admin/extraction-health` (heavy emerald/amber/rose status colors) and confirm visual parity with the pre-swap baseline — failure-rate badges should still be color-coded.
- Confirm `<Alert variant="success">` consumers still render correctly (T01 already swapped the variant; confirm no regression here).
- Run `frontend/e2e/components.spec.ts` (kitchen sink) at desktop only as a smoke check that no primitive surface broke — full 3-viewport baseline refresh is T05.

## Inputs

- `frontend/src/styles/tokens.css`
- `frontend/src/components/ui/alert.tsx`

## Expected Output

- `frontend/src/components/buildListParts/BuildListPartList.tsx`
- `frontend/src/components/buildListParts/CreateBuildListPartForm.tsx`
- `frontend/src/components/buildListParts/EditBuildListPartForm.tsx`
- `frontend/src/components/buildLists/BuildListItem.tsx`
- `frontend/src/components/buildLists/CreateBuildListForm.tsx`
- `frontend/src/components/buildLists/EditBuildListForm.tsx`
- `frontend/src/components/cars/CarListItem.tsx`
- `frontend/src/components/cars/CarModelMultiSelect.tsx`
- `frontend/src/components/filters/VehicleFilterSection.tsx`
- `frontend/src/components/parts/CreatePartForm.tsx`
- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/parts/PartList.tsx`
- `frontend/src/components/profile/SocialLinks.tsx`
- `frontend/src/components/users/UserCard.tsx`
- `frontend/src/components/auth/AuthRedirectLink.tsx`
- `frontend/src/pages/Profile.tsx`
- `frontend/src/pages/Search.tsx`
- `frontend/src/pages/admin/CrawlerAdmin.tsx`
- `frontend/src/pages/builder/ViewBuildlist.tsx`
- `frontend/src/pages/builder/ViewPart.tsx`
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx`
- `frontend/src/pages/buildLists/ViewBuildLog.tsx`

## Verification

cd frontend && test $(rg -c '(text|bg|border|ring|from|to|via)-(emerald|amber|rose|indigo)-[0-9]' src/ 2>/dev/null | wc -l) -eq 0 && test $(rg -c 'text-accent-(emerald|amber|rose|purple)' src/ 2>/dev/null | wc -l) -eq 0 && npm run type-check && npm test -- --run
