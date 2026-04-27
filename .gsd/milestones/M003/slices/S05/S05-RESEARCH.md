# Slice S05 Research: Page-by-page polish pass at three breakpoints

**Slice intent:** Visit all ~40 routes at 360 / 768 / 1280, apply structural cleanup (layout fixes, redundant block collapses up to medium-impact, off-palette stat-panel reskins, animation replacements), surface high-impact IA decisions for user approval, refresh Playwright baselines per slice for every page touched. First slice operating against the clean post-S04 substrate (`index.css` 94 lines, no legacy CSS layer).

**Active requirements owned/supported:**
- **R059 (owner)** — Polish pass at 3 breakpoints across ~40 routes; per-page verdict in slice summary
- **R056 (supports)** — No unintended page-level horizontal scroll at 360/768/1280
- **R058 (supports)** — All outbound retailer links use `target=_blank rel="noopener noreferrer"` + ExternalLink icon (extends S03's ViewPart/PartsCuration coverage to any new outbound surfaces surfaced by polish)
- **R060 (supports)** — Per-slice baseline refresh for every page touched

## Summary

S05 is a **structured visit-and-polish pass**, not a single mechanical sweep. It has two halves:

1. **High-yield judgment work** on pages that audit identified as heavy off-palette / structural-smell concentrations (CrawlerAdmin 3240 LOC, SystemStatistics bespoke `StatPanel`, three admin pages duplicating `getStatusBadge`/`LoadingOverlay`, Profile/ViewUser/ViewBuildLog with ~40 legacy `gray-300/400` survivors, auth pages split across two design vocabularies, ContactUs 3-identical-cards, etc.).

2. **Coverage backfill** — 33 of 39 prod routes have **zero** Playwright visual baselines today. R060 (per-slice baseline refresh for every page touched) only triggers when a page is touched; pages whose only S05 work is "look at it, decide it's clean" need new baselines added so S06's gauntlet has something to re-run. The slice cannot literally "visit every route at 3 viewports" without harness support — the planner must decide whether to (a) author a single-purpose `polish-coverage.spec.ts` that screenshots every route at 3 viewports, accepting baseline-refresh churn but gaining coverage; or (b) only refresh baselines for pages with code changes and record the rest as visual-only review (matching S03's autonomous-mode static-audit pattern, MEM172).

**Recommendation:** Option (a) — add a `polish-coverage.spec.ts` that screenshots all touched routes at 3 viewports. Without it, S06's R061 close gauntlet has no visual signal for the 33 unbaselined routes. Per-page verdict list in slice summary becomes the authoritative qualitative record paired with the new baselines.

The audit identified **9 natural batches** of pages with shared work; planning each as one task (with the cross-cutting components — `<Textarea>`, `<StatusBadge>`, `<LoadingOverlay>`, `<DangerActionPanel>`, `<InfoItem>`, canonical auth shell — extracted in dedicated tasks before consumer batches) is the cleanest decomposition.

## Recommendation

**Decompose S05 into ~12-14 tasks across three waves:**

**Wave A — Component extractions (block consumer batches; can run in parallel with each other):**
- `<Textarea>` primitive (consumed by Batches 5, 6, 7 — ViewBuildLog, BugReport, ReportReview, BugReportReview, UserManagement)
- `<StatusBadge variant>` + `<PriorityBadge>` (consumed by Batch 7)
- `<LoadingOverlay>` (consumed by Batch 7)
- `<InfoItem>` extraction from Profile (consumed by Batch 4)
- Canonical auth-shell decision: surface to user before Batch 3 starts (high-impact IA per R059)

**Wave B — Per-page polish batches (parallel where independent):**
- Batch 1: Marketing hero/animation cleanup (Home, About, Pricing, Support, Checkout) — collapse animation cascades, replace `from-warning via-orange-500 to-red-500` triple-stop, fix `shadow-[0_0_40px_rgba(...)]` raw rgba
- Batch 2: Static legal/contact (PrivacyPolicy, TermsOfService, ContactUs) — inline glass-card → `<Card variant="glass">`; ContactUs 3-identical-cards collapse (medium-impact, surface for approval)
- Batch 3: Auth flow unification (7 pages) — pick Login/Register/ExtensionAuth or AuthCard vocabulary; replace 4 hand-rolled error blocks with `<ErrorAlert>`; remove 4 `from-primary to-primary` no-op gradients
- Batch 4: Profile/account/user (Profile, ViewUser, AccountAlerts) — ~40 legacy gray migrations; remove `<div className="hidden md:block"></div>` spacer anti-pattern (3 sites); fix Profile's `<ConfirmationAlert>`-as-badge misuse and `window.location.href` hard-reload
- Batch 5: Build catalog + log content (BuildListsCatalog, ViewBuildLog, ViewCar) — ViewBuildLog markdown-renderer color overrides (~25); ViewCar category switcher off-palette; sidebar overflow-at-narrow IA decision (high-impact, surface)
- Batch 6: Search + standalone forms (Search, BugReport) — Search's hand-rolled input/button → `<Input>`/`<Button>`; BugReport 5 hand-rolled textareas → `<Textarea>`; consolidate Search's 3-section result blocks (medium-impact)
- Batch 7: Admin form-and-table reskin (ReportReview, BugReportReview, UserManagement) — consume `<StatusBadge>`/`<LoadingOverlay>`/`<Textarea>`; fix `bg-warning text-warning` invisible-text bug in UserManagement.tsx:428; UserManagement 11-column table responsive strategy (high-impact, surface)
- Batch 8: Admin stat panels reskin (SystemStatistics, PartsCuration) — the slice's explicit "off-palette stat panels reskinned" target; bespoke `StatPanel`/`StatRow` with `text-[10px]`/`text-[11px]` and `min-[420px]:grid-cols-3` micro-breakpoints
- Batch 9: CrawlerAdmin solo (3240 LOC, 69 raw bg colors, custom `TIER_META` mixing semantic tokens with raw `border-l-emerald-600/70`)
- Batch 10: SystemAdmin solo (10 near-identical "delete all X" panels — extract `<DangerActionPanel>` if user approves, otherwise tokenize in-place)

**Wave C — Coverage backfill + close gauntlet:**
- Batch 11: Add `polish-coverage.spec.ts` screenshotting every touched route at 3 viewports; baseline-refresh all touched pages; review every PNG diff against expected token-swap deltas (per R060 cadence, MEM170/MEM176 cascade-aware)
- Batch 12: S05 slice summary with per-page verdict list (pass / fixed / acceptable-as-scroll / surfaced-for-approval) for all ~40 routes

**Why this order:** Component extractions land first as atomic commits with rationale (per the milestone's "token / primitive additions are atomic commits" decision). Page batches can run in parallel — they touch disjoint files. Coverage backfill is intentionally last because the geometry mutations from per-page polish (e.g. removing animation cascades, collapsing redundant blocks) will cascade-drift any baselines refreshed mid-slice (MEM176 pattern from S03). Refreshing once at end-of-slice keeps reviews bounded.

**High-impact IA decisions to surface BEFORE planning starts (or at the start of their respective batches):**
1. **Canonical auth shell** — Login/Register/ExtensionAuth use inline glass cards + iconified inputs + `animate-float` orbs; ForgotPassword/Confirm/VerifyEmail use `<AuthCard>`/`<AuthForm>`/`<AuthRedirectLink>`. Pick one. (Drives Batch 3.)
2. **ContactUs 3-card collapse** — three identical cards all linking to the same email with hero-sized `<h2>` treatment. Locked exemplar (ViewPart) collapsed similar redundancy. Approve-or-skip.
3. **BuildListsCatalog sidebar at narrow widths** — entire 40-control filter sidebar renders before main content at 360/768. Drawer or accordion is medium-to-high impact.
4. **ViewBuildLog markdown renderer** — ~25 hardcoded color overrides; possibly warrants Tailwind Typography plugin (`prose` classes) or a shared `<MarkdownContent>` component. Adding `prose` is a dependency decision.
5. **UserManagement 11-column table** — 11 columns wrapped in `overflow-x-auto`; at 360 this is unusable. Card layout for narrow viewports, or column-hide breakpoints, or "open in detail dialog" — pick a strategy.

## Implementation Landscape

### Route × viewport coverage today (post-S04)

| Project | Width × Height | S05 breakpoint mapping |
|---|---|---|
| `mobile`  | 375 × 667 | 360 (closest — see MEM179) |
| `tablet`  | 768 × 1024 | 768 (exact) |
| `desktop` | 1280 × 800 | 1280 (exact) |

Routes with full 3-viewport visual baselines today (5 of 39 prod routes): `/parts`, `/parts/:id`, `/build-lists/:id`, `/admin`, `/admin/extraction-health` (plus dev-only `/_kitchen-sink`).

Routes with **zero** visual baselines (33 prod routes): `/`, `/about`, `/privacy-policy`, `/terms-of-service`, `/contact-us`, `/support`, `/pricing`, `/bug-report`, `/search`, `/user/:userId`, `/verify-email/confirm`, `/forgot-password/confirm`, `/extension-auth`, `/car-generations/:carId`, `/build-lists/:buildListId/build-log`, `/build-lists`, `/parts/:partId/edit`, `*` (NotFound), `/login`, `/register`, `/forgot-password`, `/verify-email`, `/profile`, `/account/alerts`, `/builder`, `/my-parts`, `/checkout`, `/admin/reports`, `/admin/bug-reports`, `/admin/users`, `/admin/crawler`, `/admin/system`, `/admin/statistics`, `/admin/parts-curation`. The canonical route list lives at `frontend/src/App.coverage.test.tsx:140–192` — reuse it for `polish-coverage.spec.ts`.

### Files certain to be touched (audit findings, file:line refs)

**Marketing & static (Batch 1, 2):**
- `frontend/src/pages/Home.tsx` — lines 139, 141, 151, 156, 204, 249, 318, 386, 387–413
- `frontend/src/pages/About.tsx` — lines 29, 37, 45, 52, 63, 71, 79, 87, 97, 101, 104, 127–135, 164, 179–180, 206, 220–221
- `frontend/src/pages/Pricing.tsx` — lines 59, 91, 126, 132, 192–207, 195, 228–266
- `frontend/src/pages/Support.tsx` — lines 68, 135, 141, 153–212, 158, 215–231
- `frontend/src/pages/Checkout.tsx` — lines 26, 28, 69, 102–103
- `frontend/src/pages/ContactUs.tsx` — lines 17, 33–57, 37, 59–82, 63, 85–108, 89
- `frontend/src/pages/PrivacyPolicy.tsx` — line 17
- `frontend/src/pages/TermsOfService.tsx` — line 18

**Auth (Batch 3):**
- `frontend/src/pages/authentication/Login.tsx` — lines 161, 163, 169, 173, 198, 224, 264, 303, 304–305
- `frontend/src/pages/authentication/Register.tsx` — lines 75, 81, 85, 222, 230–232, 304
- `frontend/src/pages/authentication/ForgotPassword.tsx` — lines 46–50, 83–87
- `frontend/src/pages/authentication/ForgotPasswordConfirm.tsx` — (compare-shell decision)
- `frontend/src/pages/authentication/VerifyEmail.tsx` — line 69 (`text-gray-300` survivor)
- `frontend/src/pages/authentication/ExtensionAuth.tsx` — lines 157, 160, 176–179, 188–197

**Account/builder (Batch 4, 5):**
- `frontend/src/pages/account/AccountAlerts.tsx` — lines 75, 81, 89, 104, 222–243, 227, 239, 270
- `frontend/src/pages/Profile.tsx` — lines 25–32 (extract InfoItem), 28, 29, 99, 118, 193–210, 214, 223, 227, 236, 239, 266, 277, 350, 351, 367
- `frontend/src/pages/ViewUser.tsx` — lines 98–148, 99–120, 113
- `frontend/src/pages/builder/Builder.tsx` — lines 140, 153
- `frontend/src/pages/builder/ViewCar.tsx` — lines 118–148, 161, 244, 246–273, 292–303, 297
- `frontend/src/pages/buildLists/BuildListsCatalog.tsx` — lines 440, 443, 476, 487–514, 521, 524–542, 607, 625, 631
- `frontend/src/pages/buildLists/ViewBuildLog.tsx` — lines 290–298, 302–318, 330, 341, 363–453, 462, 471, 483–497, 523–540, 610–617

**Search & forms (Batch 6):**
- `frontend/src/pages/Search.tsx` — lines 332, 341, 372–414, 419–458, 462–485, 494, 496–501, 510, 511–517
- `frontend/src/pages/BugReport.tsx` — lines 187, 241–308

**Admin (Batches 7, 8, 9, 10):**
- `frontend/src/pages/admin/ReportReview.tsx` — lines 178–192, 215–239, 256, 418–425
- `frontend/src/pages/admin/BugReportReview.tsx` — lines 199–213, 216, 257–315, 333, 354–476, 566–573
- `frontend/src/pages/admin/UserManagement.tsx` — lines 339, 345, 346–485, **428 (invisible-text bug: `bg-warning text-warning`)**, 510–752, 597–671, 678, 695
- `frontend/src/pages/admin/CrawlerAdmin.tsx` — lines 95–146, 111, 121, 131, 141, 185, 322, 740, 1556 (and pervasive)
- `frontend/src/pages/admin/SystemAdmin.tsx` — pervasive (10 near-identical danger panels; 18 raw bg colors)
- `frontend/src/pages/admin/SystemStatistics.tsx` — lines 55–131, 133–161, 504, 566, 665, 702, 727
- `frontend/src/pages/admin/PartsCuration.tsx` — lines 50–148, 84, 91, 99, 110

### Files to create

- `frontend/src/components/ui/textarea.tsx` — tokenized textarea primitive (consumed by 5 sites)
- `frontend/src/components/ui/status-badge.tsx` — `variant="pending|active|resolved|dismissed"` + `priority="low|medium|high|critical"` (consumed by 3 admin pages; replaces 3 copy-pasted `getStatusBadge` factories)
- `frontend/src/components/ui/loading-overlay.tsx` — `<div className="absolute inset-0 bg-...backdrop-blur-sm">` (consumed by 3 admin pages identically)
- `frontend/src/components/ui/info-item.tsx` — extract from `Profile.tsx:25–32` (consumed by Profile, ViewUser, ViewCar)
- `frontend/src/components/admin/danger-action-panel.tsx` — *if user approves SystemAdmin extraction* (would deduplicate 10 sections × ~80 LOC each)
- `frontend/e2e/polish-coverage.spec.ts` — `for each route in ROUTES { for each viewport { goto + screenshot } }`. Reuses `App.coverage.test.tsx` route list (lines 140–192). Preserves the `mobile=375` reality (MEM170/MEM179) — do NOT override to 360.

### Files to update

- `frontend/src/styles/tokens.css` — possibly add `--shadow-warning-glow` token to replace Pricing's `shadow-[0_0_40px_rgba(251,191,36,0.15)]`; add a tokenized `text-gradient-warning` `@utility` if Batch 1 needs more than the existing primary-stop gradient
- `frontend/playwright.config.ts` — leave the `mobile=375` project unchanged. The slice's "360" target is documented per MEM179 as a manual UAT signal; baselines run at 375. Do NOT widen — `mobile=375` is what every existing baseline assumes; changing to 360 would force a mass refresh of every baseline AND produce a falsely-narrower viewport that doesn't match any iOS device width

### Files NOT to touch (audit confirmed clean)

- `frontend/src/pages/parts/UserParts.tsx`
- `frontend/src/pages/parts/EditPart.tsx` (functional; 5 guard branches are minor, not slice scope)
- `frontend/src/pages/authentication/VerifyEmailConfirm.tsx`
- `frontend/src/pages/builder/ViewPart.tsx` (S03 already collapsed)
- `frontend/src/pages/parts/PartsCatalog.tsx` (S03 audited; baselines already current)
- `frontend/src/pages/builder/ViewBuildlist.tsx` (baselines already current)
- `frontend/src/pages/admin/AdminDashboard.tsx` and `frontend/src/pages/admin/ExtractionHealth.tsx` (baselines current)

### Substrate inventory (post-S04)

`frontend/src/index.css` (94 lines, surviving rules only):
- `@import` Tailwind + tokens
- `*` box-sizing reset
- `body` (tokenized via `hsl(var(--background/foreground))`, `background-attachment: fixed`)
- `::-webkit-scrollbar*` (3 rules; **NOT tokenized** — uses raw `rgba(255,255,255,*)`. Candidate for tokenization if S05 wants 100% discipline, otherwise leave as MEM181-style cosmetic survivor)
- `*:focus-visible` (tokenized via `hsl(var(--ring))`, MEM151)
- `::selection` / `::-moz-selection` (tokenized)
- `.global-parts-table-scroll-layer` (GPU compositor hint)
- `.main-content .container` (`max-width: 100%` for ad-column gap fill)
- `.tile-grid` / `.tile-grid-compact` (`auto-fill, minmax(min(100%, 260px), 1fr)`)

`frontend/src/styles/tokens.css` (349 lines):
- `:root` token block (lines 5–58) — surfaces, brand, semantic, borders, radius, shadow, z-index
- `@theme` Tailwind v4 bridge (lines 64–117)
- Overlay-animation primitives (Radix-driven, lines 119–240) — `enter`/`exit` keyframes + `animate-in`/`animate-out` driver utilities + `fade-in-*`/`zoom-in-*`/`slide-in-from-*`/`slide-out-to-*` + `duration-200`/`duration-300`
- Legacy decorative `@keyframes` (lines 242–309) — `fadeInScale`, `slideInUp`, `slideInLeft`, `float`, `glow` (gradientShift was deleted in S04)
- Legacy decorative `@utility` blocks — `animate-fadeInScale`, `animate-slideInUp`, `animate-slideInLeft`, `animate-float`, `animate-glow`
- Legacy `@utility text-gradient` (lines 343–349) — `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`. Colors hard-coded (legacy `--gradient-primary` was deleted in S04). Used by ~25 sites.

## Don't Hand-Roll

- **Don't override `playwright.config.ts` mobile project to 360.** Per MEM179, mobile project runs at 375; "360" is a documented manual UAT signal, not a Playwright assertion target. Changing it cascade-drifts every existing baseline (24 PNGs) and produces a viewport narrower than every iOS device width.
- **Don't refresh baselines mid-slice.** Per MEM176 cascade pattern from S03, vertical-geometry mutations (collapsing animation stagger sections, removing redundant cards, etc.) will drift any spec that fullPage-screenshots an affected route. Refresh once at end-of-slice (Batch 11), review all PNG diffs together against expected token-swap deltas.
- **Don't extract a `<Textarea>` per-batch.** Five sites consume it; one shared primitive in `components/ui/textarea.tsx` (Wave A) lands as one atomic commit with rationale per the milestone's "primitive additions are atomic commits" decision. Same logic for `<StatusBadge>` and `<LoadingOverlay>`.
- **Don't use `git revert` on a polish batch's commit chain to undo a baseline drift.** Per MEM170 + MEM176, baselines often drift for legitimate reasons (1px font-rendering tweak, color-stop adjust); review the PNG diff first, accept if expected, refresh-only if a regression.
- **Don't introduce new `animate-pulse` decorative usages.** S04 deleted the legacy `.animate-pulse` rule because Tailwind v4's built-in is byte-identical. New consumers fall through cleanly, but adding more pulse decoration on a polish pass is "design noise" creep — judge sparingly.
- **Don't skip `<Card variant="glass">` in favor of inline glass markup.** PrivacyPolicy/TermsOfService/Login/Register/ExtensionAuth/NotFound all hand-build the same `border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl` pattern instead of using the `Card` primitive. Migrating to the primitive is the cleanest token discipline win in the slice.

## Questions / Open Decisions for Planner

1. **Coverage spec or no?** Option (a) `polish-coverage.spec.ts` screenshotting all touched routes at 3 viewports gives R061 visual signal; option (b) qualitative-only verdict list per MEM172/S03 pattern. **Recommend (a)** — without it, S06's R061 close gate has no visual signal for 33 of 39 routes.
2. **Component extraction order vs page batches** — Wave A first (extractions), then Wave B (consumer batches in parallel)? Or extract just-in-time per batch? **Recommend Wave A first** — atomic commits with rationale per milestone-level decision; consumer batches reference the new primitives by import.
3. **Mobile project pixel width** — confirm staying at 375 (MEM179) and treating "360" as a documented manual-UAT signal. **Recommend confirm 375.**
4. **High-impact IA decisions** — should the 5 listed IA decisions (auth shell, ContactUs collapse, BuildListsCatalog sidebar, ViewBuildLog markdown renderer, UserManagement 11-col table) be batched into a single user-facing approval question at slice start, or interleaved per-batch? **Recommend single approval gate at slice start** — discussion-mode parity with M002's "decide all gray-area before planning" pattern (MEM107).

## Verification

How a planner can verify the slice succeeded:

```bash
# 1. Standing grep gates (12 from S04 still apply; should remain green)
cd frontend
rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/{components,pages,contexts,hooks,api,lib,__tests__}/  # exit 1 expected
rg 'text-accent-(emerald|amber|rose|purple)' src/{components,pages,contexts,hooks,api,lib,__tests__}/  # exit 1 expected
rg 'glass-(card|button)?' src/{components,pages,contexts,hooks,api,lib,__tests__}/  # exit 1 expected
rg 'var\(--(primary|neutral|accent|gradient)-' src/{components,pages,contexts,hooks,api,lib,__tests__}/  # exit 1 expected (in consumer dirs)

# 2. New S05-specific gates (planner should add to slice plan)
# 2a. No raw `text-gray-{200,300,400,500}` in pages/ (was 40+ instances pre-slice)
rg 'text-gray-(200|300|400|500)' frontend/src/pages/  # near-zero expected post-slice
# 2b. No hand-rolled `bg-(red|green|yellow|blue|orange|purple)-{500,600,700,900}` in pages/admin
rg 'bg-(red|green|yellow|blue|orange|purple)-(500|600|700|900)' frontend/src/pages/admin/  # near-zero expected
# 2c. No hand-rolled inline glass markup (`bg-white/5.*backdrop-blur-xl.*rounded-2xl`)
rg 'bg-white/5.*backdrop-blur-xl' frontend/src/pages/  # zero expected (use Card variant=glass)
# 2d. No raw rgba in shadow utilities
rg 'shadow-\[0_0_.*rgba\(' frontend/src/  # zero expected

# 3. Build / type-check / lint / vitest still green
cd frontend && npm run build  # exit 0
cd frontend && npm run type-check  # exit 0
cd frontend && npm run lint  # exit 0 (under MEM062 baseline of 108)
cd frontend && npm test -- --run  # 594+ tests pass

# 4. Playwright cascade refresh + clean run
cd frontend && npx playwright test --update-snapshots  # exit 0; PNG diffs reviewed individually
cd frontend && npx playwright test  # exit 0 — 35+ pass at 3 viewports

# 5. Per-page verdict list in S05 slice summary covers all ~40 routes
# (Manual review — slice summary must show pass/fixed/acceptable-as-scroll/surfaced for every route in App.coverage.test.tsx ROUTES list)
```

## Skills Discovered

- `make-interfaces-feel-better` — already installed at `/home/tyler-webb/.agents/skills/make-interfaces-feel-better/SKILL.md`. Directly applicable to "polish pass" work — covers stagger animations, optical alignment, font smoothing, tabular numbers. Reference during page batches.
- `userinterface-wiki` — already installed; covers animation principles, CSS, typography, prefetching, icon implementations. Reference for animation-replacement decisions.
- `accessibility` — already installed; relevant for the focus-ring / `*:focus-visible` review surfacing in polish (R020 must not regress).
- `web-design-guidelines` — already installed; relevant for the per-page verdict capture format.

No new skill installations needed — all skills relevant to S05 are pre-installed.

## Sources

- `frontend/src/App.tsx` — route table (39 prod routes + dev kitchen-sink + 404)
- `frontend/src/App.coverage.test.tsx:140–192` — canonical ROUTES list for the polish-coverage spec
- `frontend/playwright.config.ts` — mobile=375, tablet=768, desktop=1280; `maxDiffPixelRatio: 0.002`, `animations: 'disabled'`
- `frontend/src/index.css` (94 lines) and `frontend/src/styles/tokens.css` (349 lines) — substrate inventory
- `.gsd/milestones/M003/slices/S03/S03-SUMMARY.md` — MEM170 (mobile=375 not 360), MEM172 (static-audit substitute), MEM176 (cascade-baseline-refresh), MEM179 (360-as-manual-UAT-signal)
- `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md` — MEM181 (`@utility` composes with state variants), MEM182 (whole-file Write for multi-block CSS deletions)
- `.gsd/REQUIREMENTS.md` — R054–R061 active set; S05 owns R059, supports R056/R058/R060
- M003 milestone context "IA judgment up to medium-impact, surface for high-impact" decision — drives the 5 high-impact IA decisions surface-for-approval list
- M003 milestone context "Token / primitive additions are atomic commits" decision — drives Wave A (component extractions) before Wave B (consumer batches)
- M003 milestone context "Refresh visual-regression baselines per slice" decision — drives Wave C (single end-of-slice baseline refresh, not per-batch)
