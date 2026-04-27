---
id: S02
parent: M003
milestone: M003
provides:
  - ["Zero `glass-(card|button)?` consumers in `frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/`", "Zero `className=` strings containing bare `glass` token in `frontend/src/`", "Zero `var(--(primary|neutral|accent|gradient)-*)` consumers in `frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/`", "9 reskinned high-traffic surfaces: Home, Login, Register, ExtensionAuth, NotFound, PrivacyPolicy, TermsOfService, Header chrome, Footer chrome, CookieConsentBanner", "Inline tokenized glass-surface convention validated across raw `<div>` consumers and `<Card variant=\"glass\">` mixed sites", "Hover-alpha-modifier repair pattern (`/80` text, `/90` bg) ratified across S01 + S02 migrations", "Refreshed Playwright baselines at 360/768/1280 — zero baseline drift confirmed (no covered spec visits an S02-touched page)"]
requires:
  - slice: S01
    provides: Raw palette utility consumers (`bg-primary-500`, `text-emerald-400`, etc.) already migrated to semantic tokens — clean substrate for swapping glass surfaces and `var(--*)` consumers without fighting legacy palette noise.
  - slice: M002/S08
    provides: ui/Card cva primitive with `variant="glass"` exposed (`frontend/src/components/ui/card.tsx`).
  - slice: M002/S08
    provides: tokens.css semantic vocabulary including `--primary` HSL token used for `border-primary` / `text-primary` / `bg-primary` semantic utilities.
affects:
  - ["frontend/src/pages/Home.tsx", "frontend/src/pages/authentication/Login.tsx", "frontend/src/pages/authentication/Register.tsx", "frontend/src/pages/authentication/ExtensionAuth.tsx", "frontend/src/pages/NotFound.tsx", "frontend/src/pages/PrivacyPolicy.tsx", "frontend/src/pages/TermsOfService.tsx", "frontend/src/components/layout/globalHeader/Header.tsx", "frontend/src/components/layout/globalFooter/Footer.tsx", "frontend/src/components/shell/CookieConsentBanner.tsx"]
key_files:
  - ["frontend/src/pages/Home.tsx", "frontend/src/pages/authentication/Login.tsx", "frontend/src/pages/authentication/Register.tsx", "frontend/src/pages/authentication/ExtensionAuth.tsx", "frontend/src/pages/NotFound.tsx", "frontend/src/pages/PrivacyPolicy.tsx", "frontend/src/pages/TermsOfService.tsx", "frontend/src/components/layout/globalHeader/Header.tsx", "frontend/src/components/layout/globalFooter/Footer.tsx", "frontend/src/components/shell/CookieConsentBanner.tsx"]
key_decisions:
  - ["Use `<Card variant=\"glass\">` only at sites already wrapped in <Card> (Home.tsx:385); use inline tokenized utilities `border border-white/10 bg-white/5 backdrop-blur-{md,xl} supports-[backdrop-filter]:bg-white/5 [hover:bg-white/10]` everywhere else — preserves bespoke padding/animate chrome and keeps diffs className-only.", "Use `backdrop-blur-md` (12px) for legacy `glass-button` sites (matches `--glass-backdrop: blur(10px)`) and `backdrop-blur-xl` (24px) for legacy `glass-card` sites (matches `blur(20px)`).", "Drop the legacy `::before` left-to-right shimmer overlay on legacy `.glass-button` consumers — the M002 design language does not preserve it; reintroducing it would require ad-hoc per-site CSS.", "Repair hover-no-op transitions when migrating shaded palette utilities to shadeless semantic tokens: use `/80` alpha for `hover:text-primary` (lighter-on-hover) and `/90` for `hover:bg-primary` (slightly-darker-on-hover). Pattern matches MEM154 / S01 conventions.", "Scope grep gates to consumer dirs only (`frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/`) and exclude `tokens.css` / `index.css` until S04 deletes them. Use rg exit 1 = pass semantics for exclusion gates.", "Skip manual visual spot-check of the 9 S02-touched pages under autonomous mode — they have no Playwright coverage, so the 3 grep gates + build are the strongest mechanical signals. Coverage gap recorded for S05."]
patterns_established:
  - ["Inline tokenized glass surface: `border border-white/10 bg-white/5 backdrop-blur-{md,xl} supports-[backdrop-filter]:bg-white/5 [hover:bg-white/10]` (MEM166).", "Hover-no-op repair via alpha modifiers: `/80` text-hover, `/90` bg-hover when migrating shaded utilities to shadeless semantic tokens (MEM167).", "Grep-gate scoping: consumer dirs only, exclude `tokens.css`/`index.css` until S04 (MEM168). `<Card variant=\"glass\">` deliberately doesn't match `\\bglass\\b` because regex requires `className=` prefix."]
observability_surfaces:
  - ["Grep gate 1: `rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits) is the pass condition", "Grep gate 2: `rg 'className=.*\\bglass\\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits) is the pass condition", "Grep gate 3: `rg 'var\\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1 (zero hits) is the pass condition", "`npm run build` succeeding proves no `.glass*` consumer survives compilation", "Playwright `git status --short` post-run empty proves zero baseline PNG drift"]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-26T21:59:35.935Z
blocker_discovered: false
---

# S02: Glass-card & legacy `:root` var purge — pass 1 reskin

**Migrated all `glass-card`/`glass-button`/bare-`glass` consumers and all `var(--primary|neutral|accent|gradient)-*` consumers in `frontend/src/` to semantic tokens / inline tokenized surfaces; all 3 grep gates + build + type-check + lint + vitest + Playwright e2e (no `--update-snapshots`) green with zero baseline drift.**

## What Happened

## What this slice delivered

S02 closed the legacy-glass and legacy-CSS-variable consumer surfaces in `frontend/src/`, completing pass 1 of the M003 design-system migration. Three mechanical, low-risk task tracks landed in series:

**T01 — `glass-card` consumers (7 sites).** Home.tsx:385 was already a `<Card>` so it converted to `<Card variant="glass">` (the M002/S08 ui/Card cva already exposes the variant; no import change). The other 6 consumers — Login, Register, ExtensionAuth, NotFound, PrivacyPolicy, TermsOfService — are raw `<div>` containers wrapping bespoke padding shapes (`p-12`, `p-8 md:p-12`) and outer `animate-*` chrome. Those received the inline tokenized equivalent `border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5` prepended verbatim to each className. No imports were added to the div consumers — the diff is className-only, exactly as the plan required.

**T02 — Header (7 sites) + Footer (3 sites) `glass`/`glass-button` chrome.** All 10 chrome sites swapped to inline tokenized equivalents matching the M002 Card glass surface. Buttons used `backdrop-blur-md` (12px ≈ legacy `--glass-backdrop: blur(10px)`); the mobile-menu container at Header.tsx:156 used `backdrop-blur-xl` (24px ≈ legacy `.glass-card` blur(20px)) AND collapsed its duplicated `border border-white/10` into a single occurrence. The legacy `::before` left-to-right shimmer overlay (defined in `index.css` lines 353–371) was intentionally dropped — the M002 design language doesn't preserve it.

**T03 — `var(--primary-*)` consumers (3 sites in CookieConsentBanner.tsx).** Migrated to semantic `border-primary` / `text-primary` / `bg-primary`. Hover transitions that would otherwise become no-ops (because semantic tokens have no shade scale) were repaired with alpha modifiers per the MEM154 pattern: `/80` for `hover:text-primary` (matches legacy `--primary-200` lighter-on-hover intent), `/90` for `hover:bg-primary` (matches legacy `--primary-600` slightly-darker-on-hover intent). The literal RGBA shadow on line 20 was left untouched (not a palette token, out of gate scope). `tokens.css` `--*-foreground` tokens were also untouched (semantic surface, not legacy shade).

**T04 — Close gauntlet.** All 8 sequential checks (3 grep gates + type-check + lint + vitest + build + Playwright at 3 viewports) ran in a single linear pass with zero remediation cycles. `git status --short` post-run was empty — zero baseline PNG drift, confirming the slice plan's expectation that no covered Playwright spec visits an S02-touched page.

## Patterns established for downstream slices

1. **Inline tokenized glass surface.** `border border-white/10 bg-white/5 backdrop-blur-{md,xl} supports-[backdrop-filter]:bg-white/5 hover:bg-white/10` is the canonical replacement for legacy `.glass*` rules when the consumer is a raw `<div>`. `<Card variant="glass">` is preferred only when the site is already a `<Card>`. Captured as MEM166.
2. **Hover-no-op repair via alpha modifiers.** When a shaded palette utility like `hover:text-primary-200` is migrated to a shadeless semantic token, replace with alpha modifiers (`/80`, `/90`) to preserve perceptible hover feedback. Captured as MEM167. Pattern is now battle-tested across S01 + S02 migrations.
3. **Grep-gate scoping.** Exclusion gates target consumer dirs only and exclude `tokens.css` / `index.css` until S04 deletes them. The `<Card variant="glass">` syntax does NOT match the bare-`\bglass\b` regex because it requires `className=` prefix — preserving the variant-prop call sites was deliberate. Captured as MEM168.

## What S03 should know

- **Substrate is now clean** for responsive audit + ViewPart IA collapse: every glass surface and every `var(--*)` consumer in `frontend/src/` resolves to semantic tokens or inline tokenized utilities. Layout fixes against the new substrate won't fight legacy palette noise.
- **Manual visual spot-check is a known gap.** The 9 S02-touched pages have no Playwright coverage. S05's per-page polish pass (and possibly an earlier opportunistic Playwright add for at least Home/Login/Register) should fill this. Captured as MEM169.
- **Surviving legacy substrate.** `frontend/src/index.css` still contains the `.glass*` block (lines 295-381), the legacy `:root` palette block (lines 38-98), the `@theme` palette mirror (lines 7-36), and the 11 keyframes. They survive until S04 hard-deletes them. The `vite build` succeeding in S02's gauntlet only proves consumers don't reference deleted classes — the deletion itself is S04's proof.
- **Lint baseline.** `npm run lint` exited 0 in 8.8s with zero errors — well under MEM062's 108-error baseline. Net-new file count was 9 files touched and lint stayed clean.

## Verification

All 8 slice-level gauntlet checks ran linearly on a clean tree with zero remediation cycles (per T04-SUMMARY):

1. **Grep gate 1** (`rg 'glass-(card|button)?'` × 7 consumer dirs) → exit 1 (zero hits) ✅
2. **Grep gate 2** (`rg 'className=.*\bglass\b'` × 7 consumer dirs) → exit 1 (zero hits) ✅
3. **Grep gate 3** (`rg 'var\(--(primary|neutral|accent|gradient)-'` × 7 consumer dirs) → exit 1 (zero hits) ✅
4. **Type-check** (`npm --prefix frontend run type-check`) → exit 0 in 178ms ✅
5. **Lint** (`npm --prefix frontend run lint`) → exit 0 in 8815ms (zero errors, well under MEM062 baseline of 108) ✅
6. **Vitest** (`npm --prefix frontend test -- --run`) → exit 0 in 5727ms (594 tests / 90 files) ✅
7. **Build** (`npm --prefix frontend run build`) → exit 0 in 16301ms (7 routes prerendered) ✅
8. **Playwright e2e** (`npx playwright test`, NO `--update-snapshots`) → exit 0 in 16607ms (35 passed / 10 skipped, zero baseline drift) ✅

Re-validated grep gates 1–3 on this slice-completion pass — all three returned exit 1 (zero hits). `git status --short` post-T04 was empty, confirming zero baseline PNG drift and zero source mutation.

**Manual visual spot-check** of the 9 S02-touched pages (`/`, `/login`, `/register`, `/extension-auth`, `/privacy-policy`, `/terms-of-service`, NotFound, Header chrome, Footer chrome, CookieConsentBanner) at 360 / 768 / 1280 was **skipped — autonomous mode** per the slice plan's autonomous-mode carve-out. The 3 grep gates + build are the strongest mechanical signals available; visual coverage gap is recorded for S05.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"None. All 4 tasks completed without deviation from their per-task plans. The slice-level close gauntlet ran linearly with zero remediation cycles. Manual visual spot-check of the 9 touched pages was skipped per the autonomous-mode carve-out documented in T04-PLAN.md."

## Known Limitations

"Manual visual spot-check of the 9 S02-touched pages at 360/768/1280 was skipped under autonomous mode — these pages have no Playwright spec coverage, so visual regression detection is limited to the 3 grep gates + build. S05's per-page polish pass should add visual coverage for at least Home, Login, Register, Header chrome, and Footer chrome. The legacy `.glass*` block + `:root` palette + `@theme` mirror in `frontend/src/index.css` deliberately survive S02 — they're S04 territory. The 11 legacy keyframes (`fadeInScale`, `slideInUp`, etc.) are still referenced via `animate-*` utility classes (e.g. Login.tsx's `animate-slideInUp`) — those references are tracked for S04 deletion and tokenized-replacement landing."

## Follow-ups

"S03 (next slice) consumes the clean substrate for responsive audit + ViewPart IA collapse + outbound-link safety — no carry-over remediation from S02. S04 will hard-delete the legacy `.glass*` / `:root` / `@theme` blocks and the 11 keyframes (with tokenized replacements landing atomically before deletion). S05 polish pass should add Playwright coverage for the 9 S02-touched pages to close the manual-spot-check gap. The MEM166 / MEM167 / MEM168 / MEM169 captured-thoughts will be referenced by the S03 + S04 + S05 planning agents."

## Files Created/Modified

None.
