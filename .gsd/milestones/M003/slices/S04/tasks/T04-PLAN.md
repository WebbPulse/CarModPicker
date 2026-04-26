---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T04: Add tokenized `@utility text-gradient` to tokens.css preserving the gradient identity

Per research recommendation (option (a) over option (b)) — preserve the `text-gradient` class name across all ~25 consumer sites by registering it as an `@utility` block in `tokens.css`. Consumer sites confirmed by `rg -n 'text-gradient' frontend/src/{components,pages}/`: ContactUs.tsx (×6), Pricing.tsx (×2), TermsOfService.tsx (×1), PrivacyPolicy.tsx (×1), About.tsx (×6 incl. group-hover/hover variants), NotFound.tsx (×1), Support.tsx (×5 incl. group-hover variant), Checkout.tsx (×1). The legacy `.text-gradient` rule at `frontend/src/index.css:738-742` is `background: var(--gradient-primary); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; color: transparent;` — `--gradient-primary` is `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`. The replacement should preserve the same gradient visually; either inline the same colors directly, or define the gradient inline using HSL since #667eea ≈ HSL(229,83%,66%) and #764ba2 ≈ HSL(270,40%,55%). Pattern-match the existing M002/S08 `@utility animate-in` block at tokens.css:159 — use `@utility text-gradient { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; color: transparent; }`. Hover variants (`hover:text-gradient`, `group-hover:text-gradient`) compose automatically through Tailwind v4 (variants apply on top of `@utility`-declared classes per MEM063). Single atomic commit with rationale. Confirm post-add with `cd frontend && npm run build` (exit 0) — the `@utility` block is consumed at build time.

## Inputs

- `frontend/src/styles/tokens.css`
- `frontend/src/index.css`

## Expected Output

- `frontend/src/styles/tokens.css`

## Verification

rg -q '@utility text-gradient' frontend/src/styles/tokens.css && cd frontend && npm run build 2>&1 | tail -10
