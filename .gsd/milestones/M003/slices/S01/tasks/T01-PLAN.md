---
estimated_steps: 14
estimated_files: 2
skills_used: []
---

# T01: Add `--success`/`--warning`/`--info` semantic tokens and fix `ui/alert.tsx` success variant

Atomic precursor commit. Adds the missing status semantic tokens to `frontend/src/styles/tokens.css` so subsequent swap tasks can map emerald → success, amber → warning, indigo → info, rose → destructive. Pattern-matches the existing token surface: HSL-channel values in `:root`, mirrored in the `@theme` bridge as `--color-<token>: hsl(var(--<token>))`. Also fixes `frontend/src/components/ui/alert.tsx` `success` variant (currently the only `ui/*` raw-palette violator) to consume the new `text-success`/`bg-success/10`/`border-success/50` vocabulary so the variant becomes the canonical success surface for all consumers.

Rationale (per R053, MEM149): the migration cannot complete without these tokens — emerald (success), amber (warning), indigo (info), rose (destructive — token already exists) all need a semantic landing pad. This commit is small, justified, and ships before any consumer swap depends on it. Bias remains consumption: only 3 new color tokens added (with `-foreground` companions), no primitives added, no keyframes added.

Values to use (HSL channels matching the dark palette):
- `--success: 142 71% 45%;` (emerald-500-ish)
- `--success-foreground: 144 70% 96%;`
- `--warning: 38 92% 50%;` (amber-500-ish)
- `--warning-foreground: 48 96% 89%;`
- `--info: 217 91% 60%;` (indigo-500-ish; matches existing primary HSL since indigo-500 ≈ primary-500 in this palette — keep distinct token name for semantic clarity)
- `--info-foreground: 213 100% 97%;`

## Failure Modes

Not applicable — this task adds CSS custom properties and edits one component file. No external dependencies, no async paths.

## Negative Tests

- `vite build` must succeed with the new tokens declared but no consumer using them yet (proves the token additions don't break compilation).
- After alert.tsx swap: existing `<Alert variant="success">` consumers (e.g. `frontend/src/components/__tests__/` if any) still render — class names changed, but the variant API is unchanged.

## Inputs

- `frontend/src/styles/tokens.css`
- `frontend/src/components/ui/alert.tsx`

## Expected Output

- `frontend/src/styles/tokens.css`
- `frontend/src/components/ui/alert.tsx`

## Verification

cd frontend && npm run build && grep -q 'success-foreground' src/styles/tokens.css && grep -q 'bg-success/10 text-success border-success/50' src/components/ui/alert.tsx && ! rg 'emerald-500' src/components/ui/alert.tsx
