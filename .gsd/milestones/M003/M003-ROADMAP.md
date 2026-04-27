# M003: Frontend Design System Migration & Polish

**Vision:** Complete the design-system migration M002 started, hard-delete the legacy CSS layer (`@theme` palette + `:root` palette + `.glass*` + legacy component classes + decorative + animation utilities) so drift can't recur, audit every dense layout for the responsive overflow class of bug, collapse information-architecture redundancy starting with ViewPart's price blocks, and run a polish pass at three breakpoints across every page. Pure frontend; no backend, no third-party, no infrastructure.

## Success Criteria

- Zero raw legacy palette utility hits anywhere in `frontend/src/` (verified via `rg 'bg-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]'` + the text- equivalent — both return zero in `frontend/src/`)
- Zero `glass-card` / `glass-button` / `glass` references in `frontend/src/` consumer code (verified via grep)
- Zero `var(--primary-*)` / `var(--neutral-*)` / `var(--accent-*)` / legacy gradient-var consumers anywhere in `frontend/src/`
- `vite build` succeeds with the legacy `@theme` palette block deleted from `index.css` — any missed legacy class is a build error (this is the hard-delete proof)
- Every dense table view (4 admin tables + ResponsiveTableWrapper) and every dense card-grid view (PartsCatalog, BuildLists, BuildListPart list, Search) has a documented per-viewport verdict at 360 / 768 / 1280
- ViewPart shows ONE 'Price by retailer' block with sparkline + observation timing + outbound link per retailer; summary stats either dropped or compressed to a one-line header
- Every outbound retailer link uses `target="_blank" rel="noopener noreferrer"` with an external-link icon affordance
- All ~40 routes visited at 360 / 768 / 1280 with structural cleanup applied; per-page verdict list in S05 slice summary
- Playwright `toHaveScreenshot()` baselines refreshed at 360 / 768 / 1280 for every page touched, reviewed before commit (per-slice refresh)
- Lint baseline preserved at MEM062 (108 errors, zero net-new in slice-touched files); type-check clean; full vitest + Playwright suites green at three viewports

## Slices

- [x] **S01: S01** `risk:medium` `depends:[]`
  > After this: Every raw palette utility (`bg-primary-500`, `text-neutral-300`, `text-emerald-400`, `text-indigo-300`, `text-accent-*`, `bg-emerald-400`, etc.) replaced with semantic tokens across all consumer files in `frontend/src/`. Refreshed Playwright baselines at 360/768/1280 for every page touched. Build, lint, type-check, vitest, e2e all green.

- [x] **S02: S02** `risk:medium` `depends:[]`
  > After this: Every `glass-card` / `glass-button` / `glass` reference and every `var(--primary-*)` / `var(--neutral-*)` / `var(--accent-*)` / `var(--gradient-*)` consumer migrated to semantic tokens / equivalent ui/* primitive surfaces. Home, Login, Register, Header, AccountAlerts, AdminDashboard reskinned (~8 high-traffic pages). Baselines refreshed for touched pages.

- [x] **S03: S03** `risk:high` `depends:[]`
  > After this: Per-viewport verdict list (pass / fixed / acceptable-as-scroll) in slice summary for every dense `<table>` view (4 admin tables + ResponsiveTableWrapper) and every dense card-grid view (PartsCatalog, BuildLists, BuildListPart list, Search) at 360 / 768 / 1280 with realistic densest data. The `/parts` price-column overflow is fixed at root cause. ViewPart shows ONE 'Price by retailer' block (last price + sparkline + observation timing + outbound link per retailer); summary stats either dropped or compressed to a one-line header. Every outbound retailer link uses `target="_blank" rel="noopener noreferrer"` + Lucide external-link icon affordance.

- [x] **S04: S04** `risk:high` `depends:[]`
  > After this: `frontend/src/index.css` legacy `:root` palette block (lines 38-98), `@theme` palette mirror (lines 7-36), `.glass*` (lines 295-381), `.btn-primary/secondary/outline` (lines 383-482), `.card` / `.card-interactive` / `.card-table-container` (lines 484-582), `.input-modern` (lines 584-616), `.text-gradient` / `.shadow-glow` / `.border-gradient` (lines 736-756), `.skeleton` (line 647), `.hero-gradient` (line 660), and all 11 keyframes + their `.animate-*` classes are deleted. `vite build` succeeds — any missed legacy class is a build error. Targeted token / keyframe additions for surviving uses (Home entrance animation, etc.) committed atomically with rationale BEFORE the deletion.

- [x] **S05: S05** `risk:medium` `depends:[]`
  > After this: All ~40 routes visited at 360 / 768 / 1280; structural cleanup applied (layout fixes, redundant block collapses on judgment up to medium-impact, off-palette stat panels reskinned, animation replacements where the polish surfaces a need). High-impact IA changes surfaced and resolved with user approval. Per-page verdict list in slice summary. Baselines refreshed for every page touched.

- [x] **S06: S06** `risk:low` `depends:[]`
  > After this: All gates pass: zero raw palette utility hits, zero `glass-*` hits, zero legacy `:root` consumer hits in `frontend/src/`; `vite build`, `tsc --noEmit`, `eslint`, `vitest`, full Playwright suite at 3 viewports all green; manual UAT walkthrough at three viewports across priority pages (Home, PartsCatalog, ViewPart, ViewBuildList, ViewCar, Login, Register, Header, AccountAlerts, AdminDashboard, AdminExtractionHealth) documented in slice summary or M003-UAT.md.

## Boundary Map

## Boundary Map

### S01 → S02
Produces:
- Every `frontend/src/` consumer of raw palette utilities (`bg-primary-[0-9]`, `text-primary-[0-9]`, `bg-neutral-[0-9]`, `text-neutral-[0-9]`, `bg-emerald-[0-9]`, `text-emerald-[0-9]`, `bg-indigo-[0-9]`, `text-indigo-[0-9]`, `text-accent-emerald`, `text-accent-amber`, `text-accent-rose`, `text-accent-purple`) migrated to semantic tokens (`text-foreground`, `text-muted-foreground`, `bg-card`, `bg-muted`, `text-primary`, `text-success`, `text-warning`, `text-destructive`, etc.) from `tokens.css`
- Any new semantic tokens needed to fill gaps land in `tokens.css` (atomic commits with rationale per R053)
- Refreshed Playwright baselines for every page touched at 360 / 768 / 1280

Consumes:
- M002/S08 substrate: `frontend/src/styles/tokens.css` semantic token vocabulary
- M002/S08–S12: `frontend/src/components/ui/*` primitives

### S02 → S03
Produces:
- Zero `glass-card` / `glass-button` / `glass` references in `frontend/src/` consumer code (legacy block in `index.css` survives until S04)
- Zero `var(--primary-*)` / `var(--neutral-*)` / `var(--accent-*)` / `var(--gradient-*)` consumers in `frontend/src/`
- Home, Login, Register, Header, AccountAlerts, AdminDashboard reskinned without `glass-*` — replacement card surfaces use `bg-card border-border` + appropriate shadow / backdrop-blur tokens
- Refreshed Playwright baselines for every page touched

Consumes:
- S01 outputs: semantic-token migration in place; safe to do glass-* removal because the surrounding text/bg utilities already resolve to the new system

### S03 → S04
Produces:
- Per-viewport verdict list (pass / fixed / acceptable-as-scroll) for every dense `<table>` view (4 admin tables + `ResponsiveTableWrapper`) and every dense card-grid view (PartsCatalog, BuildLists, BuildListPart list, Search) at 360 / 768 / 1280
- Root-cause fixes for `/parts` price column overflow + any other overflow surfaced by the audit (min-width matching actual rendered content, OR cell content reflows / wraps cleanly, OR responsive-priority drop)
- ViewPart refactor: ONE "Price by retailer" block (table with retailer name + sparkline + observation timing + outbound link); summary stats either dropped or compressed to one-line header
- All outbound retailer links carry `target="_blank" rel="noopener noreferrer"` + Lucide external-link icon affordance
- Refreshed Playwright baselines for affected pages
- New tests if `ViewPart` component surface changed meaningfully

Consumes:
- S01 + S02: clean semantic-token surface — fixing layout against semantic tokens is cleaner than fighting legacy palette
- M002/S06: `Sparkline` component from `frontend/src/components/charts/Sparkline.tsx` — preserved in collapsed block
- M002/S08–S12: `components/ui/*` primitives for the collapsed "Price by retailer" table chrome

### S04 → S05
Produces:
- `frontend/src/index.css` legacy `:root` palette block deleted (lines 38-98)
- `frontend/src/index.css` `@theme` palette mirror deleted (lines 7-36) — palette utilities no longer compile
- `frontend/src/index.css` `.glass*` (lines 295-381), `.btn-primary/secondary/outline` (lines 383-482), `.card` / `.card-interactive` / `.card-table-container` (lines 484-582), `.input-modern` (lines 584-616), `.text-gradient` / `.shadow-glow` / `.border-gradient` (lines 736-756), `.skeleton` (line 647), `.hero-gradient` (line 660) all deleted
- All 11 keyframes (`fadeInScale`, `slideInUp`, `slideInLeft`, `slideInRight`, `pulse`, `shimmer`, `float`, `glow`, `gradientShift`, `borderGlow`, `progress-indeterminate`) and their `.animate-*` consumer classes deleted
- Any required tokenized replacements (e.g. Home entrance animation) committed atomically in `tokens.css` BEFORE deletion, with rationale
- `vite build` succeeds — proof that no consumer references the deleted classes
- Refreshed Playwright baselines for any page affected by replacement animations

Consumes:
- S01 + S02: every consumer migrated; deletion is safe
- S03: any layout fixes that depended on legacy classes are already retargeted to semantic tokens

### S05 → S06
Produces:
- Per-page verdict list for all ~40 routes at 360 / 768 / 1280 in S05 slice summary
- Structural cleanup applied where needed (layout fixes, redundant block collapses on judgment up to medium-impact, off-palette stat panels reskinned, etc.)
- High-impact IA changes surfaced and resolved (with user approval recorded in slice summary)
- Refreshed Playwright baselines for every page touched

Consumes:
- S04: clean `index.css` — polish pass is against the final substrate, no legacy noise in baselines

### S06 (close gauntlet)
Produces:
- Final gauntlet report: build / lint / type-check / vitest / Playwright all green
- Final grep gates: zero raw palette / glass-* / legacy `:root` consumer hits
- Manual UAT walkthrough record at 3 viewports across priority pages
- Optional: vitest grep-guard extended to also block `glass-*` / raw palette utilities re-entering (R017-style enforcement)

Consumes:
- All prior slices' outputs
