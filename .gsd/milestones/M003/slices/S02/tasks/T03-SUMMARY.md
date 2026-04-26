---
id: T03
parent: S02
milestone: M003
key_files:
  - frontend/src/components/shell/CookieConsentBanner.tsx
key_decisions:
  - Used `/80` for `hover:text-primary` (matches legacy --primary-200 lighter-on-hover intent) and `/90` for `hover:bg-primary` (matches legacy --primary-600 slightly-darker-on-hover intent), per the MEM154 hover-no-op repair pattern.
  - Did not touch the literal RGBA shadow on line 20 — it is not a palette token and the gate excludes it.
  - Did not modify tokens.css — --*-foreground tokens there are part of the semantic surface, not legacy shades, and are outside the consumer-dirs gate scope.
duration: 
verification_result: passed
completed_at: 2026-04-26T21:53:08.447Z
blocker_discovered: false
---

# T03: refactor(palette): swap 3 var(--primary-*) consumers in CookieConsentBanner.tsx for semantic border-primary/text-primary/bg-primary with /80 and /90 hover alphas

**refactor(palette): swap 3 var(--primary-*) consumers in CookieConsentBanner.tsx for semantic border-primary/text-primary/bg-primary with /80 and /90 hover alphas**

## What Happened

Migrated the three remaining `var(--primary-*)` arbitrary-value className consumers in `frontend/src/components/shell/CookieConsentBanner.tsx` to semantic Tailwind utilities backed by the `--primary` HSL token in `tokens.css`.

Per the T03 plan mapping table:
- Line 20 (banner top border): `border-[var(--primary-500)]` → `border-primary`
- Line 43 (Privacy Policy link): `text-[var(--primary-300)] underline hover:text-[var(--primary-200)]` → `text-primary underline hover:text-primary/80` (MEM154 hover-no-op repair: collapse hover-300/200 onto alpha modifier rather than letting hover become a no-op)
- Line 61 (Accept button): `bg-[var(--primary-500)] ... hover:bg-[var(--primary-600)]` → `bg-primary ... hover:bg-primary/90`

Left untouched per the pitfalls list:
- The literal `shadow-[0_-8px_24px_rgba(0,0,0,0.6)]` on line 20 (RGBA literal, not a palette token).
- `tokens.css` `--*-foreground` tokens (out of gate scope; foreground tokens are part of the semantic surface).

Pre-existing semantic utilities on the Reject button (`bg-card`, `hover:bg-muted`, `border-border`) and the body text (`text-foreground`) were already in place from prior work and required no changes.

This task closes the var(--*) consumer surface for S02. The grep gate for `var\(--(primary|neutral|accent|gradient)-` across all consumer dirs (`components/`, `pages/`, `contexts/`, `hooks/`, `api/`, `lib/`, `__tests__/`) now returns zero hits.

## Verification

Ran the two task-plan-mandated gates:

1. `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` → exit 1 (zero matches; ripgrep returns 1 when no matches found, which is the desired pass condition for an exclusion gate).

2. `cd frontend && npm run type-check` (= `tsc -b --noEmit`) → exit 0 (clean).

Did not run build/lint/vitest/Playwright at this task level — those are slice-level S02 gates and per the plan run after the final S02 task.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` | 1 | ✅ pass (no matches — exclusion gate) | 200ms |
| 2 | `cd frontend && npm run type-check` | 0 | ✅ pass | 9500ms |

## Deviations

None.

## Known Issues

None. The slice-level Playwright/build/lint/vitest gates remain to be run on the final S02 task.

## Files Created/Modified

- `frontend/src/components/shell/CookieConsentBanner.tsx`
