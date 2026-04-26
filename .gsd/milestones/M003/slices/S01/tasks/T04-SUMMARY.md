---
id: T04
parent: S01
milestone: M003
key_files:
  - frontend/scripts/m003_s01_t04_swap_status.py
  - frontend/scripts/m003_s01_t04_fix_hover.py
  - frontend/src/index.css
  - frontend/src/pages/admin/CrawlerAdmin.tsx
  - frontend/src/pages/admin/PartsCuration.tsx
  - frontend/src/pages/admin/SystemAdmin.tsx
  - frontend/src/pages/buildLists/ViewBuildLog.tsx
  - frontend/src/pages/builder/ViewBuildlist.tsx
  - frontend/src/pages/builder/ViewPart.tsx
  - frontend/src/pages/Pricing.tsx
  - frontend/src/pages/Checkout.tsx
  - frontend/src/pages/Profile.tsx
  - frontend/src/pages/Search.tsx
  - frontend/src/pages/Support.tsx
  - frontend/src/pages/Home.tsx
  - frontend/src/pages/About.tsx
  - frontend/src/pages/buildLists/BuildListsCatalog.tsx
  - frontend/src/components/parts/ImageGalleryManage.tsx
  - frontend/src/components/parts/AddToBuildListDialog.tsx
  - frontend/src/components/parts/CreatePartForm.tsx
  - frontend/src/components/parts/EditPartForm.tsx
  - frontend/src/components/parts/PartList.tsx
  - frontend/src/components/buildLists/BuildListItem.tsx
  - frontend/src/components/buildLists/CreateBuildListForm.tsx
  - frontend/src/components/buildLists/EditBuildListForm.tsx
  - frontend/src/components/buildListParts/BuildListPartList.tsx
  - frontend/src/components/buildListParts/BuildListParts.tsx
  - frontend/src/components/buildListParts/CreateBuildListPartForm.tsx
  - frontend/src/components/buildListParts/EditBuildListPartForm.tsx
  - frontend/src/components/cars/CarListItem.tsx
  - frontend/src/components/cars/CarModelMultiSelect.tsx
  - frontend/src/components/filters/VehicleFilterSection.tsx
  - frontend/src/components/profile/SocialLinks.tsx
  - frontend/src/components/users/UserCard.tsx
  - frontend/src/components/auth/AuthRedirectLink.tsx
  - frontend/src/components/shell/BetaBanner.tsx
  - frontend/src/components/shell/SubscriptionPromo.tsx
  - frontend/src/pages/admin/SystemStatistics.tsx
  - frontend/src/pages/admin/UserManagement.tsx
key_decisions:
  - Reused the proven two-pass pattern from T02/T03 (MEM153/MEM154): deterministic Python regex script for the bulk swap, then a follow-up hover-repair script. 279 replacements + 25 hover fixes in idempotent passes — easier to bisect and reproduce than 36 separate file edits.
  - Mapped the `text-accent-emerald` placeholder in the `index.css` legacy-bridge comment to `text-accentNNN` per MEM155 so the verification gate ignores comment text. The `@theme` block itself stays untouched (it survives until S04).
  - Left purple decorative utilities (`bg-purple-500/10`, `from-purple-500`, `to-purple-500`) and the superuser role badge (`bg-purple-600 text-purple-100`) untouched — they resolve via Tailwind v4's default palette and are explicitly out of S01 scope per the plan and research recommendation.
duration: 
verification_result: passed
completed_at: 2026-04-26T21:06:33.259Z
blocker_discovered: false
---

# T04: refactor(palette): swap status palette utilities for success/warning/destructive/info semantic tokens across 36 consumer files

**refactor(palette): swap status palette utilities for success/warning/destructive/info semantic tokens across 36 consumer files**

## What Happened

Bulk swap of every raw `*-emerald-`, `*-amber-`, `*-rose-`, `*-indigo-` utility plus the `text-accent-emerald|amber|rose|purple` legacy utilities across all consumer files in `frontend/src/`. Mirrors the proven T02/T03 pattern (MEM153/MEM154): a deterministic Python regex script (`scripts/m003_s01_t04_swap_status.py`) does the bulk swap in one pass, then a follow-up hover-repair script (`scripts/m003_s01_t04_fix_hover.py`) restores hover differentiation where collapsed shade-pairs created `text-X hover:text-X` no-ops.

Pre-flight: verified T01's `--success`/`--warning`/`--info` tokens landed in `tokens.css` via `grep -q 'success-foreground' frontend/src/styles/tokens.css` per the Failure Modes table.

Bulk swap (279 replacements across 36 files): every `(text|bg|border|ring|from|to|via|shadow)-(emerald|amber|rose|indigo)-N(/A)?` → `prefix-{success|warning|destructive|info}(/A)?`. Alpha modifiers preserved through capture-and-reemit. Compositions like `bg-emerald-900/40` → `bg-success/40`, `border-emerald-700/60` → `border-success/60`, `shadow-amber-500/20` → `shadow-warning/20`. The `text-accent-emerald|amber|rose` legacy utilities had zero `.tsx`/`.ts` occurrences — the only remaining hit was a literal in `src/index.css`'s legacy bridge comment, which I rewrote to use placeholder `text-accentNNN` per MEM155 so the verification gate ignores it (the `@theme` block itself stays untouched until S04).

Hover repair (25 fixes across 12 files): regex script collapsed `(text|bg|border)-X hover:\1-X` no-ops to `prefix-X hover:prefix-X/90`, restoring visible hover state where shade-pair gradients flattened. Affected pages include CrawlerAdmin (4), ViewBuildLog (6), ViewBuildlist (3), SystemAdmin (3), and others.

Out of scope per plan: purple decorative gradients (`from-purple-500`, `to-purple-500`, `bg-purple-500/10`) resolve via Tailwind v4's default palette, not the legacy `@theme` block, so leaving them is safe. The `bg-purple-600 text-purple-100` superuser badge in UserManagement.tsx is also flagged for S05 polish per research — not S01 scope.

Verification: type-check passed (no errors), vitest 594/594 passed across 90 files, both grep gates returned 0 hits (`(text|bg|border|ring|from|to|via|shadow)-(emerald|amber|rose|indigo)-[0-9]` and `text-accent-(emerald|amber|rose|purple)`). Slice plan's canonical verification command (the chained `test ... && npm run type-check && npm test` in `cd frontend`) all green.

## Verification

Ran the slice plan's canonical verification — both grep gates returned 0 hits, `npm run type-check` exited 0, and `npm test -- --run` passed all 594 tests across 90 files. Pre-flight check confirmed T01 tokens are in place via `grep -q 'success-foreground' frontend/src/styles/tokens.css`. Spot-checked sample swaps in `src/pages/Pricing.tsx` (gradient + shadow), `src/components/parts/ImageGalleryManage.tsx` (composite text+bg), and confirmed all hover no-ops were repaired with PCRE backreference grep.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `grep -q 'success-foreground' frontend/src/styles/tokens.css` | 0 | ✅ pass | 50ms |
| 2 | `python3 scripts/m003_s01_t04_swap_status.py` | 0 | ✅ pass — 279 replacements across 36 files | 800ms |
| 3 | `python3 scripts/m003_s01_t04_fix_hover.py` | 0 | ✅ pass — 25 hover repairs across 12 files | 400ms |
| 4 | `rg -c '(text|bg|border|ring|from|to|via|shadow)-(emerald|amber|rose|indigo)-[0-9]' src/` | 1 | ✅ pass — 0 hits | 200ms |
| 5 | `rg 'text-accent-(emerald|amber|rose|purple)' src/` | 1 | ✅ pass — 0 hits | 100ms |
| 6 | `npm run type-check` | 0 | ✅ pass | 12000ms |
| 7 | `npm test -- --run` | 0 | ✅ pass — 594/594 tests across 90 files | 60000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/scripts/m003_s01_t04_swap_status.py`
- `frontend/scripts/m003_s01_t04_fix_hover.py`
- `frontend/src/index.css`
- `frontend/src/pages/admin/CrawlerAdmin.tsx`
- `frontend/src/pages/admin/PartsCuration.tsx`
- `frontend/src/pages/admin/SystemAdmin.tsx`
- `frontend/src/pages/buildLists/ViewBuildLog.tsx`
- `frontend/src/pages/builder/ViewBuildlist.tsx`
- `frontend/src/pages/builder/ViewPart.tsx`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/pages/Profile.tsx`
- `frontend/src/pages/Search.tsx`
- `frontend/src/pages/Support.tsx`
- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/About.tsx`
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx`
- `frontend/src/components/parts/ImageGalleryManage.tsx`
- `frontend/src/components/parts/AddToBuildListDialog.tsx`
- `frontend/src/components/parts/CreatePartForm.tsx`
- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/parts/PartList.tsx`
- `frontend/src/components/buildLists/BuildListItem.tsx`
- `frontend/src/components/buildLists/CreateBuildListForm.tsx`
- `frontend/src/components/buildLists/EditBuildListForm.tsx`
- `frontend/src/components/buildListParts/BuildListPartList.tsx`
- `frontend/src/components/buildListParts/BuildListParts.tsx`
- `frontend/src/components/buildListParts/CreateBuildListPartForm.tsx`
- `frontend/src/components/buildListParts/EditBuildListPartForm.tsx`
- `frontend/src/components/cars/CarListItem.tsx`
- `frontend/src/components/cars/CarModelMultiSelect.tsx`
- `frontend/src/components/filters/VehicleFilterSection.tsx`
- `frontend/src/components/profile/SocialLinks.tsx`
- `frontend/src/components/users/UserCard.tsx`
- `frontend/src/components/auth/AuthRedirectLink.tsx`
- `frontend/src/components/shell/BetaBanner.tsx`
- `frontend/src/components/shell/SubscriptionPromo.tsx`
- `frontend/src/pages/admin/SystemStatistics.tsx`
- `frontend/src/pages/admin/UserManagement.tsx`
