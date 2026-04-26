---
depends_on: [M002]
---

# M003: Frontend Design System Migration & Polish — Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

## Project Description

Finishing pass on M002's design-system reset. M002 shipped the substrate (semantic tokens via `frontend/src/styles/tokens.css`, 9 Radix-based primitives + 5 layout primitives under `frontend/src/components/ui/`, retired `components/common/` + `components/buttons/` with R017 enforcement), but the migration was done slice-by-slice and the polish gap is now visible: ~94 files still use raw palette utilities (`text-primary-400`, `text-emerald-400`, `text-neutral-300`, etc.), `glass-card` survives on 8 high-traffic pages including Home / Login / Register / Header, the `/parts` catalog price column overflows into adjacent columns at narrow viewports, and the part-detail page shows two redundant price blocks.

This milestone completes the migration end-to-end, **hard-deletes the legacy CSS layer** (the `:root` palette block, `@theme` palette mirror, `.glass*`, `.btn-primary/secondary/outline`, `.card*`, `.input-modern`, decorative + animation utilities, and 11 keyframes in `index.css`), audits every dense layout for the responsive overflow class of bug, collapses information-architecture redundancy starting with ViewPart's price blocks, and runs a polish pass at three breakpoints across every page.

## Why This Milestone

The substrate exists but isn't being consumed end-to-end. As long as the legacy CSS layer remains valid, devs (and the LLM agents working on this codebase) keep reaching for it and drift recurs. The fix is to migrate consumers and then delete the legacy layer entirely so the door closes — using `bg-primary-500` becomes a build error, not a style choice. This is the cheapest moment to do this work: M002 just landed, the patterns are fresh, and visual-regression baselines were just refreshed.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Browse every page on `carmodpicker.com` and see the same coherent design language (no glass-card pockets, no off-palette stat panels, no legacy gradient buttons surviving in corners)
- View the `/parts` catalog at any viewport (mobile / tablet / desktop) without the price column shoving into adjacent columns
- View any dense table or card-grid view (parts, build lists, search, admin) at any viewport without overflow
- View `/parts/:id` and see one "Price by retailer" block with sparkline + observation timing + outbound `View at retailer` link per retailer — not two redundant blocks

### Entry point / environment

- Entry point: `https://carmodpicker.com` (and the staging subdomain for verification)
- Environment: production browser (Chromium tested via Playwright at 360 / 768 / 1280)
- Live dependencies involved: none (pure frontend code change; no backend, no third-party, no infrastructure)

## Completion Class

- **Contract complete means:** every grep gate passes (zero raw palette utilities, zero `glass-*` references, zero `var(--primary-*)` legacy `:root` consumers in `frontend/src/`); `vite build`, `tsc --noEmit`, `eslint`, `vitest`, and the full Playwright suite all pass; visual-regression baselines refreshed for every page touched.
- **Integration complete means:** the legacy `@theme` palette is removed from `index.css` and the build still succeeds — proof that no missed consumer references the old palette utilities.
- **Operational complete means:** n/a (no service lifecycle, no deployment topology change).

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- `vite build` succeeds with the legacy `@theme` palette block deleted from `index.css` — any missed legacy class is a build error
- A full Playwright suite run at three viewports passes with refreshed baselines reviewed against expected diffs only
- A manual UAT walkthrough at 360 / 768 / 1280 across the priority pages (Home, PartsCatalog, ViewPart, ViewBuildList, ViewCar, Login, Register, Header, AccountAlerts, AdminDashboard, AdminExtractionHealth) shows coherent visuals, no overflow, no redundant blocks
- `rg 'bg-(primary|neutral|emerald|indigo|accent)-[0-9]'`, `rg 'text-(primary|neutral|emerald|indigo|accent)-[0-9]'`, `rg 'glass-(card|button)?'`, and `rg 'var\(--(primary|neutral|accent)-'` all return zero hits in `frontend/src/`

## Architectural Decisions

### Hard-delete the legacy CSS layer (two-pass)

**Decision:** Migrate every consumer of legacy palette utilities, glass-* classes, legacy component classes (`.btn-primary/secondary/outline`, `.card*`, `.input-modern`), decorative utilities (`.text-gradient`, `.shadow-glow`, `.hero-gradient`, `.skeleton`), and animation utilities + their keyframes. Then delete all of it from `index.css` in two passes: pass 1 removes palette + glass + legacy component classes (the high-traffic surfaces this milestone is explicitly about); pass 2 removes decorative + animation utilities (which may need targeted token / keyframe additions to replace specific surviving uses, e.g. Home entrance animations).

**Rationale:** As long as both substrates coexist, drift recurs. Two-pass keeps each deletion cliff bounded — the high-traffic pass goes first because it's where the consumer count is highest and the verification is clearest; the decorative pass goes second because it's where targeted gap-fill additions are most likely.

**Alternatives Considered:**
- Single-pass deletion — simpler but a single irreversible cliff; any missed consumer breaks at runtime in one giant blob
- Soft sweep keeping the legacy block as "still works, just don't use it for new code" — fastest but the drift will recur on every new page touched

### Remove palette utilities from `@theme`

**Decision:** Delete the entire `@theme` palette block (`--color-primary-50` through `--color-accent-purple`) from `index.css` after consumers are migrated. Tooling enforces the semantic-token contract: `bg-primary-500`, `text-neutral-300`, `text-accent-emerald`, `bg-emerald-400`, `text-indigo-300`, etc. become build errors. Drift can't recur because the legacy classes literally don't compile.

**Rationale:** "Hard delete" at maximum strength means the legacy palette utilities don't resolve. Anything softer leaves both forms valid and drift recurs.

**Alternatives Considered:**
- Keep palette utilities, treat semantic tokens as "the standard" — less churn, but drift recurs because both forms still resolve

### IA judgment up to medium-impact, surface for high-impact

**Decision:** During the polish pass, when redundant blocks or unclear IA surface, collapse on judgment for any change up to medium-impact (combining two adjacent cards on one page, removing a redundant header, deduping a stats strip) and document the decision in the slice summary. Surface a proposal and wait for approval for high-impact changes (removing a feature, restructuring primary layout, navigation changes). The locked exemplar is the ViewPart price-block collapse — single "Price by retailer" table preserving outbound links + external-link affordance, with summary stats either dropped or compressed to a one-line header.

**Rationale:** The polish pass surfaces UX problems that aren't visible without doing the systematic visit. Medium-impact decisions are reversible per-page and benefit from agent judgment so the pass doesn't stall on every micro-decision; high-impact decisions affect navigation or feature surfaces and need user sign-off.

**Alternatives Considered:**
- Approve every IA change — slowest, but maximum control
- Apply all IA changes on judgment — fastest, but risks navigation/feature surprises

### Hybrid migration order: globals first, per-page polish second

**Decision:** Phase 1 of the migration is global by-token sweeps — replace one legacy class everywhere (e.g. all `text-emerald-400` → `text-success`) per atomic commit. Phase 2 is per-page polish for structural cleanup that doesn't fit a global swap (`glass-card` removal, layout fixes, animation replacements, IA collapses).

**Rationale:** The bulk of the migration is mechanical class swaps and benefits from global atomic commits — easier to bisect, faster to ship, fewer commits. The structural work (layout, IA, replacement animations) is intrinsically per-page and benefits from a focused per-page pass after the globals clear the noise.

**Alternatives Considered:**
- Pure by-page sweep — small commits, easy to roll back one page, but each global token rename touches dozens of commits
- Pure by-token sweep — fastest, but pages with multiple legacy patterns (Home, Login, Header) need a per-page follow-up anyway

### Refresh visual-regression baselines per slice

**Decision:** Each migration slice ends with `npm test -- -u` for the affected pages, baselines committed alongside the migration. Per-slice review keeps diffs bounded — real regressions stand out against ~5 expected diffs, not ~150.

**Rationale:** M002 already burned on this (MEM066, MEM140) — the batch baseline refresh at the end was the painful one because legitimate diffs (~100+) hide real regressions. Per-slice review distributes the cost and keeps each review honest.

**Alternatives Considered:**
- One refresh slice at the end — cleaner per-slice commits but the final review is one giant blob and regressions hide

### Token / primitive additions are atomic commits

**Decision:** When the migration surfaces a real gap (a semantic token that's missing, a primitive that doesn't exist, a keyframe that needs a tokenized replacement), stop, add, commit with rationale, resume. The bias is consumption of the existing system — gap-fills require concrete justification ("X pages need this and there's no clean way to express it with what we have"), not "this would be nice."

**Rationale:** Friction enforces the consumption bias. If additions land inline in migration commits, it's easy to keep adding "just one more"; atomic commits with rationale force the question "is this gap real?" and keep the audit trail clean.

**Alternatives Considered:**
- Inline additions in migration slices — faster but additions scatter across commits and audit gets harder

### Outbound retailer links: `target="_blank" rel="noopener noreferrer"` + external-link affordance

**Decision:** Every outbound `View at retailer` link in the collapsed ViewPart price block (and any similar outbound links surfaced during polish) uses `target="_blank" rel="noopener noreferrer"` with a small external-link icon affordance so users know they're leaving the site.

**Rationale:** Outlinking is the business value of the price-by-retailer block; the link safety attributes are standard, and the affordance signals the navigation intent.

**Alternatives Considered:**
- Confirmation interstitial before outbound — adds friction without clear benefit at this product stage
- `rel="sponsored"` for affiliate-style outbound — premature; affiliate program isn't established

> See `.gsd/DECISIONS.md` for the full append-only register of all project decisions.

## Error Handling Strategy

This milestone is a polish + migration pass, not a runtime feature. Error handling is bounded to migration safety and preserving existing user-facing error UX.

**Migration safety:**
- **Build-error enforcement.** Removing palette utilities from `@theme` means any missed legacy class is a `tsc` / `vite build` error before merge. CI catches it; nothing reaches main with a phantom `bg-primary-500`.
- **Visual regression as the safety net for runtime drift.** Per-slice `toHaveScreenshot()` at 360 / 768 / 1280 catches anything that compiles but renders wrong. Diffs > expected = stop, investigate, fix root cause.
- **Atomic per-token / per-page commits.** If a global token swap breaks something, `git revert` the single commit. Per-slice baseline refresh means each commit is bisectable.
- **Type-check + lint gauntlet runs every slice.** No slice closes with `tsc --noEmit` errors or new lint warnings.

**User-facing error UX:**
- Existing error / empty / loading patterns are preserved unchanged in IA collapses. When ViewPart's price blocks merge, the merged block keeps whatever empty-state and loading-state behavior the existing inline `ViewPart.tsx` blocks use. Error UX is not redesigned in this milestone.
- If the polish pass surfaces a genuinely broken error / empty state (e.g. a table that renders garbage on an empty array), fix it in place and document; do not go hunting for error UX work.

## Risks and Unknowns

- **Pass-2 deletion may surface real animation gaps.** The Home entrance animation and any survivor uses of `slideInUp` / `fadeInScale` may need tokenized replacements. Each addition is an atomic commit with rationale.
- **IA collapses beyond ViewPart depend on what the polish pass surfaces.** Judgment up to medium-impact, surface for high-impact. The size of S05's polish work isn't fully known until the systematic visit happens.
- **Visual-regression baseline drift will be heavy.** Per-slice refresh keeps reviews bounded, but the cadence is a real time cost. MEM140's lesson holds: one batch refresh hides regressions; per-slice keeps them visible.
- **Table-overflow audit unknown size.** Could be 2 problems or 12. Slice estimate (S03 = audit + targeted fixes) holds either way; the size of the fixes inside that slice isn't known until the systematic pass happens.

## Existing Codebase / Prior Art

- `frontend/src/styles/tokens.css` — M002/S08 substrate. HSL-channel dark palette + Tailwind v4 `@theme` bridge + inline `@keyframes` / `@utility` declarations. **This is the canonical token surface.** Any new tokens land here.
- `frontend/src/index.css` — contains the legacy substrate to be deleted: `:root` palette block (lines 38-98), `@theme` palette mirror (lines 7-36), 11 keyframes (lines 122-244), animation classes (lines 246-293), `.glass*` / `.btn-*` / `.card*` / `.input-modern` (lines 295-616), `.skeleton` (line 647), `.hero-gradient` (line 660), `.text-gradient` / `.shadow-glow` (lines 736-756). M003 deletes all of this.
- `frontend/src/components/ui/` — 9 Radix primitives + 5 layout primitives from M002/S08–S12. Consumption-first; new primitives only added on a proven gap.
- `frontend/src/components/common/` and `frontend/src/components/buttons/` — DELETED in M002/S12. R017 enforced via vitest grep-guard (`__tests__/no-legacy-primitives.test.ts`) + ESLint no-restricted-imports rule. Don't reintroduce.
- `frontend/src/pages/builder/ViewPart.tsx` — contains the two redundant price blocks (PriceSummaryBlock + PriceByRetailerBlock, both inline). Site of S03's IA collapse.
- `frontend/src/pages/parts/PartsCatalog.tsx` + `frontend/src/components/parts/PartList.tsx` + `PartListItem` — site of the price-column overflow on `/parts`. Card-grid layout, not `<table>`. S03 root-cause fix.
- `frontend/src/pages/admin/*.tsx` (4 files) + `frontend/src/components/tables/ResponsiveTableWrapper.tsx` — the actual `<table>` surfaces. S03 audits these as the second class.
- `frontend/e2e/*.spec.ts` — 6 specs (admin, build-list, components, parts-catalog, price-alerts, price-history, smoke) + `frontend/e2e/components.spec.ts-snapshots/` and per-spec snapshot dirs. Per-slice baseline refresh updates the affected snapshot dirs.
- `frontend/src/__tests__/no-legacy-primitives.test.ts` — R017 vitest grep-guard. Don't break it; M003 may extend it with a glass-* + palette-utility guard at S06 close.

## Relevant Requirements

- R048..R061 — see `.gsd/REQUIREMENTS.md`. R048–R053 own the migration; R054–R058 own the responsive audit + IA collapse; R059 owns the polish pass; R060 owns visual-regression coverage; R061 is the milestone close gate.
- R017 (validated, M002/S12) — no imports from `components/common/` or `components/buttons/`. M003 preserves this and may extend the guard pattern at S06.
- R020 (validated, M002/S09–S11) — keyboard-accessible focus indicators on dialogs and interactive controls. M003 must not regress this; e2e specs for it stay green.
- R035 (deferred) — light theme. Stays deferred per D003.

## Scope

### In Scope

- Token migration across all ~94 raw-palette-utility consumer files in `frontend/src/`
- Legacy `:root` palette block, `@theme` palette mirror, all `.glass*` / `.btn-*` / `.card*` / `.input-modern` / decorative / animation utilities + 11 keyframes removed from `index.css`
- Cross-class responsive audit + root-cause fixes at 360 / 768 / 1280: card-grid layouts (PartsCatalog, BuildLists, BuildListPart list, Search) AND real `<table>` surfaces (4 admin tables + `ResponsiveTableWrapper`)
- ViewPart IA collapse — single "Price by retailer" block with sparkline + observation timing + outbound link per retailer; summary stats either drop or compress to a one-line header
- Outbound link safety + external-link affordance on every outbound retailer link
- Page-by-page polish pass at three breakpoints across all ~40 routes
- Visual-regression baseline refresh per slice for every page touched
- Targeted token / primitive / keyframe additions where gap-fills are proven, as atomic commits with rationale

### Out of Scope / Non-Goals

- Light mode (R035 deferred per D003)
- Speculative token / primitive expansion beyond proven gaps
- New product features
- Visual redesign of error / empty / loading states (preserved unchanged in IA collapses unless found broken)
- Backend changes — pure frontend milestone
- Chrome extension changes — extension UI is separate
- Mobile native app (out of scope for the entire project)

## Technical Constraints

- All new tokens land in `frontend/src/styles/tokens.css` (M002/S08 substrate). No competing token surface.
- All new primitives land under `frontend/src/components/ui/` with named-export shape matching existing primitives. No reintroduction of `components/common/` or `components/buttons/` (R017).
- Migration must keep R020 (keyboard accessibility, focus indicators, Escape on dialogs) green — desktop e2e specs for this don't regress.
- Visual-regression `toHaveScreenshot()` uses `maxDiffPixelRatio: 0.002` per playwright.config (D006 + R013). Diffs above this fail; review-then-update is the contract.
- Lint baseline preserved at MEM062 (108 errors). No net-new lint errors in slice-touched files.
- Type-check (`tsc --noEmit`) stays at 0 errors.
- Backend coverage thresholds + frontend vitest 60/50/50/60 thresholds preserved (no test deletions to dodge coverage).

## Integration Points

- `frontend/src/styles/tokens.css` — site of token additions
- `frontend/src/components/ui/` — site of primitive additions
- `frontend/src/index.css` — site of all deletions
- `frontend/e2e/*.spec.ts-snapshots/` — site of baseline refreshes
- Backend — none touched
- Chrome extension — none touched
- AWS / infrastructure — none touched

## Testing Requirements

- **Unit (vitest):** every existing test stays green (594+ pass at M002 close). New tests only where component surface changes meaningfully (e.g. ViewPart's collapsed block).
- **E2E (Playwright):** every existing spec stays green at 3 viewports after baseline refresh. Refresh per slice via `npx playwright test --update-snapshots <spec>`; review the diff before committing.
- **Visual regression:** `toHaveScreenshot()` at 360 / 768 / 1280 for every page touched by a slice. Maximum coverage — no pragmatic carve-out for secondary pages.
- **Lint (`npm run lint`):** baseline preserved at MEM062 (108 errors); zero net-new lint errors in slice-touched files.
- **Type-check (`npm run type-check`):** zero errors.
- **Build (`npm run build`):** must succeed with the `@theme` palette removed at S04 — this is the milestone close gate.
- **R017 grep-guard:** vitest `no-legacy-primitives.test.ts` continues to pass. Optional extension at S06 to also guard against `glass-*` / raw palette utilities returning.

## Acceptance Criteria

**S01 — Global token sweep:**
- `rg 'bg-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]'` and `rg 'text-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]'` in `frontend/src/` (excluding `index.css` legacy block + `tokens.css`) return zero hits
- Build, lint, type-check, vitest, e2e all green
- Baselines refreshed for every page touched

**S02 — Glass + legacy `:root` purge:**
- `rg 'glass-(card|button)?\b'` in `frontend/src/` returns zero hits outside `index.css` legacy block
- `rg 'var\(--(primary|neutral|accent)-'` in `frontend/src/` returns zero hits outside `index.css` legacy block
- Home, Login, Register, Header reskinned without the legacy classes
- Baselines refreshed for touched pages

**S03 — Responsive audit + ViewPart IA collapse:**
- Per-viewport verdict list (pass / fixed / acceptable-as-scroll) in slice summary for every dense table + card-grid view
- `/parts` price column does not overflow at 360 / 768 / 1280 with realistic densest data
- ViewPart shows ONE "Price by retailer" block; summary stats either dropped or compressed to a one-line header
- All outbound retailer links carry `target="_blank" rel="noopener noreferrer"` + external-link affordance
- Baselines refreshed for affected pages

**S04 — Hard delete + pass 2:**
- `index.css` legacy `:root` palette block, `@theme` palette mirror, `.glass*`, `.btn-primary/secondary/outline`, `.card*`, `.input-modern`, `.text-gradient`, `.shadow-glow`, `.hero-gradient`, `.skeleton`, all 11 keyframes + their `.animate-*` classes are deleted
- `vite build` succeeds
- Targeted token / keyframe additions for surviving uses (Home entrance animation, etc.) committed atomically with rationale before deletion
- Baselines refreshed for any page affected by replacement animations

**S05 — Page-by-page polish pass:**
- All ~40 routes visited at 360 / 768 / 1280; per-page verdict list in slice summary
- Medium-impact IA changes applied on judgment and documented; high-impact changes surfaced and resolved
- Baselines refreshed for every page touched

**S06 — Migration completion gauntlet:**
- All grep gates from R048–R052 return zero hits
- `npm run build`, `npm run lint`, `npm run type-check`, `npm test -- --run`, `npm run test:e2e` (or equivalent) all green
- Optional: vitest grep-guard extended to also block `glass-*` / raw palette utilities re-entering (R017-style enforcement)
- Manual UAT walkthrough at three viewports across priority pages documented

## Open Questions

- Should the S06 grep-guard extension be a hard CI gate or a soft warning? — Lean hard; matches R017's existing posture.
- Does the polish pass surface IA collapses beyond ViewPart that warrant their own slice, or do they fit into S05? — Resolves during S05; if a high-impact change surfaces, surface for approval and decide.
