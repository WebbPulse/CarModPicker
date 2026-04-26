---
id: T02
parent: S01
milestone: M003
key_files:
  - frontend/src/pages/About.tsx
  - frontend/src/pages/BugReport.tsx
  - frontend/src/pages/Checkout.tsx
  - frontend/src/pages/ContactUs.tsx
  - frontend/src/pages/Home.tsx
  - frontend/src/pages/NotFound.tsx
  - frontend/src/pages/Pricing.tsx
  - frontend/src/pages/PrivacyPolicy.tsx
  - frontend/src/pages/Profile.tsx
  - frontend/src/pages/Support.tsx
  - frontend/src/pages/TermsOfService.tsx
  - frontend/src/pages/admin/CrawlerAdmin.tsx
  - frontend/src/pages/admin/SystemAdmin.tsx
  - frontend/src/pages/authentication/ExtensionAuth.tsx
  - frontend/src/pages/authentication/ForgotPassword.tsx
  - frontend/src/pages/authentication/ForgotPasswordConfirm.tsx
  - frontend/src/pages/authentication/Login.tsx
  - frontend/src/pages/authentication/Register.tsx
  - frontend/src/components/ads/AdBanner.tsx
  - frontend/src/components/authentication/GoogleAuthFlow.tsx
  - frontend/src/components/buildListParts/CreateBuildListPartForm.tsx
  - frontend/src/components/buildLists/BuildListCard.tsx
  - frontend/src/components/buildLists/CreateBuildListForm.tsx
  - frontend/src/components/buildLists/EditBuildListForm.tsx
  - frontend/src/components/cars/CarModelMultiSelect.tsx
  - frontend/src/components/forms/ImageUpload.tsx
  - frontend/src/components/forms/SearchableSelect.tsx
  - frontend/src/components/layout/globalFooter/Footer.tsx
  - frontend/src/components/layout/globalHeader/Header.tsx
  - frontend/src/components/parts/AddToBuildListDialog.tsx
  - frontend/src/components/parts/CreatePartForm.tsx
  - frontend/src/components/parts/EditPartForm.tsx
  - frontend/src/components/profile/ChangePasswordDialog.tsx
  - frontend/src/components/profile/PasskeySettings.tsx
  - frontend/src/components/profile/SecuritySettings.tsx
  - frontend/src/components/profile/SecuritySettingsDialog.tsx
  - frontend/src/components/profile/TwoFactorAuthDialog.tsx
  - frontend/src/components/routes/RouteGroupBoundary.tsx
  - frontend/src/components/shell/ChromeExtensionPromo.tsx
  - frontend/src/components/shell/CookieConsentBanner.tsx
  - frontend/src/components/shell/ErrorBoundary.tsx
  - frontend/src/components/shell/SubscriptionPromo.tsx
key_decisions:
  - Used a deterministic Python regex script over .tsx/.ts files for the bulk swap rather than per-file Edit calls — 267 replacements across 42 files in one pass, with explicit mapping table avoiding partial-shade collisions.
  - Preserved alpha modifiers (e.g. /80, /40, /50) by capturing them in the regex and re-emitting onto the new semantic prefix — alpha composes through Tailwind v4 @theme mappings since each --color-* resolves to hsl(var(--token)).
  - Manually overrode the script's default bg-neutral-900 → bg-card mapping in ErrorBoundary.tsx, flipping to bg-background because the container is full-screen page surface, not a raised inner element. All other bg-neutral-900 occurrences (one in SystemAdmin.tsx with /40 alpha) were correctly handled as raised surfaces.
  - Treated the plan's Expected Output file list as illustrative — the actual fix set was 42 files (not the enumerated 33). Plan goal was 'all files with neutral-* utilities', achieved via grep gate.
duration: 
verification_result: passed
completed_at: 2026-04-26T20:58:11.976Z
blocker_discovered: false
---

# T02: refactor(palette): swap raw neutral utilities for semantic tokens across 42 consumer files

**refactor(palette): swap raw neutral utilities for semantic tokens across 42 consumer files**

## What Happened

Bulk semantic-token migration of every raw `(text|bg|border|ring)-neutral-[0-9]+(/[0-9]+)?` utility across `frontend/src/`. 267 occurrences in 42 files were rewritten to semantic tokens (`text-foreground`, `text-muted-foreground`, `bg-card`, `bg-muted`, `bg-background`, `border-border`).

The migration was performed with a deterministic Python script using a single regex (`\b(text|bg|border|ring)-neutral-(\d+)(/\d+)?\b`) and an explicit (prefix, shade) → semantic-token mapping table. Alpha modifiers (e.g. `text-neutral-400/80`, `bg-neutral-900/40`) were preserved through the regex's optional `(/\d+)?` capture group and re-emitted onto the new semantic prefix. The script skipped `index.css` (legacy `@theme` block survives until S04) and `tokens.css` (already finalized in T01).

Mapping applied:
- `text-neutral-{100,200,300}` → `text-foreground` (default body text on dark surfaces)
- `text-neutral-{400,500,600}` → `text-muted-foreground` (secondary/tertiary labels)
- `text-neutral-900` → `text-background` (rare; inverted text on light gradient — Pricing.tsx pro-tier badge/CTA)
- `bg-neutral-700` → `bg-muted` (slightly raised inside card)
- `bg-neutral-800` → `bg-card`
- `bg-neutral-900` → `bg-card` (raised default), with one manual override in `ErrorBoundary.tsx` flipped to `bg-background` because that container is full-screen page surface, not a raised inner element
- `bg-neutral-950` → `bg-background`
- `border-neutral-{500,600,700}` → `border-border`

The two `text-neutral-400 hover:text-neutral-300` patterns in `SystemAdmin.tsx` (lines 434, 701) collapsed cleanly to `text-muted-foreground hover:text-foreground` through the global mapping — exactly matching the plan's tier-2-label flip rule without needing a dedicated regex.

The Expected Output list in the plan turned out to be illustrative — the actual fix set was 42 files (not the 33 enumerated). Files outside the enumerated list that needed migration: BugReport, NotFound, ContactUs, ForgotPassword, ForgotPasswordConfirm, ExtensionAuth, plus several form/dialog components that contained label or placeholder neutrals. All were migrated under the same mapping.

Build succeeds (vite + tsc + prerender all green, 7 routes prerendered in 11s). Type-check clean. Vitest 90 files / 594 tests pass with no neutral-class assertions broken. Post-migration `rg '(text|bg|border|ring)-neutral-[0-9]' src/` returns only one match: a CSS comment string in `index.css` describing the legacy block — which the plan explicitly preserves until S04.

No runtime/observability impact — pure CSS-class vocabulary swap. Existing structured logs, metrics, and error paths unchanged.

## Verification

Ran the slice/task verification chain end-to-end:

1. `python3 /tmp/migrate_neutral.py` executed the bulk swap — reported 42 files / 267 replacements with zero "WARN: no mapping" entries (every utility encountered had an explicit mapping).
2. Manual override in `ErrorBoundary.tsx`: `bg-card` → `bg-background` for the full-screen error fallback container (the script's default `bg-neutral-900 → bg-card` was wrong for a page-surface container).
3. `rg '(text|bg|border|ring)-neutral-[0-9]' src/` — only 1 match remains: `src/index.css:5` inside a CSS comment string (`bg-primary-500, text-accent-emerald, border-neutral-700 actually emit CSS.`). The plan explicitly excludes index.css.
4. `npm run type-check` — exit 0, no TS errors.
5. `npm run build` — exit 0, vite build 4.38s, prerender 7 routes in 11s.
6. `npm test -- --run` — 90 files / 594 tests / 0 failures.

The plan's literal verification command (`test $(rg -c '...' src/ 2>/dev/null | wc -l) -eq 0`) returns 1 because of the index.css comment, but per the slice plan and task plan that file is intentionally not touched — the comment will be removed naturally when S04 deletes the legacy `@theme` block.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 /tmp/migrate_neutral.py (42 files, 267 replacements)` | 0 | ✅ pass | 200ms |
| 2 | `rg '(text|bg|border|ring)-neutral-[0-9]' src/ (only index.css comment remains)` | 0 | ✅ pass | 30ms |
| 3 | `npm run type-check` | 0 | ✅ pass | 12000ms |
| 4 | `npm run build` | 0 | ✅ pass | 16000ms |
| 5 | `npm test -- --run` | 0 | ✅ pass | 80000ms |

## Deviations

The plan's Expected Output enumerated 33 files, but the actual fix set was 42 files. Additional files migrated (all matching the same `(text|bg|border|ring)-neutral-[0-9]` predicate): BugReport.tsx, NotFound.tsx, ContactUs.tsx, ForgotPassword.tsx, ForgotPasswordConfirm.tsx, ExtensionAuth.tsx, BuildListCard.tsx, CreateBuildListForm.tsx, EditBuildListForm.tsx, CarModelMultiSelect.tsx, ImageUpload.tsx, SearchableSelect.tsx, AddToBuildListDialog.tsx, CreatePartForm.tsx, EditPartForm.tsx, ChangePasswordDialog.tsx, PasskeySettings.tsx, SecuritySettings.tsx, SecuritySettingsDialog.tsx, TwoFactorAuthDialog.tsx, RouteGroupBoundary.tsx, ChromeExtensionPromo.tsx, CookieConsentBanner.tsx, SubscriptionPromo.tsx, CreateBuildListPartForm.tsx. The plan's stated goal was the grep gate (0 hits across `src/`), which subsumed all of these.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/About.tsx`
- `frontend/src/pages/BugReport.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/pages/ContactUs.tsx`
- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/NotFound.tsx`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/pages/PrivacyPolicy.tsx`
- `frontend/src/pages/Profile.tsx`
- `frontend/src/pages/Support.tsx`
- `frontend/src/pages/TermsOfService.tsx`
- `frontend/src/pages/admin/CrawlerAdmin.tsx`
- `frontend/src/pages/admin/SystemAdmin.tsx`
- `frontend/src/pages/authentication/ExtensionAuth.tsx`
- `frontend/src/pages/authentication/ForgotPassword.tsx`
- `frontend/src/pages/authentication/ForgotPasswordConfirm.tsx`
- `frontend/src/pages/authentication/Login.tsx`
- `frontend/src/pages/authentication/Register.tsx`
- `frontend/src/components/ads/AdBanner.tsx`
- `frontend/src/components/authentication/GoogleAuthFlow.tsx`
- `frontend/src/components/buildListParts/CreateBuildListPartForm.tsx`
- `frontend/src/components/buildLists/BuildListCard.tsx`
- `frontend/src/components/buildLists/CreateBuildListForm.tsx`
- `frontend/src/components/buildLists/EditBuildListForm.tsx`
- `frontend/src/components/cars/CarModelMultiSelect.tsx`
- `frontend/src/components/forms/ImageUpload.tsx`
- `frontend/src/components/forms/SearchableSelect.tsx`
- `frontend/src/components/layout/globalFooter/Footer.tsx`
- `frontend/src/components/layout/globalHeader/Header.tsx`
- `frontend/src/components/parts/AddToBuildListDialog.tsx`
- `frontend/src/components/parts/CreatePartForm.tsx`
- `frontend/src/components/parts/EditPartForm.tsx`
- `frontend/src/components/profile/ChangePasswordDialog.tsx`
- `frontend/src/components/profile/PasskeySettings.tsx`
- `frontend/src/components/profile/SecuritySettings.tsx`
- `frontend/src/components/profile/SecuritySettingsDialog.tsx`
- `frontend/src/components/profile/TwoFactorAuthDialog.tsx`
- `frontend/src/components/routes/RouteGroupBoundary.tsx`
- `frontend/src/components/shell/ChromeExtensionPromo.tsx`
- `frontend/src/components/shell/CookieConsentBanner.tsx`
- `frontend/src/components/shell/ErrorBoundary.tsx`
- `frontend/src/components/shell/SubscriptionPromo.tsx`
