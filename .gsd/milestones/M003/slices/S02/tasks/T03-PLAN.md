---
estimated_steps: 12
estimated_files: 1
skills_used: []
---

# T03: Migrate 3 `var(--primary-*)` consumers in `CookieConsentBanner.tsx` to semantic tokens

Replace the 3 inline `className` arbitrary-value `var(--primary-*)` calls in `frontend/src/components/shell/CookieConsentBanner.tsx` with semantic Tailwind utilities backed by the `--primary` HSL token in `tokens.css`. Mapping mirrors S01/T03 conventions (MEM154 hover-no-op repair pattern: collapse `text-primary hover:text-primary` → `text-primary hover:text-primary/80`).

**Per-site mapping** (apply mechanically):

| Line | Old (excerpt) | New (excerpt) |
|------|---------------|---------------|
| 20 | `border-t-2 border-[var(--primary-500)] shadow-[0_-8px_24px_rgba(0,0,0,0.6)]` | `border-t-2 border-primary shadow-[0_-8px_24px_rgba(0,0,0,0.6)]` |
| 43 | `text-[var(--primary-300)] underline hover:text-[var(--primary-200)]` | `text-primary underline hover:text-primary/80` |
| 61 | `px-5 py-2.5 text-sm font-semibold rounded-lg bg-[var(--primary-500)] text-white hover:bg-[var(--primary-600)] transition-colors` | `px-5 py-2.5 text-sm font-semibold rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors` |

**Rationale (matches S01/T03):** `--primary-300/400/500` all collapse to `text-primary` / `bg-primary` (no shade in the semantic palette). Hover variants that would otherwise become no-ops use alpha modifiers — `/80` for `hover:text-primary` (matches the legacy `--primary-200` lighter-on-hover intent), `/90` for `hover:bg-primary` (matches legacy `--primary-600` slightly-darker-on-hover intent).

**Pitfalls:**
- Do NOT touch `shadow-[0_-8px_24px_rgba(0,0,0,0.6)]` — it uses literal RGBA, not a `var(--*)` palette token, so it's not in scope.
- Do NOT touch `tokens.css` line 75 (`hsl(var(--primary-foreground))`) or line 84 (`hsl(var(--accent-foreground))`) — the gate is scoped to consumer dirs (excluding `tokens.css` and `index.css`), and `--*-foreground` tokens are part of the semantic surface, not legacy shades.

**Verification (run before commit):** `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` returns zero hits.

## Inputs

- ``frontend/src/components/shell/CookieConsentBanner.tsx``
- ``frontend/src/styles/tokens.css``

## Expected Output

- ``frontend/src/components/shell/CookieConsentBanner.tsx``

## Verification

Run `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — expect zero hits. Run `npm run type-check` in `frontend/` — expect exit 0.

## Observability Impact

None — pure className text migration. Grep gate is the inspection surface.
