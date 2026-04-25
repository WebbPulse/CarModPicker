---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T02: Define dark-palette token layer in styles/tokens.css and wire into Tailwind v4 @theme

Land the CSS-variable token substrate that every primitive and every reskinned page will consume. Per D003 + R011, the dark palette is locked in M002; light mode is deferred unless it falls out free.

**Token categories required:** color (background, foreground, card, popover, primary, secondary, muted, accent, destructive, border, input, ring), spacing scale (radius mainly — `--radius-sm/md/lg/xl`), typography (font-sans + font-mono families, `--font-size-*` scale already provided by Tailwind), shadows (`--shadow-sm/md/lg/xl`), z-index layers (`--z-dropdown/modal/toast`).

**Implementation:** create `frontend/src/styles/tokens.css` with `:root` block declaring all tokens (dark values). Use shadcn's standard naming so future shadcn CLI imports work without translation: `--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`, `--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`, `--muted`, `--muted-foreground`, `--accent`, `--accent-foreground`, `--destructive`, `--destructive-foreground`, `--border`, `--input`, `--ring`, `--radius`. Values express HSL channels (e.g. `222 47% 11%`) so consumers can wrap with `hsl(var(--background) / <alpha>)`.

In the same file, extend `@theme` so Tailwind utilities like `bg-background`, `text-foreground`, `border-border` resolve. Mirror existing `index.css` `@theme` block style.

`@import './styles/tokens.css'` from `frontend/src/index.css` immediately after the existing `@import 'tailwindcss'` line. Do NOT remove the existing `--primary-*/--neutral-*/--accent-*` blocks — they are still consumed by hand-rolled `components/common/` until S12. New tokens are additive.

**Why no Failure Modes etc:** no runtime — pure CSS.

## Inputs

- ``frontend/src/index.css``
- ``frontend/src/lib/utils.ts``

## Expected Output

- ``frontend/src/styles/tokens.css` (new file — :root tokens + @theme bridge for Tailwind utilities)`
- ``frontend/src/index.css` (one new @import line at top; existing content unchanged)`

## Verification

cd frontend && grep -q '@import .\./styles/tokens.css' src/index.css && grep -q -- '--background:' src/styles/tokens.css && grep -q -- '--ring:' src/styles/tokens.css && grep -q -- '--radius:' src/styles/tokens.css && grep -q '@theme' src/styles/tokens.css && npm run build > /tmp/s08-t02-build.log 2>&1 && grep -q '\.bg-background\|--background' dist/assets/*.css
