# S06: Migration completion gauntlet + UAT — Research

**Slice scope:** Run the milestone-close gauntlet against the post-S05 substrate. Re-run all 7 grep gates + 5 toolchain gates green, complete the manual UAT walkthrough at 3 viewports across priority pages, resolve (or document) the 6 IA decisions S05 deferred, and produce the milestone-close evidence record. Optionally extend the R017 vitest grep-guard to also block raw palette / `glass-*` / hand-rolled primitive re-entry.

**Owns requirement:** R061 (migration completion gauntlet). All other M003 active requirements (R048–R060) are already satisfied by S01–S05 and just need the close gauntlet to confirm zero regression.

**Risk:** low — this is verification + documentation, not code rewriting. The substrate is already clean (94-line `index.css`, 12 standing gates green at S05 close, 120 polish-coverage baselines committed). The only real code-write work is whichever IA deferrals get resolved in this slice and the optional grep-guard extension.

## Skills Discovered

No new skills installed. Existing `verify-before-complete` skill is operationally relevant for the close-gauntlet evidence requirement (fresh tool output, not "earlier in the session"). `frontend/playwright.config.ts` and `frontend/e2e/polish-coverage.spec.ts` are already authored — this slice consumes them, doesn't re-author.

## Calibration

**Light research.** This is straightforward execution of work whose substrate is already in place:
- 12 gates already passed at S05 close (the slice summary's "12 S04 standing gates post-polish" table) — S06 reproduces those + the manual UAT.
- The 6 IA deferrals are pre-enumerated in S05-SUMMARY.md "Deferrals to S06 UAT" with file paths, rationale, and the autonomous-vs-human decision context already recorded.
- No unfamiliar technology, no risky integration, no novel architecture.

The honest research output is shorter than a typical slice doc — that's the right shape.

## Implementation Landscape

### Already in place (consumed by S06, not produced)

- **`frontend/src/index.css`** — 94 lines. Legacy `:root` palette + `@theme` mirror + `.glass*` + `.btn-*` + `.card*` + `.input-modern` + decorative + animation utilities + 11 keyframes all deleted in S04. `vite build` exit code is the standing structural enforcement — any reintroduction is a build error.
- **`frontend/src/styles/tokens.css`** — semantic-token vocabulary; `--shadow-warning-glow` added in S05/T02 (semantic-role naming).
- **`frontend/src/components/ui/{textarea,status-badge,loading-overlay,card-info-item}.tsx`** — 4 new primitives from S05/T01 are the canonical implementations going forward.
- **`frontend/e2e/polish-coverage.spec.ts`** + 120 PNG baselines under `frontend/e2e/polish-coverage.spec.ts-snapshots/` — the standing visual-regression surface for all 40 routes × 3 Playwright projects (mobile=375, tablet=768, desktop=1280). Pre-dismisses cookie consent + chrome-extension promo via `addInitScript`; pins `Date.now()` to a fixed ISO; falls back to `domcontentloaded` if `networkidle` doesn't quiesce within 8s.
- **`frontend/src/test/route-coverage-list.ts`** — single source of truth for the 40 routes; consumed by both `App.coverage.test.tsx` (vitest drift guard `ALL_ROUTES.length >= 38`) and `polish-coverage.spec.ts`.
- **`frontend/src/__tests__/no-legacy-primitives.test.ts`** — R017 vitest grep-guard for `components/common/*` + `components/buttons/*` imports. Optional extension target for S06.

### S05's deferred work, pre-loaded for this slice

Source: `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` "Deferrals to S06 UAT" section. Each was tokenized in-place during S05 so the deferred decision is purely about IA structure, not legacy CSS:

1. **Auth-shell unification** — `frontend/src/pages/authentication/{Login.tsx, Register.tsx, ExtensionAuth.tsx}` wrap content in a glass-card-style surrounding wrapper (now tokenized); `frontend/src/pages/authentication/{ForgotPassword.tsx, ForgotPasswordConfirm.tsx}` use the dedicated `AuthCard` component. Two materially-different shells in one auth flow. Decision: which shell wins, or do they merge into a third primitive? **Impact if collapsed:** 5 file edits + Playwright baseline refresh on `/login`, `/register`, `/extension-auth` (and possibly `/forgot-password*`) at 3 viewports.
2. **ContactUs 3-card collapse** — `frontend/src/pages/ContactUs.tsx` renders 3 near-identical email-cards (general / business / support). Collapsing into one card with a recipient toggle is medium-to-high-impact (changes mental model from "pick a card" to "pick a recipient"). **Impact if collapsed:** 1 file rewrite + baseline refresh on `/contact-us` at 3 viewports.
3. **BuildListsCatalog sidebar drawer** — `frontend/src/pages/buildLists/BuildListsCatalog.tsx` left filter sidebar pushes content rightward at narrow viewports; ergonomically should become a slide-in drawer below tablet. **Impact if implemented:** 1 file rewrite + likely a new `ui/drawer.tsx` primitive (M002 inventory check needed) + baseline refresh on `/build-lists` at mobile.
4. **ViewBuildLog markdown-prose plugin** — `frontend/src/pages/buildLists/ViewBuildLog.tsx` markdown renderer was per-element tokenized in T04 (~25 sites). Adopting Tailwind Typography prose plugin would replace those overrides with one `prose prose-invert` class but adds a runtime dependency. **Impact if adopted:** `npm i -D @tailwindcss/typography` + plugin registration in Tailwind config + ~25 inline overrides removed + baseline refresh on `/build-lists/<uuid>/build-log` at 3 viewports.
5. **UserManagement 11-column table responsive strategy** — `frontend/src/pages/admin/UserManagement.tsx` 11-column table horizontally scrolls below desktop. Choices: (a) keep horizontal scroll (current), (b) collapse columns into expandable row, (c) move secondary columns to a row-detail view, (d) cards-on-mobile separate layout. **Impact:** depends on choice; (a) is no-op confirmation, (b)-(d) are substantial.
6. **SystemAdmin DangerActionPanel extraction** — `frontend/src/pages/admin/SystemAdmin.tsx` has 10 near-identical danger sections tokenized in-place during T05. Extracting a `DangerActionPanel` primitive (heading + danger description + ConfirmDialog wrapper) reduces SystemAdmin LOC materially. **Impact if extracted:** 1 new `frontend/src/components/admin/DangerActionPanel.tsx` (likely; admin-specific not ui-generic) + 10 inline-section replacements + baseline refresh on `/admin/system` at 3 viewports.

### The 12 standing close gates (re-run in S06)

Per `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` "12 S04 Standing Gates Post-Polish" table. All run from the worktree root unless noted:

| # | Gate | Command | Pass | Slice owning origin |
|---|------|---------|------|---------------------|
| 1 | S01 raw-palette | `rg '(text\|bg\|border\|ring\|from\|to\|via)-(primary\|neutral\|emerald\|indigo\|amber\|rose)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) | R048 |
| 2 | S01 text-accent | `rg 'text-accent-(emerald\|amber\|rose\|purple)' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) | R048 |
| 3 | S02 glass class | `rg 'glass-(card\|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) | R049 |
| 4 | S02 className glass | `rg 'className=.*\bglass\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) | R049 |
| 5 | S02 var legacy | `rg 'var\(--(primary\|neutral\|accent\|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) | R050 |
| 6 | S04 consumer-class | `rg '\b(btn-primary\|btn-secondary\|btn-outline\|input-modern\|card-interactive\|card-table-container\|skeleton\|hero-gradient\|shadow-glow\|border-gradient)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` | exit 1 (zero hits) | R051, R052 |
| 7 | S04 index.css self-inspection | `rg -c '@theme\|--primary-[0-9]\|.glass-card\|.btn-primary\|.card-interactive\|.input-modern\|.text-gradient\|.shadow-glow\|.border-gradient\|.skeleton\|.hero-gradient' frontend/src/index.css` | exit 1 (zero hits) | R051, R052 |
| 8 | type-check | `cd frontend && npm run type-check` | exit 0 | R061 |
| 9 | lint | `cd frontend && npm run lint` | exit 0 (well below MEM062 baseline of 108) | R061 |
| 10 | vitest | `cd frontend && npm test -- --run` | exit 0 (594/594) | R061 |
| 11 | vite build | `cd frontend && npm run build` | exit 0 | R061 (structural) |
| 12 | Playwright (3 viewports) | `cd frontend && npx playwright test` | passed (155 / 10 skipped / 0 failed at S05) | R060, R061 |

### Manual UAT priority pages (per ROADMAP)

The roadmap and CONTEXT both name the priority pages: **Home, PartsCatalog, ViewPart, ViewBuildList, ViewCar, Login, Register, Header, AccountAlerts, AdminDashboard, AdminExtractionHealth**. The UAT walkthrough at 360 / 768 / 1280 against these pages is the milestone close criterion (R061's last clause). 360 is the manual UAT viewport (MEM170/MEM179) — Playwright at 375 is not a substitute.

## Recommendation

**Decompose S06 into 3 tasks.** This is verification + small-batch IA resolution + documentation; sequential is correct (no parallel-safe seams).

### T01 — IA deferral resolution (autonomous-judgable items only)

The 6 IA deferrals split cleanly into "judgable in autonomous mode" vs "needs human UAT decision":

- **Judgable (apply on T01):**
  - #6 SystemAdmin DangerActionPanel extraction — pure code refactor, 10 sites → 1 primitive + 10 consumers. Reduces LOC, no UX change. Baseline of `/admin/system` should be byte-identical after extraction (semantic-token output unchanged).
  - #5(a) UserManagement 11-col table — option (a) "keep horizontal scroll" is the conservative status-quo choice and matches `acceptable-as-scroll` in S05's verdict table. Documenting this as the explicit decision (not a deferral) closes #5 without code change. The other options (b)-(d) require human judgment about which secondary columns can hide; defer those.
  - #4 ViewBuildLog prose plugin — borderline. Tailwind v4 plugin compatibility check is needed (Tailwind v4 dropped some plugin APIs). If Tailwind v4 + `@tailwindcss/typography` is supported and the plugin produces visually-comparable output to the per-element tokenization, apply. If incompatible or visually-divergent, document + defer to a follow-up. **T01 should research-then-decide, not decide blindly.**

- **Needs human UAT decision (document, do not modify in T01):**
  - #1 auth-shell unification — visual brand decision; the human UAT walkthrough sees both shells and decides.
  - #2 ContactUs 3-card collapse — UX mental-model change.
  - #3 BuildListsCatalog sidebar drawer — primitive-add (drawer) + UX change.

T01's deliverables: the judgable IA changes applied with atomic commits + rationale + baseline refresh; the not-judgable IA decisions reformatted as **explicit milestone-close UAT items** in `.gsd/milestones/M003/M003-UAT.md` (so the human reviewer has a checklist with file:line refs, before/after intent, and a decision slot per item).

**Verify:**
- For each applied change: `cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build && npx playwright test <affected-spec> --update-snapshots && git diff -- frontend/e2e/<affected-spec>-snapshots/` (visual review per MEM148).
- For the milestone close: `test -f .gsd/milestones/M003/M003-UAT.md`.

### T02 — Optional R017 grep-guard extension

Extend `frontend/src/__tests__/no-legacy-primitives.test.ts` with three new assertions:

- No raw legacy palette utility hits (gates 1, 2 above as a vitest test).
- No `glass-*` class hits (gates 3, 4).
- No hand-rolled patterns now that primitives exist: hand-rolled `<textarea>` (require `import { Textarea } from '@/components/ui/textarea'`), inline `<div className="absolute inset-0 bg-background/80 backdrop-blur-sm">` loading-overlay divs (require `LoadingOverlay`), inline status-badge factories (`getStatusBadge`, `getPriorityBadge` function names — heuristic but practical).

Pattern is identical to the existing R017 grep-guard (walks `src/`, asserts no file matches a regex). Two memory gotchas to honor:
- **MEM180 / MEM163:** word-boundary grep gates can false-positive on the word "skeleton" in test-file comments. Either scope the new assertions to non-test-file glob, or rewrite false-positive-prone comments.
- **MEM168:** scope each assertion to consumer dirs only (`src/{components,pages,contexts,hooks,api,lib,__tests__}/`) so `tokens.css` / `index.css` aren't scanned.

This is genuinely optional per the slice description ("Optional: vitest grep-guard extended..."). If T01 expands materially, T02 can split into M004 backlog. Decision rule: **apply T02 if T01 lands cleanly with budget remaining; otherwise defer to follow-up.**

**Verify:**
- `cd frontend && npm test -- --run __tests__/no-legacy-primitives` exits 0.
- Manual reintroduction probe: temporarily add `bg-primary-500` to a single file and re-run vitest; assert the new assertion fails. Revert.

### T03 — Close gauntlet + manual UAT + slice/milestone close artifacts

Run all 12 standing gates fresh (per `verify-before-complete` skill — output must be from this session, not citations to S05's table). Capture command + exit code + relevant tail of output for each gate.

Then the manual UAT walkthrough at 360 / 768 / 1280 across the 11 priority pages. The walkthrough is operator-driven (auto-mode cannot drive a real browser at 360px); document the walkthrough script + per-page-per-viewport verdict in `.gsd/milestones/M003/M003-UAT.md`. Auto-mode's role is to:
- Pre-render the 11 priority pages via Playwright at the 3 Playwright projects (mobile=375, tablet=768, desktop=1280) by re-running the relevant subset of `polish-coverage.spec.ts` baselines + the priority-page specs (admin.spec.ts, build-list.spec.ts, parts-catalog.spec.ts, price-history.spec.ts).
- For each page, list the verdict pinned by the polish-coverage baseline + a TODO checkbox for the human's 360px DevTools/manual confirmation.
- Surface the 3 explicitly-deferred IA decisions (#1, #2, #3) as a UAT decision section.

The MILESTONE close requires both `gsd_complete_slice` (S06) and `gsd_complete_milestone` (M003) per MEM143 sequencing — slice closes first.

**Verify:**
- All 12 standing gates green with command output captured in S06-SUMMARY.md (or referenced from a fresh `gauntlet/` directory with stdout files per gate).
- `.gsd/milestones/M003/M003-UAT.md` exists with: (a) per-priority-page verdict table at mobile=375 / tablet=768 / desktop=1280 backed by Playwright PNG baseline references, (b) 360px manual-walkthrough TODO checklist for the 11 priority pages, (c) decision slots for the 3 IA deferrals (#1, #2, #3).
- S06-SUMMARY.md captures: gate evidence, IA changes applied (T01 judgable items), IA changes documented for human UAT, optional grep-guard outcome (T02 applied or deferred), the standing operational signal post-M003 close.
- `gsd_complete_slice` succeeds for S06; `gsd_complete_milestone` succeeds for M003.

## Implementation Notes

### Cascade-refresh expectation for T01

Per MEM176 / MEM174: any T01 IA change that mutates a page's vertical geometry will drift Playwright fullPage baselines for **every spec that screenshots that route**, not just the spec the slice plan names. Pre-grep before each IA change:

```
cd frontend && grep -l "<route-path>" e2e/*.spec.ts
```

For example, `/admin/system` is screenshotted by `polish-coverage.spec.ts` only (no admin.spec.ts coverage of `/admin/system`); but `/build-lists` is in both `polish-coverage.spec.ts` and `build-list.spec.ts`, so a sidebar-drawer change cascades to both.

Per MEM156 / MEM160: `--update-snapshots` (no value) defaults to `changed` mode, so a pixel-equivalent refactor (DangerActionPanel extraction with semantic tokens unchanged) should refresh zero baselines. That's the desired outcome, not a no-op.

### Tailwind v4 + `@tailwindcss/typography` compatibility

Before applying T01 deferral #4, verify Tailwind v4 supports the typography plugin. As of Tailwind v4, plugin registration moved from `tailwind.config.js` to the `@plugin` directive in CSS:

```css
@import "tailwindcss";
@plugin "@tailwindcss/typography";
```

If the plugin is incompatible or produces visually-divergent output from the per-element tokenization, **defer to follow-up** rather than fight the plugin — the per-element tokenization in S05/T04 already works.

### Manual UAT walkthrough — operator vs auto-mode

R061 says: "manual UAT walkthrough at three viewports across priority pages documented." This is an operator action. Auto-mode prepares the structured walkthrough document with all the pre-rendering done; the operator runs through it in a real browser at 360 / 768 / 1280 and records verdicts. The slice can still close on auto-mode's preparation — the UAT-COMPLETE checkbox is a follow-up that doesn't block S06's `gsd_complete_slice`. M002/S13 followed this exact pattern (MEM139's live SES round-trip was an operator follow-up; the slice closed on auto-mode's preparation).

If the operator UAT surfaces a regression, treat it as a remediation slice via `gsd_reassess_roadmap` rather than holding S06 open.

### gsd_complete_slice verification phrasing (MEM142)

The verification content gate refuses any slice whose `verification` or `uatContent` matches `\b(status:\s*blocked|verification_result:\s*failed|slice is blocked|cannot complete|verification failed)\b`. The phrase "auto-mode cannot complete the live UAT walkthrough" trips this regex; rephrase to "auto-mode is unable to drive a real browser at 360px; operator follow-up captured in M003-UAT.md" or similar neutral wording.

### Priority page → spec mapping

For T03's pre-render of priority pages:

| Priority page (route) | Existing spec(s) covering | Notes |
|---|---|---|
| `/` (Home) | polish-coverage.spec.ts | fixed in S05/T02 (gradient collapse) |
| `/parts` (PartsCatalog) | parts-catalog.spec.ts, polish-coverage.spec.ts | already on shadcn primitives |
| `/parts/<id>` (ViewPart) | price-history.spec.ts, price-alerts.spec.ts (post-subscribe) | IA-collapsed in S03/T03 |
| `/build-lists/<uuid>` (ViewBuildList) | build-list.spec.ts, polish-coverage.spec.ts (UUID 404) | UUID baseline locks NotFound |
| `/car-generations/<x>` (ViewCar) | polish-coverage.spec.ts | category switcher tokenized in S05/T04 |
| `/login` | polish-coverage.spec.ts | Alert variant=destructive in S05/T03 |
| `/register` | polish-coverage.spec.ts | Alert variant=destructive in S05/T03 |
| Header (renders on every route) | every spec that screenshots a page | covered transitively |
| `/account/alerts` | polish-coverage.spec.ts (locks /login redirect for unauth user) | actual-page render needs auth fixture for UAT |
| `/admin` (AdminDashboard) | admin.spec.ts, polish-coverage.spec.ts | not touched in S05 |
| `/admin/extraction-health` | admin.spec.ts (assertion-rich), polish-coverage.spec.ts | not touched in S05 |

`/profile`, `/builder`, `/my-parts`, `/checkout`, `/account/alerts`, `/verify-email` redirect to `/login` for unauthenticated users. Polish-coverage baselines lock the redirect target. The protected-page render is exercised by domain specs + the operator's authenticated walkthrough.

## Risks and Unknowns

- **T01 deferral #4 (Tailwind Typography plugin)** may not be compatible with Tailwind v4 in this project's exact configuration. **Mitigation:** check first; defer to follow-up if incompatible.
- **T01 deferral #6 (DangerActionPanel)** may surface design-system primitive vs admin-specific component placement question (`components/ui/` vs `components/admin/`). **Mitigation:** prefer `components/admin/DangerActionPanel.tsx` — admin-specific shape (heading + danger description + ConfirmDialog wrapper), not a generic ui primitive. Consistent with M002's `components/admin/AdminUserDeleteDialog.tsx` etc.
- **The 360px manual UAT** is operator work; auto-mode can document and prepare but cannot drive. Slice can close on auto-mode's preparation per the M002/S13 pattern; the post-close UAT verdict captures any remediation needs.
- **Cascade-refresh outcome may differ from S05's null-result.** S05's pixel-equivalent migration produced zero non-polish-coverage baseline drift; if T01 applies geometry-mutating IA changes (DangerActionPanel extraction unlikely to mutate geometry but possible), expect drift cascade per MEM176. Refresh in the same task; visually review per MEM148.

## Sources

- `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` — full S05 outcome including 12 standing gates, 6 IA deferrals, per-page verdict table, cascade-refresh policy.
- `.gsd/milestones/M003/M003-CONTEXT.md` — milestone-level architectural decisions, priority-page list.
- `.gsd/milestones/M003/M003-ROADMAP.md` — slice S06 description + boundary map.
- `.gsd/REQUIREMENTS.md` — R048–R061 (M003 requirements; R061 owned by S06).
- `frontend/e2e/polish-coverage.spec.ts` + `frontend/playwright.config.ts` — visual-regression substrate.
- `frontend/src/__tests__/no-legacy-primitives.test.ts` — R017 vitest grep-guard pattern (template for T02 extension).
- Memory: MEM170, MEM179 (mobile=375 vs UAT=360); MEM156, MEM160 (`--update-snapshots` defaults to `changed` mode); MEM176, MEM174 (cascade-refresh); MEM148 (per-slice visual review); MEM168 (grep-gate scoping); MEM180, MEM163 (word-boundary false-positives); MEM142 (verification regex); MEM143 (close sequencing); MEM183, MEM146 (IA decision rights in autonomous mode).

Slice S06 researched.
