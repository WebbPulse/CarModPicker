# M003 — Migration Completion UAT

> **Status (M003 close):** M003 closed in auto-mode at `d79f15b`. All 12 standing close gates ran fresh during S06/T03 and exited green (7 grep gates with zero hits + tsc/eslint/vitest 597-tests/vite-build/Playwright 155-passed-10-skipped). The operator UAT items below are non-blocking follow-ups — record verdicts inline and commit when complete. Three IA decision slots below need a human reviewer with eyes on the rendered UI to resolve. The 360px manual walkthrough captures narrow-viewport overflow that Playwright's mobile=375 project does not surface (MEM170/MEM179).

## How to use this document

1. Run `npm run dev` from `frontend/` and open the app at http://localhost:4000.
2. Open Chrome DevTools → Device Toolbar (`Cmd+Shift+M`), pick "Responsive" and set the width manually (360 / 768 / 1280).
3. Walk the priority pages section to spot-check the visual surface; refer to the Playwright PNG baselines under `frontend/e2e/polish-coverage.spec.ts-snapshots/` for ground truth.
4. Resolve each IA Deferral Decision by ticking exactly one option and adding operator notes if applicable.

## Priority Pages — Per-Viewport Verdicts

Sourced from M003/S05/S05-SUMMARY.md (verdict legend reproduced below). PNG baseline location: `frontend/e2e/polish-coverage.spec.ts-snapshots/<route>-<viewport>.png`.

Verdict legend:
- **pass** — page touched only via incidental sweeps (e.g. `text-gray-*` migrations) or not touched at all; baseline now covers it for R061
- **fixed** — page received structural cleanup (bug fix, primitive migration, gradient/shadow retokenization, factory collapse, etc.)
- **acceptable-as-scroll** — page accepted with horizontal scroll behavior at narrow viewport; structural responsive fix deferred to M004
- **deferred-to-S06** — high-impact IA decision flagged for this UAT walkthrough; tokenized in-place during S05 but not redesigned

| Route | Mobile (375) | Tablet (768) | Desktop (1280) | Notes |
|---|---|---|---|---|
| `/` | fixed | fixed | fixed | Home: gradient collapse + text-gray sweep (S05/T02) |
| `/parts` | pass | pass | pass | Parts catalog: already on shadcn primitives |
| `/parts/<x>` | pass | pass | pass | ViewPart: UUID 404 baseline locks NotFound state |
| `/build-lists/<uuid>` | pass | pass | pass | ViewBuildList: UUID 404 locks NotFound state |
| `/car-generations/<x>` | pass | pass | pass | ViewCar: category switcher tokenized (S05/T04); missing record locks NotFound |
| `/login` | fixed | fixed | fixed | Alert variant=destructive + flat bg-primary (S05/T03) |
| `/register` | fixed | fixed | fixed | Alert variant=destructive + flat bg-primary (S05/T03) |
| Header | fixed | fixed | fixed | Visual surface covered by every route's fullPage screenshot |
| `/account/alerts` | fixed | fixed | fixed | text-gray sweep + spacer removal (S05/T03); redirects to /login when unauth |
| `/admin` | pass | pass | pass | AdminDashboard: no edits to dashboard itself (S05/T05) |
| `/admin/extraction-health` | pass | pass | pass | Already on shadcn primitives via S03/S11 |

**Other routes (full coverage in S05-SUMMARY.md):** `/about`, `/pricing`, `/support`, `/checkout`, `/contact-us`, `/privacy-policy`, `/terms-of-service`, `/forgot-password`, `/forgot-password/confirm`, `/verify-email`, `/verify-email/confirm`, `/extension-auth`, `/profile`, `/user/<uuid>`, `/builder`, `/build-lists`, `/build-lists/<uuid>/build-log`, `/search`, `/bug-report`, `/parts/<x>/edit`, `/my-parts`, `/admin/reports`, `/admin/bug-reports`, `/admin/users`, `/admin/crawler`, `/admin/system`, `/admin/statistics`, `/admin/parts-curation`, `/_kitchen-sink`, `/nonexistent-route-for-404-test`. All carry baseline coverage at 3 viewports (40 routes × 3 = 120 PNGs total).

**Known acceptable-as-scroll surfaces** (also see Decision #5 below):
- `/admin/users` at 768 — 11-column user-management table (locked by Decision #5 below as `acceptable-as-scroll`)
- `/admin/crawler` at 375 — TIER_META rate-limit table

## 360px Manual Walkthrough — Operator Checklist

Playwright's mobile project is 375px; per MEM170/MEM179 the 360px overflow signal must be checked manually because `width=360` reveals horizontal-scroll regressions that 375 does not. Use Chrome DevTools "Responsive" mode at 360×640.

For each priority page, confirm:
- No unintentional horizontal overflow (acceptable-as-scroll cases noted)
- Header navigation reachable (hamburger menu opens / closes cleanly)
- Primary CTA reachable above the fold or via natural scroll
- No text clipped, no buttons overlapping, no images cropped to unusable sizes

- [ ] `/` — open in DevTools at 360×640, confirm: no horizontal overflow, header navigation usable, primary CTA reachable. Operator notes: ___
- [ ] `/parts` (PartsCatalog) — confirm: filter chips wrap or hide cleanly, table acceptable-as-scroll-only-where-expected, pagination reachable. Operator notes: ___
- [ ] `/parts/<existing-uuid>` (ViewPart) — confirm with a real part: no horizontal overflow, image sized to viewport, action buttons reachable. Operator notes: ___
- [ ] `/build-lists/<existing-uuid>` (ViewBuildList) — confirm: tabs / sections reachable, no overflow. Operator notes: ___
- [ ] `/car-generations/<existing-slug>` (ViewCar) — confirm: category switcher reachable, no overflow. Operator notes: ___
- [ ] `/login` — confirm: form inputs sized to viewport, error alert renders inside shell, no overflow. Operator notes: ___
- [ ] `/register` — confirm: form inputs sized to viewport, error alert renders inside shell, no overflow. Operator notes: ___
- [ ] Header (any page) — confirm: logo + hamburger fit at 360, menu opens to a usable surface, no truncated text. Operator notes: ___
- [ ] `/account/alerts` — log in first, confirm: alert list scrolls cleanly, no overflow. Operator notes: ___
- [ ] `/admin` (AdminDashboard) — log in as admin, confirm: section cards reachable, no overflow. Operator notes: ___
- [ ] `/admin/extraction-health` — log in as admin, confirm: tables wrap or scroll-as-expected, no overflow on key surfaces. Operator notes: ___

## IA Deferral Decisions

S05 deferred 6 IA items to this UAT walkthrough. T01 (this slice) resolved 3 of them autonomously:

- **#4 ViewBuildLog markdown prose plugin** — deferred again as a long-term option. Per-element tokenization landed in S05/T04 is preserved. See "Resolved autonomously by T01" below for rationale.
- **#5 UserManagement 11-col table responsive strategy** — locked as `acceptable-as-scroll` (option a). See "Resolved autonomously by T01" below.
- **#6 SystemAdmin DangerActionPanel extraction** — applied. See "Resolved autonomously by T01" below.

The remaining 3 require human visual judgment and are recorded as decision slots below.

### #1 Auth-shell unification

**Files:**
- `frontend/src/pages/authentication/Login.tsx`
- `frontend/src/pages/authentication/Register.tsx`
- `frontend/src/pages/authentication/ExtensionAuth.tsx`
- `frontend/src/pages/authentication/ForgotPassword.tsx`
- `frontend/src/pages/authentication/ForgotPasswordConfirm.tsx`
- `frontend/src/pages/authentication/VerifyEmail.tsx`
- `frontend/src/components/auth/AuthCard.tsx`

**Observation:** Login, Register, and ExtensionAuth use a glass-card-style surrounding wrapper (now tokenized off the legacy `glass-card` class but still rendered inline as `Card` + custom padding). ForgotPassword, ForgotPasswordConfirm, and VerifyEmail use the dedicated `AuthCard` component. Two materially-different shells for one auth flow surfaces inconsistency at narrow viewports.

**Trade-offs:**
- Keep both shells: lowest churn but visual inconsistency persists; future auth pages must pick a side without guidance.
- Unify on glass-card wrapper: keeps the "branded" look of the primary auth pages; ForgotPassword family loses its dedicated component and inherits inline JSX.
- Unify on AuthCard: collapses 3 inline-shell pages onto a tested component; Login/Register/ExtensionAuth visual weight may shift slightly (worth comparing PNG baselines after migration).
- Merge into a third primitive: most work, cleanest long-term shape; appropriate if the auth surface keeps growing.

**Decision:** [ ] keep both shells | [ ] unify on glass-card | [ ] unify on AuthCard | [ ] merge to new primitive

**Operator notes:** ___

### #2 ContactUs 3-card collapse

**Files:**
- `frontend/src/pages/ContactUs.tsx`

**Observation:** The page renders 3 near-identical email-cards (general / business / support) stacked on mobile and tiled on desktop. Each card has its own heading, description, and `mailto:` link. Collapsing into a single card with a recipient toggle (segmented control or dropdown) is a medium-to-high-impact UX change because it shifts the user mental model from "pick a card" to "pick a recipient, then send."

**Trade-offs:**
- Keep 3 cards: lowest churn; mobile experience is acceptable (cards stack); the redundancy is actually scannable.
- Collapse to 1 card with toggle: tighter mobile footprint and reduces information duplication; but losing the visual distinction between recipient types may lower discoverability.
- Collapse to 1 card with `<select>` of recipients: simplest layout; least visual interest.

**Decision:** [ ] keep 3 cards | [ ] collapse to 1 card with toggle | [ ] collapse to 1 card with select | [ ] other (note below)

**Operator notes:** ___

### #3 BuildListsCatalog sidebar drawer

**Files:**
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx`
- (potential new) `frontend/src/components/ui/drawer.tsx`

**Observation:** The page has a left filter sidebar that pushes content rightward at narrow viewports; ergonomically the sidebar should become a slide-in drawer below tablet breakpoint. M002 inventory check: the codebase has `frontend/src/components/ui/sheet.tsx` (Radix Dialog wrapper used for slide-in surfaces) but no dedicated `drawer.tsx`. A drawer can be built on top of Sheet without minting a new primitive.

**Trade-offs:**
- Keep current sidebar at all viewports: simplest; current `acceptable-as-scroll` baseline already locks the rendered geometry.
- Slide-in drawer (Sheet-based) at `<lg`: matches mobile-first patterns; one filter button in the header, sheet opens from the left.
- Bottom sheet on `<sm`, side drawer on `sm-lg`: most ergonomic but adds a breakpoint-conditional UX shift that needs careful animation.
- New `ui/drawer.tsx` primitive: appropriate only if drawers will recur elsewhere (currently no other consumer).

**Decision:** [ ] keep sidebar | [ ] slide-in drawer (Sheet-based) at `<lg` | [ ] bottom sheet on `<sm` + drawer on `sm-lg` | [ ] mint new ui/drawer.tsx primitive

**Operator notes:** ___

## Resolved Autonomously by T01

### #4 ViewBuildLog markdown prose plugin (deferred again as long-term option)

**Files reviewed:** `frontend/src/pages/buildLists/ViewBuildLog.tsx`, `frontend/src/index.css`, `frontend/package.json`.

**Decision rule applied:** Per MEM186 (the conservative path is sanctioned), and the T01 decision rule "prefer per-element tokenization if there is any visual ambiguity," T01 chose to **leave the per-element tokenization in place** and not adopt `@tailwindcss/typography`.

**Rationale:**
- The S05/T04 per-element tokenization (~13 element overrides — p, h1-h3, ul, ol, li, code, pre, blockquote, a, img, strong, em — all on semantic tokens) is already covered by polish-coverage baselines at 3 viewports for `/build-lists/<uuid>/build-log`.
- `@tailwindcss/typography` ships its own opinionated gray scale via `prose-invert`; visual parity with our semantic tokens (`text-foreground` / `bg-muted` / `text-info` / `border-info`) cannot be guaranteed without a side-by-side PNG comparison.
- Adopting the plugin replaces ~13 explicit overrides with one `prose prose-invert` class but adds a runtime dependency and couples the surface to the plugin's typography opinions.
- The dependency-add risk in autonomous mode is high; deferring keeps M003 close-state stable and leaves the plugin as a future M004 polish opportunity if a human reviewer chooses to A/B the visual output.

**Future M004 path:** If a future slice wants to revisit this, the work is: `npm i -D @tailwindcss/typography`; add `@plugin '@tailwindcss/typography';` to `frontend/src/index.css` after `@import 'tailwindcss';`; replace the 13 per-element overrides with a single `<div className="prose prose-invert">` wrapper; refresh the 3 polish-coverage baselines for `/build-lists/<uuid>/build-log` and visually compare.

### #5 UserManagement 11-column table responsive strategy (locked as acceptable-as-scroll)

**Files modified:** `frontend/src/pages/admin/UserManagement.tsx` — added a one-line decision-record comment above the existing `<div className="overflow-x-auto">` table boundary referencing M003-UAT.md and MEM179.

**Decision:** option (a) `acceptable-as-scroll`. The 11-column admin user-management table is operationally usable at desktop and tablet; at mobile it horizontally scrolls. This is consistent with MEM172 (4 admin tables also accept horizontal scroll) and MEM179 (the 360px manual UAT signal is the canonical narrow-viewport check).

**Future M004 backlog:** options (b) collapse columns into expandable row, (c) move secondary columns to a row-detail view, (d) cards-on-mobile remain available if narrow-viewport ergonomics become a priority. None apply for the M003 close.

### #6 SystemAdmin DangerActionPanel extraction (applied)

**Files created:** `frontend/src/components/admin/DangerActionPanel.tsx` (~58 LOC).

**Files modified:** `frontend/src/pages/admin/SystemAdmin.tsx` — 3 deletion-accordion panels (cars, global-parts/manufacturers, bucket cleanup) refactored to consume `<DangerActionPanel>`.

**Scope deviation from plan:** The slice plan said "10 near-identical danger sections collapse to 10 component instances." The actual SystemAdmin layout has only **3 near-identical danger panels** inside the Deletion-options collapsible accordion (cars warning-tone, parts/manufacturers destructive-tone, bucket info-tone). The other "destructive-feeling" sections (Database Migrations, Data Initialization) are top-level Card sections with materially different shapes (Card + h2 heading + subtitle + own ConfirmDialog or no dialog at all) and are not part of the deferral. T01 followed code reality and refactored only the 3 panels that genuinely match.

**API:** `<DangerActionPanel title description dangerColor='destructive'|'warning'|'info'>{children}</DangerActionPanel>`. Owns the panel's outer chrome (`p-3 border-t bg-{tone}/20 border-{tone}/50` + heading + description); consumers slot their buttons, result blocks, and confirm-dialog mounts via `children`. Component lives at `frontend/src/components/admin/DangerActionPanel.tsx` per the existing admin-scoped component placement (matches `ReportDialog.tsx`).

**Visual parity:** Pure refactor with semantic-token output unchanged. polish-coverage's `/admin/system` baselines should refresh zero PNGs on the cascade pass (MEM156/MEM160 default `=changed` mode).

## Forward Pointers

- After resolving the 3 IA decisions above, file follow-up issues for any "merge to new primitive" or "drawer" choices that need their own implementation slice in M004.
- The 360px manual walkthrough operator notes are durable evidence — the verdicts captured here are the authoritative narrow-viewport check, complementing the Playwright mobile=375 baselines.
- Cascade-refresh expectation if any decision is implemented post-close: refresh affected polish-coverage baselines via `npx playwright test polish-coverage.spec.ts --update-snapshots` and visually review per MEM148.
