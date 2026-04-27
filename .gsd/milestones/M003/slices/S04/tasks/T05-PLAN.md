---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T05: Rewrite body / *:focus-visible / ::selection in index.css to hsl(var(--*)) so they survive :root deletion

Three structural rules in `frontend/src/index.css` currently consume the legacy `:root` palette block that T06 will delete: `body { background: var(--gradient-dark); color: var(--neutral-100); }` (lines 106-121), `*:focus-visible { outline: 2px solid var(--primary-500); outline-offset: 2px; }` (location to confirm via Read of `index.css:621-700` range), and `::selection { background: var(--primary-500); color: white; }` (location to confirm). After T06 these `var(--*)` resolutions die. Rewrite each to use the `tokens.css` HSL semantic vocabulary BEFORE T06's deletion: (a) body `background: hsl(var(--background))` (a flat dark — `222 47% 6%`, near-black; visually approximates the legacy `linear-gradient(135deg, #2c3e50 0%, #34495e 50%, #2c3e50 100%)` mid-tone) and `color: hsl(var(--foreground))`; alternatively keep gradient identity with `background: linear-gradient(135deg, hsl(var(--background)) 0%, hsl(var(--muted)) 50%, hsl(var(--background)) 100%)` if Playwright Home/kitchen-sink baselines drift unacceptably, (b) `*:focus-visible` outline → `hsl(var(--ring))` (identical channels to `--primary-500` per S04 research — visually safe), (c) `::selection` background → `hsl(var(--primary))`, color → `hsl(var(--primary-foreground))`. Keep the `body` font-family / line-height / `-webkit-font-smoothing` / `overflow-x: hidden` rules intact — only the color/background lines change. Single atomic commit. Use `cd frontend && npm run build` to verify no syntax error before T06 starts deleting upstream substrate.

## Inputs

- `frontend/src/index.css`
- `frontend/src/styles/tokens.css`

## Expected Output

- `frontend/src/index.css`

## Verification

rg -q 'background: hsl\(var\(--background' frontend/src/index.css && rg -q 'hsl\(var\(--ring' frontend/src/index.css && rg -q 'hsl\(var\(--primary' frontend/src/index.css && cd frontend && npm run build 2>&1 | tail -5

## Observability Impact

Signals added/changed: replaces three rules' color resolution. How a future agent inspects this: `rg 'var\(--' frontend/src/index.css` should now return zero hits to legacy `--primary-*` / `--neutral-*` / `--gradient-*` consumers (only `--background`/`--foreground`/`--ring`/`--primary`/`--primary-foreground` from tokens.css). Failure state exposed: a missed rewrite means T06's deletion produces undefined colors at runtime — visual regression on body background or focus outline. Cascade-refresh signal per MEM176 if Playwright Home / kitchen-sink baselines drift on the body-background change.
