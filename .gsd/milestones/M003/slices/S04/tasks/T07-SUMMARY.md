---
id: T07
parent: S04
milestone: M003
key_files:
  - frontend/src/index.css
key_decisions:
  - Single atomic Write rewrite over incremental Edit calls — 14+ separate deletions across one file would compound risk of partial-state breakage between edits; whole-file rewrite is auditable in one diff and lets the build verify the rewrite atomically. Same approach T06 used.
  - Deleted .animate-pulse with the legacy @keyframes pulse — verified our rule was byte-identical to Tailwind v4's built-in (`pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite`) and confirmed no @keyframes pulse / @utility animate-pulse exists in tokens.css, so the 4 known consumers (Pricing.tsx, About.tsx, Support.tsx, spinner.tsx) fall through cleanly to Tailwind's built-in. Zero behavior change.
  - Final file is 94 lines vs. task plan's ~50-80 estimate — the overage is the preserved scrollbar styling block (~30 lines) and tile-grid utilities (~12 lines), both on the PRESERVE list. Correct overage, not missed deletion.
duration: 
verification_result: passed
completed_at: 2026-04-26T23:09:20.728Z
blocker_discovered: false
---

# T07: Hard-delete all 11 keyframes, 10 .animate-* classes, and .skeleton/.hero-gradient/.text-gradient/.border-gradient/.shadow-glow from index.css; vite build green

**Hard-delete all 11 keyframes, 10 .animate-* classes, and .skeleton/.hero-gradient/.text-gradient/.border-gradient/.shadow-glow from index.css; vite build green**

## What Happened

Pass-2 of the S04 hard-delete: removed the legacy animation + decorative layer from `frontend/src/index.css`. Deleted all 11 `@keyframes` blocks (`fadeInScale`, `slideInUp`, `slideInLeft`, `slideInRight`, `pulse`, `shimmer`, `float`, `glow`, `gradientShift`, `borderGlow`, `progress-indeterminate`) and their 10 corresponding `.animate-*` consumer classes (the 11th keyframe `progress-indeterminate` had no `.animate-*` rule — it's referenced by name from a tokens.css `@utility`). Also deleted `.skeleton` (zero consumers), `.hero-gradient` (zero consumers), `.text-gradient` (now lives in tokens.css from T04), `.border-gradient` (zero consumers), and `.shadow-glow` + `.shadow-glow:hover` (zero consumers).

Preserved exactly what the task plan called out: `@import 'tailwindcss'` + `@import './styles/tokens.css'` header, `* { box-sizing }`, the `body` block (with T05's `hsl(var(--background))` form per T06's flatten), `::-webkit-scrollbar*` rules, `.global-parts-table-scroll-layer`, `*:focus-visible`, `::selection` / `::-moz-selection`, `.main-content .container`, and `.tile-grid`/`.tile-grid-compact`.

Single atomic Write rewrite (per R053 and the same approach T06 used) over incremental Edit calls — 14+ separate deletions with precise line ranges across one file would compound risk of partial-state breakage between edits, whereas one whole-file rewrite is auditable in a single diff and lets the build verify the rewrite atomically.

Verified the `.animate-pulse` rule's identity with Tailwind v4's built-in (`pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite`) before deletion and confirmed via grep that no `@keyframes pulse` or `@utility animate-pulse` exists in tokens.css — so the 4 known `animate-pulse` consumers (Pricing.tsx, About.tsx, Support.tsx, spinner.tsx) fall through cleanly to Tailwind's built-in with zero behavior change. The `vite build` succeeding is the load-bearing proof: any consumer surviving with a now-deleted animation class would have triggered an unresolved utility error.

Final `frontend/src/index.css` is 94 lines (down from 311 pre-T07, down from 757 pre-S04). Slightly above the task plan's ~50–80 estimate because the preserved scrollbar styling block (~30 lines) and tile-grid utilities (~12 lines) are larger than that ceiling implies — both are explicitly load-bearing per the task plan's PRESERVE list, so this is correct overage rather than missed deletion.

## Verification

All three T07 verification gates pass (rg exit=1 = zero matches = desired pass condition):
- Gate 1: `rg -c '@keyframes (fadeInScale|slideInUp|slideInLeft|slideInRight|pulse|shimmer|float|glow|gradientShift|borderGlow|progress-indeterminate)' frontend/src/index.css` → exit 1 (0 matches)
- Gate 2: `rg -c '\.animate-(fadeInScale|slideInUp|slideInLeft|slideInRight|pulse|shimmer|float|glow|gradient|border-glow)' frontend/src/index.css` → exit 1 (0 matches)
- Gate 3: `rg -c '\.(skeleton|hero-gradient|text-gradient|border-gradient|shadow-glow)' frontend/src/index.css` → exit 1 (0 matches)
- Final: `wc -l frontend/src/index.css` → 94 lines

Slice-level enforcement gate: `cd frontend && npm run build` → ✓ built in 4.53s + prerender complete (7 routes in 11.1s). This is the canonical S04 structural signal — the build IS the enforcement now, and any reintroduction of a deleted class would surface as a vite build error naming the unresolved utility.

Consumer-dir cross-checks: `rg 'className=.*\b(skeleton|hero-gradient|border-gradient|shadow-glow)\b'` over `frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}` → exit 1 (0 matches). Same regex for `animate-shimmer|animate-gradient|animate-border-glow|animate-slideInRight` → exit 1 (0 matches). The 4 known `animate-pulse` consumers fall through to Tailwind v4's built-in.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run build` | 0 | ✅ pass | 15630ms |
| 2 | `rg -c '@keyframes (fadeInScale|slideInUp|slideInLeft|slideInRight|pulse|shimmer|float|glow|gradientShift|borderGlow|progress-indeterminate)' frontend/src/index.css` | 1 | ✅ pass | 50ms |
| 3 | `rg -c '\.animate-(fadeInScale|slideInUp|slideInLeft|slideInRight|pulse|shimmer|float|glow|gradient|border-glow)' frontend/src/index.css` | 1 | ✅ pass | 50ms |
| 4 | `rg -c '\.(skeleton|hero-gradient|text-gradient|border-gradient|shadow-glow)' frontend/src/index.css` | 1 | ✅ pass | 50ms |
| 5 | `wc -l frontend/src/index.css` | 0 | ✅ pass (94 lines, target ~50-80 + ~30 preserved scrollbar block + ~12 tile-grid utilities) | 30ms |
| 6 | `rg -n 'className=.*\b(skeleton|hero-gradient|border-gradient|shadow-glow)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}` | 1 | ✅ pass | 80ms |
| 7 | `rg -n 'className=.*\b(animate-shimmer|animate-gradient|animate-border-glow|animate-slideInRight)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}` | 1 | ✅ pass | 80ms |

## Deviations

Final line count is 94 vs. task plan's stated ~50-80 ballpark. The delta is the preserved `::-webkit-scrollbar*` block (~30 lines) and the `.tile-grid` / `.tile-grid-compact` utilities (~12 lines), both explicitly on the PRESERVE list. Not a missed deletion — a load-bearing under-estimate in the plan's ballpark.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/index.css`
