# S04 Research — Hard delete: `@theme` palette + `:root` legacy block + pass-2 decoratives & animations

## Summary

S04 is the load-bearing finale of the M003 design-system migration: delete the legacy CSS layer in `frontend/src/index.css` so drift can't recur. Two sequential passes inside one slice (per D012) on the same single file. Most of the deletion is **pure dead code** — `.skeleton`, `.hero-gradient`, `.shadow-glow`, `.border-gradient`, `.global-parts-table-scroll-layer`, the `progress-indeterminate` keyframe, the `glass-*` block, and 100% of `card`/`card-interactive`/`card-table-container` rules have **zero consumers** in `src/`. They evaporate without replacement. Three categories require real work before deletion:

1. **`btn-primary` / `btn-secondary` migration** (8 consumer call-sites across 6 files) — S02's glass-* purge missed these because they're a different legacy family. Migrate to a `<Button>` ui/* primitive (Header CTAs, Checkout, NotFound, RouteGroupBoundary fallback, ChromeExtensionPromo, SubscriptionPromo).
2. **`input-modern` migration** (2 consumer call-sites: EditPartForm `<select>`, SearchableSelect `<input>`) — both need swap to ui/* equivalents (`<Input>` or styled `<select>`).
3. **`text-gradient` migration** (~25 consumer call-sites across 8 marketing pages) — the heavy lift; deleting `.text-gradient` without replacement is the cliff that needs either a tokenized `@utility` or a per-site swap to `bg-clip-text` Tailwind utilities.
4. **Animation replacements** for `animate-fadeInScale` (10 sites), `animate-slideInUp` (15 sites), `animate-slideInLeft` (1 site), `animate-float` (5 sites), `animate-glow` (5 sites), `animate-pulse` (5 sites — `animate-pulse` is also a Tailwind built-in so deleting OUR override is a behavior change to investigate). Tokenized `@utility` blocks in `tokens.css` are the cleanest landing.
5. **Body / `*:focus-visible` / `::selection` replacement** — the only structural elements that survive in `index.css` and currently resolve to `var(--gradient-dark)` / `var(--neutral-100)` / `var(--primary-500)` (which die when `:root` legacy block deletes). Rewrite to `hsl(var(--background))` / `hsl(var(--foreground))` / `hsl(var(--ring))`.

After all of that, the `vite build` succeeding with the legacy `@theme` block deleted is the load-bearing proof: any missed consumer of `bg-primary-500`, `text-neutral-300`, `text-accent-emerald`, `glass-card`, `btn-primary`, `card-interactive`, `text-gradient`, `animate-slideInUp`, etc. becomes a build error. R061 (milestone close gate) gets its strongest enforcement from this build success.

The slice is **risk:high** in the roadmap — the risk is concentrated in the animation + text-gradient replacement decisions (whether to keep tokenized equivalents or accept visual drift to Tailwind built-ins) and in the no-Playwright-coverage marketing pages (About / ContactUs / Pricing / Support / Privacy / Terms / Login / Register / NotFound) where animation-replacement regressions won't surface until S05/S06 manual UAT. Mitigated by atomic commits per replacement decision (D017) so individual missteps are revertable, and by ordering the deletion AFTER the additions land + AFTER consumers migrate.

## Recommendation

Order the slice as **add tokenized replacements first → migrate remaining consumers → delete in two passes → close gauntlet**. Concretely:

1. **T01 — Land tokenized animation replacements in `tokens.css`** (precursor commit). Add the surviving `@keyframes` (`fadeInScale`, `slideInUp`, `slideInLeft`, `slideInRight`, `float`, `glow`, `gradient-shift`) plus their `@utility animate-fadeInScale`/etc. blocks alongside the existing `enter`/`exit` keyframes (M002/S08 pattern, lines 119–158). Drop `slideInRight` / `gradientShift` / `borderGlow` if zero consumers (likely some are dead). Keep `animate-pulse` semantics matching Tailwind's built-in (or DELETE our override and let Tailwind's built-in kick in — investigate during T01 design). One atomic commit with rationale per D017.

2. **T02 — Migrate `btn-primary` / `btn-secondary` consumers** (8 sites, 6 files). Replace each with `<Button variant="default">` (or `variant="secondary"` / `outline`) from `frontend/src/components/ui/button.tsx`. Per-file edits, single atomic commit. Verifies via grep gate `rg 'btn-primary|btn-secondary|btn-outline' src/` exit 1.

3. **T03 — Migrate `input-modern` consumers** (2 sites). EditPartForm `<select>` line 349 + SearchableSelect `<input>` line 294. Both currently spell out tokenized utilities anyway — drop the trailing `input-modern` class, keep the rest. Single atomic commit. Verifies via `rg 'input-modern' src/` exit 1.

4. **T04 — Migrate `text-gradient` consumers** (~25 sites, 8 pages). Two viable approaches; pick at task plan time:
   - **(a) Tokenized `@utility text-gradient`** in `tokens.css` — preserves visual identity, swap-free at consumer sites, but keeps a decorative class alive that S05 polish might want to retire entirely.
   - **(b) Per-site replacement** — swap each `<span className="text-gradient">…</span>` to `<span className="bg-linear-to-r from-primary to-foreground bg-clip-text text-transparent">…</span>` (or similar Tailwind v4 utilities). Honest tokenized rendering, more diff churn.
   - **Recommended: (a)** for atomicity + S04 close gate signal; (b) deferred to S05 polish if the marketing-page visual review wants it.

5. **T05 — Migrate animation consumers** (animate-fadeInScale / slideInUp / slideInLeft / float / glow / pulse). If T01 landed the tokenized `@utility` blocks, this task is a no-op for class names — consumers already say `animate-fadeInScale` and the replacement blocks resolve them. Verify by visiting each consumer file and confirming no class-name change is required. Optional cleanup: review whether any animation consumer wants to switch to Tailwind's built-in `animate-pulse` instead of our customized 2s ease infinite. Any cleanup is per-site and can be folded into S05 polish — out of scope for this task unless it surfaces a regression.

6. **T06 — Pass 1 deletion** (the 4 high-traffic legacy blocks). Delete from `frontend/src/index.css`:
   - Lines 7–37: `@theme { --color-primary-... --color-accent-purple }` palette mirror.
   - Lines 39–99: `:root { --primary-... --gradient-... }` legacy variables.
   - Lines 295–381: `.glass`, `.glass-card`, `.glass-card.card-interactive`, `.glass-button`, `.glass-button::before`.
   - Lines 383–482: `.btn-primary`, `.btn-secondary`, `.btn-outline` + their `::before` rules + hover states.
   - Lines 484–582: `.card`, `.card::before`, `.card-interactive`, `.card-interactive::before`, `.card-interactive:hover`, `.card-table-container`, `.card-table-container::before`, `.card-table-container:hover`.
   - Lines 539–544: `.global-parts-table-scroll-layer` (0 consumers, dead).
   - Lines 584–616: `.input-modern`, `.input-modern:focus`, `.input-modern::placeholder`, `.input-modern:focus::placeholder`.
   - Lines 668–698: the legacy responsive `@media (max-width: 768px) { .glass / .card / .btn-* }` and `@media (max-width: 480px) { .card / .btn-* }` blocks (everything they target is now deleted).
   - **Rewrite** the `body { background: var(--gradient-dark); color: var(--neutral-100); }` block (lines 106–121) to use `hsl(var(--background))` / `hsl(var(--foreground))` from tokens.css. Same for `*:focus-visible { outline: 2px solid var(--primary-500); }` → `outline: 2px solid hsl(var(--ring));` and `::selection { background: var(--primary-500); color: white; }` → `background: hsl(var(--primary)); color: hsl(var(--primary-foreground));`.
   - Run `npm run build` — any missed consumer is a build error. Fix in place if any surface, then re-run. Single atomic commit.

7. **T07 — Pass 2 deletion** (decoratives + animations). Delete from `frontend/src/index.css`:
   - Lines 122–245: all 11 keyframes (`fadeInScale`, `slideInUp`, `slideInLeft`, `slideInRight`, `pulse`, `shimmer`, `float`, `glow`, `gradientShift`, `borderGlow`, `progress-indeterminate`).
   - Lines 246–294: `.animate-fadeInScale`, `.animate-slideInUp`, etc.
   - Line 647: `.skeleton` (0 consumers).
   - Line 660: `.hero-gradient` (0 consumers).
   - Lines 736–757: `.text-gradient`, `.border-gradient`, `.shadow-glow`, `.shadow-glow:hover` (0 consumers for `border-gradient` / `shadow-glow`; `text-gradient` either lives via T04(a) `@utility` or is gone).
   - Run `npm run build` — must succeed. Single atomic commit.

8. **T08 — Close gauntlet**. Carry-forward S01/S02/S03 grep gates (now stronger because `@theme` is gone — palette utilities literally don't compile):
   - `rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/` exit 1 (already 0; now also a build error if violated).
   - `rg 'text-accent-(emerald|amber|rose|purple)' src/` exit 1.
   - `rg 'glass-(card|button)?' src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1.
   - `rg 'var\(--(primary|neutral|accent|gradient)-' src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1.
   - **New S04 gates**: `rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1.
   - `npm run type-check` exit 0; `npm run lint` exit 0 (under MEM062 baseline 108); `npm test -- --run` all green; `npm run build` exit 0; `npx playwright test --update-snapshots` then `npx playwright test` (no flag) all green at 3 viewports across 6 specs.
   - Cascade-refresh signal per MEM176: any spec that fullPage-screenshots a route with replaced animations or rewritten body-background may legitimately drift; review each PNG before commit.

This ordering keeps every deletion preceded by a working replacement, makes the `vite build` after each pass the load-bearing proof, and means a missed consumer surfaces as a single build error rather than a runtime visual regression on a non-Playwright-covered page.

## Implementation Landscape

### File definitely touched

- **`frontend/src/index.css`** (757 lines today) — single deletion target. After S04: ~50–80 lines containing `@import 'tailwindcss'`, `@import './styles/tokens.css'`, `* { box-sizing }`, body styling rewritten to `hsl(var(--*))`, scrollbar styling, `*:focus-visible` rewritten to `hsl(var(--ring))`, `::selection` rewritten to `hsl(var(--primary))`, `.main-content .container`, `.tile-grid` + `.tile-grid-compact`. Everything else deleted.

### Files definitely touched (precursor adds)

- **`frontend/src/styles/tokens.css`** — append surviving keyframes + `@utility` animate-* blocks following the existing M002/S08 pattern at lines 119–158 (`@keyframes enter`, `@keyframes exit`, `@utility animate-in { animation-name: enter; … }`).

### Files definitely touched (consumer migration)

- **`frontend/src/pages/NotFound.tsx:19`** — `btn-primary` → `<Button>`.
- **`frontend/src/pages/Checkout.tsx:130`** — `btn-primary` → `<Button>` (currently styled with `px-5 py-3 rounded-xl text-sm font-semibold opacity-50 cursor-not-allowed inline-flex items-center gap-2` overriding btn-primary chrome — verify the Button primitive's `disabled` state matches before swap).
- **`frontend/src/components/layout/globalHeader/Header.tsx:93,188`** — desktop + mobile login CTA buttons. Both `btn-primary px-4 py-2 rounded-xl text-sm font-medium`.
- **`frontend/src/components/routes/RouteGroupBoundary.tsx:69,76`** — error fallback `btn-primary` + `btn-secondary` pair.
- **`frontend/src/components/shell/ChromeExtensionPromo.tsx:114`** — `btn-primary` install CTA.
- **`frontend/src/components/shell/SubscriptionPromo.tsx:75`** — `btn-primary` upgrade CTA.
- **`frontend/src/components/parts/EditPartForm.tsx:349`** — `<select>` with `input-modern` trailing class. Drop `input-modern` (the spelt-out tokenized utilities before it already cover the look).
- **`frontend/src/components/forms/SearchableSelect.tsx:294`** — `<input>` with same pattern. Drop `input-modern`.

### Files definitely touched (text-gradient / animation consumers)

If T04 picks **option (a)** tokenized @utility, NO consumer-file edits are needed for `text-gradient` and `animate-*`. Just verify by running build after the addition.

If T04 picks **option (b)** per-site `text-gradient` replacement: 25 sites across `About.tsx`, `Pricing.tsx`, `Support.tsx`, `ContactUs.tsx`, `PrivacyPolicy.tsx`, `TermsOfService.tsx`, `Checkout.tsx`, `NotFound.tsx`.

For the animation classes, even with tokenized replacements landing in T01, **review the consumer list once** to confirm none want to switch to Tailwind built-ins (e.g. `animate-pulse` already exists in Tailwind v4 with semantics `2s cubic-bezier(0.4, 0, 0.6, 1) infinite`; our override at index.css:264-266 is `2s cubic-bezier(0.4, 0, 0.6, 1) infinite` — IDENTICAL. Safe to drop our override entirely without behavior change. Confirm at T01 design.).

### Files audited (purple-* deviation list — out of S04 scope)

Per S03 summary deviation note + S01 commit 390fb4c, the 7 files using raw `purple-*` utilities resolve through Tailwind v4's default palette (independent of the deleted `@theme` block). They will still compile after S04. Out of scope for S04 deletion proof — flagged for S05 polish judgment:
- `src/App.tsx:171,177` (decorative blur backgrounds)
- `src/pages/builder/ViewBuildlist.tsx:316` (button styled `bg-purple-600 hover:bg-purple-700`)
- `src/pages/admin/UserManagement.tsx:454` (superuser role badge)
- `src/pages/About.tsx:37,87,101,104` (decorative gradients)
- `src/pages/Home.tsx:249` (decorative)
- `src/pages/authentication/Login.tsx:163` (decorative blur)
- `src/pages/authentication/Register.tsx:75` (decorative blur)

### Visual-regression baselines that may refresh (T08)

Per MEM148 + MEM176 cascade pattern. Playwright projects: `mobile` (375×667), `tablet` (768×1024), `desktop` (1280×800). 6 specs / 24 PNGs at risk:

- `frontend/e2e/components.spec.ts-snapshots/kitchen-sink-…` × 3 viewports — kitchen-sink uses NO legacy classes; **no refresh expected**. If it drifts, the body-background rewrite is the likely cause.
- `frontend/e2e/admin.spec.ts-snapshots/…` — admin pages don't use animate-*/text-gradient; **only refresh if body-background change visible**.
- `frontend/e2e/build-list.spec.ts-snapshots/…` — same reasoning.
- `frontend/e2e/parts-catalog.spec.ts-snapshots/…` — same.
- `frontend/e2e/price-history.spec.ts-snapshots/…` — same.
- `frontend/e2e/price-alerts.spec.ts-snapshots/…` — same.
- `frontend/e2e/smoke.spec.ts-snapshots/` — covers Home (`/`), heavy `animate-slideInUp`/`animate-glow`/`animate-float` consumer. **Refresh expected** if T01's tokenized animations don't pixel-match the originals.

**Coverage gap for marketing pages**: `/about`, `/pricing`, `/support`, `/contact-us`, `/privacy-policy`, `/terms-of-service`, `/login`, `/register`, `/extension-auth`, `/_kitchen-sink` (covered) — only `/` (smoke), `/_kitchen-sink` (components), and `/parts/:id` (price-history, price-alerts) get visual-regression coverage among S04-impacted pages. Animation-replacement regressions on About/Pricing/Support/ContactUs/PrivacyPolicy/TermsOfService/Login/Register/NotFound have NO Playwright signal — they surface only at S05/S06 manual UAT.

### Critical e2e behavior to preserve

- **Body background visual continuity** — the current `var(--gradient-dark)` body is mostly hidden behind App.tsx's `bg-linear-to-br from-card via-muted to-card` container, but during initial paint and on body-direct surfaces the gradient shows. Replacement should be **`hsl(var(--background))`** (a flat dark — `222 47% 6%`, near-black) which approximates the gradient's mid-tone (`#34495e` ≈ HSL `210 17% 28%`). Visually different but the App-level container immediately covers it. If a flash-of-different-color shows during route transitions, that's a regression — fix by either keeping a `linear-gradient(135deg, hsl(var(--background)) 0%, hsl(var(--muted)) 50%, hsl(var(--background)) 100%)` as a body background OR by tightening the App container z-stack.
- **Focus outline visual continuity** — `var(--primary-500)` was `#3b82f6` (HSL `217 91% 60%`); `hsl(var(--ring))` is `217 91% 60%`. **Identical**. Safe.
- **Selection visual continuity** — same reasoning. `var(--primary-500)` = `hsl(var(--primary))`. Safe.

### Patterns from S01–S03 to reuse

- **Two-pass deterministic Python regex script** (MEM158) for the `btn-primary` migration if the per-file edit count gets large. Likely overkill at 8 sites — direct Edit calls are cleaner.
- **All 7 utility prefixes** (MEM157, MEM159) for any palette gate — already covered in S03's gate set.
- **Hover-no-op repair via alpha modifiers** (MEM167) — `<Button>` primitive variants already encode hover styles correctly, but verify the migrated CTAs' hover state doesn't silently drop.
- **Comment-as-grep-target convention** (MEM163) — `index.css` will get fewer remaining lines, but any descriptive comment that names a deleted class should not literally re-spell it (e.g. don't write "now that .glass-card is deleted, …" without using a placeholder).
- **Cascade-refresh** (MEM176) — body-background rewrite + animation tokenization may drift any of the 6 specs. Expect 3–6 PNG refreshes; review each before commit.
- **Playwright `--update-snapshots` semantics** (MEM156, MEM160) — defaults to `changed` mode in 1.59+. Running it once after T07 will rewrite only PNGs that actually drifted.

## Risks and Unknowns

### High

- **Animation tokenized replacement pixel-equivalence**. Moving 11 keyframes from `index.css` `@keyframes` blocks to `tokens.css` `@keyframes` + `@utility` blocks is mechanically the same Tailwind v4 mechanism — they should resolve identically. But the surrounding context (cascade order, vendor prefixes, animation timing function rounding) can produce subpixel differences that drift baselines. **Mitigation**: keep T01 atomic; run the smoke spec immediately after T01 to detect pixel drift on Home before it compounds with later deletions.
- **`.glass-button::before` shimmer drop**. The legacy `.glass-button` had a left-to-right shimmer overlay (lines 353–371). S02 already migrated `glass-button` consumers to inline tokenized utilities WITHOUT the shimmer (per S02 summary's "intentionally dropped" decision). **No risk now** — this is just confirming S02 closed it correctly.
- **`text-gradient` pre-cascading-keyframe behavior**. The current `.text-gradient` rule has `animation: gradientShift 3s ease infinite;` baked in (line 743). Migrating consumers to `bg-clip-text text-transparent` Tailwind utilities loses the animation. **Mitigation**: pick T04 option (a) — tokenized `@utility text-gradient` keeps the gradient + animation; or accept the static-vs-animated visual change as a polish-pass decision and commit it explicitly with rationale.
- **No Playwright coverage on 9+ animation-heavy pages**. About, Pricing, Support, ContactUs, Login, Register, ExtensionAuth, PrivacyPolicy, TermsOfService, NotFound, Checkout. **Mitigation**: S04 doesn't ship these to production directly — they're visited at S05 polish + S06 UAT. Any animation-replacement regression surfaces there. Keep T01 + T07 commits atomic so a polish-pass discovery can cleanly revert one piece without unwinding the whole deletion.

### Medium

- **`*:focus-visible` outline behavior**. The legacy `*:focus-visible { outline: 2px solid var(--primary-500); outline-offset: 3px; border-radius: 4px; }` is on EVERY focusable element in the app (the universal selector). Rewriting to `hsl(var(--ring))` is visually identical (same color), but the universal selector competes with `ui/*` primitives' own `focus-visible:ring-*` Tailwind utilities. **Mitigation**: confirm by visiting `<Button>`, `<Input>`, `<Select>`, `<Dialog>` etc. — they specify `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` which competes via specificity. Today the universal `outline: 2px solid` shows as a thin blue outline on TOP of any ring. If the rewrite preserves the behavior bit-for-bit, baselines stay green. If it doesn't, R020 (keyboard-accessible focus indicators) is at risk — verify with kitchen-sink + manual tab walk.
- **Body background rewrite produces a visible flash**. The current `var(--gradient-dark)` linear gradient body is unique vs. App.tsx's `bg-linear-to-br from-card via-muted to-card` container. For a brief moment during initial paint, body shows. Rewriting body to flat `hsl(var(--background))` removes the gradient entirely. **Mitigation**: verify on a slow-network simulator in T06's manual smoke. If a regression surfaces, build a tokenized linear-gradient body in `tokens.css` mirroring App.tsx's gradient.
- **`animate-pulse` collision with Tailwind built-in**. Our `.animate-pulse` (index.css:264-266) declares `pulse` keyframes (`50% { opacity: 0.8; transform: scale(1.02); }`). Tailwind v4's built-in `animate-pulse` uses `pulse` keyframes (`50% { opacity: 0.5; }`) — DIFFERENT semantics. After we delete our override + our keyframe, Tailwind's built-in takes over with different opacity + no scale. **Mitigation**: either keep our customized `pulse` keyframe + `@utility animate-pulse` in tokens.css to override (but Tailwind's built-in `@utility` has higher specificity unless we name-collide carefully), or accept the Tailwind built-in as the new behavior and commit the change explicitly. **Recommendation**: drop our override and let Tailwind built-in win — it's more standard, the visual diff at the 5 consumer sites is minor (status-dot pulse, blur-bg pulse, spinner caption pulse).

### Low

- **Lint baseline preserved**. MEM062 = 108 errors. S04 doesn't add new lint errors mechanically (deletions reduce, additions in tokens.css are CSS — not lint-scanned). Expect lint to stay clean.
- **Vitest grep-guard extension** (R061 close gate). S06 plans to optionally extend `__tests__/no-legacy-primitives.test.ts` with a glass-* / palette-utility guard. Out of scope for S04 (the build-error enforcement is stronger), but if a S04 follow-up wants belt-and-suspenders enforcement, the pattern is in `no-legacy-primitives.test.ts:32` (`LEGACY_PRIMITIVE_RE = /from\s+['"](?:\.\.\/)+(?:common|buttons)\//;`).

## Don't Hand-Roll

- **`<Button>` primitive** — `frontend/src/components/ui/button.tsx`. Use this for every `btn-primary` / `btn-secondary` migration. Its variants (`default`, `destructive`, `outline`, `secondary`, `ghost`, `link`) already cover the legacy three. Already imports `Loader2` for disabled-with-spinner state.
- **`<Input>` primitive** — `frontend/src/components/ui/input.tsx` (look for `cn(...)` wrapping `flex h-10 w-full rounded-md border border-input bg-background...`). Use for SearchableSelect input migration; preserves accessibility + focus-visible-ring contract.
- **Inline tokenized glass surface** (MEM166 from S02) — already the pattern at Login/Register/ExtensionAuth/NotFound for raw `<div>` containers. No new primitive needed.
- **Tailwind v4 `@utility` blocks** — already used in tokens.css (`@utility animate-in`, `@utility fade-in-0`, etc., lines 159–240). The new animation utilities follow the same pattern.
- **Tailwind v4 default palette** — `purple-500`, `red-500`, `pink-500`, `blue-500`, `orange-500` etc. resolve through the built-in palette without our `@theme` registration. They survive S04. Don't try to re-register them.

## Sources

- `.gsd/DECISIONS.md` D012 (two-pass hard delete), D013 (`@theme` palette deletion), D016 (per-slice baseline refresh), D017 (atomic commits with rationale for additions).
- `.gsd/milestones/M003/M003-CONTEXT.md` — milestone context, scope, completion class.
- `.gsd/milestones/M003/M003-ROADMAP.md` — boundary map S03 → S04 → S05.
- `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md` — patterns established (MEM156–163), bulk-swap scripts under `frontend/scripts/`.
- `.gsd/milestones/M003/slices/S02/S02-SUMMARY.md` — inline tokenized glass surface (MEM166), hover alpha repair (MEM167), grep gate scoping (MEM168), no-Playwright-coverage gap (MEM169).
- `.gsd/milestones/M003/slices/S03/S03-SUMMARY.md` — cascade-refresh pattern (MEM176), 360-vs-375 viewport gap (MEM179), purple-* S04 deferral.
- `frontend/src/index.css` — primary deletion target (full read in this research session).
- `frontend/src/styles/tokens.css` — primary addition target; existing M002/S08 `@keyframes enter / exit` + `@utility animate-in / animate-out / fade-in-0 / zoom-in-95 / slide-in-from-*` pattern.
- `frontend/src/components/ui/card.tsx` — `<Card variant="glass">` cva (independent of `.glass*` index.css rules).
- `frontend/src/components/ui/button.tsx` — `<Button>` primitive (target for btn-* migration).
- `frontend/eslint.config.js:76-87` — existing `no-restricted-imports` pattern (R017 enforcement template).
- `frontend/src/__tests__/no-legacy-primitives.test.ts` — vitest grep-guard pattern (R017 enforcement template; S06 may extend).
- `frontend/scripts/prerender.mjs` — 7 prerendered marketing routes that are heavy `animate-*`/`text-gradient` consumers without Playwright coverage.

## Skills Discovered

None installed during this research. The technologies (Tailwind v4, React 19, Playwright) are core stack already covered by the project. No external library research required for this slice — it's pure deletion + replacement against substrates already established in M002.
