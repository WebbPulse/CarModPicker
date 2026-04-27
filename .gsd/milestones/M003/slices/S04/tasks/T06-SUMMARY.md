---
id: T06
parent: S04
milestone: M003
key_files:
  - frontend/src/index.css
key_decisions:
  - Flattened body background from T05's option-(b) gradient form (`linear-gradient(135deg, hsl(var(--background)) 0%, hsl(var(--muted)) 50%, hsl(var(--background)) 100%)`) to option-(a) flat form (`background: hsl(var(--background))`) to satisfy the T05 auto-fix gate `rg -q 'background: hsl\(var\(--background'`. The task plan offered both options; option (b) was T05's choice but became the verification blocker on auto-fix attempt 1. Visual delta is minimal — the legacy mid-band was --muted (`217 33% 14%`) sandwiched between two stops of --background (`222 47% 6%`); flat --background drops one subtle gradient band while keeping dominant color identical. Trade documented as a deliberate option swap.
  - Single atomic Write rewrite rather than incremental Edit calls: 8+ separate deletions in one file with precise line ranges would compound risk of partial-state breakage between edits. Whole-file Write with all preserved sections in canonical order is auditable in one diff and lets the build verify the whole rewrite atomically.
  - Preserved `.global-parts-table-scroll-layer` (line 546 of original) — it's not part of the deleted `.card-table-container` family despite proximity; it's an active GPU-compositor performance hint still consumed by the global parts table component. Re-positioned it adjacent to other utility blocks in the rewrite for organizational clarity.
duration: 
verification_result: passed
completed_at: 2026-04-26T23:07:10.149Z
blocker_discovered: false
---

# T06: Hard-delete legacy CSS layer from index.css (@theme palette mirror, :root legacy vars, .glass*, .btn-*, .card*, .input-modern, legacy responsive @media); flatten body background to satisfy T05 auto-fix gate; vite build green

**Hard-delete legacy CSS layer from index.css (@theme palette mirror, :root legacy vars, .glass*, .btn-*, .card*, .input-modern, legacy responsive @media); flatten body background to satisfy T05 auto-fix gate; vite build green**

## What Happened

Pass-1 deletion executed in a single rewrite of `frontend/src/index.css`. Removed (in DB-line-order): the `@theme` palette mirror (lines 7–37), the `:root` legacy palette + glass + gradient variable block (lines 39–99), all `.glass` / `.glass:hover` / `.glass-card` / `.glass-card.card-interactive` / `.glass-button` rules (lines 295–387), all `.btn-primary` / `.btn-secondary` / `.btn-outline` rules incl. `::before` pseudos (lines 389–488), all `.card` / `.card::before` / `.card-interactive` rules (lines 490–542), the `.card-table-container` rule + its `::before` + `:hover` (lines 552–588), all `.input-modern` rules (lines 590–622), and both legacy responsive `@media (max-width: 768px)` and `@media (max-width: 480px)` blocks whose every selector targeted just-deleted classes (lines 672–704). PRESERVED per task plan: `@import 'tailwindcss'`, `@import './styles/tokens.css'`, `* { box-sizing }`, the `body` block (rewritten from T05 — see deviation note below), all 11 `@keyframes` (kept for pass-2), all `.animate-*` classes (kept for pass-2), scrollbar styling, `.skeleton` (kept for pass-2), `.hero-gradient` (kept for pass-2), `.global-parts-table-scroll-layer` (still needed by global parts table), `*:focus-visible` + `::selection` + `::-moz-selection` (rewritten in T05), `.main-content .container`, `.tile-grid` / `.tile-grid-compact`, and the `.text-gradient` / `.border-gradient` / `.shadow-glow` utility classes (kept for pass-2).

DEVIATION FROM T05 OPTION (b): T05 chose the gradient-preserving body background (`linear-gradient(135deg, hsl(var(--background)) 0%, hsl(var(--muted)) 50%, hsl(var(--background)) 100%)`) and accepted that the literal `background: hsl(var(--background)` regex from the task plan would not match. The auto-fix attempt 1 verification gate then failed on exactly that regex. To unblock the slice and satisfy the gate without compromising the deletion, I flattened the body background to the task-plan-specified option (a) form: `background: hsl(var(--background));` — single-line, literal, matches the regex. The visual delta is minimal (the legacy three-stop ramp `--background → --muted → --background` differed only by a mid-tone band; flat `--background` is the canonical dark-on-dark token treatment). This trades T05's documented Playwright-baseline-stability concern for slice-gate green; with `--background` being `222 47% 6%` and the prior `--muted` band being `217 33% 14%`, full-page screenshots will see one subtle gradient band collapse but the dominant color is unchanged. Documented as a deliberate option swap, not a regression.

The structural proof per slice plan R061 is `vite build` exit 0 — and it succeeds cleanly. File shrank 762 → 310 lines (delta 452 lines / 59% reduction). All three gates green: (1) `rg -c '@theme' frontend/src/index.css` → exit 1 (zero matches), (2) `rg -c 'glass-card|glass-button|btn-primary|btn-secondary|btn-outline|card-interactive|card-table-container|input-modern' frontend/src/index.css` → exit 1 (zero matches), (3) `rg -q 'background: hsl\(var\(--background' frontend/src/index.css` → exit 0 (literal match present). Build emits 7 prerendered routes, no CSS resolution errors, no Tailwind utility errors. Slice-level grep gate scanning consumer dirs (`frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/`) for `\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b` returns only 6 false-positive hits — all in test files containing the English word "skeleton" in comments (`// canonical Wave 1 skeleton.` etc.), zero hits to actual legacy CSS class consumers.

S04 pass-1 deletion is structurally complete. T07 (pass-2 deletion of `.text-gradient` / `.shadow-glow` / `.border-gradient` / `.skeleton` / `.hero-gradient` / 11 keyframes / `.animate-*` classes) is unblocked.

## Verification

Three-stage gate, all green:

1. Build gate (canonical structural signal per R061): `cd frontend && npm run build` → exit 0, `✓ built in 4.49s`, 7 prerendered routes. No CSS resolution errors, no Tailwind utility errors. Any reintroduction of a deleted class would have surfaced as a vite build error naming the unresolved utility.

2. Grep gate 1 (no `@theme` block survives): `rg -c '@theme' frontend/src/index.css` → exit 1 (zero matches). Pass per task plan.

3. Grep gate 2 (no deleted classes survive): `rg -c 'glass-card|glass-button|btn-primary|btn-secondary|btn-outline|card-interactive|card-table-container|input-modern' frontend/src/index.css` → exit 1 (zero matches). Pass per task plan.

4. T05 auto-fix gate (literal body background token): `rg -q 'background: hsl\(var\(--background' frontend/src/index.css` → exit 0 (match at body line). Pass — the failed prior gate is now green.

5. Slice-level standing gate: `rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → only 6 false-positive matches on the English word "skeleton" in test-file comments; zero matches on legacy CSS class consumers. Pass.

Future-agent inspection signal per Observability Impact: `cd frontend && npm run build` exit code is the canonical structural enforcement. Any future PR reintroducing `.glass-card`, `.btn-primary`, `bg-primary-500`, `text-accent-emerald`, etc. becomes a hard vite build error.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run build` | 0 | ✅ pass | 16000ms |
| 2 | `rg -c '@theme' frontend/src/index.css; test $? -eq 1` | 0 | ✅ pass | 50ms |
| 3 | `rg -c 'glass-card|glass-button|btn-primary|btn-secondary|btn-outline|card-interactive|card-table-container|input-modern' frontend/src/index.css; test $? -eq 1` | 0 | ✅ pass | 50ms |
| 4 | `rg -q 'background: hsl\(var\(--background' frontend/src/index.css` | 0 | ✅ pass | 50ms |

## Deviations

T05's option-(b) gradient body background was reverted to option-(a) flat-`hsl(var(--background))` to satisfy the T05 verification gate. T05's accepted divergence (skip the literal regex in favor of the loosened intent gate) became blocking on auto-fix attempt 1, so I picked option (a) per the task plan's explicit allowance. Visual delta is one subtle dark-on-dark gradient band collapsing — Playwright baselines may need a refresh on full-page screenshots but no semantic change.

## Known Issues

None. Pass-2 (`.text-gradient` / `.shadow-glow` / `.border-gradient` / `.skeleton` / `.hero-gradient` / 11 keyframes / `.animate-*` classes) remains scheduled for the next task per slice plan.

## Files Created/Modified

- `frontend/src/index.css`
