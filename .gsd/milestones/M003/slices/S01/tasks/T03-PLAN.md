---
estimated_steps: 12
estimated_files: 3
skills_used: []
---

# T03: Global swap: primary palette utilities → semantic tokens

Bulk semantic swap of every raw `*-primary-[0-9]+(/[0-9]+)?` utility across all consumer files. ~120+ occurrences across `text-primary-{200,300,400}`, `bg-primary-{500,600,700}`, `border-primary-{400,500}`, `ring-primary-500`, `from-primary-500`, `to-primary-600`, `shadow-primary-500/N`.

Mapping table (Tailwind v4's `/N` alpha modifier composes with semantic tokens because `--color-primary` resolves to `hsl(var(--primary))`):
- `text-primary-400` / `text-primary-300` / `text-primary-200` → `text-primary` (let the dark palette tone handle differentiation; if a hover state needed `primary-300`-then-`primary-200`, collapse to `text-primary hover:text-primary/90`)
- `bg-primary-500` → `bg-primary`
- `bg-primary-600` → `bg-primary` (hover/active states use opacity: `hover:bg-primary/90`)
- `bg-primary-700` → `bg-primary/80` (deepest active state)
- `bg-primary-500/10` → `bg-primary/10`, `bg-primary-500/20` → `bg-primary/20`, `bg-primary-500/25` → `bg-primary/25` (alpha modifier preserves)
- `border-primary-500` → `border-primary`, `border-primary-400` → `border-primary`
- `ring-primary-500` → `ring-primary` (also `ring-primary-500/20`, `/30`, `/50` preserve alpha)
- `from-primary-500` / `to-primary-600` / `via-primary-500` → `from-primary` / `to-primary` / `via-primary` (gradient utilities compose with `--color-primary`)
- `shadow-primary-500/10` and `shadow-primary-500/25` — Tailwind v4 does NOT auto-derive `shadow-primary` from `--color-primary` (shadow utility is bespoke). Two options: (a) inline the shadow as a custom utility class via `style={{ boxShadow: '0 0 20px hsl(var(--primary) / 0.25)' }}` or (b) keep as raw decorative `shadow-` and flag for S04. **Recommended: convert to inline `style` boxShadow** so the migration is complete; if there are >5 occurrences and they all live on Home/decorative pages, it is acceptable to leave them and add a comment `// FIXME(S04): shadow-primary token` so the S04 hard-delete catches it.

After swap: `rg -c '(text|bg|border|ring|from|to|via)-primary-[0-9]' frontend/src/` returns 0. Re-run vitest after sweep.

## Inputs

- `frontend/src/styles/tokens.css`

## Expected Output

- `frontend/src/components/buildLists/BuildListItem.tsx`
- `frontend/src/components/buildLists/CreateBuildListForm.tsx`
- `frontend/src/components/buildLists/EditBuildListForm.tsx`
- `frontend/src/components/forms/FormField.tsx`
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/parts/CreatePartForm.tsx`
- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/parts/PartList.tsx`
- `frontend/src/components/profile/EditProfileForm.tsx`
- `frontend/src/components/shell/PromoBanner.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/pages/Profile.tsx`
- `frontend/src/pages/Search.tsx`
- `frontend/src/pages/Support.tsx`
- `frontend/src/pages/admin/CrawlerAdmin.tsx`
- `frontend/src/pages/admin/PartsCuration.tsx`
- `frontend/src/pages/admin/SystemAdmin.tsx`
- `frontend/src/pages/admin/SystemStatistics.tsx`
- `frontend/src/pages/admin/UserManagement.tsx`
- `frontend/src/pages/authentication/Login.tsx`
- `frontend/src/pages/authentication/Register.tsx`
- `frontend/src/pages/builder/ViewBuildlist.tsx`
- `frontend/src/pages/builder/ViewPart.tsx`
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx`

## Verification

cd frontend && test $(rg -c '(text|bg|border|ring|from|to|via)-primary-[0-9]' src/ 2>/dev/null | wc -l) -eq 0 && npm run type-check && npm test -- --run
