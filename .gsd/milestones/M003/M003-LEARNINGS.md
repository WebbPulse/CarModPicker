---
phase: M003
phase_name: Frontend Design System Migration & Polish
project: CarModPicker
generated: 2026-04-27T02:15:00Z
counts:
  decisions: 9
  lessons: 8
  patterns: 9
  surprises: 6
missing_artifacts: []
---

# M003 — Structured Learnings

### Decisions

- **D012 — Hard-delete legacy CSS substrate in two passes inside one slice (S04)**, with targeted tokenized replacements landing atomically BEFORE deletion. Chose hard-delete over coexistence because as long as both substrates work, drift recurs (devs and LLM agents reach for the legacy classes that still resolve). Two-pass keeps each deletion cliff bounded — pass 1 high-traffic surface, pass 2 decoratives + animations.
  Source: M003-ROADMAP.md/Boundary Map S03→S04
- **D013 — Delete `@theme` palette block entirely after consumers migrate**; surviving raw palette utilities become hard `vite build` errors. Build-error enforcement is the cheapest possible drift gate — CI catches it, no human review needed. Anything softer (keep both forms valid) means drift recurs.
  Source: DECISIONS.md/D013
- **D014 — IA decision rights split**: agent judgment up to medium-impact (combine adjacent cards, remove redundant header, dedupe stat strips, ViewPart price-block collapse exemplar); high-impact changes (remove feature, restructure layout, navigation changes) need user approval and surface as proposals.
  Source: DECISIONS.md/D014
- **D015 — Hybrid migration ordering**: Phase 1 (S01) global by-token sweeps via Python regex bulk-swap (one legacy class everywhere per atomic commit); Phase 2 (S02 + S05) per-page work for structural cleanup that doesn't fit a global swap.
  Source: DECISIONS.md/D015
- **D016 — Per-slice baseline refresh at maximum coverage** (every page touched, 360/768/1280). M002 burned on batch refresh hiding regressions (~150 legitimate diffs hide the 2-3 real ones); per-slice review keeps each diff set bounded so real regressions stand out against expected token-swap diffs.
  Source: DECISIONS.md/D016
- **D017 — Targeted gap-fill additions are standalone atomic commits with rationale**; bias toward consumption of existing system. Friction enforces the consumption bias — if additions land inline in migration commits, "just one more" creep is unbounded.
  Source: DECISIONS.md/D017
- **D018 — Aggressive collapse of ViewPart price blocks** (M003/S03): ONE `Price by retailer` table sourced from `priceSummary.retailers` joined to `listingsData` by `retailer_id`; standalone summary stats card dropped or compressed to one-line header. Conservative alternatives preserve clutter without UX benefit.
  Source: DECISIONS.md/D018
- **D019 — Outbound retailer link safety + affordance** (M003/S03): every link uses `target="_blank" rel="noopener noreferrer"` + Lucide `<ExternalLink>` icon; no interstitial; no `rel="sponsored"` (affiliate program unestablished). Standard safety attributes prevent reverse-tabnabbing without adding friction.
  Source: DECISIONS.md/D019
- **D020 — Defer all high-impact IA changes to S06 UAT under autonomous mode** (M003/S05): per MEM146/D014, autonomous mode cannot ask for user approval, so guessing risks mislabeling deliberate user choices as "approved cleanup." Cleaner to surface deferrals in slice summary for the operator UAT.
  Source: DECISIONS.md/D020

### Lessons

- **Two-pass deterministic Python regex bulk-swap scales cleanly across 60+ consumer files**: pass 1 captures `\b(text|bg|border|ring|from|to|via|shadow)-<color>-\d+(/\d+)?\b` with alpha preserved; pass 2 collapses hover-no-op transitions to alpha-modifier form (`/80` text, `/90` bg). Idempotent, faster than per-file Edit calls, easy to bisect. **Capture all 7 utility prefixes (gradient + shadow included) up front** — gradient prefixes bit S01/T02–T04 and forced fix-in-place at the close gauntlet.
  Source: S01-SUMMARY.md/Key decisions
- **Grep gates that contain literal palette/glass tokens in their own regex source or comments self-trip.** Two complementary fixes: (1) rewrite explanatory comments containing palette names with placeholder strings (`bg-primaryNNN`, `text-accentNNN`); (2) construct regex sources via string concatenation (`new RegExp('\\bgla' + 'ss-...')`) so literal banned tokens never appear in source. Comment fix needed at S01; regex-concat fix needed at S06/T03 when promoting per-PR rg gates into vitest assertions.
  Source: S01-SUMMARY.md/Patterns established + S06-SUMMARY.md/Key decisions
- **`vite build` succeeding with `@theme` deleted is the load-bearing structural enforcement.** Once legacy classes don't compile, drift literally cannot recur — any reintroduction is a hard build error at PR time. Cheapest possible drift gate (CI catches it, no human review needed).
  Source: M003-ROADMAP.md/Success Criteria
- **Tailwind v4 `@utility` blocks compose with hover/group-hover variants** (MEM181), so tokenized `@utility animate-*` replacements work as drop-in keyframe substitutes. The smoke.spec.ts NOT being refreshed at S04 close is the null-result proof.
  Source: S04-SUMMARY.md (referenced in inlined slice context)
- **Cascade-refresh for visual-regression baselines** (MEM176): when a slice mutates page geometry (e.g. ViewPart collapse), refresh both the primary spec AND any spec that snapshots the same page at a different viewport. S03 refreshed 6 PNGs (3 price-history primary + 3 price-alerts cascade) on the same geometry mutation.
  Source: S03-SUMMARY.md (inlined excerpt)
- **Reality-check slice-plan section counts before extracting components** (MEM198). Plan said 'collapse 10 near-identical danger sections to 10 component instances'; reality was 3 shape-compatible sections + 2 unrelated sections using Card chrome with own dialog flows. Refactor what actually shares structure, not what the plan said.
  Source: S06-SUMMARY.md/Key decisions
- **Hover-alpha-modifier repair pattern** (MEM167): when migrating shaded palette utilities (`text-emerald-400 hover:text-emerald-500`) to shadeless semantic tokens, the hover becomes a no-op. Repair via alpha modifiers: `/80` for hover-text (lighter on hover), `/90` for hover-bg (slightly darker on hover).
  Source: S02-SUMMARY.md/Key decisions
- **Operator UAT items remain non-blocking for milestone close** (MEM142). Auto-mode cannot drive a real browser at 360px or resolve high-impact IA decisions; the structured operator handoff (M003-UAT.md with file:line refs + observation notes + trade-off enumeration + verdict checkboxes) is the deliverable, not the operator's signed-off completion.
  Source: M003-VALIDATION.md/Verdict Rationale + S06-SUMMARY.md/Known limitations

### Patterns

- **Two-pass Python regex bulk-swap pattern** for global token migrations: pass 1 swaps utilities with alpha preserved across 7 prefixes (`text|bg|border|ring|from|to|via|shadow`); pass 2 repairs collapsed hover no-ops via alpha modifiers. Reusable for any future palette/keyframe/utility deletion.
  Source: S01-SUMMARY.md/Patterns established
- **Inline tokenized glass surface convention**: `border border-white/10 bg-white/5 backdrop-blur-{md,xl} supports-[backdrop-filter]:bg-white/5 [hover:bg-white/10]` (MEM166). Use `<Card variant="glass">` only at sites already wrapped in `<Card>`; use the inline form elsewhere to preserve bespoke padding/animate chrome and keep diffs className-only.
  Source: S02-SUMMARY.md/Patterns established
- **`priceSummary.retailers` as primary truth + listings as `product_url` join**: single-source-of-truth IA pattern for any future "summary block + list block" redundancy collapse where the unique signal in the second block is a distinguishing field (here, the outbound link).
  Source: S03-SUMMARY.md (inlined excerpt)
- **Atomic-substrate-add-before-deletion** (R053): when migration surfaces a real gap, stop the migration, add the token / primitive / keyframe in `tokens.css` or `components/ui/`, commit as standalone atomic commit with rationale, then resume. S04's tokenized `@utility animate-*` blocks added BEFORE the keyframe deletion is the exemplar.
  Source: M003-ROADMAP.md/Boundary Map S03→S04
- **Cascade snapshot refresh on geometry mutation** (MEM176): when a slice changes page layout (block collapse, table reflow), refresh the primary spec AND any spec that snapshots the affected page at a different viewport. Mechanical rule: `git status --short -- frontend/e2e/*-snapshots/` after `--update-snapshots` reveals which specs actually drifted.
  Source: S03-SUMMARY.md (inlined excerpt)
- **Per-gate evidence persistence at milestone close** (MEM197): one file per gate under `.gsd/milestones/M###/slices/S##/gauntlet/<gate-name>.txt` (12 files for 12 gates). Captures exit codes + output tails for durable forensic record. Reusable for any future milestone-close gauntlet.
  Source: S06-SUMMARY.md/Patterns established
- **Shared `scan(globs, patterns, allowlist)` helper for vitest grep-guard tests** (MEM195): dedupes files across globs, applies regex per file, short-circuits on first match. DRY structure for "no re-entry" assertions; allowlist excludes `index.css`, `tokens.css`, each ui/* primitive source, and the guard file itself.
  Source: S06-SUMMARY.md/Patterns established
- **String-concat regex sources to avoid grep-guard self-trip** (MEM196): `new RegExp('\\bgla' + 'ss-(?:card|button)?\\b')` so literal banned tokens never appear in source code. Extends MEM163 placeholder convention from comments-only to regex sources.
  Source: S06-SUMMARY.md/Patterns established
- **Admin-specific component placement** (MEM199): admin chrome primitives (DangerActionPanel) live at `components/admin/`, matching ReportDialog's placement, not `components/ui/`. The ui/ directory is reserved for cross-domain primitives.
  Source: S06-SUMMARY.md/Patterns established

### Surprises

- **Plan-stated file counts were systematically speculative.** S01/T02 Expected Output enumerated 33 files; actual fix set was 42. T03 Expected Output similarly off (27 actual vs plan list). T06 framed as pure verification caught 6 surviving raw-palette gradient sites that T02–T04 missed because their regex didn't cover gradient prefixes (`from|to|via`). The grep gate (zero hits) was the authoritative contract, not the plan's enumeration.
  Source: S01-SUMMARY.md/Deviations
- **Decorative `bg-purple-*` (3 sites) outside the legacy palette scope.** ViewBuildlist superuser badge, Login/Register decorative blur, and Home decorative gradients resolve via Tailwind v4's default palette, not the legacy `@theme` block. The S06 close-gauntlet gate definition correspondingly excluded `purple` from gate 1 (`(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]`) — narrower than the roadmap success-criteria language.
  Source: S01-SUMMARY.md/Known limitations + S06-SUMMARY.md verification block
- **DangerActionPanel scope reduction**: plan said '10 near-identical danger sections in SystemAdmin.tsx'. Reality: only 3 sections were genuinely shape-compatible (the Deletion-options accordion). Migrations and Data-Initialization sections at the top of the page use Card chrome + h2/subtitle/own-dialog-flow and aren't extraction candidates. Captured as MEM198.
  Source: S06-SUMMARY.md/Deviations
- **DangerActionPanel API simplified from plan.** Plan suggested `confirmDialogProps` as a panel API. Bucket-cleanup has dual buttons (List + Purge) where only Purge is dialog-gated, making a single `confirmDialogProps` prop a poor fit. Component instead exposes `children` slot for full composition flexibility. Captured as MEM199.
  Source: S06-SUMMARY.md/Deviations
- **T02's grep-guard test file self-tripped gates 3 + 4 at S06/T03.** The test file's own regex sources contained literal `glass-*` strings — exactly what the gate searches for. Fixed in-place via string-concat regex construction (MEM196 extends MEM163 from comments to regex). The fix is a forward-loop pattern: any future grep-guard assertion file must use string-concat for banned tokens.
  Source: S06-SUMMARY.md/Deviations
- **Test-comment occurrences of 'skeleton' triggered the consumer-dir gate after S04.** S04 deleted the `.skeleton` class but 6 test comments still contained the literal token. Renamed 'skeleton' → 'scaffold' to satisfy `\b(...|skeleton|...)\b` per MEM163/MEM180 — placeholder-strings convention applies to test fixtures, not just source comments.
  Source: S04 (inlined excerpt) + S06 verification
