---
id: T01
parent: S01
milestone: M003
key_files:
  - frontend/src/styles/tokens.css
  - frontend/src/components/ui/alert.tsx
key_decisions:
  - Added --success/--warning/--info plus -foreground companions in :root and mirrored them in @theme as --color-* hsl(var()) entries — exact pattern-match with --destructive.
  - Kept --info distinct from --primary even though both resolve to 217 91% 60% — semantic clarity over channel deduplication; lets S04 re-tune independently.
  - Migrated alert.tsx success variant in this same atomic commit because it's the only ui/* primitive with raw-palette utilities; consolidating it here keeps subsequent T02+ swaps purely consumer-side.
duration: 
verification_result: passed
completed_at: 2026-04-26T20:53:14.133Z
blocker_discovered: false
---

# T01: feat(tokens): add success/warning/info semantic tokens and migrate alert success variant

**feat(tokens): add success/warning/info semantic tokens and migrate alert success variant**

## What Happened

Atomic precursor commit for the M003/S01 palette migration. Added three new semantic status tokens to `frontend/src/styles/tokens.css` — `--success` (142 71% 45%), `--warning` (38 92% 50%), `--info` (217 91% 60%) — each with a `-foreground` companion. All six tokens were declared in the `:root` block under the existing `Semantic` group (next to `--destructive`) and mirrored in the Tailwind v4 `@theme` bridge as `--color-success`, `--color-warning`, `--color-info` (plus their foregrounds), exposing utilities like `bg-success`, `text-warning`, `border-info`, etc. Pattern-matches the existing `--destructive` token surface exactly: HSL-channel values composable via `hsl(var(--token) / <alpha>)`.\n\nAs noted in the task plan, `--info` shares HSL channels with `--primary` (both 217 91% 60%) since indigo-500 ≈ primary-500 in this palette. Kept the token name distinct anyway — semantic clarity in consumer code is more important than channel deduplication, and downstream S04 retirement work might re-tune one without the other.\n\nFixed `frontend/src/components/ui/alert.tsx` `success` variant — the only `ui/*` raw-palette violator — replacing `border-emerald-500/50 bg-emerald-500/10 text-emerald-300 [&>svg]:text-emerald-300` with `bg-success/10 text-success border-success/50 [&>svg]:text-success`. The variant API is unchanged: existing `<Alert variant="success">` consumers (e.g. `ConfirmationAlert`, `SuccessAlert`) keep working; only the resolved class names differ.\n\nNo consumer file in `frontend/src/` uses the new tokens yet — that's the point of this commit. Subsequent S01 tasks (T02+) will perform the consumer swaps onto these tokens. The legacy `@theme` palette block in `index.css` survives untouched; per the slice plan it's deleted in S04.

## Verification

Ran the slice-/task-level verification chain end-to-end:\n\n1. `npm ci` (cold install, 816 packages) — succeeded.\n2. `npm run build` — `tsc -b && vite build && node scripts/prerender.mjs` all green; 7 prerender routes succeeded; build completed in 4.43s with no token-related warnings or errors. Proves the new tokens declared but unused don't break compilation (negative-test gate from the task plan).\n3. `grep -q 'success-foreground' src/styles/tokens.css` — exit 0.\n4. `grep -q 'bg-success/10 text-success border-success/50' src/components/ui/alert.tsx` — exit 0.\n5. `rg 'emerald-500' src/components/ui/alert.tsx` — exit 1 (no matches), confirming the alert success variant no longer references raw emerald-500 utilities.\n\nNo runtime/observability changes — pure CSS/class-vocabulary swaps.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm run build` | 0 | ✅ pass | 16000ms |
| 2 | `grep -q 'success-foreground' src/styles/tokens.css` | 0 | ✅ pass | 5ms |
| 3 | `grep -q 'bg-success/10 text-success border-success/50' src/components/ui/alert.tsx` | 0 | ✅ pass | 5ms |
| 4 | `rg 'emerald-500' src/components/ui/alert.tsx` | 1 | ✅ pass | 8ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/styles/tokens.css`
- `frontend/src/components/ui/alert.tsx`
