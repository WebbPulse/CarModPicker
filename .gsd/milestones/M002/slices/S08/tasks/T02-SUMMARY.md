---
id: T02
parent: S08
milestone: M002
key_files:
  - frontend/src/styles/tokens.css
  - frontend/src/index.css
key_decisions:
  - Used HSL-channel values (e.g. '222 47% 6%') with hsl() wrapping in @theme — matches shadcn convention and lets consumers compose alpha later.
  - Added shadow scale and z-index layers in tokens.css alongside color/radius even though the verification chain only checks color tokens — the task plan calls them out explicitly and S08 primitives will need them.
  - Kept legacy --primary-*/--neutral-*/--accent-* blocks untouched per the task plan — new tokens are additive and parallel until components/common/ gets reskinned in S12.
duration: 
verification_result: passed
completed_at: 2026-04-25T19:21:10.932Z
blocker_discovered: false
---

# T02: Add shadcn-compatible dark-palette tokens.css with HSL channels + Tailwind v4 @theme bridge, imported from index.css

**Add shadcn-compatible dark-palette tokens.css with HSL channels + Tailwind v4 @theme bridge, imported from index.css**

## What Happened

Created `frontend/src/styles/tokens.css` and wired it into `frontend/src/index.css`. The new file declares the full shadcn-standard token vocabulary on `:root` using HSL-channel values (e.g. `222 47% 6%`) so consumers can compose alpha via `hsl(var(--background) / <alpha>)`. Color tokens cover background/foreground, card, popover, primary/secondary/accent, muted, destructive (each with their `-foreground` pair), plus border/input/ring. Spacing exposes `--radius` (0.5rem default) and the `--radius-sm/md/lg/xl` scale. Shadow scale `--shadow-sm/md/lg/xl` and z-index layers `--z-dropdown/modal/toast` are also declared per the task plan.

The `@theme` block in the same file bridges every token into Tailwind v4 utilities by mapping each `--color-*` to `hsl(var(--token))` so `bg-background`, `text-foreground`, `border-border`, `ring-ring`, `rounded-sm/md/lg/xl`, and `shadow-sm/md/lg/xl` resolve. `--font-sans` mirrors the Inter stack already in body styles; `--font-mono` adds a system mono stack. The block style mirrors the existing `@theme` block in index.css, exactly as the plan instructed.

In `index.css` I added a single line — `@import './styles/tokens.css';` — immediately after `@import 'tailwindcss';`. The existing `@theme` and `:root` blocks (the legacy `--primary-*/--neutral-*/--accent-*` palette consumed by `components/common/`) are untouched, since they remain live until S12. New tokens are strictly additive.

This task is pure CSS — no runtime, no failure modes, no load profile, no negative tests, matching the task plan's explicit "no Failure Modes etc" note. Slice-level Playwright verification stays deferred to T05 per the slice plan.

## Verification

Ran the full task verification chain from the plan: `grep -q '@import .\./styles/tokens.css' src/index.css && grep -q -- '--background:' src/styles/tokens.css && grep -q -- '--ring:' src/styles/tokens.css && grep -q -- '--radius:' src/styles/tokens.css && grep -q '@theme' src/styles/tokens.css && npm run build > /tmp/s08-t02-build.log 2>&1 && grep -q '\.bg-background\|--background' dist/assets/*.css`. Exit code 0. The build (`tsc -b && vite build` + prerender postbuild) succeeded in 3.40s with the existing chunk-size warning unchanged, and the bundled CSS at `dist/assets/index-B8rBQysB.css` contains `--background:222 47% 6%`, confirming Tailwind v4's `@theme` bridge resolved the new tokens into the production stylesheet. No test runs needed — pure CSS substrate.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `grep -q '@import .\./styles/tokens.css' src/index.css && grep -q -- '--background:' src/styles/tokens.css && grep -q -- '--ring:' src/styles/tokens.css && grep -q -- '--radius:' src/styles/tokens.css && grep -q '@theme' src/styles/tokens.css && npm run build > /tmp/s08-t02-build.log 2>&1 && grep -q '\.bg-background\|--background' dist/assets/*.css` | 0 | pass | 6000ms |

## Deviations

None.

## Known Issues

None. Existing Vite "chunks larger than 600 kB" warning on `vendor-CIqYcDgw.js` is pre-existing and unrelated to this task.

## Files Created/Modified

- `frontend/src/styles/tokens.css`
- `frontend/src/index.css`
