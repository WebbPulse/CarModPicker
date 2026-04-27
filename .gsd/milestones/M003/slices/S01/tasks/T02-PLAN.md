---
estimated_steps: 19
estimated_files: 3
skills_used: []
---

# T02: Global swap: neutral palette utilities → semantic tokens (text/bg/border/ring on all surfaces)

Bulk semantic swap of every raw `*-neutral-[0-9]+(/[0-9]+)?` utility across all 68 consumer files in `frontend/src/`. The neutrals are the highest-volume cohort (~250+ occurrences across `text-neutral-{100,200,300,400,500,600,900}`, `bg-neutral-{700,800,900,950}`, `border-neutral-{500,600,700}`).

Mapping table (apply file-by-file with per-file judgment for the 300/200 cases):
- `text-neutral-400` → `text-muted-foreground` (default — secondary body text)
- `text-neutral-500` → `text-muted-foreground` (placeholder/tier-3 label)
- `text-neutral-600` → `text-muted-foreground` (very subtle label)
- `text-neutral-300` → `text-foreground` (default; flip to `text-muted-foreground` only when surrounding code shows a tier-2 label — e.g. `text-neutral-400 hover:text-neutral-300` should become `text-muted-foreground hover:text-foreground`)
- `text-neutral-200` → `text-foreground`
- `text-neutral-100` → `text-foreground`
- `text-neutral-900` → `text-background` (rare — usually inverted-on-light contexts; check each occurrence)
- `bg-neutral-950` → `bg-background`
- `bg-neutral-900` → `bg-background` (page surface) or `bg-card` (raised surface) — use surrounding context
- `bg-neutral-800` → `bg-card`
- `bg-neutral-700` → `bg-muted` or `bg-card` — usually muted (slightly raised inside a card)
- `border-neutral-700` → `border-border`
- `border-neutral-600` → `border-border`
- `border-neutral-500` → `border-border`
- Alpha modifiers: `text-neutral-400/80` → `text-muted-foreground/80` (alpha modifier composes through semantic tokens because `--color-muted-foreground: hsl(var(--muted-foreground))`)

Work by-file in alphabetical order across `frontend/src/`. After each file is migrated, re-run the file's vitest spec (if one exists) to catch any test asserting on raw class names. After all neutrals migrated, run `rg '(text|bg|border|ring)-neutral-[0-9]' frontend/src/` and confirm 0 hits.

Do NOT touch `frontend/src/index.css` (legacy block survives until S04). Do NOT touch `frontend/src/styles/tokens.css` again. Do NOT touch decorative purples or default Tailwind v4 colors (orange, sky, etc.).

## Inputs

- `frontend/src/styles/tokens.css`
- `frontend/src/components/ui/alert.tsx`

## Expected Output

- `frontend/src/components/ads/AdBanner.tsx`
- `frontend/src/components/auth/AuthRedirectLink.tsx`
- `frontend/src/components/authentication/GoogleAuthFlow.tsx`
- `frontend/src/components/buildListParts/BuildListPartList.tsx`
- `frontend/src/components/buildLists/BuildListItem.tsx`
- `frontend/src/components/cars/CarListItem.tsx`
- `frontend/src/components/forms/FormField.tsx`
- `frontend/src/components/layout/globalFooter/Footer.tsx`
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/parts/PartList.tsx`
- `frontend/src/components/profile/SocialLinks.tsx`
- `frontend/src/components/shell/PromoBanner.tsx`
- `frontend/src/components/users/UserCard.tsx`
- `frontend/src/pages/About.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/pages/PrivacyPolicy.tsx`
- `frontend/src/pages/Profile.tsx`
- `frontend/src/pages/Search.tsx`
- `frontend/src/pages/Support.tsx`
- `frontend/src/pages/TermsOfService.tsx`
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
- `frontend/src/pages/buildLists/ViewBuildLog.tsx`

## Verification

cd frontend && rg -c '(text|bg|border|ring)-neutral-[0-9]' src/ ; test $(rg -c '(text|bg|border|ring)-neutral-[0-9]' src/ 2>/dev/null | wc -l) -eq 0 && npm run type-check && npm test -- --run
