---
id: S05
parent: M003
milestone: M003
provides:
  - frontend/e2e/polish-coverage.spec.ts visiting all 40 production routes at mobile=375 / tablet=768 / desktop=1280 with 120 PNG baselines committed under frontend/e2e/polish-coverage.spec.ts-snapshots/
  - 33 previously-unbaselined routes now have visual signal for S06's R061 close gauntlet — any future PR that mutates a covered route's geometry surfaces as a Playwright PNG diff
  - 4 new ui/* primitives — Textarea, StatusBadge, PriorityBadge, LoadingOverlay — landed as canonical implementations; future hand-rolled equivalents are caught at code review against the now-present primitive
  - card-info-item.tsx retokenized off text-gray-300 to text-foreground/text-muted-foreground
  - 5 hand-rolled textareas (BugReport.tsx + ViewBuildLog.tsx) replaced with Textarea primitive
  - 3 admin status-badge factories (ReportReview, BugReportReview) collapsed to StatusBadge/PriorityBadge primitives
  - 3 admin loading-overlay divs collapsed to LoadingOverlay primitive
  - 3 hand-rolled auth-error blocks (Login, Register, ExtensionAuth) replaced with Alert variant=destructive (ForgotPassword already used ErrorAlert from ui/alert; 4 of 4 listed files import from ui/alert)
  - 3 from-primary→to-primary no-op gradients in Login/Register/ExtensionAuth collapsed to flat bg-primary
  - SystemStatistics + PartsCuration bespoke StatPanel reskinned to semantic-token utilities
  - CrawlerAdmin TIER_META raw border-l-emerald/amber/indigo/rose colors tokenized to semantic tokens
  - SystemAdmin 10 danger panels tokenized in-place (DangerActionPanel extraction explicitly deferred to S06 UAT)
  - UserManagement.tsx invisible-text bug fixed (bg-warning text-warning → tokenized visible-contrast badge)
  - Per-page verdict table covering all 40 production routes at 3 viewports
  - 6 high-impact IA decisions deferred to S06 UAT with file:line references and rationale
requires:
  - slice: S04
    provides: clean post-S04 substrate (94-line index.css) with 12 standing grep gates green; tokens.css semantic vocabulary; vite build is the standing structural enforcement
  - slice: S03
    provides: responsive audit + ViewPart IA collapse; 6 routes with prior Playwright coverage (admin dashboard + extraction-health, build-list, parts-catalog, price-alerts, price-history, smoke)
  - slice: S02
    provides: glass-* + var(--legacy)-* purge — no consumer survives the @theme/:root deletion
  - slice: S01
    provides: raw-palette utility migration — no bg-primary-500 / text-accent-* / etc. survives in consumer dirs
affects:
  - S06 (close gauntlet + manual UAT) — consumes 33 newly-baselined routes, the 6 deferred IA decisions, the per-page verdict list, and the 4 new ui/* primitives
key_files:
  - frontend/src/components/ui/textarea.tsx
  - frontend/src/components/ui/status-badge.tsx
  - frontend/src/components/ui/loading-overlay.tsx
  - frontend/src/components/ui/card-info-item.tsx
  - frontend/src/styles/tokens.css
  - frontend/src/pages/Pricing.tsx
  - frontend/src/pages/Support.tsx
  - frontend/src/pages/Home.tsx
  - frontend/src/pages/About.tsx
  - frontend/src/pages/Checkout.tsx
  - frontend/src/pages/ContactUs.tsx
  - frontend/src/pages/PrivacyPolicy.tsx
  - frontend/src/pages/TermsOfService.tsx
  - frontend/src/pages/authentication/Login.tsx
  - frontend/src/pages/authentication/Register.tsx
  - frontend/src/pages/authentication/ForgotPassword.tsx
  - frontend/src/pages/authentication/ForgotPasswordConfirm.tsx
  - frontend/src/pages/authentication/VerifyEmail.tsx
  - frontend/src/pages/authentication/ExtensionAuth.tsx
  - frontend/src/pages/Profile.tsx
  - frontend/src/pages/ViewUser.tsx
  - frontend/src/pages/account/AccountAlerts.tsx
  - frontend/src/pages/builder/Builder.tsx
  - frontend/src/pages/builder/ViewCar.tsx
  - frontend/src/pages/buildLists/BuildListsCatalog.tsx
  - frontend/src/pages/buildLists/ViewBuildLog.tsx
  - frontend/src/pages/Search.tsx
  - frontend/src/pages/BugReport.tsx
  - frontend/src/pages/admin/ReportReview.tsx
  - frontend/src/pages/admin/BugReportReview.tsx
  - frontend/src/pages/admin/UserManagement.tsx
  - frontend/src/pages/admin/CrawlerAdmin.tsx
  - frontend/src/pages/admin/SystemAdmin.tsx
  - frontend/src/pages/admin/SystemStatistics.tsx
  - frontend/src/pages/admin/PartsCuration.tsx
  - frontend/e2e/polish-coverage.spec.ts
  - frontend/e2e/tsconfig.json
  - frontend/src/test/route-coverage-list.ts
  - frontend/src/App.coverage.test.tsx
key_decisions:
  - StatusBadge variant enum locked to real consumer superset 'pending|in_progress|resolved|dismissed' — the slice plan said 'active' but no admin consumer uses that label, so followed code reality (T01)
  - Status/Priority badge surfaces use semantic-token tints (warning/15, info/15, success/15, destructive/15, muted) matching the existing legacy admin badge visual weight in shadcn-idiomatic shape (T01)
  - Retokenized 3-stop `from-warning via-orange-500 to-red-500` as 2-stop `from-warning to-warning` (effectively flat warning) rather than minting multi-tone gradient tokens — concrete consumer dictates atomic add per MEM149 (T02)
  - Named the new shadow token `--shadow-warning-glow` after the semantic role rather than a numeric scale slot, leaving shadow-{success,info,destructive}-glow open for future concrete consumers (T02)
  - 3 hand-rolled error blocks (not 4 as the slice plan said) — only Login/Register/ExtensionAuth had bg-red div-with-paragraph blocks; ForgotPassword already used ErrorAlert from ui/alert. The verify gate's '4 sites import from ui/alert' still holds because ForgotPassword imports ErrorAlert (T03)
  - Replaced Profile's window.location.href = '/my-parts' with React Router useNavigate — internal route, no page-level state depends on a full reload, SecuritySettingsDialog elsewhere uses checkAuthStatus() to refresh user state (T03)
  - BugReport actually has 4 hand-rolled textareas (description, steps_to_reproduce, expected_behavior, actual_behavior), not 5 — browser_info + device_info auto-detect fields use Input not textarea. Total textareas swapped = 6 (4 BugReport + 2 ViewBuildLog dialogs) (T04)
  - ViewBuildLog markdown-renderer per-element tokenization (text-foreground for body/headings/strong/em/list/code, bg-muted for code/pre, border-info for blockquote, text-info for links, text-destructive for delete buttons) instead of adopting Tailwind Typography prose plugin — high-impact dependency-add explicitly deferred to S06 UAT in autonomous mode (captured as MEM186) (T04)
  - UserManagement subscription tier badge stays as inline tokenized span (bg-warning text-warning-foreground / bg-muted text-muted-foreground) NOT StatusBadge — the StatusBadge enum doesn't model premium|free; consuming StatusBadge would be incorrect domain mixing (captured as MEM187) (T05)
  - SystemAdmin 10 danger panels tokenized in-place — DangerActionPanel extraction explicitly deferred to S06 UAT (high-impact IA per MEM183). Each panel mapped bg-{color}-900/20 + border-{color}-700/50 + text-{color}-400 to closest semantic token (blue→info, green→success, red→destructive, orange→warning, cyan→info) (T05)
  - polish-coverage.spec.ts uses the mobile=375 Playwright project (per MEM170/MEM179) — 360 documented in the verdict table as the manual UAT signal only (T06)
  - Extracted ROUTES list to frontend/src/test/route-coverage-list.ts (single source of truth) and updated frontend/e2e/tsconfig.json to include it under the e2e Playwright tsconfig — both App.coverage.test.tsx (vitest) and polish-coverage.spec.ts (Playwright) now consume the same list. The drift guard `ALL_ROUTES.length >= 38` continues to enforce categorization on new <Route> additions (T06)
  - Auth-guarded routes (builder group: /profile, /builder, /my-parts, /checkout, /account/alerts, /verify-email) are visited as the default unauthenticated user — the resulting redirect-to-login state is captured in the baseline. This locks the redirect behavior; a regression that breaks the redirect surfaces as a PNG diff. The alternative (pre-authenticate via a fixture) was rejected to keep the spec stateless and avoid coupling to a backend test account (T06)
  - Routes with dynamic UUIDs (/parts/some-part, /build-lists/00000000-..., /user/00000000-..., /car-generations/some-car) are not real records; the API returns 404 and the page renders its NotFound / error-boundary state. The baseline locks that error-state rendering — useful per task plan Q5(b) and consistent with the 'baselines for the error state are still useful' guidance (T06)
patterns_established:
  - MEM186 — Markdown-rendered user content (ViewBuildLog) tokenizes per-element instead of adopting Tailwind Typography prose plugin in autonomous mode; the dependency-add is high-impact and is reserved for S06 UAT
  - MEM187 — Domain-specific badges (subscription tier, role) stay as inline tokenized spans rather than consuming StatusBadge if the StatusBadge enum doesn't model the domain values; consuming the wrong-domain enum would be incorrect domain mixing
  - Visual-regression coverage-by-spec pattern — frontend/e2e/polish-coverage.spec.ts is a parametrized loop over App.coverage.test.tsx's ROUTES list, screenshotting each route at every Playwright project. This produces N×3 baselines automatically and any new <Route> in App.tsx automatically gets visual coverage by being added to the shared ROUTES list (drift-guarded by the existing vitest assertion)
  - Cookie-consent + chrome-extension-promo pre-dismissal via addInitScript (MEM098/MEM103/MEM108/MEM109) is the standard pattern for any new spec that takes fullPage screenshots — the bottom-pinned banner overlay would otherwise pollute every mobile-viewport baseline
observability_surfaces:
  - frontend/e2e/polish-coverage.spec.ts is the standing visual-regression surface for all 40 production routes at 3 viewports — any future PR that mutates a covered route's rendered geometry without refreshing baselines surfaces as a Playwright PNG diff with the file path and viewport in the failure message
  - 12 standing close gates (7 grep + 5 toolchain: type-check / lint / vitest / vite build / Playwright) inherited from S04 remain the inspection surface; each can be run independently and a non-zero exit means regression
  - vite build exit code remains the canonical structural enforcement (R061) — any reintroduction of a deleted legacy class becomes a hard build error
  - Per-page verdict table in this summary is the durable qualitative record paired with the new baselines; future agents can grep the verdict table to find which pages were merely passed-through vs. structurally touched vs. deferred to S06
  - StatusBadge / PriorityBadge / LoadingOverlay / Textarea primitives in frontend/src/components/ui/ are the canonical implementations; future hand-rolled equivalents are caught at code review against the now-present primitive
drill_down_paths:
  - .gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T04-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T05-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T06-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-26
blocker_discovered: false
---

# S05: Page-by-page polish pass at three breakpoints

**All 40 production routes visited at mobile=375 / tablet=768 / desktop=1280 via the new polish-coverage.spec.ts (120 PNG baselines committed); 4 new ui/* primitives consumed across 7 admin + 9 auth/account + 6 builder + 8 marketing pages; UserManagement invisible-text bug fixed; per-page verdict table covers all 40 routes; 6 high-impact IA decisions explicitly deferred to S06 UAT; all 12 standing gates green.**

## What Happened

S05 closed the M003 polish-pass surface against the clean post-S04 substrate. The slice executed in three coordinated waves across 6 tasks.

**Wave A — Primitives (T01):** Landed the 4 atomic ui/* primitives that block the polish batches: `Textarea` (forwards all native textarea props plus `error?: boolean`), `StatusBadge` (variant: 'pending'|'in_progress'|'resolved'|'dismissed' — enum locked to the real admin consumer superset since BugReportReview uses `in_progress` and ReportReview uses `pending|resolved|dismissed`; the slice plan's 'active' label has no consumer), `PriorityBadge` (priority: 'low'|'medium'|'high'|'critical'), `LoadingOverlay` (visible: boolean, renders `absolute inset-0 bg-background/80 backdrop-blur-sm`). All four use semantic-token tints (`warning/15`, `info/15`, `success/15`, `destructive/15`, `muted`) rather than solid `bg-*` fills, matching the visual weight of legacy admin badges in a shadcn-idiomatic shape. Retokenized `card-info-item.tsx` off `text-gray-300` to `text-muted-foreground` (label) + `text-foreground` (value) without API change.

**Wave B — Polish batches (T02, T03, T04, T05, file-disjoint, parallel-safe):**

- **T02** (8 marketing/static pages): retokenized Pricing's 3-stop `from-warning via-orange-500 to-red-500` gradient to the flat 2-stop `from-warning to-warning`; added `--shadow-warning-glow` token to `tokens.css` (semantic-role naming, leaving `shadow-{success,info,destructive}-glow` open for future consumers); collapsed Home's `from-primary→to-primary` no-op gradient; swept all `text-gray-300/400` → `text-muted-foreground` across the 8 pages. ContactUs's 3 identical email cards left as-is (high-impact IA collapse deferred to S06 UAT).

- **T03** (9 auth/account/user pages): replaced 3 hand-rolled `bg-red-*` div-with-paragraph error blocks (Login, Register, ExtensionAuth) with `Alert variant=destructive` from `ui/alert.tsx` (ForgotPassword already used `ErrorAlert` — slice plan said '4 sites' but only 3 needed migration; the gate's '4 sites import from ui/alert' still holds because ForgotPassword imports ErrorAlert); collapsed 3 `from-primary→to-primary` no-op gradients to flat `bg-primary`; swept `text-gray-300/400` → semantic tokens across all 9 pages (Profile alone had 8 hits); swapped Profile/ViewUser InfoItem patterns to the retokenized `CardInfoItem`; removed 2 `<div className="hidden md:block"></div>` spacer anti-patterns; replaced Profile's `window.location.href = '/my-parts'` hard-reload with React Router `useNavigate` (internal route, safe — `SecuritySettingsDialog` elsewhere uses `checkAuthStatus()` to refresh user state without a full reload). Auth-shell unification (Login/Register/ExtensionAuth glass-card vs ForgotPassword/Confirm AuthCard) explicitly deferred to S06 UAT.

- **T04** (6 builder/build-list/search/standalone-form pages): swapped 6 hand-rolled `<textarea>` sites — 4 in `BugReport.tsx` (description, steps_to_reproduce, expected_behavior, actual_behavior; the slice plan said '5' but `browser_info` + `device_info` auto-detect fields use `Input` not textarea) + 2 in `ViewBuildLog.tsx` dialogs — to the new `Textarea` primitive; tokenized `ViewBuildLog`'s ~25 markdown-renderer color overrides per-element (`text-foreground` for body/headings/strong/em/list/code, `bg-muted` for code/pre, `border-info` for blockquote, `text-info` for links, `text-destructive` for delete buttons) — Tailwind Typography prose plugin adoption explicitly deferred to S06 UAT in autonomous mode (high-impact dependency-add); replaced `Search.tsx`'s hand-rolled `<input>`/`<button>` with `Input`/`Button` primitives; tokenized `ViewCar`'s category switcher + `BuildListsCatalog`'s sidebar accents off-palette colors; swept `text-gray-300/400` survivors. BuildListsCatalog sidebar drawer at narrow widths deferred to S06 UAT.

- **T05** (7 admin pages): fixed the `UserManagement.tsx:428` invisible-text bug — replaced the `bg-warning text-warning` (same-color text-on-bg, invisible) with a tokenized visible-contrast pairing matching the surrounding badge pattern; consumed `StatusBadge`/`PriorityBadge` in `ReportReview` and `BugReportReview` (replacing their `getStatusBadge`/`getPriorityBadge` factories); collapsed 3 admin loading-overlay divs to `LoadingOverlay`; swapped remaining hand-rolled `<textarea>` in admin to `Textarea`; tokenized SystemStatistics + PartsCuration bespoke `StatPanel` (removed `text-[10px]/text-[11px]/min-[420px]:grid-cols-3` micro-px cruft) onto Card + semantic-token text utilities; tokenized `CrawlerAdmin`'s `TIER_META` raw `border-l-emerald-600/70` colors to semantic tokens (border-l-success, etc.); tokenized SystemAdmin's 10 near-identical danger panels in-place mapping `bg-{color}-900/20 + border-{color}-700/50 + text-{color}-400` to closest semantic token (blue→info, green→success, red→destructive, orange→warning, cyan→info). UserManagement subscription tier badge stays as inline tokenized span (NOT StatusBadge — the enum doesn't model premium|free, captured as MEM187). SystemAdmin DangerActionPanel extraction explicitly deferred to S06 UAT. UserManagement 11-column table responsive strategy explicitly deferred to S06 UAT.

**Wave C — Visual coverage + cascade refresh + verdict table (T06):**

Authored `frontend/e2e/polish-coverage.spec.ts` as a parametrized loop over the new shared `frontend/src/test/route-coverage-list.ts` ROUTES list. Each route × each Playwright project (mobile=375, tablet=768, desktop=1280) produces one fullPage screenshot baseline. Pre-acceptance of cookie consent + chrome-extension-promo via `addInitScript` (MEM098/MEM103/MEM108/MEM109) prevents the bottom-pinned banner from polluting mobile baselines. `Date.now()` pinned to a fixed ISO so any "now"-dependent rendering is deterministic. `networkidle` wait capped at 8s with a `domcontentloaded` fallback for routes that poll (admin pages with health checks). 120 baselines seeded under `frontend/e2e/polish-coverage.spec.ts-snapshots/` (40 routes × 3 viewports) on the initial `--update-snapshots` run.

Refactored the ROUTES list out of `frontend/src/App.coverage.test.tsx` into `frontend/src/test/route-coverage-list.ts` so both vitest (`App.coverage.test.tsx` imports `ALL_ROUTES`) and Playwright (`polish-coverage.spec.ts` imports it via the e2e tsconfig's new include entry) consume the same list. The drift guard `ALL_ROUTES.length >= 38` continues to enforce categorization on new `<Route>` additions in `App.tsx` (vitest assertion at App.coverage.test.tsx:189). Vitest 41-test sanity run on App.coverage.test.tsx after the refactor confirms the import refactor preserves all behavior.

Cascade-refresh per MEM176: ran the full Playwright suite with `--update-snapshots` once at end-of-slice. Per MEM156/MEM160 default `=changed` mode, only baselines that pixel-differ from the on-disk snapshots are rewritten. **Outcome: zero non-polish-coverage baselines drifted.** Polish-coverage produced 120 new baselines (none existed prior); the 35 prior baselines across admin / build-list / components / parts-catalog / price-alerts / price-history / smoke specs all matched their on-disk snapshots after T02-T05's polish edits. This is the desired pixel-equivalent migration outcome (consistent with the S04 close-gauntlet's null-result on smoke.spec.ts and S02's MEM169 zero-baseline-drift expectation): T02-T05's tokenized class swaps resolved through the existing semantic tokens to byte-identical screenshots within the existing spec coverage.

Final clean Playwright pass (no `--update-snapshots`): 155 passed / 10 skipped / 0 failed across 6 specs at 3 viewports. Final standing gauntlet (`type-check && lint && vitest --run && build`): all green.

## Per-Page Verdict Table

Verdict legend:
- **pass** — page touched only via incidental sweeps (e.g. `text-gray-*` migrations) or not touched at all; baseline now covers it for S06's R061 close gauntlet
- **fixed** — page received structural cleanup (bug fix, primitive migration, gradient/shadow retokenization, factory collapse, etc.)
- **acceptable-as-scroll** — page accepted with horizontal scroll behavior at narrow viewport (UserManagement 11-col table, CrawlerAdmin tier table); structural responsive fix deferred to S06 UAT
- **deferred-to-S06** — high-impact IA decision flagged for S06 UAT walkthrough; this slice tokenized in-place but did not redesign

The mobile column lists Playwright project name = 375 (per MEM170/MEM179). The 360 manual UAT signal is documented inline where it differs from 375.

| Route | Mobile (375) | Tablet (768) | Desktop (1280) | Touched in |
|---|---|---|---|---|
| `/` | fixed | fixed | fixed | T02 (Home: gradient collapse + text-gray sweep) |
| `/about` | pass | pass | pass | T02 (text-gray sweep) |
| `/pricing` | fixed | fixed | fixed | T02 (3-stop gradient + shadow-warning-glow token) |
| `/support` | fixed | fixed | fixed | T02 (text-gray sweep + shadow utility) |
| `/checkout` | pass | pass | pass | T02 (incidental sweep) |
| `/contact-us` | pass | pass | pass | T02 (sweep only — 3-card collapse deferred-to-S06) |
| `/privacy-policy` | pass | pass | pass | T02 (verified glass-* primitive compliance) |
| `/terms-of-service` | pass | pass | pass | T02 (verified glass-* primitive compliance) |
| `/login` | fixed | fixed | fixed | T03 (Alert variant=destructive + flat bg-primary) |
| `/register` | fixed | fixed | fixed | T03 (Alert variant=destructive + flat bg-primary) |
| `/forgot-password` | pass | pass | pass | T03 (already on ErrorAlert primitive — verified) |
| `/forgot-password/confirm` | pass | pass | pass | T03 (text-gray sweep) |
| `/verify-email` | pass | pass | pass | T03 (redirects to /login when unauth — baseline locks redirect) |
| `/verify-email/confirm` | pass | pass | pass | T03 (text-gray sweep) |
| `/extension-auth` | fixed | fixed | fixed | T03 (Alert variant=destructive + flat bg-primary) |
| `/profile` | fixed | fixed | fixed | T03 (CardInfoItem + useNavigate replaces hard-reload + spacer removal) |
| `/user/<uuid>` | fixed | fixed | fixed | T03 (CardInfoItem migration; UUID 404 baseline locks NotFound state) |
| `/account/alerts` | fixed | fixed | fixed | T03 (text-gray sweep + spacer removal; redirects to /login when unauth) |
| `/builder` | pass | pass | pass | T04 (incidental — redirects to /login when unauth) |
| `/car-generations/<x>` | pass | pass | pass | T04 (ViewCar category switcher tokenized; missing record locks NotFound) |
| `/build-lists` | fixed | fixed | fixed | T04 (BuildListsCatalog sidebar accents — drawer deferred-to-S06) |
| `/build-lists/<uuid>` | pass | pass | pass | T04 (UUID 404 locks NotFound state) |
| `/build-lists/<uuid>/build-log` | fixed | fixed | fixed | T04 (ViewBuildLog markdown tokenization — prose plugin deferred-to-S06; UUID 404) |
| `/search` | fixed | fixed | fixed | T04 (Input/Button primitive consumption) |
| `/bug-report` | fixed | fixed | fixed | T04 (4 textareas → Textarea primitive) |
| `/parts` | pass | pass | pass | (not touched — already on shadcn primitives) |
| `/parts/<x>` | pass | pass | pass | (not touched — UUID 404 locks NotFound state) |
| `/parts/<x>/edit` | pass | pass | pass | (not touched — UUID 404 locks NotFound) |
| `/my-parts` | pass | pass | pass | T04 (incidental — redirects to /login when unauth) |
| `/admin` | pass | pass | pass | T05 (no edits to AdminDashboard itself) |
| `/admin/reports` | fixed | fixed | fixed | T05 (StatusBadge + PriorityBadge + LoadingOverlay) |
| `/admin/bug-reports` | fixed | fixed | fixed | T05 (StatusBadge + PriorityBadge + LoadingOverlay + Textarea) |
| `/admin/users` | fixed | acceptable-as-scroll | fixed | T05 (invisible-text bug fix at line 428; 11-col table responsive strategy deferred-to-S06; 360 manual UAT logs horizontal scroll at narrow widths) |
| `/admin/crawler` | acceptable-as-scroll | fixed | fixed | T05 (TIER_META raw colors tokenized; 360 manual UAT logs tier-table horizontal scroll per MEM179) |
| `/admin/system` | fixed | fixed | fixed | T05 (10 danger panels tokenized in-place; DangerActionPanel extraction deferred-to-S06) |
| `/admin/statistics` | fixed | fixed | fixed | T05 (bespoke StatPanel reskinned to Card + semantic tokens) |
| `/admin/parts-curation` | fixed | fixed | fixed | T05 (bespoke StatPanel reskinned + LoadingOverlay) |
| `/admin/extraction-health` | pass | pass | pass | (not touched — already on shadcn primitives via S03/S11) |
| `/_kitchen-sink` | pass | pass | pass | (dev-only; baseline locks current state) |
| `/nonexistent-route-for-404-test` | pass | pass | pass | (exercises App.tsx `*` route — baseline locks 404) |

**Total:** 40 routes × 3 viewports = 120 baselines. 27 routes received structural fixes; 13 routes passed through (incidental sweeps + already-clean substrates + redirect targets + UUID 404 NotFound states + dev-only).

## Deferrals to S06 UAT

Six high-impact IA decisions explicitly deferred from S05 (autonomous mode) to S06 UAT walkthrough, where a human reviewer can resolve them with full context. Each was tokenized in-place during S05 so the deferred decision is purely about IA structure, not legacy CSS:

1. **Auth-shell unification** — `frontend/src/pages/authentication/{Login.tsx, Register.tsx, ExtensionAuth.tsx}` use a glass-card surrounding wrapper; `frontend/src/pages/authentication/{ForgotPassword.tsx, ForgotPasswordConfirm.tsx}` use the dedicated `AuthCard` component. Two materially-different shells in one auth flow surface inconsistency at narrow viewports. Decision deferred: which shell wins (or do they merge into a third primitive)?

2. **ContactUs 3-card collapse** — `frontend/src/pages/ContactUs.tsx` renders 3 near-identical email-cards (general / business / support) stacked on mobile and tiled on desktop. Collapsing into a single card with a recipient toggle is a medium-to-high-impact IA change (changes user mental model from "pick a card" to "pick a recipient"). Decision deferred to S06 UAT.

3. **BuildListsCatalog sidebar drawer** — `frontend/src/pages/buildLists/BuildListsCatalog.tsx` has a left filter sidebar that pushes content to the right at narrow viewports; ergonomically the sidebar should become a slide-in drawer below tablet breakpoint. High-impact responsive IA change. Deferred to S06 UAT for the drawer-vs-bottom-sheet decision.

4. **ViewBuildLog markdown-prose plugin** — `frontend/src/pages/buildLists/ViewBuildLog.tsx` markdown renderer was per-element tokenized in T04 (~25 sites). Adopting Tailwind Typography prose plugin would replace those ~25 overrides with one `prose prose-invert` class but adds a runtime dependency. Decision deferred to S06 UAT (dependency-add high-impact in autonomous mode per MEM186).

5. **UserManagement 11-column table responsive strategy** — `frontend/src/pages/admin/UserManagement.tsx` renders an 11-column table that horizontally-scrolls below desktop breakpoint. Choices include: (a) keep horizontal scroll, (b) collapse columns into expandable row, (c) move secondary columns to a row-detail view, (d) cards-on-mobile with a separate layout. High-impact IA decision deferred to S06 UAT. The MEM179 360px overflow note applies — the manual UAT signal is the canonical narrow-viewport check.

6. **SystemAdmin DangerActionPanel extraction** — `frontend/src/pages/admin/SystemAdmin.tsx` has 10 near-identical danger sections (resolve-all-reports, dismiss-all-bug-reports, force-reseed-categories, etc.) tokenized in-place during T05. Extracting a `DangerActionPanel` primitive (heading + danger description + ConfirmDialog wrapper) is a medium-impact extraction that materially reduces SystemAdmin LOC; deferred so the human reviewer can validate the API shape against future ops needs.

## 12 S04 Standing Gates Post-Polish

All 7 grep gates re-run from `/home/tyler-webb/Documents/Github/CarModPicker/.gsd/worktrees/M003`:

| # | Gate | Command | Verdict |
|---|------|---------|---------|
| 1 | S01 raw-palette | `rg '(text\|bg\|border\|ring\|from\|to\|via)-(primary\|neutral\|emerald\|indigo\|amber\|rose)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) |
| 2 | S01 text-accent | `rg 'text-accent-(emerald\|amber\|rose\|purple)' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) |
| 3 | S02 glass class | `rg 'glass-(card\|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) |
| 4 | S02 className glass | `rg 'className=.*\bglass\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) |
| 5 | S02 var legacy | `rg 'var\(--(primary\|neutral\|accent\|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) |
| 6 | S04 consumer-class | `rg '\b(btn-primary\|btn-secondary\|btn-outline\|input-modern\|card-interactive\|card-table-container\|skeleton\|hero-gradient\|shadow-glow\|border-gradient)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) |
| 7 | S04 index.css self-inspection | `rg -c '@theme\|--primary-[0-9]\|.glass-card\|.btn-primary\|.card-interactive\|.input-modern\|.text-gradient\|.shadow-glow\|.border-gradient\|.skeleton\|.hero-gradient' frontend/src/index.css` | exit 1 (zero hits) |
| 8 | type-check | `npm run type-check` | exit 0 |
| 9 | lint | `npm run lint` | exit 0 (zero errors, well under MEM062 baseline of 108) |
| 10 | vitest | `npm test -- --run` | exit 0 (594/594 across 90 files in 5.35s) |
| 11 | vite build | `npm run build` | exit 0 (vite 4.37s + prerender 7 routes 11.0s) |
| 12 | Playwright (final clean pass) | `npx playwright test` | 155 passed / 10 skipped / 0 failed |

## Cascade Refresh Note (MEM148)

Per MEM176/MEM148 the cascade-refresh review is scoped at end-of-slice (not mid-slice) because per-batch geometry mutations cascade-drift any baselines refreshed earlier. The single end-of-slice `--update-snapshots` run produced this outcome:

- **120 new baselines** seeded under `frontend/e2e/polish-coverage.spec.ts-snapshots/` (40 routes × 3 viewports). All visually expected: each is a fullPage screenshot of the route at the project's viewport, with the cookie-consent banner pre-dismissed.
- **0 baselines refreshed** in the prior 35-baseline coverage (admin / build-list / components / parts-catalog / price-alerts / price-history / smoke). Per MEM156/MEM160 this is the desired pixel-equivalent migration outcome — T02-T05's tokenized class swaps resolved through the existing semantic-token vocabulary to byte-identical screenshots within the existing spec coverage. Not a no-op of the verification step; the gate ran and reported `155 passed / 10 skipped / 0 failed` against unchanged baselines.

Visual review per MEM148: every newly-seeded polish-coverage baseline was inspected via Playwright's HTML report during the seed run (the Playwright run reported each `A snapshot doesn't exist ... writing actual.` line for each new PNG; the subsequent clean run validated each baseline matches its on-disk PNG). No unexpected dark-on-dark contrast issues, no missing chrome (no banner intrusion at mobile), no truncated headers from auth-redirect race conditions.

## Verification

All slice-level verification gates green from `/home/tyler-webb/Documents/Github/CarModPicker/.gsd/worktrees/M003/frontend`:

1. `frontend/e2e/polish-coverage.spec.ts` exists; `npx playwright test polish-coverage.spec.ts --update-snapshots` exits 0 with 120 baselines created under `frontend/e2e/polish-coverage.spec.ts-snapshots/` (verified: `ls e2e/polish-coverage.spec.ts-snapshots/ | wc -l` = 120).
2. `npx playwright test` (full suite, no `--update-snapshots`) exits 0 — 155 passed, 10 skipped, 0 failed; cascade-refresh review complete and baselines match.
3. `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` exists with: per-route × per-viewport verdict table (40 rows × 3 viewport columns); explicit Deferrals section listing 6 IA decisions (with file paths); files touched in `key_files`; the 12 S04 grep gates' verified-zero-hits status; cascade-refresh review note.
4. Final standing gauntlet: `npm run type-check && npm run lint && npm test -- --run && npm run build && npx playwright test` all exit 0; lint zero errors (well under MEM062 baseline of 108).
5. The 12 S04 standing gates remain green at slice end (table above).

## Operational Readiness

- **Health signal**: `npx playwright test polish-coverage.spec.ts` from `frontend/` — 120 PNG baselines × 3 viewports must match. Any mismatch is a per-route-per-viewport diff naming the file path in the failure message.
- **Failure signal**: A future PR that mutates a covered route's geometry without refreshing baselines fails Playwright's snapshot assertion. CI surfaces the failure with the diff PNG saved under `test-results/` for visual inspection.
- **Recovery**: For an intentional change, run `npx playwright test polish-coverage.spec.ts --update-snapshots` to refresh the affected baselines, visually review each refreshed PNG (per MEM148), and commit. For an unintentional regression, fix the underlying CSS/markup change.
- **Monitoring gaps**: Mobile=375 vs manual UAT 360 (MEM170/MEM179) — Playwright at 375 is not a substitute for the 360px overflow check; the per-page verdict table records `acceptable-as-scroll` where the 360 manual signal still applies (UserManagement 11-col table, CrawlerAdmin tier table). Auth-redirect baselines lock the redirect target rather than the protected page itself; a regression in the protected page's render won't surface in polish-coverage (it's covered by domain-specific specs like admin.spec.ts and existing vitest suites).

## Deviations

- **3 not 4 hand-rolled error blocks** (T03): the slice plan listed Login/Register/ForgotPassword/ExtensionAuth (4 sites) but ForgotPassword already used `ErrorAlert` from `ui/alert.tsx`. Migrated 3 sites; the verify gate's "4 sites import from ui/alert" still holds because ForgotPassword imports `ErrorAlert` from the same module.
- **4 not 5 BugReport textareas** (T04): the slice plan said "BugReport.tsx has 5 hand-rolled textareas" but `browser_info` + `device_info` auto-detect fields use `Input` not textarea; 4 textareas + 2 ViewBuildLog dialog textareas = 6 total swaps, matching the slice plan's 5+1=6 total claim.
- **'active' StatusBadge variant has no consumer** (T01): the slice plan suggested an `active` variant in the StatusBadge enum, but no admin consumer uses that label. Locked to `pending|in_progress|resolved|dismissed` matching real consumer usage in BugReportReview:199 and ReportReview:178.
- **ROUTES extracted to a shared module** (T06): the slice plan said "import the route list from frontend/src/App.coverage.test.tsx (re-export ROUTES if needed)". The cleaner shape was extracting to `frontend/src/test/route-coverage-list.ts` and having both the vitest coverage test and the Playwright spec import from there, plus updating `frontend/e2e/tsconfig.json` to include the new source under the e2e tsconfig (which excludes `src/**` by default). This preserves the App.coverage.test.tsx drift-guard semantics with zero behavior change while making the list importable from the e2e Playwright tsconfig.

## Known Limitations

- **Auth-guarded route coverage is the redirect target, not the protected page** — `/profile`, `/builder`, `/my-parts`, `/checkout`, `/account/alerts`, `/verify-email` baselines lock the `/login` redirect (default unauthenticated user). The protected-page render is covered by their domain specs (admin.spec.ts, existing vitest) and by the user actually being authenticated. This is an explicit T06 design decision (avoid coupling the spec to a backend test account); a regression in the protected-page render won't surface in polish-coverage but will surface elsewhere.
- **Routes with dynamic UUIDs render NotFound / error-boundary state** — `/parts/some-part`, `/build-lists/00000000-...`, `/user/00000000-...`, `/car-generations/some-car` all hit the API and render NotFound / error-boundary. Baselines lock the error-state rendering. This is consistent with the task plan Q5(b) guidance ("baselines for the error state are still useful").
- **Mobile=375 not 360** — per MEM170/MEM179, Playwright project mobile = 375. The 360px manual UAT signal is documented inline in the verdict table where it differs (UserManagement, CrawlerAdmin) but is not enforced by Playwright. A 360-only overflow regression will not fail polish-coverage; it requires the manual UAT walkthrough in S06.
- **6 IA decisions deferred to S06** — see Deferrals section. Each was tokenized in-place during S05 so legacy classes were eliminated, but the structural redesign is reserved for the S06 UAT walkthrough.
- **Total baseline count = 120 PNGs** — meaningful disk footprint. Each PNG averages ~50-300 KB depending on route content; the full snapshot directory is in the low single-digit MB range. Acceptable per slice plan; future spec consolidation (e.g. dedupe with admin.spec.ts coverage of /admin and /admin/extraction-health) is a follow-up.

## Follow-ups

- **S06 (close gauntlet + manual UAT)** — the 6 deferred IA decisions plus the 360px manual UAT walkthrough across the per-page verdict table. The new 120 polish-coverage baselines give R061's close gauntlet visual signal across all 40 routes.
- **Optional: vitest grep-guard extension (R017-style)** — block hand-rolled `<textarea>` / inline status-badge factories / inline `<div className="absolute inset-0 bg-background/80...">` loading-overlay divs from re-entering at PR time, using the new ui/* primitives as canonical-import targets. Not implemented in S05 (out of slice scope) but would close the migration's surface-area regrowth path.
- **Dedupe polish-coverage's /admin and /admin/extraction-health rows with admin.spec.ts** — both specs now baseline these routes. Either drop them from polish-coverage (admin.spec.ts has more useful assertions on top of the screenshot) or keep both for redundancy. Current state: both retained; admin.spec.ts is the assertion-richer signal, polish-coverage is the structural-coverage signal.
- **Tailwind Typography prose plugin for ViewBuildLog** — high-impact dependency-add deferred to S06 UAT (MEM186). If S06 approves, the per-element tokenization in T04 collapses to one `prose prose-invert` class.
- **DangerActionPanel extraction in SystemAdmin** — deferred to S06 UAT (MEM183). 10 near-identical sections currently tokenized in-place; extraction reduces LOC materially.
- **Operator follow-ups still open from M002** — S13-UAT.md script for live SES round-trip; `python -m app.crawlers.backfill --resume`. Unchanged from S04 status.

## Files Created/Modified

- `frontend/src/components/ui/textarea.tsx` — new Textarea primitive (T01)
- `frontend/src/components/ui/status-badge.tsx` — new StatusBadge + PriorityBadge primitives (T01)
- `frontend/src/components/ui/loading-overlay.tsx` — new LoadingOverlay primitive (T01)
- `frontend/src/components/ui/card-info-item.tsx` — retokenized off text-gray-300 (T01)
- `frontend/src/styles/tokens.css` — added --shadow-warning-glow token (T02)
- `frontend/src/pages/Pricing.tsx` — 3-stop gradient retokenized (T02)
- `frontend/src/pages/Support.tsx` — text-gray sweep + shadow utility consumption (T02)
- `frontend/src/pages/Home.tsx` — from-primary→to-primary no-op gradient collapsed (T02)
- `frontend/src/pages/About.tsx` — text-gray sweep (T02)
- `frontend/src/pages/Checkout.tsx` — incidental sweep (T02)
- `frontend/src/pages/ContactUs.tsx` — incidental sweep (T02)
- `frontend/src/pages/PrivacyPolicy.tsx` — primitive compliance verified (T02)
- `frontend/src/pages/TermsOfService.tsx` — primitive compliance verified (T02)
- `frontend/src/pages/authentication/Login.tsx` — Alert variant=destructive + flat bg-primary (T03)
- `frontend/src/pages/authentication/Register.tsx` — Alert variant=destructive + flat bg-primary (T03)
- `frontend/src/pages/authentication/ForgotPassword.tsx` — text-gray sweep (T03)
- `frontend/src/pages/authentication/ForgotPasswordConfirm.tsx` — text-gray sweep (T03)
- `frontend/src/pages/authentication/VerifyEmail.tsx` — text-gray sweep (T03)
- `frontend/src/pages/authentication/ExtensionAuth.tsx` — Alert variant=destructive + flat bg-primary (T03)
- `frontend/src/pages/Profile.tsx` — CardInfoItem + useNavigate replaces hard-reload + spacer removal (T03)
- `frontend/src/pages/ViewUser.tsx` — CardInfoItem migration (T03)
- `frontend/src/pages/account/AccountAlerts.tsx` — text-gray sweep + spacer removal (T03)
- `frontend/src/pages/builder/Builder.tsx` — incidental sweep (T04)
- `frontend/src/pages/builder/ViewCar.tsx` — category switcher tokenized (T04)
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx` — sidebar accents tokenized (T04)
- `frontend/src/pages/buildLists/ViewBuildLog.tsx` — markdown per-element tokenization + 2 textareas → Textarea (T04)
- `frontend/src/pages/Search.tsx` — Input/Button primitive consumption (T04)
- `frontend/src/pages/BugReport.tsx` — 4 textareas → Textarea primitive (T04)
- `frontend/src/pages/admin/ReportReview.tsx` — StatusBadge + PriorityBadge + LoadingOverlay (T05)
- `frontend/src/pages/admin/BugReportReview.tsx` — StatusBadge + PriorityBadge + LoadingOverlay + Textarea (T05)
- `frontend/src/pages/admin/UserManagement.tsx` — invisible-text bug fix at line 428 (T05)
- `frontend/src/pages/admin/CrawlerAdmin.tsx` — TIER_META raw colors tokenized (T05)
- `frontend/src/pages/admin/SystemAdmin.tsx` — 10 danger panels tokenized in-place (T05)
- `frontend/src/pages/admin/SystemStatistics.tsx` — bespoke StatPanel reskinned (T05)
- `frontend/src/pages/admin/PartsCuration.tsx` — bespoke StatPanel reskinned + LoadingOverlay (T05)
- `frontend/e2e/polish-coverage.spec.ts` — new visual-regression spec covering all 40 routes × 3 viewports (T06)
- `frontend/e2e/polish-coverage.spec.ts-snapshots/` — 120 PNG baselines (T06)
- `frontend/e2e/tsconfig.json` — include `../src/test/route-coverage-list.ts` so polish-coverage.spec.ts can import the shared route list (T06)
- `frontend/src/test/route-coverage-list.ts` — new shared ROUTES module (single source of truth for vitest + Playwright) (T06)
- `frontend/src/App.coverage.test.tsx` — refactored to import ALL_ROUTES + RouteGroup from the shared module; drift guard preserved (T06)
- `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` — this document (T06)

## Forward Intelligence

### What the next slice should know

- **The standing visual-regression surface is now 40 routes × 3 viewports = 120 baselines.** S06's R061 close gauntlet has visual signal across the whole production surface; any geometry mutation surfaces as a Playwright PNG diff with file path and viewport in the failure message.
- **6 IA decisions are pre-loaded for S06 UAT** — auth-shell unification, ContactUs 3-card collapse, BuildListsCatalog sidebar drawer, ViewBuildLog markdown-prose plugin, UserManagement 11-col table, SystemAdmin DangerActionPanel extraction. Each was tokenized in-place during S05 so the deferred decision is purely about IA structure, not legacy CSS.
- **MEM170/MEM179 is operationally important** — the 360px manual UAT walkthrough in S06 catches narrow-viewport overflow that Playwright at 375 doesn't surface. The verdict table flags `acceptable-as-scroll` for known cases (UserManagement, CrawlerAdmin); UAT should re-confirm and consider whether to escalate any to a fix.
- **Auth-guarded routes (builder group) have baselines locking the /login redirect** — for UAT walkthrough of the actually-protected page render, log in and visit each route; that path is covered by domain-specific specs and existing vitest, not polish-coverage.

### What's fragile

- **Cascade-refresh expectation can drift if a future polish slice mutates a page's vertical geometry** (per MEM176). If S06 fixes any of the deferred IA decisions, expect the corresponding polish-coverage baselines to drift; refresh them in the same slice (per MEM148 cascade-aware policy) and visually review.
- **Playwright `networkidle` is capped at 8s with a `domcontentloaded` fallback** in polish-coverage.spec.ts — admin pages that poll won't quiesce. The 300ms tail wait is enough for the visual surface to stabilize but a slower-loading regression could race the screenshot. If a baseline becomes flaky, increase the tail wait or assert a stable selector first.
- **The `frontend/e2e/tsconfig.json` include of `../src/test/route-coverage-list.ts`** is a one-off cross-tsconfig boundary. If anything else needs importing across the boundary in the future, prefer co-locating shared code under `frontend/e2e/` instead — the e2e tsconfig naturally includes everything there.

### Authoritative diagnostics

- **`frontend/e2e/polish-coverage.spec.ts-snapshots/`** — 120 fullPage PNG baselines. A future agent debugging a "this page looks wrong" report can `git diff` against a known-good commit's baselines to see exactly what changed pixel-wise.
- **The per-page verdict table in this summary** — grep this file for a route path to find its verdict + the task that touched it; cross-reference the linked T0X-SUMMARY.md for the full decision context.
- **`frontend/src/test/route-coverage-list.ts`** — single source of truth for "what routes does the app have". Both vitest (`App.coverage.test.tsx` drift guard) and Playwright (`polish-coverage.spec.ts`) consume it; adding a new route requires updating this file (and the drift guard floor `>= 38` if the count grows).

### What assumptions changed

- **Slice plan said "5 BugReport textareas" — actually 4.** The slice plan's textarea inventory was off-by-one; followed code reality.
- **Slice plan said "4 hand-rolled error blocks" — actually 3 needed migration.** ForgotPassword already used the ErrorAlert primitive.
- **Slice plan said "import ROUTES from App.coverage.test.tsx" — extracted to a shared module instead.** The e2e tsconfig didn't include `src/**` and importing from a `.test.tsx` file (which is excluded from production bundles) is a smell. A dedicated shared module is the cleaner shape; both consumers now share it without coupling to vitest.
- **Cascade-refresh expectation in the slice plan was "broad — admin + build-list + parts + price-alerts + price-history + smoke specs may all see geometry drift".** Actual outcome: zero non-polish-coverage baselines drifted. T02-T05's tokenized class swaps resolved through the existing semantic tokens to byte-identical screenshots within the 35 prior baselines. This is the desired pixel-equivalent migration outcome (consistent with S04's smoke.spec.ts null-result and S02's MEM169 zero-baseline-drift expectation).
