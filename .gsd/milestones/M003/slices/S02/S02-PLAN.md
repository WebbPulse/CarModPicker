# S02: Glass-card & legacy `:root` var purge — pass 1 reskin

**Goal:** Remove every `glass-card` / `glass-button` / bare-`glass` class consumer in `frontend/src/` and every `var(--primary-*)` / `var(--neutral-*)` / `var(--accent-*)` / `var(--gradient-*)` consumer in `frontend/src/` (excluding `tokens.css` and `index.css`, which survive until S04). Migrate each call site onto either the existing `Card variant="glass"` primitive (Home line 385 only) or the inline tokenized equivalent `border border-white/10 bg-white/5 backdrop-blur-{xl,md} supports-[backdrop-filter]:bg-white/5 [hover:bg-white/10]`. Migrate the 3 `var(--primary-*)` consumers in `CookieConsentBanner.tsx` to semantic `border-primary` / `text-primary` / `bg-primary` (with `/80` and `/90` alpha modifiers for hover and shade-600). Verify all gates pass: 3 grep gates (glass class consumers, bare-glass-in-className, var(--*) consumers), build, type-check, lint, vitest, and Playwright e2e at 3 viewports with no `--update-snapshots`.
**Demo:** Every `glass-card` / `glass-button` / `glass` reference and every `var(--primary-*)` / `var(--neutral-*)` / `var(--accent-*)` / `var(--gradient-*)` consumer migrated to semantic tokens / equivalent ui/* primitive surfaces. Home, Login, Register, Header, AccountAlerts, AdminDashboard reskinned (~8 high-traffic pages). Baselines refreshed for touched pages.

## Must-Haves

- `rg 'glass-(card|button)?' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` returns zero hits
- `rg 'className=.*\bglass\b' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` returns zero hits
- `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` returns zero hits
- `npm run type-check` exits 0
- `npm run lint` exits 0 (no net-new errors against MEM062 baseline of 108)
- `npm test -- --run` (vitest) exits 0
- `npm run build` (vite + prerender) exits 0
- `npx playwright test` (no `--update-snapshots`) exits 0 across all 3 viewports
- Legacy `.glass*` rules and `:root` / `@theme` palette blocks in `frontend/src/index.css` are intentionally NOT deleted in S02 (S04 territory)

## Proof Level

- This slice proves: Mechanical static-text migration. Proof is grep-gate cleanliness + zero Playwright baseline drift on existing covered pages + manual visual spot-check of the 9 touched pages at 3 viewports (since none of the 6 covered Playwright specs visits a touched page, manual verification is the visual-regression backstop). Not a runtime-boundary slice.

## Integration Closure

No cross-runtime integration. Frontend-only class-string changes. Closure is the close-gauntlet command sequence in T04 returning all-zero / all-green.

## Verification

- Grep gates remain the canonical inspection surface (S01's 6 R048 gates plus S02's 3 new gates). No new runtime observability needed — pure compile-time / class-string migration. Build-time the legacy `.glass*` block in `index.css` still resolves until S04, so Playwright snapshot diffs at maxDiffPixelRatio: 0.002 are the only visual regression signal during S02.

## Tasks

- [x] **T01: Migrate `glass-card` consumers (7 files) to `Card variant="glass"` or inline tokenized equivalent** `est:30 minutes`
  Replace every `glass-card` class string in the 7 consumer files with either the M002/S08 `Card variant="glass"` primitive (only at `frontend/src/pages/Home.tsx` line 385, which is already a `<Card>`) or the inline tokenized equivalent `border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5` for the 6 raw-`<div>` consumers (Login, Register, ExtensionAuth, NotFound, PrivacyPolicy, TermsOfService). The inline form is preferred over a `<Card>` conversion for the raw-div consumers because they wrap padding shapes (`p-12`, `p-8 md:p-12`) that the `Card` `padding` prop doesn't model cleanly, and they sit inside outer `animate-*` chrome that the inline form preserves verbatim.

**Per-file mapping table** (apply mechanically — no judgment per site):

| File | Old | New |
|------|-----|-----|
| `frontend/src/pages/Home.tsx:385` | `<Card className="glass-card">` | `<Card variant="glass">` |
| `frontend/src/pages/authentication/Login.tsx:169` | `<div className="glass-card rounded-2xl p-8 animate-slideInUp">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 animate-slideInUp">` |
| `frontend/src/pages/authentication/Register.tsx:81` | `<div className="glass-card rounded-2xl p-8 animate-slideInUp">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 animate-slideInUp">` |
| `frontend/src/pages/authentication/ExtensionAuth.tsx:157` | `<div className="glass-card rounded-2xl p-8 animate-slideInUp">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 animate-slideInUp">` |
| `frontend/src/pages/NotFound.tsx:16` | `<div className="glass-card rounded-2xl p-12 max-w-md mx-auto animate-fadeInScale">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-12 max-w-md mx-auto animate-fadeInScale">` |
| `frontend/src/pages/PrivacyPolicy.tsx:17` | `<div className="glass-card rounded-2xl p-8 md:p-12">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 md:p-12">` |
| `frontend/src/pages/TermsOfService.tsx:18` | `<div className="glass-card rounded-2xl p-8 md:p-12">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 md:p-12">` |

**Pitfalls:**
- Do NOT touch `btn-primary` (Header / NotFound), `text-gradient` (NotFound), or `animate-slideInUp/fadeInScale` (multiple files) — all S04 territory.
- Do NOT add a `Card` import to the 6 div-based consumers — keep the `<div>` shape so the diff is `className`-only.
- Do NOT touch the surrounding decorative `<div className="absolute inset-0 overflow-hidden">` background-blob containers above the glass panels.

**Verification (run before commit):** `rg 'glass-card' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` must return zero hits.

**Failure modes to watch:** None of the 6 div-based files import `Card` today; if a typo accidentally introduces `<Card>`-style markup, vite build will fail with an undefined-component error. Type-check after the edits.
  - Files: `frontend/src/pages/Home.tsx`, `frontend/src/pages/authentication/Login.tsx`, `frontend/src/pages/authentication/Register.tsx`, `frontend/src/pages/authentication/ExtensionAuth.tsx`, `frontend/src/pages/NotFound.tsx`, `frontend/src/pages/PrivacyPolicy.tsx`, `frontend/src/pages/TermsOfService.tsx`
  - Verify: Run `rg 'glass-card' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — expect zero hits. Run `npm run type-check` in `frontend/` — expect exit 0. Run `npm run build` in `frontend/` — expect exit 0.

- [x] **T02: Migrate `glass` / `glass-button` chrome on Header (7 sites) and Footer (3 sites) to inline tokenized equivalents** `est:30 minutes`
  Replace every `glass` and `glass-button` class string in `frontend/src/components/layout/globalHeader/Header.tsx` and `frontend/src/components/layout/globalFooter/Footer.tsx` with the inline tokenized equivalent. The migration drops the legacy `::before` left-to-right shimmer overlay (defined in `index.css` lines 353–371) since the M002 design language doesn't preserve it. The Header line 156 mobile-menu container also drops a duplicated `border border-white/10` Tailwind class layered on top of the legacy `.glass-card` border.

**Per-site mapping table** (apply mechanically):

| Site | Old | New |
|------|-----|-----|
| `Header.tsx:67` profile-link | `flex items-center space-x-2 glass px-4 py-2 rounded-xl hover:bg-white/10 transition-all duration-300 group` | `flex items-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl transition-all duration-300 group` |
| `Header.tsx:77` desktop-logout | `flex items-center space-x-2 glass-button px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300` | `flex items-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300` |
| `Header.tsx:87` desktop-login | `glass-button px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300` | `border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300` |
| `Header.tsx:104` mobile-toggle | `md:hidden glass-button p-2 rounded-lg text-white hover:text-primary transition-all duration-300` | `md:hidden border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 p-2 rounded-lg text-white hover:text-primary transition-all duration-300` |
| `Header.tsx:156` mobile-menu container | `glass-card mx-4 mb-4 rounded-xl border border-white/10` | `border border-white/10 bg-white/5 backdrop-blur-xl mx-4 mb-4 rounded-xl` (drop the duplicated `border border-white/10`; use `backdrop-blur-xl` because legacy `.glass-card` used `--glass-backdrop: blur(20px)` ≈ `xl`) |
| `Header.tsx:171` mobile-logout | `w-full flex items-center justify-center space-x-2 glass-button px-4 py-2 rounded-xl text-sm font-medium text-white` | `w-full flex items-center justify-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white` |
| `Header.tsx:181` mobile-login | `block w-full text-center glass-button px-4 py-2 rounded-xl text-sm font-medium text-white` | `block w-full text-center border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white` |
| `Footer.tsx:121,129,137` social icons (× 3) | `w-10 h-10 glass rounded-lg flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/10 transition-all duration-300` | `w-10 h-10 border border-white/10 bg-white/5 backdrop-blur-md rounded-lg flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/10 transition-all duration-300` |

**Notes on the inline expression choice:**
- `glass-button` legacy used `backdrop-filter: blur(10px)` — closest tailwind utility is `backdrop-blur-md` (12px).
- `glass-card` legacy used `backdrop-filter: blur(20px)` — closest is `backdrop-blur-xl` (24px). Header line 156 (mobile-menu container) is the only `glass-card` site in this task.
- `bg-white/5` matches the M002 `Card variant="glass"` background; `border border-white/10` matches the variant border. Consistent with the 10+ existing `<Card variant="glass">` consumers (About, Pricing, Support, ContactUs, Checkout) the user has already accepted.

**Pitfalls:**
- Don't touch `btn-primary` on `Header.tsx` lines 93 and 188 — S04 territory.
- Don't touch any `animate-*` classes on Header — S04 territory.
- Header.tsx line 156: the duplicated `border border-white/10` MUST be reduced to a single occurrence in the new className.

**Verification (run before commit):** Both grep gates 1 and 2 (see T04) must return zero hits.
  - Files: `frontend/src/components/layout/globalHeader/Header.tsx`, `frontend/src/components/layout/globalFooter/Footer.tsx`
  - Verify: Run `rg 'glass-(card|button)?' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — expect zero hits. Run `rg 'className=.*\bglass\b' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — expect zero hits. Run `npm run type-check` in `frontend/` — expect exit 0.

- [x] **T03: Migrate 3 `var(--primary-*)` consumers in `CookieConsentBanner.tsx` to semantic tokens** `est:10 minutes`
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
  - Files: `frontend/src/components/shell/CookieConsentBanner.tsx`
  - Verify: Run `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — expect zero hits. Run `npm run type-check` in `frontend/` — expect exit 0.

- [x] **T04: S02 close gauntlet — run all 3 grep gates + build + type-check + lint + vitest + Playwright** `est:20 minutes`
  Verify the slice is closed by running the full S02 gauntlet from the slice goal in sequence. All commands must exit 0 / return zero hits. If any gate fails, fix in place and re-run the full gauntlet from the start (do NOT auto-rewrite Playwright baselines).

**Sequence (run from `frontend/` unless otherwise specified):**

1. **Grep gate 1 (glass class consumers):** `rg 'glass-(card|button)?' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — Expected: zero hits.

2. **Grep gate 2 (bare-`glass` in className strings):** `rg 'className=.*\bglass\b' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — Expected: zero hits. (`<Card variant="glass">` consumers do not match because the regex requires `className=` prefix.)

3. **Grep gate 3 (`var(--*)` consumers, scoped past `tokens.css` and `index.css`):** `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — Expected: zero hits.

4. **Type-check:** `cd frontend && npm run type-check` — expect exit 0.
5. **Lint:** `cd frontend && npm run lint` — expect exit 0 (or no net-new errors against MEM062 baseline of 108).
6. **Vitest:** `cd frontend && npm test -- --run` — expect exit 0.
7. **Build:** `cd frontend && npm run build` — expect exit 0 (proves no `.glass*` consumer survives compilation).
8. **Playwright e2e at 3 viewports:** `cd frontend && npx playwright test` — expect exit 0 with NO `--update-snapshots` flag. Zero baseline drift expected because no covered spec visits an S02-touched page; if a baseline drifts, that's a real regression — investigate, do NOT auto-rewrite.

**Manual visual spot-check (optional but recommended for slice summary):**

The 9 S02-touched pages have no Playwright coverage. If running in autonomous mode, record "manual visual spot-check skipped — autonomous-mode" in the summary. If interactive, document a one-line per-page verdict at 360 / 768 / 1280 viewports for `/`, `/login`, `/register`, `/extension-auth`, `/privacy-policy`, `/terms-of-service`, NotFound (any 404 path), Header chrome, Footer chrome, CookieConsentBanner.

**Pitfalls:**
- Do NOT pass `--update-snapshots` to Playwright. Zero-rewrite is the desired R048 outcome.
- The legacy `.glass*` block in `frontend/src/index.css` survives. If `npm run build` fails, the issue is a typo from T01/T02, NOT a missing legacy class.
- The 3 grep gates are all scoped past `tokens.css` and `index.css` (consumer dirs only). Don't widen the scope until S04 deletes them.

**Failure modes:**
- Surviving glass-* hit → missed call site in T01/T02. Fix in place, re-run gauntlet from step 1.
- Surviving `var(--*)` hit → confirm gate is scoped past `tokens.css` and `index.css`. If still failing, fix file in place.
- Playwright baseline diff → real visual regression. Run failing spec headed and inspect; likely T02 over-stripped a className.
- Vitest failure → component test snapshot drifted. Investigate; do not blanket-update.
  - Files: `frontend/src/`, `frontend/playwright.config.ts`, `frontend/package.json`
  - Verify: All 8 commands above complete with exit 0 / zero hits in a single linear sequence on a clean working tree (no `--update-snapshots` flag anywhere). Document the verification command sequence and outputs in the task SUMMARY when calling `gsd_complete_task`.

## Files Likely Touched

- frontend/src/pages/Home.tsx
- frontend/src/pages/authentication/Login.tsx
- frontend/src/pages/authentication/Register.tsx
- frontend/src/pages/authentication/ExtensionAuth.tsx
- frontend/src/pages/NotFound.tsx
- frontend/src/pages/PrivacyPolicy.tsx
- frontend/src/pages/TermsOfService.tsx
- frontend/src/components/layout/globalHeader/Header.tsx
- frontend/src/components/layout/globalFooter/Footer.tsx
- frontend/src/components/shell/CookieConsentBanner.tsx
- frontend/src/
- frontend/playwright.config.ts
- frontend/package.json
