---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T07: Pass-2 deletion: 11 keyframes + .animate-* consumer classes + .skeleton/.hero-gradient/.text-gradient/.shadow-glow/.border-gradient

The decoratives + animations sweep. With T01 having registered tokenized `@utility animate-fadeInScale`/`slideInUp`/`slideInLeft`/`float`/`glow` blocks in `tokens.css` and T04 having registered `@utility text-gradient`, the legacy `.animate-*` and `.text-gradient` rules in `index.css` are now redundant. Delete from `frontend/src/index.css` (line numbers based on pre-T06 layout — re-read after T06 to get current line numbers): the 11 `@keyframes` blocks (`fadeInScale`, `slideInUp`, `slideInLeft`, `slideInRight`, `pulse`, `shimmer`, `float`, `glow`, `gradientShift`, `borderGlow`, `progress-indeterminate`); the corresponding `.animate-fadeInScale`, `.animate-slideInUp`, `.animate-slideInLeft`, `.animate-slideInRight`, `.animate-pulse`, `.animate-shimmer`, `.animate-float`, `.animate-glow`, `.animate-gradient`, `.animate-border-glow` consumer classes; `.skeleton` (zero consumers per research); `.hero-gradient` (zero consumers); `.text-gradient`, `.border-gradient`, `.shadow-glow`, `.shadow-glow:hover` (text-gradient now lives in tokens.css from T04; border-gradient + shadow-glow have zero consumers). NOTE the `.animate-pulse` rule is IDENTICAL to Tailwind v4's built-in (`pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite`) — deleting our override falls through to Tailwind's built-in with zero behavior change, so existing `animate-pulse` consumers (Pricing.tsx:94, Support.tsx:71+158, About.tsx:104, spinner.tsx:52) keep working. PRESERVE `* { box-sizing }`, the body block, scrollbar rules, `*:focus-visible`, `::selection`, `.main-content .container`, `.tile-grid`, `.tile-grid-compact`. Run `cd frontend && npm run build` — must succeed. Single atomic commit per R053. Final `index.css` should be ~50–80 lines.

## Inputs

- `frontend/src/index.css`
- `frontend/src/styles/tokens.css`

## Expected Output

- `frontend/src/index.css`

## Verification

cd frontend && npm run build 2>&1 | tail -10 && rg -c '@keyframes (fadeInScale|slideInUp|slideInLeft|slideInRight|pulse|shimmer|float|glow|gradientShift|borderGlow|progress-indeterminate)' frontend/src/index.css; test $? -eq 1 && rg -c '\.animate-(fadeInScale|slideInUp|slideInLeft|slideInRight|pulse|shimmer|float|glow|gradient|border-glow)' frontend/src/index.css; test $? -eq 1 && rg -c '\.(skeleton|hero-gradient|text-gradient|border-gradient|shadow-glow)' frontend/src/index.css; test $? -eq 1 && wc -l frontend/src/index.css

## Observability Impact

Signals added/changed: build success after deletion proves no consumer references the deleted classes. How a future agent inspects this: `wc -l frontend/src/index.css` should return ~50–80 (down from 757). Failure state exposed: any consumer surviving with a now-deleted animation class triggers a vite build error naming the unresolved utility.
