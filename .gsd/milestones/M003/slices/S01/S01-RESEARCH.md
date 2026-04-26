# S01 — Global Token Sweep: Palette Utility Migration

**Calibration:** Targeted research. The work is mechanical (rg-driven find-and-replace across consumer files), the substrate is well-understood from M002, and prior memories (MEM145, MEM147, MEM149) lock the strategy. Where research is needed: precise scope (file count, distinct utility count, occurrence ranking), the **mapping table** from raw utility → semantic token, and the **gap-fill list** that has to land as atomic commits before the bulk sweep can complete.

---

## Summary

S01 is a **mechanical, by-token global sweep** of every raw legacy palette utility (`bg-primary-500`, `text-neutral-300`, `text-emerald-400`, `text-indigo-300`, `text-accent-emerald`, `bg-emerald-400`, etc.) across all consumer files in `frontend/src/`, replacing them with semantic tokens (`bg-primary`, `text-muted-foreground`, `text-success`, `text-foreground`, etc.) backed by `frontend/src/styles/tokens.css`.

**Scope (measured 2026-04-26):**
- **66 consumer files** in `frontend/src/` use raw palette utilities (one additional file is `index.css` itself — out of scope; that's S04).
- **159 distinct utility classes** used (counting every prefix × color × shade × alpha-modifier combination).
- **~700+ total occurrences** by line count (heaviest concentrations: `text-neutral-400` (116×), `text-neutral-300` (88×), `text-primary-400` (60×), `text-indigo-300` (19×), `text-indigo-400` (18×), `text-emerald-300` (18×), `border-indigo-500` (18×)).
- **Top consumer files:** `pages/admin/CrawlerAdmin.tsx`, `components/layout/globalFooter/Footer.tsx`, `pages/authentication/Register.tsx`, `pages/Checkout.tsx`, `pages/admin/SystemAdmin.tsx`, `pages/Home.tsx`, `pages/Pricing.tsx`, `pages/PrivacyPolicy.tsx`, `components/layout/globalHeader/Header.tsx`, `pages/admin/PartsCuration.tsx`.

**Existing semantic-token vocabulary (`tokens.css`):** `background, foreground, card, popover, primary, secondary, muted, accent, destructive, border, input, ring` (plus alpha composition via `hsl(var(--token) / N)`-style or the `text-foo/N` Tailwind alpha-modifier syntax — already in use, e.g. `border-destructive/50`).

**Critical gap surfaced:** there is **no `--success` / `--warning` / `--info` semantic token** in `tokens.css`. Emerald (success), amber (warning), rose (error/danger), indigo (info/role), purple (role/superuser) all need either a semantic token or a documented decision to keep them as the canonical Tailwind colors. Per MEM149 + R053, the gap-fill is an atomic commit landing in `tokens.css` BEFORE the consumer sweep that depends on it.

**Strategy locked by MEM147:** Phase 1 (this slice) is **global by-token atomic commits** — one PR-scale commit per legacy class swap that touches every consumer in one shot. NOT per-page. This makes each commit bisectable, the diff bounded to one rename, and review easy. Per-page structural work (glass-card removal, layout, IA collapses) is S02/S05.

**Visual-regression strategy locked by MEM148:** Per-slice baseline refresh at 360 / 768 / 1280 (note: actual mobile viewport in `playwright.config.ts` is 375, not 360 — the M003 vocabulary calls it "360" but the implemented value is 375; planner should keep the existing 375 unless intentionally re-baselining at 360). Every page touched by S01 gets baselines refreshed. Diff review is scoped to "expected token-swap diffs only" — anything else is investigated.

---

## Recommendation

**Execute as four task batches inside one slice:**

1. **T1 — Gap-fill semantic tokens (atomic precursor commit).** Add `--success`, `--success-foreground`, `--warning`, `--warning-foreground` (and arguably `--info` / `--info-foreground` for indigo) to `tokens.css` as HSL-channel tokens, mirror in the `@theme` bridge so utilities `bg-success` / `text-success` / `border-success` / `text-warning` / etc. resolve. Document rationale in the commit (R053). This is the **only** non-mechanical commit in S01 and it MUST land first because most subsequent token swaps depend on it. Also: fix `components/ui/alert.tsx` `success` variant to use `bg-success/10 text-success border-success/50` instead of the raw `bg-emerald-500/10 text-emerald-300 border-emerald-500/50` it currently hard-codes — this is a primitive fix that makes the variant consumable through the new vocabulary (and removes the only `ui/*` palette-utility violator).

2. **T2 — Bulk text/bg/border swaps for the four high-frequency neutrals.** These are pure semantic swaps with no judgment — every occurrence of:
   - `text-neutral-400` → `text-muted-foreground` (116 occurrences) — context: secondary body text, subtle labels
   - `text-neutral-300` → `text-foreground` or `text-muted-foreground` (88 — needs minor judgment per file: `300` is "primary body text on dark surfaces" in this codebase; `text-foreground` is the closer token. But where it's a hover-darkening of `text-neutral-400`, `text-foreground` is wrong and the existing `text-muted-foreground` should stay. **Planner judgment: default to `text-foreground`; flip to `text-muted-foreground` only when surrounding code shows it's a tier-2 label.**)
   - `text-neutral-200` → `text-foreground` (16 occurrences)
   - `text-neutral-500` / `text-neutral-600` / `text-neutral-100` / `text-neutral-900` (~30 occurrences total) — each needs a one-time judgment call (see Mapping Table below).
   - `bg-neutral-700` / `bg-neutral-800` / `bg-neutral-900` / `bg-neutral-950` → `bg-card` / `bg-muted` / `bg-background` (under 20 occurrences total, mostly Login/Register/Header).
   - `border-neutral-700` / `border-neutral-600` / `border-neutral-500` → `border-border` (≈5 occurrences).

3. **T3 — Primary palette swap.** `text-primary-400` (60×), `text-primary-300` (16×), `text-primary-200`, `bg-primary-500` (5×), `bg-primary-500/10`, `bg-primary-500/20`, `bg-primary-500/25`, `bg-primary-600`, `bg-primary-700`, `border-primary-500` (11×), `border-primary-400` (7×), `ring-primary-500` (4×), `ring-primary-500/20`, `ring-primary-500/30`, `ring-primary-500/50`, `from-primary-500` / `to-primary-600` / etc. — most map cleanly to `text-primary` / `bg-primary` / `bg-primary/10` / `border-primary` / `ring-primary` (Tailwind v4's `/N` alpha modifier composes with semantic tokens because `--color-primary` is `hsl(var(--primary))`). The `from-*` / `to-*` / `via-*` gradient utilities migrate the same way. `shadow-primary-500/10` and `shadow-primary-500/25` need a `shadow-primary` companion or stay as decorative (S04/S05 territory if the gradient itself is going away).

4. **T4 — Status/accent palette swap (depends on T1 tokens).** Once `--success` / `--warning` exist:
   - All `text-emerald-*` / `bg-emerald-*` / `border-emerald-*` / `ring-emerald-*` / `from-emerald-*` / `to-emerald-*` → `text-success` / `bg-success` / `bg-success/10` / etc.
   - All `text-amber-*` / `bg-amber-*` / `border-amber-*` / `ring-amber-*` / `from-amber-*` / `shadow-amber-*` → `text-warning` / `bg-warning` / etc.
   - All `text-rose-*` / `bg-rose-*` / `border-rose-*` → `text-destructive` / `bg-destructive/10` / `border-destructive/50` (rose is the existing status mapping in CrawlerAdmin's "error" lane).
   - All `text-indigo-*` / `bg-indigo-*` / `border-indigo-*` / `ring-indigo-*` — JUDGMENT CALL. Indigo plays "info" / "role" in CrawlerAdmin and "form-focus" in build-list forms. Two options: (a) add `--info` token, map all indigo to `text-info` / `bg-info`; or (b) keep indigo as Tailwind default (it'll resolve via Tailwind v4's default palette once `@theme` is deleted — verified: `indigo` is part of Tailwind's default v4 palette). **Recommend (a)** — add `--info` so all status colors are tokenized. Cost is one more token; benefit is no untokenized status color survives. Locks the contract.
   - `text-accent-emerald` / `text-accent-amber` / `text-accent-rose` / `text-accent-purple` (the tokens defined in the legacy `@theme` block) — only `text-accent-emerald` is referenced (1 occurrence). Map to `text-success` and remove.
   - Purple — 1 role badge in `UserManagement.tsx` (`bg-purple-600 text-purple-100` for superuser). Decorative purple gradients in Home/About/Login/Register/App are NOT in scope for S01 because `purple-500` resolves via Tailwind's default v4 palette, not via the legacy `@theme` block. **Plan recommendation: leave decorative purple alone in S01; surface for S04 when `@theme` is deleted (any survivor that becomes a build error gets handled then).** For the role badge, propose either keeping it as Tailwind purple or adding a `--role-superuser` token — owner judgment.

**Then the slice closes with:**

5. **T5 — Verification.** Run the grep gates (R048):
   - `rg 'bg-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]' frontend/src/` → 0 hits
   - `rg 'text-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]' frontend/src/` → 0 hits
   - `rg 'border-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]' frontend/src/` → 0 hits
   - `rg 'ring-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]' frontend/src/` → 0 hits
   - `rg '(from|to|via)-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]' frontend/src/` → 0 hits (modulo `purple` decorative survivors flagged for S04)
   - `rg 'text-accent-(emerald|amber|rose|purple)' frontend/src/` → 0 hits

6. **T6 — Visual-regression baseline refresh** at 360/768/1280 for every page touched. Any spec that screenshots a page with raw palette utilities will drift; per-slice refresh prevents the M002/MEM140 batch-refresh problem.

7. **T7 — Gauntlet:** `vite build`, `tsc --noEmit`, `eslint` (108-error baseline preserved per MEM062), `vitest --run` (594+ passes), `playwright test` (all 3 viewports green).

---

## Implementation Landscape

### Substrate (already exists; consume, don't re-create)

- **`frontend/src/styles/tokens.css`** — semantic-token surface. `:root` block declares HSL-channel values; `@theme` block bridges them as `--color-<token>: hsl(var(--<token>))` so Tailwind utilities (`bg-foo`, `text-foo`, `border-foo`) resolve. Lines 1-102 (token surface) + 104-225 (animation primitives — out of scope for S01).
- **`frontend/src/index.css`** — legacy `@theme` palette (lines 7-36) that S01 is migrating consumers OFF of, plus `:root` palette (lines 38-98), `.glass*` (S02 territory), `.btn-*` / `.card*` / `.input-modern` (S04), 11 keyframes (S04), decorative utilities (S04). **DO NOT EDIT in S01.** S01 only touches consumer files; the legacy block survives until S04.
- **`frontend/src/components/ui/*`** — 9 Radix primitives (`alert`, `button`, `card`, `combobox`, `confirm-dialog`, `dialog`, `dropdown-menu`, `input`, `pagination`, `select`, `sheet`, `tabs`) + others. All except `alert.tsx` already use semantic tokens. **`alert.tsx` `success` variant uses raw `emerald-500/300` palette utilities — must be fixed in T1 alongside the token gap-fill.**
- **`frontend/src/__tests__/no-legacy-primitives.test.ts`** — R017 grep guard for legacy import paths. Does NOT currently scan for raw palette utilities. **Out of scope for S01** (S06 may extend it as part of the close gauntlet); but planner should be aware the pattern exists for future use.
- **`frontend/playwright.config.ts`** — 3 projects (`mobile: 375×667`, `tablet: 768×1024`, `desktop: 1280×800`), all `Desktop Chrome` engine (per MEM066/MEM068, do NOT introduce `iPhone SE` / `iPad` device presets — they are webkit and break baselines). `maxDiffPixelRatio: 0.002`, `animations: 'disabled'`. `testDir: './e2e'`. **The vocabulary in M003-CONTEXT says "360" but the actual implemented mobile viewport is 375.** Planner: keep 375 unless an explicit re-baseline at 360 is intended (out of scope for S01).
- **`frontend/e2e/` snapshot directories** — `admin.spec.ts-snapshots/`, `build-list.spec.ts-snapshots/`, `components.spec.ts-snapshots/`, `parts-catalog.spec.ts-snapshots/`, `price-alerts.spec.ts-snapshots/`, `price-history.spec.ts-snapshots/`. **All six are at risk of drift** because S01 touches admin pages (CrawlerAdmin, PartsCuration, SystemAdmin, UserManagement, SystemStatistics), build-list pages (BuildListsCatalog, BuildListItem, BuildListCard, ViewBuildlist, ViewBuildLog, BuildListPart*), parts pages (ViewPart, PartList, PartsCatalog, ImageGallery*), price pages (price-alerts via `components/parts/AddToBuildListDialog.tsx` and others), and the cross-page kitchen-sink (`components.spec.ts` exercises all primitives including `Alert success` if T1 fixes it). **Per-slice refresh covers ALL six.**

### File scope by directory

```
frontend/src/
├── App.tsx                                                 [decorative purple/blue — flag, leave for S04]
├── components/
│   ├── ads/AdBanner.tsx                                    [ad banner palette]
│   ├── auth/AuthRedirectLink.tsx                           [link colors]
│   ├── authentication/GoogleAuthFlow.tsx                   [neutral text-heavy]
│   ├── buildListParts/                                     [4 files; indigo focus + neutral]
│   ├── buildLists/                                         [5 files; indigo focus + neutral]
│   ├── cars/                                               [2 files]
│   ├── filters/VehicleFilterSection.tsx
│   ├── forms/                                              [2 files; primary focus rings]
│   ├── layout/
│   │   ├── globalFooter/Footer.tsx                         [HEAVY: 13× text-neutral-400]
│   │   └── globalHeader/Header.tsx                         [primary/neutral; glass-card overlap with S02]
│   ├── parts/                                              [6 files; primary + emerald status + neutral]
│   ├── profile/                                            [7 files; primary + neutral]
│   ├── routes/RouteGroupBoundary.tsx
│   ├── shell/                                              [5 files; promo banners]
│   ├── ui/alert.tsx                                        [PRIMITIVE — T1 gap-fill]
│   └── users/UserCard.tsx
├── pages/
│   ├── About.tsx, Checkout.tsx, ContactUs.tsx, Home.tsx,
│   ├── Pricing.tsx, PrivacyPolicy.tsx, Profile.tsx,
│   ├── Search.tsx, Support.tsx, TermsOfService.tsx,
│   ├── BugReport.tsx, NotFound.tsx
│   ├── admin/                                              [5 files; status colors heavy in CrawlerAdmin]
│   ├── authentication/                                     [5 files; neutral + primary]
│   ├── builder/                                            [2 files: ViewBuildlist, ViewPart]
│   └── buildLists/                                         [2 files: BuildListsCatalog, ViewBuildLog]
└── (everything else uses semantic tokens already)
```

### Token Mapping Table (canonical reference for the planner)

#### Neutrals (semantic surface)
| Legacy class                | Semantic replacement                                     | Notes |
|-----------------------------|----------------------------------------------------------|-------|
| `text-neutral-100`          | `text-foreground`                                        | Primary text |
| `text-neutral-200`          | `text-foreground`                                        | Primary text |
| `text-neutral-300`          | `text-foreground` (default) OR `text-muted-foreground` (when used as tier-2 label)  | Judgment per occurrence |
| `text-neutral-400`          | `text-muted-foreground`                                  | Tier-2 / secondary text |
| `text-neutral-400/80`       | `text-muted-foreground/80`                               | Alpha modifier |
| `text-neutral-500`          | `text-muted-foreground`                                  | Tier-2 / placeholder |
| `text-neutral-600`          | `text-muted-foreground`                                  | Subtle / disabled hint |
| `text-neutral-900`          | `text-background` OR keep as Tailwind default if intentional inversion (Pricing.tsx amber CTAs) | **Judgment** — `Pricing.tsx` uses on yellow CTA, `text-background` works; otherwise verify per use |
| `bg-neutral-700`            | `bg-muted` or `bg-secondary`                             | Login/Register input bg-fallback. Verify intent. |
| `bg-neutral-700/50`         | `bg-muted/50`                                            |  |
| `bg-neutral-800`            | `bg-card` or `bg-muted`                                  | Verify per use |
| `bg-neutral-800/50`         | `bg-card/50`                                             |  |
| `bg-neutral-900`            | `bg-background`                                          |  |
| `bg-neutral-900/40`         | `bg-background/40`                                       |  |
| `bg-neutral-950`            | `bg-background`                                          | (background already darker than `card`) |
| `border-neutral-500`        | `border-border`                                          |  |
| `border-neutral-600`        | `border-border`                                          |  |
| `border-neutral-700`        | `border-border`                                          |  |
| `from-neutral-500/900`, `via-neutral-800`, `to-neutral-300/600/900` | Decorative — preserve gradient with `from-muted` / `via-muted` / `to-background` style, OR flag for S05 polish | Mostly decorative panels |

#### Primary (brand)
| Legacy class                | Semantic replacement                                     | Notes |
|-----------------------------|----------------------------------------------------------|-------|
| `text-primary-200/300/400`  | `text-primary` (sometimes `text-primary/80` for `300`-as-hover) | Verify hover/active intent |
| `bg-primary-400/10`         | `bg-primary/10`                                          |  |
| `bg-primary-500`            | `bg-primary`                                             |  |
| `bg-primary-500/{10,20,25}` | `bg-primary/{10,20,25}`                                  | Tailwind v4 alpha modifier composes |
| `bg-primary-600`            | `bg-primary` (or `bg-primary/90` for hover)              |  |
| `bg-primary-700`            | `bg-primary` (or `bg-primary/80` for active)             |  |
| `border-primary-400`        | `border-primary/70` or `border-primary`                  |  |
| `border-primary-500`        | `border-primary`                                         |  |
| `ring-primary-500`          | `ring-primary`                                           |  |
| `ring-primary-500/{20,30,50}` | `ring-primary/{20,30,50}`                              |  |
| `from-primary-500/600`, `to-primary-300/600/700`, `via-primary-100`, `from-primary-500/30` | `from-primary` / `to-primary` / etc. | Gradient compositions; planner: visually verify on Home/Pricing/Support |
| `shadow-primary-500/{10,25}` | Either add `shadow-primary` token OR drop the colored shadow (S05 polish judgment) | Decorative — flag if no clean semantic |

#### Status (NEEDS T1 GAP-FILL: --success, --warning, --info)
| Legacy class                | Semantic replacement (assuming T1 lands)                 | Notes |
|-----------------------------|----------------------------------------------------------|-------|
| `text-emerald-200/300/400/500` | `text-success` (sometimes `text-success/80` for /70 alpha or 200-tier) | Status: success/healthy |
| `text-emerald-{400,500}/{70,80}` | `text-success/{70,80}`                                |  |
| `bg-emerald-400/500`        | `bg-success`                                             |  |
| `bg-emerald-500/{5,10,20,70,80}` | `bg-success/{5,10,20,70,80}`                        |  |
| `bg-emerald-600/700`        | `bg-success` (or `bg-success/90`)                        |  |
| `bg-emerald-{700,800,900,950}/{10,30,40,50,60,80}` | `bg-success/{10,20,30,40}` (collapse the 900/40 ≈ 10% surface tint pattern) | The `900/40` pattern is "tinted-success surface"; map to `bg-success/10` or `/15` consistently |
| `border-emerald-500/{30,50}` | `border-success/{30,50}`                                |  |
| `border-emerald-{600,700,800}/{40,60}` | `border-success/{40,60}`                          |  |
| `ring-emerald-500/20`       | `ring-success/20`                                        |  |
| `from-emerald-500`, `to-emerald-500` | `from-success` / `to-success`                   |  |
| `text-accent-emerald` | `text-success` | The legacy `@theme` accent token; only 1 occurrence |
| `text-amber-{100..500}/{0,70,90}` | `text-warning` (or `text-warning/N`)               | Status: warning |
| `bg-amber-{400,500,600,700,900}/{10,15,20,40,60}` | `bg-warning/{10,20,40}`                       |  |
| `border-amber-{400,500,600,700}/{30,40,50,60}` | `border-warning/{30,40,60}`                      |  |
| `ring-amber-400/50`         | `ring-warning/50`                                        |  |
| `from-amber-{400,500}/30`, `from-amber-400` | `from-warning` / `from-warning/30`               | Pricing.tsx CTA gradient |
| `shadow-amber-500/{20,40}`  | EITHER add `shadow-warning` OR drop the colored shadow (planner judgment) |  |
| `text-rose-{300,400}/{0,70}` | `text-destructive` (or `text-destructive/70`)           | Already mapped semantically |
| `bg-rose-500`, `bg-rose-900/40` | `bg-destructive` / `bg-destructive/10`               |  |
| `border-rose-{500,700}/{40,60}` | `border-destructive/{40,60}`                         |  |
| `text-indigo-{200,300,400,500}/{0,70}` | `text-info` (T1 adds the token)                  | "Info" / focus accent |
| `bg-indigo-{500,600,700,900}/{0,20,30,40}` | `bg-info` / `bg-info/{20,30,40}`                |  |
| `border-indigo-{500,700}/{0,40,50,60}` | `border-info/{40,50,60}`                            |  |
| `ring-indigo-500`           | `ring-info`                                              |  |

#### Out of scope for S01 (flag for S04 / S05)
| Legacy class                | Where used                                               | Disposition |
|-----------------------------|----------------------------------------------------------|-------|
| `from-blue-500/20`, `to-purple-500/20`, `via-purple-500`, `from-purple-500`, `to-purple-500`, `bg-purple-{500,600,700}`, `text-purple-100`, `from-pink-500`, `to-pink-500` | Home, About, App, Login, Register decorative; UserManagement role badge | Survives `@theme` deletion (Tailwind v4 default palette has these colors). **DEFER to S04**: when `@theme` is deleted, build either still passes (=keep) or fails (=migrate then). Do NOT touch in S01 — the slice scope is the legacy `@theme` palette block only. |

---

## Risks and Mitigations

- **R1: Token gap-fill bikeshed.** Whether to add `--info` (indigo) is a real call — planner should flag this for the user/owner if the agent's recommendation (add it) doesn't match intent. Cost of NOT adding it: indigo survives as raw Tailwind default after S04 deletion (it'll resolve fine because Tailwind's v4 default palette has `indigo`), but it's untokenized. Recommend adding for consistency.
- **R2: `text-neutral-300` ambiguity.** Some occurrences are tier-1 body text (→ `text-foreground`), some are tier-2 labels (→ `text-muted-foreground`). The 88 occurrences are spread across ~30 files. Planner: for atomic-commit-per-token to remain bisectable, either (a) split into two commits ("text-neutral-300 → text-foreground in body-text contexts" + "text-neutral-300 → text-muted-foreground in label contexts") or (b) accept that a single commit will need per-file review. Recommend (b): one commit, files listed in the message, judgment documented.
- **R3: Decorative gradient survivors.** Many `from-primary-500 to-primary-600` etc. compositions are decorative. Replacing with `from-primary to-primary` produces a flat (no gradient) result. Planner: where the visual intent is a gradient, preserve the gradient with semantic-token alpha modifiers (`from-primary to-primary/80`) OR — simpler — leave the gradient utilities in place IF the file is also slated for S05 polish (Home, About, Login, Register, Pricing, Support, NotFound). **The visual-regression baseline refresh will catch any unintended flat-out.**
- **R4: Cross-spec snapshot drift (MEM113, MEM140).** Reskinning a page also drifts ANY spec that screenshots that page (e.g. CrawlerAdmin admin.spec.ts will drift after T4 even if no admin-specific test code changed). Plan: per-slice refresh sweep is part of T6, executed as one commit covering ALL six snapshot directories.
- **R5: `ui/alert.tsx` Alert.success consumers.** Any test that asserts on the literal class names (`bg-emerald-500/10`, `text-emerald-300`) will break when T1 swaps the variant to use `bg-success`. Search for that pattern: `rg 'emerald|alert.*success' frontend/src/**/*.test.tsx` before editing — found one assertion of `bg-destructive` in `confirm-dialog.test.tsx` but not emerald-specific. Verify zero direct emerald-class assertions exist.
- **R6: Lint baseline at 108 errors (MEM062).** S01 must not regress this. The bulk of S01 changes are class-name strings inside `className=` props — neither ESLint nor TypeScript scans these. Risk surface is low; gauntlet at T7 catches regressions.

## Don't Hand-Roll

- **Don't touch `index.css`.** Lines 7-36 (`@theme` palette mirror), lines 38-98 (`:root` palette block) — survive until S04. S01 ONLY edits consumer files + `tokens.css` (T1 gap-fill) + `components/ui/alert.tsx` (T1 fix).
- **Don't reskin individual pages.** S01 is by-token, not by-page. Per MEM147, structural / page-level work is S02 (glass-card removal on Home/Login/Register/Header/AccountAlerts/AdminDashboard) and S05 (polish). Resist scope creep — if a token swap surfaces a real layout bug or `glass-card` survivor, leave it for the assigned slice.
- **Don't introduce new `ui/*` primitives.** Per MEM116/MEM149, the bias is consumption. T1's only addition is semantic tokens in `tokens.css` (and the surgical fix to `alert.tsx`).
- **Don't add `tailwindcss-animate`** (MEM063 / MEM070) — Tailwind v4 `@utility` declarations already cover what's needed.
- **Don't introduce webkit-backed Playwright device presets** (MEM066 / MEM068) — keep `Desktop Chrome` for all 3 projects.
- **Don't touch decorative blue/pink/purple gradients** in Home / About / App / Login / Register — they're outside the legacy `@theme` block and will be evaluated in S04 (when `@theme` is deleted, if they break, they're migrated then).
- **Don't refresh baselines globally with `--update-snapshots` from project root** without per-spec review (MEM140 lesson) — the diff is reviewed per-spec / per-page before commit so legitimate regressions stay visible.

## Skills Discovered

None — this is a mechanical migration in an existing codebase using established patterns. No new framework / library. The relevant in-tree skills (`tdd`, `verify-before-complete`, `make-interfaces-feel-better`) are already available in the harness.

## Sources

- `frontend/src/styles/tokens.css` — semantic-token surface (read in full)
- `frontend/src/index.css` lines 1-120 — legacy `@theme` palette mirror + `:root` block (read; do not edit in S01)
- `frontend/src/components/ui/alert.tsx` — primitive needing T1 fix (read in full)
- `frontend/src/components/ui/{dialog,sheet,tabs,combobox,dropdown-menu,button,input,confirm-dialog,pagination}.tsx` — semantic-token vocabulary already in use (sampled via grep)
- `frontend/src/__tests__/no-legacy-primitives.test.ts` — R017 grep guard pattern (read in full; out-of-scope reference)
- `frontend/playwright.config.ts` — viewport projects (read in full)
- `frontend/e2e/{admin,build-list,components,parts-catalog,price-alerts,price-history,smoke}.spec.ts` — listed; cross-spec drift surface area
- `.gsd/REQUIREMENTS.md` lines 229-289 — R048 / R049 / R050 / R053 ownership
- Memories: MEM003, MEM006, MEM062, MEM063, MEM066, MEM068, MEM070, MEM072, MEM110, MEM113, MEM116, MEM140, MEM144, MEM145, MEM147, MEM148, MEM149
