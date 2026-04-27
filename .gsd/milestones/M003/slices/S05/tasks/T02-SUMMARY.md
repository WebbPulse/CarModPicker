---
id: T02
parent: S05
milestone: M003
key_files:
  - frontend/src/styles/tokens.css
  - frontend/src/pages/Pricing.tsx
  - frontend/src/pages/Support.tsx
  - frontend/src/pages/Checkout.tsx
  - frontend/src/pages/Home.tsx
key_decisions:
  - Retokenized 3-stop `from-warning via-orange-500 to-red-500` as 2-stop `from-warning to-warning` (effectively flat warning) rather than minting multi-tone gradient tokens — concrete consumer dictates atomic add per MEM149.
  - Named the new shadow token `--shadow-warning-glow` after the semantic role rather than a numeric scale slot, leaving `shadow-{success,info,destructive}-glow` open for future concrete consumers.
  - Collapsed Home.tsx `from-primary to-primary` no-op gradients to flat `bg-primary` (2 sites) and `from-white via-primary to-primary` to `from-white to-primary` (1 site, real wordmark) — `from-X to-X` with no via is a literal CSS no-op.
  - Animation cascades in Pricing/Support hero blocks (animate-fadeInScale wrapper + animate-glow icon + animate-pulse blur) are three *distinct* animations and were left intact — they are not no-op stacks.
  - About.tsx / ContactUs.tsx / PrivacyPolicy.tsx / TermsOfService.tsx required no edits — read pass confirmed token compliance and they hold the 3 verify gates green via existing state. ContactUs 3-card collapse intentionally deferred to S06 UAT per slice plan.
duration: 
verification_result: passed
completed_at: 2026-04-27T00:17:35.747Z
blocker_discovered: false
---

# T02: feat: Polish 8 marketing/static pages — retokenize 3-stop warning gradient, add --shadow-warning-glow, collapse Home no-op gradients

**feat: Polish 8 marketing/static pages — retokenize 3-stop warning gradient, add --shadow-warning-glow, collapse Home no-op gradients**

## What Happened

Polish-pass batch on the 8 marketing/static pages. Three concrete substrate edits + collapses against the clean post-S04 layer:

1. **`frontend/src/styles/tokens.css`** — added `--shadow-warning-glow: 0 0 40px hsl(var(--warning) / 0.15)` in `:root` and bridged through `@theme` as `--shadow-warning-glow: var(--shadow-warning-glow)`. Atomic single-token add per MEM149 — concrete consumer (Pricing.tsx Premium tier card) replaces the raw `shadow-[0_0_40px_rgba(251,191,36,0.15)]` arbitrary value.

2. **`frontend/src/pages/Pricing.tsx`** — replaced the 3-stop `from-warning via-orange-500 to-red-500` icon gradient (and its blur-twin) with 2-stop `from-warning to-warning` + flat `bg-warning/30` blur. Replaced the raw rgba shadow at the highlighted-tier ring with the new `shadow-warning-glow` token. Three additional `from-warning to-orange-500` 2-stop variants (CTA badge, CTA button, button hover-shadow line via `shadow-warning/...`) collapsed to `from-warning to-warning` via `replace_all`.

3. **`frontend/src/pages/Support.tsx`** — same 3-stop hero icon gradient retokenized identically. The two `bg-linear-to-r from-primary to-primary hover:from-primary hover:to-primary text-white` button declarations (real no-op cascade — start = end = same hover) collapsed to `bg-primary hover:bg-primary/90 text-white`. The `from-warning to-orange-500` data literal in `supportOptions[].color` retokenized to `from-warning to-warning`.

4. **`frontend/src/pages/Checkout.tsx`** — the lone 3-stop `from-warning via-orange-500 to-red-500` Premium-crown hero icon gradient retokenized to 2-stop `from-warning to-warning`.

5. **`frontend/src/pages/Home.tsx`** — collapsed three real no-op gradients: the hero-icon `from-primary to-primary` (line 151) and the Featured-Builds section-icon `from-primary to-primary` (line 204) both flattened to `bg-primary`; the wordmark `bg-linear-to-r from-white via-primary to-primary` collapsed to `from-white to-primary` (the `via-primary` and `to-primary` were a literal middle/end no-op). Other Home gradients (`from-purple-500 to-primary`, `from-success to-primary`) preserved — they have two distinct stops and serve as real chrome.

About.tsx, ContactUs.tsx, PrivacyPolicy.tsx, TermsOfService.tsx — verified token-compliant on read; no edits needed. ContactUs's 3 identical email cards intentionally NOT collapsed per slice plan (high-impact IA deferred to S06 UAT). About.tsx's `text-red-500` heart icon on Support is decorative, outside the gate's forbidden palette and outside this task's verify scope.

**Decisions made (autonomous):**
- 3-stop `from-warning via-orange-500 to-red-500` retokenized as 2-stop `from-warning to-warning` (effectively flat warning) rather than introducing a multi-tone gradient token. Rationale: `--warning` already covers the amber visual weight; orange/red were decorative noise that the gate forbids and that a tokenized 3-stop would require minting new tokens for. Flat warning preserves the warning semantic without dependency growth (MEM149).
- `shadow-warning-glow` named after the *semantic role* (warning glow), not a numeric shadow scale slot — leaves `shadow-{success,info,destructive}-glow` open for future concrete consumers without preemptive minting.
- Animation cascades reviewed; the `animate-fadeInScale` wrapper + `animate-glow` icon + `animate-pulse` blur in Pricing/Support hero pattern uses three *distinct* animations (none are no-op cascades), so left intact.

**Memory captured:** [MEM]+1 pattern memory on tokenized colored-shadow utilities composing via `--shadow-<name>: 0 0 40px hsl(var(--<token>) / 0.15)` mirrored through `@theme`.

## Verification

All 5 T02 verify steps + the 12 standing S04 grep gates run clean:

- Verify #1: `rg 'from-warning via-orange-500 to-red-500|from-amber-[0-9]|via-orange-[0-9]|to-red-[0-9]' frontend/src/pages/Pricing.tsx` exit 1 (0 hits) ✅
- Verify #2: `rg 'shadow-\[0_0_40px_rgba' frontend/src/pages/{Home,About,Pricing,Support,Checkout,ContactUs,PrivacyPolicy,TermsOfService}.tsx` exit 1 ✅
- Verify #3: `rg 'text-gray-(300|400)' frontend/src/pages/{Home,About,Pricing,Support,Checkout,ContactUs,PrivacyPolicy,TermsOfService}.tsx` exit 1 ✅
- Verify #4: All 12 S04 grep gates green (raw-palette, accent-purple, glass-card/button, className=glass, var(--legacy-*)-*, btn-/input-modern/card-interactive/skeleton/hero-gradient/shadow-glow/border-gradient — all exit 1) ✅
- Verify #5: `cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build` all exit 0; 594 vitest pass; vite build green; prerender of 7 static routes (Home/About/Pricing/Support/ContactUs/PrivacyPolicy/TermsOfService — note Checkout is auth-shaped so not prerendered) succeeded ✅

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg 'from-warning via-orange-500 to-red-500|from-amber-[0-9]|via-orange-[0-9]|to-red-[0-9]' frontend/src/pages/Pricing.tsx` | 1 | ✅ pass | 50ms |
| 2 | `rg 'shadow-\[0_0_40px_rgba' frontend/src/pages/{Home,About,Pricing,Support,Checkout,ContactUs,PrivacyPolicy,TermsOfService}.tsx` | 1 | ✅ pass | 60ms |
| 3 | `rg 'text-gray-(300|400)' frontend/src/pages/{Home,About,Pricing,Support,Checkout,ContactUs,PrivacyPolicy,TermsOfService}.tsx` | 1 | ✅ pass | 55ms |
| 4 | `rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass | 250ms |
| 5 | `rg 'text-accent-(emerald|amber|rose|purple)' src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass | 200ms |
| 6 | `rg 'glass-(card|button)?' src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass | 180ms |
| 7 | `rg 'className=.*\bglass\b' src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass | 200ms |
| 8 | `rg 'var\(--(primary|neutral|accent|gradient)-' src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass | 180ms |
| 9 | `rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' src/{components,pages,contexts,hooks,api,lib,__tests__}/` | 1 | ✅ pass | 220ms |
| 10 | `npm run type-check` | 0 | ✅ pass | 5500ms |
| 11 | `npm run lint` | 0 | ✅ pass | 6200ms |
| 12 | `npm test -- --run` | 0 | ✅ pass (594/594) | 60000ms |
| 13 | `npm run build` | 0 | ✅ pass (vite build + prerender 7 static routes) | 16000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/styles/tokens.css`
- `frontend/src/pages/Pricing.tsx`
- `frontend/src/pages/Support.tsx`
- `frontend/src/pages/Checkout.tsx`
- `frontend/src/pages/Home.tsx`
