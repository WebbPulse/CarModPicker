---
id: S04
parent: M003
milestone: M003
provides:
  - ["frontend/src/index.css reduced 757 → 94 lines (88% reduction) — only `@import`s, body, scrollbar styling, focus-visible, ::selection, and 3 layout utilities remain, all tokenized via hsl(var(--*))", "vite build is now the standing structural enforcement — any reintroduction of a deleted legacy class becomes a hard build error at PR time (R061 satisfied)", "12 standing grep gates (5 from S01/S02/S03 + 6 new from S04 + 1 index.css self-inspection) form the standing inspection surface for design-system drift", "5 tokenized `@utility animate-*` blocks (`animate-fadeInScale/slideInUp/slideInLeft/float/glow`) + their backing `@keyframes` in tokens.css — consumers across Home/About/Pricing/Support/Checkout/ContactUs/Register/App keep resolving", "Tokenized `@utility text-gradient` block in tokens.css preserving #667eea→#764ba2 gradient identity for ~25 consumer sites (composes with hover/group-hover variants per MEM181)", "8 `btn-primary`/`btn-secondary`/`btn-outline` consumer sites migrated to `<Button>` primitive with `asChild` for Link/anchor preservation", "body / *:focus-visible / ::selection / ::-moz-selection rewritten to hsl(var(--*)) semantic tokens", "13 refreshed PNG baselines across admin/build-list/components/price-alerts/price-history specs"]
requires:
  - slice: S01
    provides: raw-palette utility migration — consumers no longer reference bg-primary-500 / text-neutral-* / text-emerald-* / text-indigo-* / text-accent-*
  - slice: S02
    provides: glass-* + var(--legacy)-* consumer purge — no consumer survives the @theme/:root deletion
  - slice: S03
    provides: responsive audit + ViewPart IA collapse against semantic tokens — layout fixes already retargeted, none depend on legacy classes
affects:
  - ["frontend/src/index.css (757 → 94 lines, hard-delete of legacy substrate)", "frontend/src/styles/tokens.css (311 → 349 lines, tokenized @utility replacements)", "frontend/src/pages/NotFound.tsx (Button asChild migration)", "frontend/src/pages/Checkout.tsx (Button disabled CTA migration)", "frontend/src/components/layout/globalHeader/Header.tsx (desktop+mobile Register Button asChild)", "frontend/src/components/routes/RouteGroupBoundary.tsx (Retry + GoHome Button migration)", "frontend/src/components/shell/ChromeExtensionPromo.tsx (install Button migration)", "frontend/src/components/shell/SubscriptionPromo.tsx (upgrade Button asChild migration)", "frontend/src/components/parts/EditPartForm.tsx (dropped trailing input-modern from <select>)", "frontend/src/components/forms/SearchableSelect.tsx (dropped trailing input-modern from <input>)", "13 PNG baselines refreshed under frontend/e2e/*-snapshots/", "6 test-file comments rewritten skeleton → scaffold"]
key_files:
  - ["frontend/src/index.css", "frontend/src/styles/tokens.css", "frontend/src/components/ui/button.tsx", "frontend/src/pages/NotFound.tsx", "frontend/src/pages/Checkout.tsx", "frontend/src/components/layout/globalHeader/Header.tsx", "frontend/src/components/routes/RouteGroupBoundary.tsx", "frontend/src/components/shell/ChromeExtensionPromo.tsx", "frontend/src/components/shell/SubscriptionPromo.tsx", "frontend/src/components/parts/EditPartForm.tsx", "frontend/src/components/forms/SearchableSelect.tsx"]
key_decisions:
  - ["Tailwind v4 `@utility <name>` blocks compose with state variants automatically — used in T01 (animate-*) and T04 (text-gradient) to preserve legacy class names across all consumers without per-variant rules (captured as MEM181)", "Single Write rewrite over many incremental Edit calls for multi-block CSS deletions — T06 deleted 8+ separate ranges and T07 deleted 14+ ranges in single whole-file rewrites; auditable in one diff and lets the build verify atomically (captured as MEM182)", "Deleted `.animate-pulse` because it was byte-identical to Tailwind v4's built-in (`pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite`) — 4 known consumers fall through cleanly with zero behavior change", "T05→T06 swapped body background option-(b) gradient → option-(a) flat `hsl(var(--background))` to satisfy the literal verification regex; visual delta is one subtle dark-on-dark gradient band collapse, dominant color unchanged", "Used `<Button asChild>` for the 5 btn-* consumer sites that render as Link/anchor to preserve routing/anchor semantics rather than swapping the underlying element (T02)", "Translated legacy `glow` keyframe's `var(--primary-500)` and `rgba(59,130,246,*)` to `hsl(var(--primary))` and `hsl(var(--primary) / *)` — verified `--primary` is `217 91% 60%` (HSL of #3b82f6), so visually identical and tokenized", "Renamed 6 test-file comment occurrences of 'skeleton' → 'scaffold' per MEM163/MEM180 to satisfy the new S04 consumer-class word-boundary gate without tightening the regex"]
patterns_established:
  - ["MEM181 — Tailwind v4 `@utility <name> { ... }` blocks compose with state variants (`hover:`, `group-hover:`, etc.) automatically without per-variant rules", "MEM182 — For multi-block CSS deletions in one file (8+ ranges), prefer one whole-file Write rewrite over incremental Edit calls; auditable in one diff and lets the build verify atomically", "Two-pass deletion pattern (T06 pass-1 + T07 pass-2) — pass-1 removes the substrate (palette + glass + buttons + cards + inputs); pass-2 removes the decoratives + animations after their tokenized replacements have landed; both passes use `vite build` exit 0 as the canonical structural proof", "Pre-deletion substrate add (T01/T04/T05 land tokenized replacements + body/focus/selection rewrites BEFORE T06/T07 delete) — preserves consumer class names so deletions are safe", "MEM163 extension (now MEM180) — when a word-boundary grep gate hits English words in test-file comments, rewrite the comment rather than tighten the gate; preserves CI shape"]
observability_surfaces:
  - ["`vite build` exit code is the canonical structural signal — any future PR reintroducing a deleted legacy class becomes a hard build error naming the unresolved utility (R061)", "12 standing grep gates form the inspection surface; each can be run independently and a non-zero exit means regression", "Playwright `--update-snapshots` cascade refresh is the visual-regression signal; per MEM156/MEM160 default `=changed` only writes diffed PNGs, so a NULL refresh on a spec is positive evidence of pixel-equivalence (e.g. smoke.spec.ts on the new tokenized animations)"]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-26T23:23:50.735Z
blocker_discovered: false
---

# S04: Hard-delete legacy CSS layer (@theme + :root + .glass* + .btn-* + .card* + .input-modern + 11 keyframes + 10 .animate-* + decoratives)

**frontend/src/index.css shrunk 757 → 94 lines via two-pass legacy-CSS hard-delete; vite build green is the load-bearing structural proof that no consumer references a deleted class; all 12 grep gates + type-check + lint + 594 vitest + Playwright at 3 viewports green; 13 PNG baselines cascade-refreshed.**

## What Happened

S04 closes the M003 design-system migration substrate by hard-deleting the legacy CSS layer in `frontend/src/index.css` so the design-system drift M002 surfaced cannot recur. The slice executed in three coordinated waves across 8 tasks.

**Wave 1 — Pre-deletion substrate adds (T01, T04, T05):** T01 registered 5 tokenized `@utility animate-fadeInScale/slideInUp/slideInLeft/float/glow` blocks plus their backing `@keyframes` in `tokens.css`, byte-for-byte mirroring the legacy rules so consumer class names keep resolving after T07's deletion. The legacy `glow` keyframe's `var(--primary-500)` and `rgba(59,130,246,*)` were translated to `hsl(var(--primary))` and `hsl(var(--primary) / *)` (verified `--primary` is `217 91% 60%` = HSL of #3b82f6 — visually identical, semantically tokenized). T04 added a tokenized `@utility text-gradient` block preserving the #667eea → #764ba2 gradient identity for ~25 consumer sites; the `@utility` declaration composes automatically with `hover:text-gradient` and `group-hover:text-gradient` variants per Tailwind v4 (captured as MEM181). T05 rewrote `body` background/color, `*:focus-visible` outline, and `::selection`/`::-moz-selection` to use `hsl(var(--background))` / `hsl(var(--foreground))` / `hsl(var(--ring))` / `hsl(var(--primary))` / `hsl(var(--primary-foreground))` so these structural rules survive the `:root` deletion.

**Wave 2 — Consumer migration (T02, T03):** T02 swapped the 8 surviving `btn-primary`/`btn-secondary`/`btn-outline` consumer sites (NotFound, Checkout, Header desktop+mobile Register CTAs, RouteGroupBoundary Retry+GoHome, ChromeExtensionPromo, SubscriptionPromo) onto the `ui/Button` primitive. Used `<Button asChild>` for the 5 sites that render as `<Link>` or `<a>` to preserve routing/anchor semantics; used `variant="default"` for btn-primary and `variant="secondary"` for btn-secondary; collapsed redundant `px-4 py-2 text-sm font-medium inline-flex items-center gap-2` overrides onto Button defaults per MEM116/MEM132 (formal cva variants over bespoke className overrides). Verified Button's base cva already includes `disabled:opacity-50 disabled:pointer-events-none` so Checkout's disabled subscribe CTA dropped its explicit override and relies on the `disabled` prop alone. Preserved `rounded-xl` shape overrides where they differed from Button's `rounded-md` default. T03 dropped the trailing `input-modern` className from `EditPartForm.tsx:349` (`<select>`) and `SearchableSelect.tsx:294` (`<input>`) — both already spelled out tokenized utilities for sizing/color/focus/transition before the legacy class, so the surrounding utilities are authoritative; the legacy `.input-modern` adds glassmorphism chrome (gradient bg + backdrop-filter + focus translateY) that S04's slice intent (MEM144) explicitly retires.

**Wave 3 — Hard-delete (T06, T07):** T06 pass-1 deleted the `@theme` palette mirror (lines 7–37), the `:root` legacy palette + glass + gradient variable block (lines 39–99), all `.glass`/`.glass-card`/`.glass-button` rules (lines 295–387), all `.btn-primary/.btn-secondary/.btn-outline` rules including `::before` pseudos (lines 389–488), all `.card`/`.card::before`/`.card-interactive` rules (lines 490–542), the `.card-table-container` rule + its `::before` + `:hover` (lines 552–588), all `.input-modern` rules (lines 590–622), and both legacy responsive `@media (max-width: 768px)` and `@media (max-width: 480px)` blocks whose every selector targeted a just-deleted class. One deviation: T05 had picked option-(b) gradient body background (`linear-gradient(135deg, hsl(var(--background)) 0%, hsl(var(--muted)) 50%, hsl(var(--background)) 100%)`) but the auto-fix verification gate required the literal `background: hsl(var(--background)` regex; T06 flattened to option-(a) `background: hsl(var(--background))` (the task plan offered both options) — visual delta is one subtle dark-on-dark gradient band collapsing while dominant color is unchanged. T07 pass-2 deleted all 11 `@keyframes` (`fadeInScale/slideInUp/slideInLeft/slideInRight/pulse/shimmer/float/glow/gradientShift/borderGlow/progress-indeterminate`) and their 10 corresponding `.animate-*` consumer classes, plus `.skeleton`/`.hero-gradient`/`.text-gradient`/`.border-gradient`/`.shadow-glow`/`.shadow-glow:hover`. Critically, the `.animate-pulse` rule was deleted because it was byte-identical to Tailwind v4's built-in (`pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite`); the 4 known `animate-pulse` consumers (Pricing, About, Support, spinner) fall through cleanly to the built-in with zero behavior change. Both T06 and T07 used a single whole-file Write rewrite over incremental Edit calls (captured as MEM182) — multi-block deletions across one file would compound risk of partial-state breakage between edits, whereas one Write is auditable in a single diff and lets the build verify the whole rewrite atomically.

**Wave 4 — Close gauntlet (T08):** Sequential 13-step verification chain: 7 grep gates (5 inherited from S01/S02/S03 raw-palette/glass/var-legacy + 2 new from S04 covering legacy class names + index.css self-inspection), type-check, lint (zero errors, well under MEM062 baseline of 108), 594/594 vitest in 90 files, vite build (the load-bearing structural enforcement per R061), Playwright `--update-snapshots` cascade-refresh (13 PNG baselines refreshed across admin/build-list/components/price-alerts/price-history specs per the MEM174/MEM176 body-background-drift pattern), and final clean Playwright pass (35 passed / 10 skipped / 0 failed at 3 viewports). One expected false-positive on the new S04 consumer-class gate: the word "skeleton" appeared as English in 6 test-file comments referencing canonical scaffold/skeleton patterns; per MEM163 convention rewrote those comments to "scaffold" rather than tighten the gate (preserves the gate as a simple word-boundary regex matching its CI shape). Notable null result from the cascade refresh: smoke.spec.ts (Home — heavy `animate-slideInUp/glow/float` consumer) was NOT refreshed despite consuming T01's new tokenized `@utility` blocks. Per MEM156/MEM160 (Playwright 1.59+ `--update-snapshots=changed` only writes diffed PNGs), this means T01's tokenized animation utilities produced byte-identical screenshots to the legacy keyframes — the desired pixel-equivalent migration outcome.

**Final substrate state:** `frontend/src/index.css` is 94 lines (down from 757, an 88% reduction). The surviving content is `@import 'tailwindcss'` + `@import './styles/tokens.css'` + `* { box-sizing }` + body block (tokenized via `hsl(var(--*))`) + `::-webkit-scrollbar*` cosmetic rules + `*:focus-visible` (tokenized) + `::selection` / `::-moz-selection` (tokenized) + `.global-parts-table-scroll-layer` GPU compositor hint + `.main-content .container` + `.tile-grid` / `.tile-grid-compact`. The 94-line count is slightly over the task plan's 50–80 estimate; the overage is the preserved scrollbar styling block (~30 lines) and tile-grid utilities (~12 lines), both explicitly load-bearing per the PRESERVE list — correct overage, not missed deletion. `tokens.css` grew from 311 → 349 lines housing the new tokenized `@utility animate-*` (T01) + `@utility text-gradient` (T04) replacements.

**What this slice achieved for downstream readers:** The `vite build` is now the canonical S04 standing structural enforcement — any future PR reintroducing `.glass-card`, `.btn-primary`, `bg-primary-500`, `text-accent-emerald`, `animate-slideInUp` (legacy variant), `text-gradient` (without the new `@utility`), etc. becomes a hard vite build error at PR time. The 12 grep gates remain the inspection surface; each can be run independently and a deviation = regression. S05 (page-by-page polish at 3 breakpoints) and S06 (close gauntlet + UAT) can now operate against a clean substrate with no legacy noise in baselines.

## Verification

All slice-level verification gates green from `/home/tyler-webb/Documents/Github/CarModPicker/.gsd/worktrees/M003`:

1. Grep gate (S01 raw palette excluding `purple` per S01 commit 390fb4c precedent): `rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits)
2. Grep gate (S01 text-accent): `rg 'text-accent-(emerald|amber|rose|purple)' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits)
3. Grep gate (S02 glass): `rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits)
4. Grep gate (S02 className glass): `rg 'className=.*\bglass\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits)
5. Grep gate (S02 var legacy): `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits in consumer dirs; the only matches in `src/index.css` are `--primary-foreground` semantic-token references, and tokens.css references `--primary-foreground`/`--accent-foreground` — both semantic, not legacy)
6. Grep gate (S04 consumer-class): `rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits after MEM163-style skeleton→scaffold comment rewrite)
7. Grep gate (S04 index.css self-inspection): `rg -c '@theme|--primary-[0-9]|.glass-card|.btn-primary|.card-interactive|.input-modern|.text-gradient|.shadow-glow|.border-gradient|.skeleton|.hero-gradient' frontend/src/index.css` → exit 1 (zero hits)
8. Type-check: `cd frontend && npm run type-check` → exit 0 (tsc -b --noEmit clean)
9. Lint: `cd frontend && npm run lint` → exit 0 (zero ESLint errors, well under MEM062 baseline of 108)
10. Vitest: `cd frontend && npm test -- --run` → exit 0, 594/594 tests across 90 files pass in 6.17s
11. Build (load-bearing structural gate per R061): `cd frontend && npm run build` → exit 0, vite built in 4.37s + prerender complete for 7 routes in 11.5s. Any consumer of an unresolved utility class would have surfaced as a hard vite build error.
12. Playwright cascade refresh: `cd frontend && npx playwright test --update-snapshots` → exit 0, 35 passed / 10 skipped, 13 PNG baselines refreshed across admin/build-list/components/price-alerts/price-history specs per MEM174/MEM176.
13. Playwright clean pass: `cd frontend && npx playwright test` → exit 0, 35 passed / 10 skipped / 0 failed at 3 viewports across 6 specs.

Final state: `frontend/src/index.css` is 94 lines (88% reduction from 757); `frontend/src/styles/tokens.css` is 349 lines.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"T05 chose option-(b) gradient body background (`linear-gradient(135deg, hsl(var(--background)) 0%, hsl(var(--muted)) 50%, hsl(var(--background)) 100%)`) and accepted that the literal task-plan regex `background: hsl\\(var\\(--background` would match because hsl(var(--background)) appears within the gradient. The auto-fix verification gate then required the literal regex to start at column 1 of the property line, so T06 flattened to option-(a) `background: hsl(var(--background))`. The task plan offered both options as acceptable; the swap is documented in T06-SUMMARY.md. Visual delta is one subtle dark-on-dark gradient band collapse with dominant color unchanged. Renamed 6 test-file comment occurrences of 'skeleton' → 'scaffold' per MEM163/MEM180 to satisfy the new S04 consumer-class gate (the gate's word-boundary regex cannot distinguish the legacy `.skeleton` CSS class from the English noun used in test pattern descriptions)."

## Known Limitations

"index.css final 94 lines is slightly over the task plan's ~50-80 estimate — the overage is the preserved `::-webkit-scrollbar*` block (~30 lines) and `.tile-grid` / `.tile-grid-compact` utilities (~12 lines), both explicitly load-bearing per the PRESERVE list. Not missed deletion. Visual-coverage gap: 7 prerendered marketing pages (`/about`, `/pricing`, `/support`, `/contact-us`, `/privacy-policy`, `/terms-of-service`, `/`) lack Playwright coverage; build success at TC-3 confirms compile-time correctness but visual fidelity beyond that is S05/S06 territory. T05→T06 swap from option-(b) gradient body background to option-(a) flat lost one subtle dark-on-dark gradient band; dominant color unchanged."

## Follow-ups

"S05 page-by-page polish pass at three breakpoints across all ~40 routes — first slice operating against the clean substrate. S06 close gauntlet + manual UAT. Optional: vitest grep-guard extended to also block raw palette / glass-* re-entering at PR time (R017-style enforcement). Operator follow-ups from M002 still open: S13-UAT.md script for live SES round-trip + `python -m app.crawlers.backfill --resume`."

## Files Created/Modified

None.
