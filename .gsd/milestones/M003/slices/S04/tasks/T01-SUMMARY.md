---
id: T01
parent: S04
milestone: M003
key_files:
  - frontend/src/styles/tokens.css
key_decisions:
  - Translated legacy `glow` keyframe's `var(--primary-500)` (#3b82f6) and `rgba(59,130,246,*)` references to `hsl(var(--primary))` and `hsl(var(--primary) / *)` — verified --primary is `217 91% 60%` which is the HSL of #3b82f6, so visually identical and tokenized. The other four keyframes are byte-for-byte copies of the legacy rules.
  - Confirmed via grep that animate-slideInRight/shimmer/gradient/border-glow have zero consumers in src/, so safely omitted per task plan.
  - Did not register an animate-pulse override — the legacy rule is identical to Tailwind v4's built-in, and T07's deletion falls through to the built-in with no behavior change.
duration: 
verification_result: passed
completed_at: 2026-04-26T22:55:24.939Z
blocker_discovered: false
---

# T01: Add tokenized @utility animate-fadeInScale/slideInUp/slideInLeft/float/glow blocks to tokens.css so S04 pass-2 deletion of index.css legacy keyframes leaves consumer class names resolving

**Add tokenized @utility animate-fadeInScale/slideInUp/slideInLeft/float/glow blocks to tokens.css so S04 pass-2 deletion of index.css legacy keyframes leaves consumer class names resolving**

## What Happened

Precursor add for S04's pass-2 deletion (T07). Appended five tokenized animation `@utility` blocks plus their five backing `@keyframes` to `frontend/src/styles/tokens.css` so the consumer sites in Home/About/Pricing/Support/Checkout/ContactUs/Register/App keep resolving `animate-fadeInScale`, `animate-slideInUp`, `animate-slideInLeft`, `animate-float`, and `animate-glow` after T07 deletes the legacy `.animate-*` rules from `index.css`.

Pattern-matched the existing M002/S08 `@keyframes enter` / `@utility animate-in` block at `tokens.css:119-177`. Each new keyframe is a byte-for-byte copy of its legacy counterpart (`index.css` lines 124-214) so Playwright Home/kitchen-sink baselines do not drift — same durations (0.4s/0.5s/4s/2s), same easings (`cubic-bezier(0.4, 0, 0.2, 1) forwards` for entrance, `ease-in-out infinite` for float, `ease-in-out infinite alternate` for glow), same transform geometry.

One translation was required: the legacy `glow` keyframe references `var(--primary-500)` (`#3b82f6`) which dies after T06's `:root` deletion. Verified that `--primary` in `tokens.css` is `217 91% 60%` (= HSL of #3b82f6), so rewrote glow's box-shadow to `hsl(var(--primary))` and replaced the hard-coded `rgba(59, 130, 246, 0.3|0.5)` with `hsl(var(--primary) / 0.3|0.5)` — visually identical, semantically tokenized.

Per task plan, intentionally skipped `animate-slideInRight`, `animate-shimmer`, `animate-gradient`, `animate-border-glow` after grep-verifying zero consumers in `frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/`. Also skipped `animate-pulse` because the legacy rule (`pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite`) is identical to Tailwind v4's built-in — T07's deletion will fall through to the built-in with zero behavior change.

This task does not yet exercise the load-bearing `npm run build` proof — that comes in T06 when the `@theme` palette block deletes. For now, the build still succeeds (legacy rules in `index.css` are untouched), confirming the `@utility` declarations parse cleanly under Tailwind v4 and don't conflict with the still-present legacy `.animate-*` classes.

## Verification

Ran the task plan's verification command verbatim:

1. `rg -q '@utility animate-fadeInScale' frontend/src/styles/tokens.css` — exit 0
2. `rg -q '@utility animate-slideInUp' frontend/src/styles/tokens.css` — exit 0
3. `rg -q '@utility animate-slideInLeft' frontend/src/styles/tokens.css` — exit 0
4. `rg -q '@utility animate-float' frontend/src/styles/tokens.css` — exit 0
5. `rg -q '@utility animate-glow' frontend/src/styles/tokens.css` — exit 0
6. `cd frontend && npm run build` — exit 0, vite built in 4.41s, prerender complete for 7 routes in 11.1s

Slice-level verification (`npm run build` as canonical structural signal): PASSES at this stage. The load-bearing T06/T07 deletion-then-build proof is still pending downstream, but T01's contribution to the slice is confirmed: five tokenized utilities are registered and Tailwind v4 accepts them without error.

Skipped-animation grep verification (additional check, not in the verify script): `rg 'animate-slideInRight|animate-shimmer|animate-gradient|animate-border-glow' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` returned zero matches — confirms the four animations the task plan instructed to skip are safe to omit.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -q '@utility animate-fadeInScale' frontend/src/styles/tokens.css && rg -q '@utility animate-slideInUp' frontend/src/styles/tokens.css && rg -q '@utility animate-slideInLeft' frontend/src/styles/tokens.css && rg -q '@utility animate-float' frontend/src/styles/tokens.css && rg -q '@utility animate-glow' frontend/src/styles/tokens.css` | 0 | ✅ pass | 80ms |
| 2 | `cd frontend && npm run build` | 0 | ✅ pass | 16500ms |
| 3 | `rg 'animate-slideInRight|animate-shimmer|animate-gradient|animate-border-glow' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass (zero hits — confirms safe to skip) | 50ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/styles/tokens.css`
