---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T01: Add tokenized animation @utility blocks to tokens.css for surviving consumer animation classes

Precursor add. The legacy `.animate-fadeInScale`, `.animate-slideInUp`, `.animate-slideInLeft`, `.animate-float`, `.animate-glow` classes (defined in `frontend/src/index.css` lines 247–294) have live consumers in Home.tsx (4×slideInUp + 2×float + 1×glow), About.tsx (1×fadeInScale + 6×slideInUp + 1×glow), Pricing.tsx (1×fadeInScale + N×slideInUp + 1×glow), Support.tsx (3×fadeInScale + 2×slideInUp + 1×glow), Checkout.tsx (1×fadeInScale + 3×slideInUp), ContactUs.tsx (multiple fadeInScale), Register.tsx (slideInUp + 2×float), App.tsx (3×float). When S04's pass-2 deletion removes these `.animate-*` rules from `index.css`, those consumer sites would silently lose animation unless the same class names resolve through `tokens.css` first. Pattern-match the existing M002/S08 `@keyframes enter` / `@utility animate-in` block at `tokens.css:119-177` — use `@keyframes <name> { from {...} to {...} }` + `@utility animate-<name> { animation: <name> <duration> <easing> ... }` pairs. Authoring rule: animations should be visually equivalent to the legacy rules (so Playwright baselines don't drift on Home/kitchen-sink). The legacy `.animate-pulse` rule (`pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite`) is IDENTICAL to Tailwind v4's built-in `animate-pulse` — DO NOT add a tokenized override; deleting our `.animate-pulse` in T07 is a no-op behavior change and Tailwind's built-in keeps working. Skip `animate-slideInRight` / `animate-shimmer` / `animate-gradient` / `animate-border-glow` after grep-verifying zero consumers in `frontend/src/`.

## Inputs

- `frontend/src/styles/tokens.css`
- `frontend/src/index.css`

## Expected Output

- `frontend/src/styles/tokens.css`

## Verification

rg -q '@utility animate-fadeInScale' frontend/src/styles/tokens.css && rg -q '@utility animate-slideInUp' frontend/src/styles/tokens.css && rg -q '@utility animate-slideInLeft' frontend/src/styles/tokens.css && rg -q '@utility animate-float' frontend/src/styles/tokens.css && rg -q '@utility animate-glow' frontend/src/styles/tokens.css && cd frontend && npm run build 2>&1 | tail -20

## Observability Impact

Signals added/changed: none beyond build-time class resolution. How a future agent inspects this: `rg '@utility animate-' frontend/src/styles/tokens.css` lists registered animation utilities. Failure state exposed: if a consumer references an unregistered animation name after T07 deletes the legacy rules, vite build fails with the unresolved class name.
