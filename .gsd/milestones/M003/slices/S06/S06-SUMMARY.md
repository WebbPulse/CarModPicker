---
id: S06
parent: M003
milestone: M003
provides:
  - ["Final 12-gate close gauntlet evidence (7 grep gates green + 5 toolchain gates green) with persisted per-gate stdout/stderr files", "Vitest grep-guard regression net: 3 new assertions blocking raw-palette / glass-* / hand-rolled primitive re-entry at test time (in addition to per-PR rg gates)", "DangerActionPanel admin-page primitive (frontend/src/components/admin/DangerActionPanel.tsx) for future admin danger sections", "M003-UAT.md operator-handoff document with 3 human-judgment IA decision slots, 360px manual walkthrough checklist, and priority-page verdict table", "M003 milestone-close evidence record: zero raw palette / glass-* / legacy :root consumer hits in frontend/src/, vite build green against 94-line post-S04 index.css", "Pattern: per-gate evidence persistence under .gsd/milestones/M###/slices/S##/gauntlet/ (MEM197) for future milestone-close gauntlets", "Pattern: shared scan() helper for vitest grep-guard tests (MEM195) — DRY structure for future 'no re-entry' assertions", "Convention: string-concat regex sources to avoid grep-guard self-trip (MEM196) — extends MEM163 from comments to regex"]
requires:
  - slice: S01
    provides: semantic-token migration of all raw palette utilities (substrate for grep-guard assertion 1)
  - slice: S02
    provides: glass-* removal in consumer code + var(--primary-*)/var(--neutral-*)/var(--accent-*)/var(--gradient-*) consumer migration (substrate for grep-guard assertion 2 + gate 5)
  - slice: S03
    provides: ResponsiveTableWrapper + dense-view audit + ViewPart 'Price by retailer' refactor + outbound-link affordance (substrate the polish-coverage spec captures)
  - slice: S04
    provides: Hard-deleted legacy @theme block + :root palette + .glass* + consumer classes from index.css (substrate for grep gate 7 / vite build proof)
  - slice: S05
    provides: polish-coverage.spec.ts with 120 PNG baselines across 40 routes × 3 viewports (the standing visual-regression surface S06 verifies stays green); 6 IA deferral list (3 auto + 3 human-judgment) consumed by T01
affects:
  - ["frontend/src/__tests__/no-legacy-primitives.test.ts (extended with 3 M003-S06 assertions + shared scan helper)", "frontend/src/pages/admin/SystemAdmin.tsx (3 deletion-accordion panels refactored to DangerActionPanel)", "frontend/src/pages/admin/UserManagement.tsx (one-line decision-record code comment added above table)", "frontend/src/components/admin/DangerActionPanel.tsx (NEW)", ".gsd/milestones/M003/M003-UAT.md (NEW)", ".gsd/milestones/M003/slices/S06/gauntlet/ (NEW directory with 12 evidence files)"]
key_files:
  - ["frontend/src/components/admin/DangerActionPanel.tsx", "frontend/src/pages/admin/SystemAdmin.tsx", "frontend/src/pages/admin/UserManagement.tsx", "frontend/src/__tests__/no-legacy-primitives.test.ts", ".gsd/milestones/M003/M003-UAT.md", ".gsd/milestones/M003/slices/S06/gauntlet/gate1-raw-palette.txt", ".gsd/milestones/M003/slices/S06/gauntlet/gate10-vitest.txt", ".gsd/milestones/M003/slices/S06/gauntlet/gate11-vite-build.txt", ".gsd/milestones/M003/slices/S06/gauntlet/gate12-playwright.txt"]
key_decisions:
  - ["DangerActionPanel scope: 3 panels (Deletion-options accordion), not 10 sections — followed code reality over plan's section count (MEM198)", "DangerActionPanel API: panel-chrome only with children slot, no embedded ConfirmDialog composition — bucket-cleanup's dual-button shape made confirmDialogProps a poor fit (MEM199)", "ViewBuildLog prose-plugin: deferred to M004 — per-element tokenization preserved per MEM186 conservative-path rule and visual-parity uncertainty in autonomous mode (MEM201)", "UserManagement 11-col table: locked as acceptable-as-scroll (option a); options (b)-(d) move to M004 backlog (MEM200)", "vitest grep-guard self-trip fix: regex sources constructed via string concatenation (`new RegExp('\\\\bgla' + 'ss-...')`) so literal banned tokens never appear in source — extends MEM163 placeholder convention from comments to regex (MEM196)", "Per-gate evidence persistence: one file per gate under `.gsd/milestones/M###/slices/S##/gauntlet/<gate-name>.txt` (12 files for 12 gates) (MEM197)", "M003-UAT.md scope: 3 human-judgment decision slots + 3 auto-resolved sections + 360px operator walkthrough checklist + priority-page verdict table; SHA-stamped (d79f15b) summary block per MEM142 framing", "Slice-closer sequencing: T03 prepared evidence + UAT.md but did not write S06-SUMMARY.md — closer agent's gsd_complete_slice call is the canonical write path per MEM143"]
patterns_established:
  - ["Per-gate evidence persistence: one file per gate under `.gsd/milestones/M###/slices/S##/gauntlet/<gate-name>.txt` for milestone-close gauntlets (MEM197)", "Shared scan(globs, patterns, allowlist) helper for vitest grep-guard tests — dedupes files across globs, applies regex per file, short-circuits on first match (MEM195)", "String-concat regex sources to avoid grep-guard self-trip: `new RegExp('\\\\bgla' + 'ss-...')` so literal banned tokens never appear in source (MEM196 extends MEM163)", "Reality-check slice-plan section counts before extraction — refactor only what actually shares structure (MEM198)", "Admin-specific component placement: DangerActionPanel lives at `components/admin/`, matching ReportDialog's placement, not `components/ui/` (MEM199)"]
observability_surfaces:
  - ["Per-PR grep gates 1-7 (raw-palette / text-accent / glass-card|button / className=*glass* / var(--legacy-) / consumer-class / index.css self-inspection) — re-entry surfaces as non-zero exit", "Vitest grep-guard `frontend/src/__tests__/no-legacy-primitives.test.ts` — 4 assertions (1 R017 + 3 M003-S06) surface re-entry at npm test time", "Playwright polish-coverage spec (`frontend/e2e/polish-coverage.spec.ts`) — 120 PNG baselines across 40 routes × 3 viewports, surfaces visual regressions at npm run test:e2e time", "vite build (`npm run build`) — any reference to deleted legacy classes (`@theme` palette, `.glass*`, `.btn-primary`, etc.) surfaces as build error", "Per-gate evidence files at `.gsd/milestones/M003/slices/S06/gauntlet/gate{1..12}-*.txt` — durable forensic record of close-gauntlet exit codes and output tails"]
drill_down_paths:
  - [".gsd/milestones/M003/slices/S06/S06-PLAN.md", ".gsd/milestones/M003/slices/S06/tasks/T01-SUMMARY.md", ".gsd/milestones/M003/slices/S06/tasks/T02-SUMMARY.md", ".gsd/milestones/M003/slices/S06/tasks/T03-SUMMARY.md", ".gsd/milestones/M003/M003-UAT.md", ".gsd/milestones/M003/slices/S06/gauntlet/", ".gsd/milestones/M003/M003-ROADMAP.md", ".gsd/milestones/M003/slices/S05/S05-SUMMARY.md"]
duration: ""
verification_result: passed
completed_at: 2026-04-27T01:52:13.085Z
blocker_discovered: false
---

# S06: Migration completion gauntlet + UAT

**Closed M003 design-system migration: 12-gate close gauntlet green with persisted per-gate evidence, 3 autonomous IA deferrals resolved (DangerActionPanel extraction + UserManagement scroll-lock + ViewBuildLog prose deferral), vitest grep-guard extended to block raw-palette / glass-* / hand-rolled primitive re-entry, and M003-UAT.md operator handoff finalized with 3 human-judgment decision slots.**

## What Happened

## What this slice delivered

S06 was the milestone-close gauntlet: prove the post-S05 substrate holds, resolve every IA deferral that auto-mode could judge, prepare a structured operator UAT document for the human-judgment items, and lay down a regression net so the migration cannot silently un-do itself in M004.

Three tasks landed sequentially, each as an atomic commit:

**T01 — IA deferral resolution + M003-UAT.md preparation** (commit `f0737f2`). S05 deferred 6 IA decisions to S06 UAT. T01 split them along the auto-judgable / human-judgable axis:

- **Item #6 — SystemAdmin DangerActionPanel extraction** *(applied)*: Created `frontend/src/components/admin/DangerActionPanel.tsx` (~58 LOC) owning panel chrome (heading + description + tone-driven outer container with `bg-{tone}/20 + border-{tone}/50`) and slotting interactive content via `children`. API: `{ title, description, dangerColor: 'destructive'|'warning'|'info', children }`. Refactored 3 deletion-accordion panels in `SystemAdmin.tsx` to consume it (cars=warning, global-parts/manufacturers=destructive, bucket-cleanup=info). **Scope deviation from plan:** plan said "10 near-identical sections" — reality was 3 genuinely shape-compatible sections (the Deletion-options accordion). Migrations and Data-Initialization sections at the top of the page use Card chrome + h2/subtitle/own-dialog-flow and aren't extraction candidates. Captured as MEM198 (reality-check slice-plan section counts before extraction). The simpler API (no `confirmDialogProps` prop) is appropriate because bucket-cleanup has dual buttons where only Purge is dialog-gated — pushing ConfirmDialog into the component would have forced an awkward composition. Captured as MEM199.

- **Item #5 — UserManagement 11-column table responsive strategy** *(locked as `acceptable-as-scroll`)*: One-line decision-record comment added above the existing `<div className="overflow-x-auto">` table boundary in `frontend/src/pages/admin/UserManagement.tsx` referencing M003-UAT.md and MEM179. Options (b)-(d) move to M004 backlog. Captured as MEM200.

- **Item #4 — ViewBuildLog markdown prose plugin** *(deferred to M004)*: Per the task plan's decision rule and MEM186 conservative-path sanction, opted to leave per-element tokenization in place rather than adopt `@tailwindcss/typography`. Plugin ships its own opinionated gray scale via `prose-invert`; visual parity with our semantic tokens cannot be guaranteed without side-by-side PNG comparison, and dependency-add risk is high in autonomous mode. M003-UAT.md documents the exact migration steps if a human reviewer revisits. Captured as MEM201.

- **Items #1-#3 — human-judgment decision slots** *(documented in M003-UAT.md)*: Auth-shell unification (Login/Register/ExtensionAuth use a glass-card-style wrapper now tokenized vs ForgotPassword/ForgotPasswordConfirm/VerifyEmail using `AuthCard.tsx`); ContactUs 3-card collapse (3 near-identical email-cards → potentially one card with recipient toggle); BuildListsCatalog sidebar drawer (left filter sidebar pushes content rightward at narrow viewports → drawer-vs-bottom-sheet at `<lg`, likely needs new `ui/drawer.tsx`). Each slot has file:line refs, observation notes, trade-off enumeration, and a verdict checkbox.

Cascade refresh per MEM156/MEM160: DangerActionPanel refactor is pixel-equivalent to inline JSX — Playwright `polish-coverage.spec.ts` ran 120/120 baselines clean with zero PNG drift. Confirmed via `git status --short -- frontend/e2e/polish-coverage.spec.ts-snapshots/` returning empty.

**T02 — vitest grep-guard extension** (commit `d79f15b`). Extended `frontend/src/__tests__/no-legacy-primitives.test.ts` with a new `describe('M003-S06: no legacy design-system re-entry')` block containing three `it()` assertions promoting per-PR `rg` gates into vitest assertions: (1) raw legacy palette utilities (combines standing palette gates 1+2), (2) `glass-*` class references, (3) hand-rolled patterns now that ui/* primitives exist (`<textarea`, inline loading-overlay, inline `getStatusBadge`/`getPriorityBadge` factories). Refactored to a shared `scan(globs, patterns, allowlist)` helper rather than duplicating per-assertion bodies — captured as MEM195. Allowlists exclude `index.css`, `styles/tokens.css`, each ui/* primitive source, and the guard file itself.

Verification probe: created temporary `frontend/src/pages/__probe_violation__.tsx` with one violation per assertion. Probe run produced 3 failing tests with file:line:match output. Probe deleted before final verification run, which is now green: 4/4 vitest tests pass, eslint clean, tsc -b --noEmit clean.

**T03 — fresh 12-gate close gauntlet + M003-UAT.md SHA-stamping** (commit `fb922fc`). All 12 standing close gates re-ran fresh in this session and exited at expected pass codes:

Grep gates 1-7 (exit 1 / zero hits = pass): raw palette utilities, text-accent utilities, glass-card|glass-button class re-entry, className=*glass* class re-entry, var(--legacy-) consumer references, consumer-class re-entry (btn-primary/input-modern/etc.), index.css self-inspection (@theme/--primary-N/.glass-card/etc.).

Toolchain gates 8-12 (exit 0 = pass): tsc -b --noEmit ~12s, eslint zero errors, vitest 597/597 across 90 files in 5.41s (3 more than S05's 594 from T02 extensions), vite build 4.47s + prerender 7 routes 11.1s, full Playwright suite 155 passed / 10 skipped / 0 failed at 3 viewports.

Per-gate evidence persisted under `.gsd/milestones/M003/slices/S06/gauntlet/gate{1..12}-*.txt` — 12 files for 12 gates. Captured as MEM197.

**Self-trip fix in `no-legacy-primitives.test.ts`:** First gate-3/4 run hit non-zero with matches in T02's new test file itself (literal `glass-*` strings in regex sources and comments). Fixed via string-concat regex construction: `new RegExp('\\bgla' + 'ss-(?:card|button)?\\b')`. Comments and `it()` test name rewritten to use `glassNAME`. After the fix, gates 3+4 exit 1 (clean), and the vitest assertion still works correctly. Extends MEM163 placeholder convention from comments-only to regex sources. Captured as MEM196.

**M003-UAT.md finalization:** Top-level summary block added citing SHA `d79f15b`, framing M003 as closed in auto-mode and operator UAT items as non-blocking follow-ups (per MEM142). Verified all 14 file paths referenced in the document resolve to real files in the post-S05 substrate.

## What this slice established for downstream

- **The M003 design-system migration is closed.** Zero raw palette utility hits, zero `glass-*` hits, zero legacy `:root`/`@theme` consumer hits anywhere in `frontend/src/`. `vite build` succeeds against the 94-line post-S04 `index.css`. The grep-guard extension means re-entry surfaces at vitest time, not just per-PR rg time.
- **The polish-coverage spec from S05** (120 PNG baselines across 40 routes × 3 viewports) is the standing visual-regression surface for M004+.
- **DangerActionPanel** is available as `frontend/src/components/admin/DangerActionPanel.tsx` for any future admin-page danger sections.
- **3 IA decisions await human judgment** (auth-shell unification, ContactUs 3-card collapse, BuildListsCatalog sidebar drawer) with full trade-off enumeration in `M003-UAT.md`. M004 planning should consume that document.
- **360px manual walkthrough** is operator-driven follow-up captured in M003-UAT.md — auto-mode cannot drive a real browser at 360px. Per MEM142, this does not block slice/milestone close.
- **Per-gate evidence pattern** (MEM197) is now available for future milestone-close gauntlets.

## Key follow-ups for M004

1. Operator runs the 360px manual walkthrough checklist in `M003-UAT.md` and records verdicts.
2. Operator resolves the 3 human-judgment IA decisions with verdict checkboxes.
3. Optional: revisit `@tailwindcss/typography` for ViewBuildLog if visual parity can be confirmed.
4. Optional: revisit UserManagement 11-column table responsive options (b)-(d) if scroll-as-affordance proves insufficient.

## Verification

All slice-level verification gates ran fresh in this session (T03 captured under `.gsd/milestones/M003/slices/S06/gauntlet/gate{1..12}-*.txt`) and re-spot-checked at slice close:

**Grep gates 1-7 (exit 1 / zero hits = pass):**
1. `rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → zero hits
2. `rg 'text-accent-(emerald|amber|rose|purple)' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → zero hits
3. `rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → zero hits (after T03 self-trip fix)
4. `rg 'className=.*\bglass\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → zero hits (after T03 self-trip fix)
5. `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → zero hits
6. `rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' frontend/src/{...}/` → zero hits
7. `rg -c '@theme|--primary-[0-9]|.glass-card|.btn-primary|...' frontend/src/index.css` → zero hits

**Toolchain gates 8-12 (exit 0 = pass):**
8. `cd frontend && npm run type-check` → tsc -b --noEmit clean (~12s)
9. `cd frontend && npm run lint` → zero eslint errors (~7s)
10. `cd frontend && npm test -- --run` → 597/597 tests across 90 files (5.41s), exit 0 — 3 more tests than S05's 594 from T02 grep-guard extensions
11. `cd frontend && npm run build` → vite 4.47s + prerender 7 routes 11.1s, exit 0
12. `cd frontend && npx playwright test` → 155 passed / 10 skipped / 0 failed at 3 viewports (48.5s), exit 0

**Slice-specific deliverables:**
- `.gsd/milestones/M003/M003-UAT.md` exists (171 lines) with 6 sections (3 human-judgment + 3 auto-resolved) and SHA-stamped summary block
- 12 evidence files persisted under `.gsd/milestones/M003/slices/S06/gauntlet/`
- `frontend/src/components/admin/DangerActionPanel.tsx` created and consumed by 3 panels in SystemAdmin
- `frontend/src/__tests__/no-legacy-primitives.test.ts` extended with 3 new assertions (4 total tests pass)
- `git status --short -- frontend/e2e/` → zero PNG baseline drift

**Spot-check at slice close:** Re-ran gate 1 (raw palette utilities) — exit 1 / zero hits. Working tree clean. All 3 task commits landed on milestone/M003 branch (`f0737f2`, `d79f15b`, `fb922fc`).

All verification phrasing per MEM142 — neutral wording throughout, no banned strings.

## Requirements Advanced

None.

## Requirements Validated

- R061 — S06 ran fresh 12-gate milestone-close gauntlet (7 grep + 5 toolchain) — all green with per-gate evidence persisted under .gsd/milestones/M003/slices/S06/gauntlet/. Vitest 597/597, Playwright 155 passed across 3 viewports, vite build clean against post-S04 index.css. M003-UAT.md operator handoff prepared with 3 human-judgment decision slots; 3 auto-judgable IA deferrals resolved (DangerActionPanel extraction + UserManagement scroll-lock + ViewBuildLog prose deferral). Vitest grep-guard extended to block raw-palette/glass-*/hand-rolled-primitive re-entry.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"Two deviations recorded across the 3 tasks:

**T01 — DangerActionPanel scope reduction:** Plan specified '10 near-identical danger sections in SystemAdmin.tsx collapse to 10 component instances.' Reality: only 3 sections were genuinely shape-compatible (the Deletion-options accordion: cars/global-parts-and-manufacturers/bucket-cleanup). The Migrations and Data-Initialization sections at the top of the page use Card chrome with h2/subtitle/own-dialog-flow and are not extraction candidates. Refactored what actually shares structure (3 panels), captured as MEM198 (reality-check slice-plan section counts before extraction). Documented in M003-UAT.md.

**T01 — DangerActionPanel API simplified:** Plan suggested `confirmDialogProps` as a panel API. Implementation omits it — bucket-cleanup has dual buttons (List + Purge) where only Purge is dialog-gated, making a single `confirmDialogProps` prop a poor fit. Component instead exposes `children` slot for full composition flexibility. Captured as MEM199.

**T03 — Self-trip fix in T02's grep-guard test file:** Not a deviation from plan; a natural part of 'run gates fresh and capture evidence'. First gate-3/4 run hit non-zero with matches in the new test file's literal regex sources. Fixed in-place via string-concat regex construction per MEM163/MEM180 conventions. Without this fix, gates would not be green this session. Captured as MEM196."

## Known Limitations

"None blocking. Auto-mode cannot drive a real browser at 360px width — the 360px manual walkthrough in M003-UAT.md is operator-driven follow-up, captured per MEM142 as non-blocking. The 3 human-judgment IA decision slots in M003-UAT.md remain by design — they are operator-judgment items requiring side-by-side visual comparison and UX trade-off resolution beyond what auto-mode can decide. The vitest grep-guard hand-rolled-primitive regex is heuristic-only (literal-token-order match) and could be slipped past by reformulation; accepted trade-off, future false-negatives can be tightened."

## Follow-ups

"## Operator-driven follow-ups (non-blocking per MEM142)

1. **360px manual walkthrough** — Operator opens M003-UAT.md '360px Manual Walkthrough' section, sets DevTools viewport to 360×640, walks the 11 priority pages (Home, PartsCatalog, ViewPart, ViewBuildList, ViewCar, Login, Register, Header, AccountAlerts, AdminDashboard, AdminExtractionHealth), records verdict per page.

2. **3 human-judgment IA decisions** —
   - **Auth-shell unification**: Login/Register/ExtensionAuth (glass-card-style, now tokenized) vs ForgotPassword/ForgotPasswordConfirm/VerifyEmail (AuthCard component). Decide which shell wins or merge into a third primitive.
   - **ContactUs 3-card collapse**: 3 near-identical email-cards. Collapsing to one card with recipient toggle is medium-to-high-impact UX change.
   - **BuildListsCatalog sidebar drawer**: Left filter sidebar pushes content rightward at narrow viewports. Decide drawer-vs-bottom-sheet at <lg breakpoint; likely needs new ui/drawer.tsx primitive.

## M004 backlog candidates (deferred from S06)

3. **ViewBuildLog @tailwindcss/typography adoption** — currently per-element tokenization preserved per MEM186. Plugin adoption requires side-by-side PNG comparison to confirm visual parity with semantic tokens. Migration steps documented in M003-UAT.md.

4. **UserManagement 11-column table responsive options (b)-(d)** — locked as acceptable-as-scroll for M003. Options: priority-drop columns / stack on mobile / virtualized horizontal scroll.

5. **Vitest grep-guard heuristic tightening** — current hand-rolled regex (`<textarea\\s`, inline loading-overlay literal, `getStatusBadge`/`getPriorityBadge` factory names) is heuristic-only. Reformulations of the literal token order would slip past. False-negatives can be tightened if discovered."

## Files Created/Modified

- `frontend/src/components/admin/DangerActionPanel.tsx` — NEW (~58 LOC) — panel chrome (heading + description + tone-driven outer container) with children slot for interactive content. API: { title, description, dangerColor: 'destructive'|'warning'|'info', children }.
- `frontend/src/pages/admin/SystemAdmin.tsx` — Refactored 3 deletion-accordion panels (cars=warning, global-parts/manufacturers=destructive, bucket-cleanup=info) to consume DangerActionPanel.
- `frontend/src/pages/admin/UserManagement.tsx` — One-line decision-record code comment added above existing overflow-x-auto table boundary referencing M003-UAT.md and MEM179 (acceptable-as-scroll lock).
- `frontend/src/__tests__/no-legacy-primitives.test.ts` — Extended with 3 new vitest assertions (raw-palette, glass-*, hand-rolled primitives) using shared scan() helper. T03 self-trip fix: glass regex sources constructed via string concatenation.
- `.gsd/milestones/M003/M003-UAT.md` — NEW — operator handoff document with priority-page verdict table, 360px walkthrough checklist, 3 human-judgment decision slots, 3 auto-resolved sections, SHA-stamped (d79f15b) summary block.
- `.gsd/milestones/M003/slices/S06/gauntlet/gate1-raw-palette.txt` — Persisted evidence: raw palette utility grep gate (exit 1 / zero hits).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate2-text-accent.txt` — Persisted evidence: text-accent grep gate (exit 1 / zero hits).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate3-glass-class.txt` — Persisted evidence: glass-card|glass-button class re-entry grep gate (exit 1 / zero hits after T03 self-trip fix).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate4-classname-glass.txt` — Persisted evidence: className=*glass* class re-entry grep gate (exit 1 / zero hits after T03 self-trip fix).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate5-var-legacy.txt` — Persisted evidence: var(--legacy-) consumer reference grep gate (exit 1 / zero hits).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate6-consumer-class.txt` — Persisted evidence: consumer-class re-entry grep gate (exit 1 / zero hits).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate7-index-css.txt` — Persisted evidence: index.css self-inspection grep gate (exit 1 / zero hits).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate8-type-check.txt` — Persisted evidence: tsc -b --noEmit (exit 0, ~12s).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate9-lint.txt` — Persisted evidence: eslint . (exit 0, zero errors).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate10-vitest.txt` — Persisted evidence: vitest single-pass (exit 0, 597/597 tests across 90 files in 5.41s).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate11-vite-build.txt` — Persisted evidence: vite build + prerender 7 routes (exit 0, vite 4.47s + prerender 11.1s).
- `.gsd/milestones/M003/slices/S06/gauntlet/gate12-playwright.txt` — Persisted evidence: full Playwright suite at 3 viewports (exit 0, 155 passed / 10 skipped / 0 failed in 48.5s).
